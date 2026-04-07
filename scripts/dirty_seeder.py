#!/usr/bin/env python3
"""
Lead-Ops · Dirty Seeder
========================
Populates master.db with 50 "dirty" CRM leads that simulate
real-world data quality issues: typos, missing fields, stale
emails, wrong industries, inconsistent formatting.

Usage::

    python scripts/dirty_seeder.py
"""

from __future__ import annotations

import json
import random
import string
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db_models import (
    AccountORM,
    Base,
    LeadORM,
    create_db_engine,
    create_all_tables,
)
from sqlalchemy.orm import Session as DBSession

# ── Styling ───────────────────────────────────────────────────────────────────
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ── Seed Data ─────────────────────────────────────────────────────────────────

# Ground truth companies (from solutions.json)
GROUND_TRUTH = [
    {"name": "Stripe", "industry": "FinTech", "revenue": 14_000_000_000, "employees": 8000, "website": "https://stripe.com", "hq": "San Francisco"},
    {"name": "Snowflake", "industry": "Cloud Data", "revenue": 2_800_000_000, "employees": 6800, "website": "https://snowflake.com", "hq": "Bozeman"},
    {"name": "Datadog", "industry": "DevOps / Observability", "revenue": 2_100_000_000, "employees": 5500, "website": "https://datadoghq.com", "hq": "New York"},
    {"name": "Cloudflare", "industry": "Cybersecurity / CDN", "revenue": 1_300_000_000, "employees": 3800, "website": "https://cloudflare.com", "hq": "San Francisco"},
    {"name": "HubSpot", "industry": "MarTech / CRM", "revenue": 2_200_000_000, "employees": 7400, "website": "https://hubspot.com", "hq": "Cambridge"},
    {"name": "Twilio", "industry": "Communications Platform", "revenue": 4_000_000_000, "employees": 5200, "website": "https://twilio.com", "hq": "San Francisco"},
    {"name": "MongoDB", "industry": "Database / Infrastructure", "revenue": 1_700_000_000, "employees": 4600, "website": "https://mongodb.com", "hq": "New York"},
    {"name": "Atlassian", "industry": "Collaboration / DevTools", "revenue": 3_800_000_000, "employees": 11000, "website": "https://atlassian.com", "hq": "Sydney"},
    {"name": "Okta", "industry": "Identity / Cybersecurity", "revenue": 2_300_000_000, "employees": 5800, "website": "https://okta.com", "hq": "San Francisco"},
    {"name": "CrowdStrike", "industry": "Cybersecurity", "revenue": 3_100_000_000, "employees": 8500, "website": "https://crowdstrike.com", "hq": "Austin"},
]

# Additional fictional companies for mid-market and SMB leads
EXTRA_COMPANIES = [
    {"name": "Velocify AI", "industry": "AI / ML", "revenue": 120_000_000, "employees": 450, "website": "https://velocify.ai"},
    {"name": "NexGen Analytics", "industry": "Business Intelligence", "revenue": 85_000_000, "employees": 320, "website": "https://nexgenanalytics.com"},
    {"name": "Prism Health Tech", "industry": "HealthTech", "revenue": 200_000_000, "employees": 800, "website": "https://prismhealthtech.com"},
    {"name": "ClearPath Logistics", "industry": "Logistics / Supply Chain", "revenue": 340_000_000, "employees": 1200, "website": "https://clearpathlogistics.com"},
    {"name": "Apex Financial", "industry": "FinTech", "revenue": 75_000_000, "employees": 280, "website": "https://apexfinancial.io"},
    {"name": "Quantum Security", "industry": "Cybersecurity", "revenue": 45_000_000, "employees": 150, "website": "https://quantumsecurity.com"},
    {"name": "BluePeak CRM", "industry": "SaaS / CRM", "revenue": 30_000_000, "employees": 110, "website": "https://bluepeakcrm.com"},
    {"name": "DataForge", "industry": "Data Engineering", "revenue": 22_000_000, "employees": 90, "website": "https://dataforge.dev"},
    {"name": "Relay Commerce", "industry": "E-commerce", "revenue": 180_000_000, "employees": 650, "website": "https://relaycommerce.com"},
    {"name": "Sentinel Ops", "industry": "DevOps", "revenue": 55_000_000, "employees": 200, "website": "https://sentinelops.io"},
    {"name": "Orbit Cloud", "industry": "Cloud Infrastructure", "revenue": 410_000_000, "employees": 1500, "website": "https://orbitcloud.com"},
    {"name": "Forma Design", "industry": "Design Tools", "revenue": 15_000_000, "employees": 60, "website": "https://formadesign.co"},
    {"name": "PayStream", "industry": "FinTech", "revenue": 95_000_000, "employees": 380, "website": "https://paystream.io"},
    {"name": "GreenChain Supply", "industry": "Sustainability / Logistics", "revenue": 28_000_000, "employees": 100, "website": "https://greenchainsupply.com"},
    {"name": "MediSync", "industry": "HealthTech", "revenue": 62_000_000, "employees": 240, "website": "https://medisync.health"},
]

