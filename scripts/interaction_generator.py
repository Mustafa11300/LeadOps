#!/usr/bin/env python3
"""
Lead-Ops · Interaction Log Generator
======================================
Generates realistic email threads between SDRs and prospects.
Each thread contains embedded MEDDIC signals that the AI agent must extract.

Usage::

    python scripts/interaction_generator.py

Generates 3–5 email threads per lead (150–250 total emails).
Each email may contain MEDDIC signals tagged with pillar and strength.
"""

from __future__ import annotations

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db_models import (
    InteractionLogORM,
    LeadORM,
    create_db_engine,
    create_all_tables,
)
from sqlalchemy.orm import Session as DBSession

# ── Styling ───────────────────────────────────────────────────────────────────
GREEN = "\033[92m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# ── SDR Team ──────────────────────────────────────────────────────────────────

SDRS = [
    {"name": "Rachel Torres", "email": "rachel.torres@leadops.io"},
    {"name": "Kevin Park", "email": "kevin.park@leadops.io"},
    {"name": "Maya Krishnan", "email": "maya.krishnan@leadops.io"},
    {"name": "Jake Morrison", "email": "jake.morrison@leadops.io"},
]

# ── MEDDIC Signal Templates ──────────────────────────────────────────────────
# Each template has: pillar, strength, and email body content

