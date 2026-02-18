"""
Dev environment bootstrap — runs migrations then seeds the database.

Registered as the `dev` entrypoint in pyproject.toml.
Invoked via: uv run dev
"""

import subprocess
import sys
from pathlib import Path


def main():
    """Bootstrap dev environment: run migrations then seed. Invoked via: uv run dev"""
    print("Running migrations...")
    # Use sys.executable to ensure we use the same Python/venv that is running this script.
    # alembic is installed in the same venv so `python -m alembic` works without PATH requirements.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
    )

    print("Seeding database...")
    subprocess.run(
        [sys.executable, str(Path(__file__).parent / "seed.py")],
        check=True,
    )

    print("Dev environment ready.")
    print("Inspect DB: sqlite3 moxie.db")
    print("Run sync: uv run sheets-sync")
    print("Run tests: uv run pytest tests/ -v")


if __name__ == "__main__":
    main()