ALL_COMPANIES = GROUND_TRUTH + EXTRA_COMPANIES

FIRST_NAMES = ["James", "Sarah", "Michael", "Priya", "David", "Emma", "Carlos", "Aisha", "Wei", "Fatima",
               "John", "Lisa", "Robert", "Maria", "Ahmed", "Nina", "Thomas", "Yuki", "Daniel", "Sofia",
               "Alex", "Jordan", "Taylor", "Morgan", "Casey"]

LAST_NAMES = ["Smith", "Johnson", "Williams", "Patel", "Kim", "Chen", "Garcia", "Brown", "Lee", "Anderson",
              "Wilson", "Thompson", "Martinez", "Davis", "Rodriguez", "Murphy", "O'Brien", "Singh", "Müller", "Tanaka"]

TITLES = ["VP of Sales", "Director of Engineering", "CTO", "VP of Marketing", "Head of Operations",
          "Director of IT", "CFO", "VP of Product", "Director of Sales", "Head of Procurement",
          "Chief Revenue Officer", "VP of Engineering", "Director of Business Development"]

TECH_STACKS = [
    ["Python", "AWS", "PostgreSQL"],
    ["Java", "Azure", "MySQL"],
    ["Go", "GCP", "MongoDB"],
    ["Ruby", "AWS", "Redis"],
    ["Node.js", "Kubernetes", "Elasticsearch"],
    ["React", "TypeScript", "Firebase"],
    ["Scala", "Spark", "Databricks"],
    ["Rust", "Docker", "Terraform"],
]

LEAD_SOURCES = ["inbound", "outbound", "referral", "event", "partner", "organic", "paid"]


# ── Dirtying Functions ───────────────────────────────────────────────────────

def _add_typo(name: str) -> str:
    """Introduce a realistic typo into a company name."""
    typos = {
        "Stripe": ["Stripee", "Strpe", "Stipe", "Sripe"],
        "Snowflake": ["Snoflake", "Snowflke", "SnowFlake", "Snowlake"],
        "Datadog": ["DataDog", "Datdog", "Data Dog", "Dataadog"],
        "Cloudflare": ["CloudFlare", "Clouflare", "Clodflare", "Cloud Flare"],
        "HubSpot": ["Hub Spot", "Hubpot", "HubSppot", "Hubspot"],
        "Twilio": ["Twillio", "Twilo", "Twillo", "Twiliio"],
        "MongoDB": ["Mongo DB", "MongoDb", "Mogodb", "MongDB"],
        "Atlassian": ["Atlasian", "Attlassian", "Atlasssian", "Atlasian"],
        "Okta": ["OKTA", "Oktta", "Oka", "Okta Inc"],
        "CrowdStrike": ["Crowd Strike", "CrowdStike", "Crowdstrike", "CrowStrike"],
    }
    if name in typos:
        return random.choice(typos[name])
    # Generic typo for other companies
    if len(name) > 4 and random.random() < 0.5:
        i = random.randint(1, len(name) - 2)
        return name[:i] + name[i + 1:]  # delete a char
    return name.upper() if random.random() < 0.3 else name + ", Inc."


