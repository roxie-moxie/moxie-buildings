"""CLI to bootstrap the first admin user.

Usage:
    uv run create-admin --email admin@example.com --password secret123 --name "Alex"
"""
import argparse
import sys

from sqlalchemy.exc import IntegrityError

from moxie.api.auth import hash_password
from moxie.db.models import User
from moxie.db.session import SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an admin user in the Moxie database")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password (will be hashed)")
    parser.add_argument("--name", required=True, help="Admin display name")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        user = User(
            name=args.name,
            email=args.email,
            password_hash=hash_password(args.password),
            role="admin",
            is_active=True,
        )
        db.add(user)
        db.commit()
        print(f"Admin created successfully: {args.email} (name={args.name})")
    except IntegrityError:
        db.rollback()
        print(f"Error: An account with email '{args.email}' already exists.", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
