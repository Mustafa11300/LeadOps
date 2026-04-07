#!/usr/bin/env python3
"""
Lead-Ops · Database Initializer
================================
Creates the master.db SQLite database with all tables defined
in db_models.py.

Usage::

    python database_init.py

This script is idempotent — running it again will not destroy
existing data (CREATE TABLE IF NOT EXISTS).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db_models import Base, create_db_engine, create_all_tables, AccountORM

from sqlalchemy.orm import Session as DBSession

# ── Styling ───────────────────────────────────────────────────────────────────

GREEN = "\033[92m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def init_database(db_path: str = "master.db") -> None:
    """Create the database and all tables."""
    db_url = f"sqlite:///{db_path}"
    print(f"\n{BOLD}{CYAN}🗄️  Lead-Ops · Database Initializer{RESET}")
    print(f"   Database: {db_path}\n")

    engine = create_db_engine(db_url, echo=False)

    # Create all tables
    create_all_tables(engine)
    print(f"  {GREEN}✔{RESET} Tables created: leads, accounts, interaction_logs, enrichment_cache")

    # Verify tables exist
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    expected = {"leads", "accounts", "interaction_logs", "enrichment_cache"}
    missing = expected - set(tables)

    if missing:
        print(f"  ✘ Missing tables: {missing}")
        sys.exit(1)
    else:
        print(f"  {GREEN}✔{RESET} All 4 tables verified")

    # Print schema summary
    print(f"\n  {BOLD}Schema Summary:{RESET}")
    for table_name in sorted(tables):
        if table_name in expected:
            columns = inspector.get_columns(table_name)
            col_names = [c["name"] for c in columns]
            print(f"    {CYAN}•{RESET} {table_name} ({len(columns)} columns): {', '.join(col_names[:6])}{'...' if len(col_names) > 6 else ''}")

    # Check file size
    db_file = Path(db_path)
    if db_file.exists():
        size_kb = db_file.stat().st_size / 1024
        print(f"\n  {GREEN}✔{RESET} Database file size: {size_kb:.1f} KB")
        if size_kb < 5000:
            print(f"  {GREEN}✔{RESET} Well within 8GB HF container limit")

    print(f"\n  {GREEN}{BOLD}✔  master.db initialized successfully.{RESET}\n")

    engine.dispose()


if __name__ == "__main__":
    init_database()