def _add_formatting_mess(name: str) -> str:
    """Add inconsistent formatting."""
    options = [
        name.upper(),
        name.lower(),
        f"  {name}  ",  # leading/trailing spaces
        f"{name}, Inc.",
        f"{name} Inc",
        f"{name} (US)",
        name,  # clean (sometimes)
    ]
    return random.choice(options)


def _stale_email(first: str, last: str) -> str:
    """Generate a stale/outdated email address."""
    stale_domains = ["oldcompany.com", "previous-employer.net", "legacy-corp.com",
                     "departed.org", "former-role.com"]
    return f"{first.lower()}.{last.lower()}@{random.choice(stale_domains)}"


def _generate_dirty_lead(company: dict, idx: int) -> dict:
    """Generate a single dirty lead with realistic CRM messiness."""
    rng = random.Random(idx * 42 + hash(company["name"]))

    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    title = rng.choice(TITLES)

    # Start with clean data
    lead = {
        "lead_uuid": str(uuid.uuid4()),
        "company_name": company["name"],
        "industry": company["industry"],
        "annual_revenue": company["revenue"],
        "employee_count": company.get("employees"),
        "website": company.get("website"),
        "contact_name": f"{first} {last}",
        "contact_title": title,
        "contact_email": f"{first.lower()}.{last.lower()}@{company['name'].lower().replace(' ', '')}.com",
        "contact_linkedin": f"https://linkedin.com/in/{first.lower()}-{last.lower()}-{rng.randint(1000, 9999)}",
        "tech_stack": rng.choice(TECH_STACKS),
        "lead_source": rng.choice(LEAD_SOURCES),
        "status": "new",
        "is_dirty": True,
    }

    # ── Apply dirtiness ──────────────────────────────────────────────────

    # 30% — Typos in company name
    if rng.random() < 0.30:
        lead["company_name"] = _add_typo(company["name"])

    # 20% — Formatting mess (even if no typo)
    if rng.random() < 0.20:
        lead["company_name"] = _add_formatting_mess(lead["company_name"])

    # 40% — Missing revenue
    if rng.random() < 0.40:
        lead["annual_revenue"] = None

    # 35% — Missing employee count
    if rng.random() < 0.35:
        lead["employee_count"] = None

    # 20% — Wrong/vague industry
    if rng.random() < 0.20:
        wrong_industries = ["Tech", "Software", "IT", "Technology", "Computer", "Digital"]
        lead["industry"] = rng.choice(wrong_industries)

    # 25% — Stale email
    if rng.random() < 0.25:
        lead["contact_email"] = _stale_email(first, last)

    # 15% — Missing ALL contact info
    if rng.random() < 0.15:
        lead["contact_name"] = None
        lead["contact_title"] = None
        lead["contact_email"] = None
        lead["contact_linkedin"] = None

    # 10% — Outdated revenue (older, lower figure)
    if lead["annual_revenue"] is not None and rng.random() < 0.10:
        lead["annual_revenue"] = int(lead["annual_revenue"] * rng.uniform(0.4, 0.7))

    # 20% — Missing website
    if rng.random() < 0.20:
        lead["website"] = None

    # 15% — Empty tech stack
    if rng.random() < 0.15:
        lead["tech_stack"] = []

    return lead


# ── Main ──────────────────────────────────────────────────────────────────────