MEDDIC_SIGNALS = {
    "identify_pain": [
        {
            "strength": 0.9,
            "subject": "Re: Current workflow challenges",
            "body": (
                "Thanks for asking about our pain points. Honestly, the biggest issue is that "
                "we're spending 40+ hours a week manually reconciling data between our legacy ERP "
                "and the new CRM. Our ops team is burning out — we've already lost two analysts "
                "this quarter because of the workload. If we don't solve this by Q3, I'm worried "
                "we'll lose more people and miss our revenue targets."
            ),
        },
        {
            "strength": 0.7,
            "subject": "Re: Discovery follow-up",
            "body": (
                "To follow up on our call — the manual data entry is killing our productivity. "
                "Our reps are spending about 30% of their day on administrative tasks instead of "
                "actually selling. It's frustrating for everyone, and our VP of Sales brought it up "
                "in the last board meeting as a major blocker."
            ),
        },
        {
            "strength": 0.5,
            "subject": "Re: Initial introduction",
            "body": (
                "We're generally happy with our current setup, but there are definitely areas where "
                "things could be smoother. The reporting takes longer than it should, and we sometimes "
                "miss leads because of how our pipeline is set up. Not urgent, but worth exploring."
            ),
        },
    ],
    "metrics": [
        {
            "strength": 0.9,
            "subject": "Re: ROI discussion",
            "body": (
                "I ran the numbers with our finance team. We calculated we're losing approximately "
                "$2.3M per quarter due to leads falling through the cracks — our conversion rate "
                "dropped from 18% to 11% since the migration. If your solution can help us get back "
                "to even 15%, that's roughly $1.5M in recovered revenue per quarter. The CFO is very "
                "interested in seeing a concrete business case."
            ),
        },
        {
            "strength": 0.6,
            "subject": "Re: Value proposition",
            "body": (
                "We estimate the current process inefficiencies cost us somewhere in the range of "
                "$500K-$800K annually, though we haven't done a formal analysis. Our average deal "
                "cycle is 47 days and we'd like to get it under 30. Anything that moves the needle "
                "on pipeline velocity would be valuable."
            ),
        },
        {
            "strength": 0.3,
            "subject": "Re: Exploring options",
            "body": (
                "We know there's room for improvement but haven't quantified it yet. Our team "
                "generally feels like we could be more efficient. Would your platform help with "
                "that? We'd need to see some case studies from similar companies."
            ),
        },
    ],
    "economic_buyer": [
        {
            "strength": 0.9,
            "subject": "Re: Next steps — executive alignment",
            "body": (
                "Great news — I spoke with our CFO, Diana Chen, and she's approved a budget of "
                "$250K for this initiative. She wants to be on the next call to discuss implementation "
                "timeline and ROI projections. I'm CC'ing her on this email. She has final sign-off "
                "authority for anything under $500K."
            ),
        },
        {
            "strength": 0.6,
            "subject": "Re: Budget discussion",
            "body": (
                "I'll need to run this by our VP of Operations, Mark Stevens. He controls the budget "
                "for this type of purchase. I've mentioned your solution to him and he seemed open but "
                "wants to see a demo first. Can we schedule something for next week?"
            ),
        },
        {
            "strength": 0.3,
            "subject": "Re: Pricing inquiry",
            "body": (
                "Thanks for the pricing breakdown. I need to check with my team lead about the budget "
                "situation. I'm not sure who specifically would need to approve this — probably someone "
                "on the leadership team. Let me figure that out and get back to you."
            ),
        },
    ],
    "champion": [
        {
            "strength": 0.9,
            "subject": "Re: Internal update — exciting news",
            "body": (
                "I've already presented your solution to our CTO and she's keen. She asked me to set "
                "up a technical deep-dive with the engineering team next week. I also put together "
                "a one-pager comparing your platform to our current approach — the numbers clearly "
                "favor switching. Between you and me, there might be some pushback from the IT team "
                "because they like the current vendor, but our CTO outranks them and she's on board."
            ),
        },
        {
            "strength": 0.6,
            "subject": "Re: Internal advocacy",
            "body": (
                "I shared your case study with a few colleagues and the feedback was positive. "
                "Our Director of Engineering said it 'looks promising' and would be open to a "
                "technical evaluation. I'll try to get a meeting on the calendar."
            ),
        },
        {
            "strength": 0.3,
            "subject": "Re: Follow-up",
            "body": (
                "I think your solution is interesting, but I'm not really the right person to push "
                "this forward internally. I'm more of an end user. Maybe try reaching out to our "
                "IT department directly? They handle all vendor evaluations."
            ),
        },
    ],
    "decision_criteria": [
        {
            "strength": 0.8,
            "subject": "Re: Technical requirements",
            "body": (
                "We've put together our evaluation criteria. The must-haves are: SOC2 compliance, "
                "SSO integration with Okta, real-time API (sub-200ms latency), and native Salesforce "
                "connector. Nice-to-haves include custom reporting dashboards and mobile access. "
                "We're evaluating against two other vendors — one is a startup and the other is an "
                "established player. Timeline for decision is end of next month."
            ),
        },
        {
            "strength": 0.5,
            "subject": "Re: What we're looking for",
            "body": (
                "We need something that integrates with Salesforce and is easy to use. Security "
                "is important too — we're in a regulated industry so compliance matters. Beyond "
                "that, we're still figuring out our exact requirements. Can you send over a "
                "feature comparison matrix?"
            ),
        },
    ],
    "decision_process": [
        {
            "strength": 0.8,
            "subject": "Re: Procurement timeline",
            "body": (
                "Here's how our buying process works: after the demo, we'll need a 2-week technical "
                "pilot with our engineering team. Then there's a vendor review meeting with our "
                "procurement committee (meets first Monday of each month). After that, legal review "
                "takes about 5 business days. If everything checks out, our CFO signs off. We're "
                "targeting a contract start date of January 15th."
            ),
        },
        {
            "strength": 0.4,
            "subject": "Re: What's next?",
            "body": (
                "I'm not entirely sure about the internal process for bringing on a new vendor. "
                "I think we'd need to do a demo, then maybe some kind of trial? Let me check with "
                "our IT team on what the usual steps are. We're not in a huge rush."
            ),
        },
    ],
}

# ── Neutral Email Templates ──────────────────────────────────────────────────

