"""Grant or revoke the admin role for an existing account using the ORM."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.user import User


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email", help="Email address of an existing account")
    parser.add_argument("role", choices=("user", "admin"))
    args = parser.parse_args()

    db = SessionLocal()
    try:
        account = db.query(User).filter(User.email == args.email.strip().lower()).first()
        if account is None:
            parser.error(f"No account found for {args.email!r}; register the account first")
        account.role = args.role
        db.commit()
        print(f"Updated {account.email} to role {account.role!r}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
