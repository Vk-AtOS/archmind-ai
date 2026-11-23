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
    assert " m²" in svg.text and " m</text>" in svg.text
    ft = a.get(f"/api/v1/options/{opts[0]['id']}/plans/0.svg?units=ft").text
    assert " ft²" in ft and " ft</text>" in ft and " m²" not in ft
    assert " mm</text>" in a.get(f"/api/v1/options/{opts[0]['id']}/plans/0.svg?units=mm").text
    assert a.get(f"/api/v1/options/{opts[0]['id']}/plans/0.svg?units=yd").status_code == 422
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


def test_account_wide_cap_does_not_lock_user_out_of_known_network(client: TestClient) -> None:
    _, email = org_admin(client)  # org_admin signs in from "testclient": a trusted network now
    for i in range(20):  # distributed attack: 4 networks x 5 failures
        c = TestClient(client.app, client=(f"203.0.113.{i // 5}", 1))
        c.post("/api/v1/auth/login", json={"email": email, "password": "nope"})
    stranger = TestClient(client.app, client=("198.51.100.99", 1))
    assert stranger.post("/api/v1/auth/login", json={"email": email, "password": PW}).status_code == 429
    known = TestClient(client.app)
    assert known.post("/api/v1/auth/login", json={"email": email, "password": PW}).status_code == 200
    # Once capped, new networks are refused before a failure is recorded, so outsiders cannot
    # push the count towards the trusted allowance; an attacker on the trusted network itself
    # still gets only 5 tries.
    late = TestClient(client.app, client=("203.0.113.200", 1))
    assert late.post("/api/v1/auth/login", json={"email": email, "password": "nope"}).status_code == 429
    for _ in range(5):
        known.post("/api/v1/auth/login", json={"email": email, "password": "nope"})
    assert known.post("/api/v1/auth/login", json={"email": email, "password": PW}).status_code == 429


def test_create_admin_rejects_addresses_login_would_refuse(client: TestClient) -> None:
    # Regression: owner@archmind.local was created but could never sign in.
    os.environ["ARCHMIND_ADMIN_PASSWORD"] = PW
    with pytest.raises(SystemExit, match="login form"):
        create_admin("Org", "owner@archmind.local", "Owner")


def test_actual_cost_needs_opt_in_and_reports_estimate_error(client: TestClient) -> None:
    a, _ = org_admin(client)
    pr = a.post("/api/v1/projects", json={"name": "Built"}).json()
    opt = a.post(f"/api/v1/projects/{pr['id']}/briefs", json=BRIEF).json()["options"][0]
    url = f"/api/v1/options/{opt['id']}/actual-costs"
    assert a.get("/api/v1/org/settings").json() == {"data_use_opt_in": False}
    assert a.post(url, json={"total": 1_200_000, "currency": "INR"}).status_code == 409  # off by default
    assert a.put("/api/v1/org/settings", json={"data_use_opt_in": True}).status_code == 200
    assert a.post(url, json={"total": 1_200_000, "currency": "USD"}).status_code == 422
    r = a.post(url, json={"total": 1_200_000, "currency": "INR", "note": "final bill"})
    assert r.status_code == 201, r.text
    body = r.json()
    expected = round((opt["estimate_total"] - 1_200_000) / 1_200_000 * 100, 1)
    assert body["error_pct"] == expected
    assert len(a.get(url).json()) == 1
    viewer = add_user(a, "viewer")
    assert viewer.post(url, json={"total": 1, "currency": "INR"}).status_code == 403
    assert viewer.put("/api/v1/org/settings", json={"data_use_opt_in": False}).status_code == 403
    other, _ = org_admin(client)
    assert other.get(url).status_code == 404


def test_reviewers_rate_layouts_and_summary_groups_by_generator(client: TestClient) -> None:
    a, _ = org_admin(client)
    pr = a.post("/api/v1/projects", json={"name": "Rated"}).json()
    opt = a.post(f"/api/v1/projects/{pr['id']}/briefs", json=BRIEF).json()["options"][0]
    url = f"/api/v1/options/{opt['id']}/rating"
    scores = {"usability": 4, "circulation": 3, "daylight": 5, "buildability": 4, "client_ready": 2}
    reviewer = add_user(a, "reviewer")
    assert reviewer.put(url, json={**scores, "comment": "kitchen too narrow"}).status_code == 200
    assert (
        reviewer.put(url, json={**scores, "client_ready": 3}).status_code == 200
    )  # replaces, not duplicates
    assert len(a.get(f"/api/v1/options/{opt['id']}/ratings").json()) == 1
    assert reviewer.put(url, json={**scores, "usability": 6}).status_code == 422
    assert add_user(a, "contributor").put(url, json=scores).status_code == 403
    summary = a.get("/api/v1/ratings/summary").json()
    assert summary[0]["ratings"] == 1 and summary[0]["averages"]["client_ready"] == 3.0
    other, _ = org_admin(client)
    assert other.put(url, json=scores).status_code == 404
    assert other.get("/api/v1/ratings/summary").json() == []
