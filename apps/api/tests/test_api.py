import os
import uuid

import pytest
from fastapi.testclient import TestClient

from archmind.cli import create_admin

PW = "correct-horse-battery"
BRIEF = {
    "plot_width_m": 12,
    "plot_depth_m": 15,
    "setbacks": {"front": 3, "rear": 1.5, "left": 1, "right": 1},
    "floors": 2,
    "rooms": [
        {"type": "living"},
        {"type": "kitchen"},
        {"type": "dining"},
        {"type": "bedroom", "count": 3},
        {"type": "bathroom", "count": 2},
    ],
}


def org_admin(client: TestClient) -> tuple[TestClient, str]:
    """New organisation with a signed-in admin; returns a client carrying that admin's cookie."""
    email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    os.environ["ARCHMIND_ADMIN_PASSWORD"] = PW
    create_admin("Org " + email, email, "Admin")
    c = TestClient(client.app)
    assert c.post("/api/v1/auth/login", json={"email": email, "password": PW}).status_code == 200
    return c, email


def add_user(admin: TestClient, role: str) -> TestClient:
    email = f"{role}-{uuid.uuid4().hex[:8]}@example.com"
    r = admin.post(
        "/api/v1/users", json={"email": email, "name": role, "role": role, "temporary_password": PW}
    )
    assert r.status_code == 201, r.text
    c = TestClient(admin.app)
    assert c.post("/api/v1/auth/login", json={"email": email, "password": PW}).status_code == 200
    return c


def test_login_logout_and_session_required(client: TestClient) -> None:
    assert client.get("/api/v1/me").status_code == 401
    a, email = org_admin(client)
    me = a.get("/api/v1/me").json()
    assert me["email"] == email and me["role"] == "admin"
    assert a.post("/api/v1/auth/logout", json={}).status_code == 204
    assert a.get("/api/v1/me").status_code == 401


def test_lockout_is_per_address_so_attackers_cannot_lock_out_victims(client: TestClient) -> None:
    _, email = org_admin(client)
    attacker = TestClient(client.app, client=("203.0.113.9", 4000))
    for _ in range(5):
        r = attacker.post("/api/v1/auth/login", json={"email": email, "password": "nope"})
        assert r.status_code == 401
    assert attacker.post("/api/v1/auth/login", json={"email": email, "password": PW}).status_code == 429
    victim = TestClient(client.app, client=("198.51.100.7", 5000))
    assert victim.post("/api/v1/auth/login", json={"email": email, "password": PW}).status_code == 200


def test_unknown_email_and_wrong_password_look_the_same(client: TestClient) -> None:
    _, email = org_admin(client)
    c = TestClient(client.app, client=("192.0.2.1", 1))
    a = c.post("/api/v1/auth/login", json={"email": email, "password": "nope"})
    b = c.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "nope"})
    assert (a.status_code, a.json()) == (b.status_code, b.json())


def test_oversized_brief_is_rejected(client: TestClient) -> None:
    a, _ = org_admin(client)
    pr = a.post("/api/v1/projects", json={"name": "Big"}).json()
    many = {**BRIEF, "rooms": [{"type": "bedroom"}] * 11 + BRIEF["rooms"]}
    assert a.post(f"/api/v1/projects/{pr['id']}/briefs", json=many).status_code == 422
    huge = {**BRIEF, "rooms": [{"type": "living", "target_area_m2": 10_000}, *BRIEF["rooms"][1:]]}
    assert a.post(f"/api/v1/projects/{pr['id']}/briefs", json=huge).status_code == 422