def seed_dirty_leads(db_path: str = "master.db", count: int = 50) -> None:
    """Generate and insert dirty leads into the database."""
    db_url = f"sqlite:///{db_path}"
    engine = create_db_engine(db_url)
    create_all_tables(engine)

    print(f"\n{BOLD}{CYAN}🌱  Lead-Ops · Dirty Seeder{RESET}")
    print(f"   Database: {db_path}")
    print(f"   Generating {count} messy CRM leads...\n")

    # Track dirtiness stats
    stats = {
        "typos": 0, "missing_revenue": 0, "missing_employees": 0,
        "wrong_industry": 0, "stale_email": 0, "missing_contact": 0,
        "formatting_mess": 0, "outdated_revenue": 0, "missing_website": 0,
        "empty_tech_stack": 0,
    }

    leads_to_insert = []

    # Generate leads — cycle through companies to reach count
    for i in range(count):
        company = ALL_COMPANIES[i % len(ALL_COMPANIES)]
        dirty = _generate_dirty_lead(company, i)

        # Track stats
        if dirty["company_name"] != company["name"]:
            if dirty["company_name"].strip() != company["name"]:
                stats["typos"] += 1
        if dirty["annual_revenue"] is None:
            stats["missing_revenue"] += 1
        if dirty["employee_count"] is None:
            stats["missing_employees"] += 1
        if dirty["contact_name"] is None:
            stats["missing_contact"] += 1
        if dirty["website"] is None:
            stats["missing_website"] += 1
        if not dirty["tech_stack"]:
            stats["empty_tech_stack"] += 1

        lead_orm = LeadORM(
            lead_uuid=dirty["lead_uuid"],
            company_name=dirty["company_name"],
            industry=dirty["industry"],
            annual_revenue=dirty["annual_revenue"],
            employee_count=dirty["employee_count"],
            website=dirty["website"],
            contact_name=dirty["contact_name"],
            contact_title=dirty["contact_title"],
            contact_email=dirty["contact_email"],
            contact_linkedin=dirty["contact_linkedin"],
            tech_stack_json=json.dumps(dirty["tech_stack"]) if dirty["tech_stack"] else None,
            lead_source=dirty["lead_source"],
            status=dirty["status"],
            is_dirty=dirty["is_dirty"],
        )
        leads_to_insert.append(lead_orm)

    # Insert into DB
    with DBSession(engine) as session:
        # Also create Account records for ground truth companies
        for company in GROUND_TRUTH:
            existing = session.query(AccountORM).filter_by(company_name=company["name"]).first()
            if not existing:
                revenue = company["revenue"]
                if revenue >= 500_000_000:
                    segment = "enterprise"
                elif revenue >= 50_000_000:
                    segment = "mid_market"
                else:
                    segment = "smb"

                account = AccountORM(
                    company_name=company["name"],
                    industry=company["industry"],
                    annual_revenue=company["revenue"],
                    employee_count=company.get("employees"),
                    website=company.get("website"),
                    segment=segment,
                )
                session.add(account)

        session.add_all(leads_to_insert)
        session.commit()

        total_leads = session.query(LeadORM).count()
        total_accounts = session.query(AccountORM).count()

    # Print report
    print(f"  {GREEN}✔{RESET} Inserted {count} dirty leads")
    print(f"  {GREEN}✔{RESET} Created {len(GROUND_TRUTH)} Account records")
    print(f"\n  {BOLD}Dirtiness Distribution:{RESET}")
    for stat, value in stats.items():
        pct = (value / count) * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        label = stat.replace("_", " ").title()
        print(f"    {bar} {pct:5.1f}%  {label} ({value}/{count})")

    print(f"\n  {BOLD}Database Totals:{RESET}")
    print(f"    Leads:    {total_leads}")
    print(f"    Accounts: {total_accounts}")
    print(f"\n  {GREEN}{BOLD}✔  Dirty seeding complete.{RESET}\n")

    engine.dispose()


if __name__ == "__main__":
    seed_dirty_leads()