NEUTRAL_EMAILS_OUTBOUND = [
    {
        "subject": "Introduction — Lead-Ops Platform",
        "body": (
            "Hi {contact_name},\n\nI came across {company_name} and thought our platform might be "
            "a good fit for your team's sales operations workflow. We help companies automate lead "
            "enrichment and qualification using AI.\n\nWould you be open to a 15-minute introductory "
            "call this week?\n\nBest,\n{sdr_name}"
        ),
    },
    {
        "subject": "Following up — {company_name}",
        "body": (
            "Hi {contact_name},\n\nJust wanted to follow up on my previous email. I believe we can "
            "help {company_name} improve pipeline velocity and lead quality.\n\nHappy to work around "
            "your schedule for a quick chat.\n\nBest,\n{sdr_name}"
        ),
    },
    {
        "subject": "Quick question about your sales process",
        "body": (
            "Hi {contact_name},\n\nI'm curious — how does your team currently handle lead "
            "qualification? We've been working with similar companies in the {industry} space "
            "and have seen some interesting patterns.\n\nWould love to compare notes.\n\nBest,\n{sdr_name}"
        ),
    },
    {
        "subject": "Demo scheduling — {company_name}",
        "body": (
            "Hi {contact_name},\n\nGreat speaking with you earlier. As discussed, I'd love to "
            "schedule a demo to show you how our platform works in practice. Would any of these "
            "times work?\n\n- Tuesday 2pm PT\n- Wednesday 10am PT\n- Thursday 3pm PT\n\n"
            "Best,\n{sdr_name}"
        ),
    },
]

NEUTRAL_EMAILS_INBOUND = [
    {
        "subject": "Re: Introduction — Lead-Ops Platform",
        "body": (
            "Hi {sdr_name},\n\nThanks for reaching out. We're actually exploring solutions in "
            "this space right now. Could you send over some more information about your pricing "
            "and integrations?\n\nRegards,\n{contact_name}"
        ),
    },
    {
        "subject": "Re: Demo scheduling",
        "body": (
            "Hi {sdr_name},\n\nTuesday at 2pm works for me. Please send over a calendar invite. "
            "I'll also loop in my colleague {colleague_name} who handles our CRM.\n\n"
            "Regards,\n{contact_name}"
        ),
    },
    {
        "subject": "Re: Following up",
        "body": (
            "Hi {sdr_name},\n\nSorry for the delayed response — it's been a hectic quarter. "
            "I'm still interested but need a couple of weeks before we can schedule anything. "
            "Can you check back in mid-{month}?\n\nRegards,\n{contact_name}"
        ),
    },
]


def _generate_thread_for_lead(
    lead: LeadORM,
    thread_idx: int,
    base_time: datetime,
) -> list[InteractionLogORM]:
    """Generate a single email thread for a lead."""
    rng = random.Random(lead.id * 100 + thread_idx)
    sdr = rng.choice(SDRS)
    thread: list[InteractionLogORM] = []
    current_time = base_time + timedelta(days=rng.randint(0, 30))

    contact_name = lead.contact_name or "there"
    contact_email = lead.contact_email or f"contact@{lead.company_name.lower().replace(' ', '')}.com"
    company_name = lead.company_name
    industry = lead.industry or "technology"
    colleague_name = f"{rng.choice(['Alex', 'Sam', 'Jamie', 'Morgan'])} {rng.choice(['Smith', 'Lee', 'Brown'])}"
    months = ["January", "February", "March", "April", "May", "June"]

    def _fmt(body: str) -> str:
        return body.format(
            contact_name=contact_name,
            company_name=company_name,
            sdr_name=sdr["name"],
            industry=industry,
            colleague_name=colleague_name,
            month=rng.choice(months),
        )

    # 1. Outbound intro
    outbound = rng.choice(NEUTRAL_EMAILS_OUTBOUND)
    thread.append(InteractionLogORM(
        lead_id=lead.id,
        log_type="email",
        direction="outbound",
        from_addr=sdr["email"],
        to_addr=contact_email,
        subject=_fmt(outbound["subject"]),
        body=_fmt(outbound["body"]),
        timestamp=current_time,
    ))
    current_time += timedelta(hours=rng.randint(4, 72))

    # 2. Inbound reply
    inbound = rng.choice(NEUTRAL_EMAILS_INBOUND)
    thread.append(InteractionLogORM(
        lead_id=lead.id,
        log_type="email",
        direction="inbound",
        from_addr=contact_email,
        to_addr=sdr["email"],
        subject=_fmt(inbound["subject"]),
        body=_fmt(inbound["body"]),
        timestamp=current_time,
    ))
    current_time += timedelta(hours=rng.randint(2, 48))

    # 3–5. MEDDIC signal emails
    # Pick 1–3 MEDDIC pillars to include signals for
    pillars = list(MEDDIC_SIGNALS.keys())
    rng.shuffle(pillars)
    num_signals = rng.randint(1, 3)
    selected_pillars = pillars[:num_signals]

    for pillar in selected_pillars:
        signal = rng.choice(MEDDIC_SIGNALS[pillar])

        thread.append(InteractionLogORM(
            lead_id=lead.id,
            log_type="email",
            direction="inbound",
            from_addr=contact_email,
            to_addr=sdr["email"],
            subject=signal["subject"],
            body=signal["body"],
            meddic_signal=pillar,
            signal_strength=signal["strength"],
            timestamp=current_time,
        ))
        current_time += timedelta(hours=rng.randint(12, 96))

        # Sometimes the SDR replies to the signal
        if rng.random() < 0.6:
            reply_body = (
                f"Hi {contact_name},\n\nThank you for sharing that — it's really helpful context. "
                f"I want to make sure we address this properly. Let me put together a tailored "
                f"proposal based on what you've described.\n\nBest,\n{sdr['name']}"
            )
            thread.append(InteractionLogORM(
                lead_id=lead.id,
                log_type="email",
                direction="outbound",
                from_addr=sdr["email"],
                to_addr=contact_email,
                subject=f"Re: {signal['subject']}",
                body=reply_body,
                timestamp=current_time,
            ))
            current_time += timedelta(hours=rng.randint(4, 48))

    return thread


