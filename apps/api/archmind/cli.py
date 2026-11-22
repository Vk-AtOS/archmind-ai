"""Bootstrap commands. Usage: python -m archmind.cli create-admin ORG EMAIL NAME
(password read from ARCHMIND_ADMIN_PASSWORD or prompted; never passed on the command line)."""

import getpass
import os
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select

from archmind.db import session_factory
from archmind.models import Membership, Organization, User
from archmind.security import audit, hash_password


def create_admin(org_name: str, email: str, name: str) -> None:
    # Same check as the login form: an address it would reject (e.g. a reserved .local domain)
    # must not be accepted here, or the admin can never sign in.
    try:
        email = TypeAdapter(EmailStr).validate_python(email)
    except ValidationError:
        sys.exit(f"{email!r} is not an address the login form accepts; use a real domain")
    password = os.environ.get("ARCHMIND_ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
    if len(password) < 12:
        sys.exit("password must be at least 12 characters")
    with session_factory()() as db:
        if db.scalar(select(User).where(User.email == email.lower())):
            sys.exit(f"{email} already exists")
        org = Organization(name=org_name)
        user = User(email=email.lower(), name=name, password_hash=hash_password(password))
        db.add_all([org, user])
        db.flush()
        db.add(Membership(org_id=org.id, user_id=user.id, role="admin"))
        audit(db, "org.bootstrap", org.id, user.id, str(org.id))
        db.commit()
        print(f"created organisation {org.id} with admin {email}")


if __name__ == "__main__":
    if len(sys.argv) != 5 or sys.argv[1] != "create-admin":
        sys.exit(__doc__)
    create_admin(*sys.argv[2:])
