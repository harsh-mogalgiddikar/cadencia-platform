"""
Idempotent Alembic migration runner.

context.md §15: Alembic migrations must be idempotent.
Safe to run at container startup — checks current head before applying.

Usage:
    python scripts/migrate.py

The script:
1. Reads DATABASE_URL from environment.
2. Checks the current Alembic revision.
3. Runs `alembic upgrade head` if not already at head.
4. Exits 0 on success, 1 on failure.
"""

from __future__ import annotations

import os
import subprocess
import sys

# Configure structlog before importing infrastructure
os.environ.setdefault("APP_ENV", "development")

import structlog

from src.shared.infrastructure.logging import configure_logging

configure_logging()
log = structlog.get_logger(__name__)


def run_migrations() -> None:
    """Run alembic upgrade head. Idempotent — safe if already at head."""
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        log.error("migration_aborted", reason="DATABASE_URL not set")
        sys.exit(1)

    log.info("migration_starting", database_url=database_url.split("@")[-1])

    # Check current revision
    result = subprocess.run(
        ["alembic", "current"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    current = result.stdout.strip()
    log.info("migration_current_revision", revision=current)

    # Run upgrade
    result = subprocess.run(
        ["alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )

    if result.returncode != 0:
        log.error(
            "migration_failed",
            returncode=result.returncode,
            stderr=result.stderr,
            stdout=result.stdout,
        )
        sys.exit(1)

    log.info(
        "migration_complete",
        stdout=result.stdout.strip() or "already at head",
    )


if __name__ == "__main__":
    run_migrations()