# ── Main ──────────────────────────────────────────────────────────────────────

def generate_interactions(db_path: str = "master.db") -> None:
    """Generate interaction logs for all leads in the database."""
    db_url = f"sqlite:///{db_path}"
    engine = create_db_engine(db_url)

    print(f"\n{BOLD}{CYAN}📧  Lead-Ops · Interaction Log Generator{RESET}")
    print(f"   Database: {db_path}\n")

    total_emails = 0
    total_signals = 0
    signal_counts = {pillar: 0 for pillar in MEDDIC_SIGNALS}

    base_time = datetime(2025, 10, 1, 9, 0, 0)

    with DBSession(engine) as session:
        leads = session.query(LeadORM).all()

        if not leads:
            print(f"  ⚠ No leads found in database. Run dirty_seeder.py first.")
            return

        print(f"  Generating emails for {len(leads)} leads...\n")

        all_logs: list[InteractionLogORM] = []

        for lead in leads:
            rng = random.Random(lead.id)
            num_threads = rng.randint(3, 5)

            for t in range(num_threads):
                thread = _generate_thread_for_lead(lead, t, base_time)
                all_logs.extend(thread)

                for log in thread:
                    total_emails += 1
                    if log.meddic_signal:
                        total_signals += 1
                        signal_counts[log.meddic_signal] += 1

        session.add_all(all_logs)
        session.commit()

        total_in_db = session.query(InteractionLogORM).count()

    # Report
    print(f"  {GREEN}✔{RESET} Generated {total_emails} emails across {len(leads)} leads")
    print(f"  {GREEN}✔{RESET} Embedded {total_signals} MEDDIC signals")
    print(f"\n  {BOLD}MEDDIC Signal Distribution:{RESET}")
    for pillar, count in sorted(signal_counts.items(), key=lambda x: -x[1]):
        bar = "█" * min(count, 30) + "░" * max(0, 30 - count)
        label = pillar.replace("_", " ").title()
        print(f"    {bar} {count:3d}  {label}")

    print(f"\n  {BOLD}Database Total:{RESET} {total_in_db} interaction logs")
    print(f"\n  {GREEN}{BOLD}✔  Interaction generation complete.{RESET}\n")

    engine.dispose()


if __name__ == "__main__":
    generate_interactions()