def test_full_flow_brief_to_options_and_exports(client: TestClient) -> None:
    a, _ = org_admin(client)
    pr = a.post("/api/v1/projects", json={"name": "House A", "location": "Plot 12"}).json()
    r = a.post(f"/api/v1/projects/{pr['id']}/briefs", json=BRIEF)
    assert r.status_code == 201, r.text
    opts = r.json()["options"]
    assert len(opts) == 3
    assert all(o["failed_checks"] == 0 and o["estimate_total"] > 0 for o in opts)
    detail = a.get(f"/api/v1/options/{opts[0]['id']}").json()
    assert detail["estimate"]["label"].startswith("Indicative")
    assert len(detail["layout"]["floors"]) == 2
    svg = a.get(f"/api/v1/options/{opts[0]['id']}/plans/0.svg")
    assert svg.status_code == 200 and svg.headers["content-type"].startswith("image/svg+xml")
    ifc = a.get(f"/api/v1/options/{opts[0]['id']}/model.ifc")
    assert ifc.status_code == 200 and ifc.text.startswith("ISO-10303-21")
    assert len(a.get(f"/api/v1/projects/{pr['id']}/briefs").json()) == 1
    actions = {e["action"] for e in a.get("/api/v1/audit").json()}
    assert {"auth.login", "project.create", "brief.create", "option.export_ifc"} <= actions


def test_invalid_brief_is_rejected_with_field_errors(client: TestClient) -> None:
    a, _ = org_admin(client)
    pr = a.post("/api/v1/projects", json={"name": "Tiny"}).json()
    r = a.post(f"/api/v1/projects/{pr['id']}/briefs", json={**BRIEF, "plot_width_m": 5, "plot_depth_m": 6})
    assert r.status_code == 422


def test_other_tenant_cannot_see_projects_or_options(client: TestClient) -> None:
    a, _ = org_admin(client)
    b, _ = org_admin(client)
    pr = a.post("/api/v1/projects", json={"name": "Secret"}).json()
    opt = a.post(f"/api/v1/projects/{pr['id']}/briefs", json=BRIEF).json()["options"][0]
    assert b.get(f"/api/v1/projects/{pr['id']}").status_code == 404
    assert b.get(f"/api/v1/projects/{pr['id']}/briefs").status_code == 404
    assert b.post(f"/api/v1/projects/{pr['id']}/briefs", json=BRIEF).status_code == 404
    assert b.get(f"/api/v1/options/{opt['id']}").status_code == 404
    assert b.get(f"/api/v1/options/{opt['id']}/model.ifc").status_code == 404
    assert all(p["id"] != pr["id"] for p in b.get("/api/v1/projects").json())


@pytest.mark.parametrize(
    ("role", "can_project", "can_brief"),
    [
        ("viewer", False, False),
        ("reviewer", False, False),
        ("contributor", False, True),
        ("project_manager", True, True),
    ],
)
def test_role_permissions(client: TestClient, role: str, can_project: bool, can_brief: bool) -> None:
    a, _ = org_admin(client)
    pr = a.post("/api/v1/projects", json={"name": "P"}).json()
    u = add_user(a, role)
    assert (u.post("/api/v1/projects", json={"name": "X"}).status_code == 201) == can_project
    assert (u.post(f"/api/v1/projects/{pr['id']}/briefs", json=BRIEF).status_code == 201) == can_brief
    assert u.get(f"/api/v1/projects/{pr['id']}").status_code == 200  # every role can read
    assert (
        u.post(
            "/api/v1/users",
            json={"email": "x@example.com", "name": "x", "role": "viewer", "temporary_password": PW},
        ).status_code
        == 403
    )


def test_mutations_require_json(client: TestClient) -> None:
    a, _ = org_admin(client)
    r = a.post(
        "/api/v1/projects", content="name=x", headers={"content-type": "application/x-www-form-urlencoded"}
    )
    assert r.status_code == 415


def test_ipv6_addresses_in_one_network_share_a_throttle_key() -> None:
    from archmind.security import client_key

    assert client_key("2001:db8::1") == client_key("2001:db8::ffff") == "2001:db8::/64"
    assert client_key("203.0.113.9") == "203.0.113.9"
    assert client_key(None) == "unknown"
