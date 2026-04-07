# Lead-Ops

> **OpenEnv-compliant RL environment for autonomous sales lead enrichment, MEDDIC qualification, and strategic routing.**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.11-green.svg)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)]()

---

## 🌐 Environment Description

Lead-Ops models the end-to-end lifecycle of a B2B sales lead as a reinforcement learning environment. An autonomous agent observes raw CRM data, takes actions to enrich and qualify leads, and receives reward signals based on data quality, MEDDIC coverage, and routing accuracy.

The environment exposes **three tasks** that mirror the real-world Sales Operations pipeline:

| Task ID | Description | Max Steps |
|---|---|---|
| `enrich_lead` | Enrich a raw CRM lead with firmographic, technographic, and contact intelligence | 10 |
| `meddic_qualify` | Score a lead against the 6 MEDDIC pillars | 12 |
| `strategic_route` | Route a qualified lead to the optimal AE or team | 5 |

---

## 📐 Observation Space

The agent observes a `LeadObservation` object representing the current state of a CRM lead:

| Field | Type | Description |
|---|---|---|
| `lead_id` | `str` | Unique lead identifier |
| `company_name` | `str` | Company name |
| `industry` | `str?` | Industry vertical |
| `annual_revenue` | `float?` | Annual revenue (USD) |
| `employee_count` | `int?` | Number of employees |
| `website` | `str?` | Company website URL |
| `contact_name` | `str?` | Primary contact name |
| `contact_title` | `str?` | Contact job title |
| `contact_email` | `str?` | Contact email |
| `contact_linkedin` | `str?` | LinkedIn profile URL |
| `tech_stack` | `list[str]` | Known technologies used |
| `lead_source` | `LeadSource?` | Acquisition channel |
| `meddic_scores` | `MEDDICScores?` | MEDDIC qualification scores |
| `enrichment_data` | `dict?` | Raw enrichment payload |
| `routing_result` | `RoutingResult?` | Routing assignment |

---

## 🎯 Action Space

Actions follow a **Chain-of-Thought (CoT)** format — the agent must articulate its reasoning before invoking a tool:

```json
{
  "thought": "The lead is missing firmographic data. I should search for company revenue and employee count to improve enrichment coverage.",
  "tool_name": "tavily_search",
  "parameters": {"query": "Acme Corp annual revenue employees"},
  "confidence": 0.85
}
```

### Available Tools

| Tool | Description | Primary Task |
|---|---|---|
| `tavily_search` | Web search for company intelligence | `enrich_lead` |
| `crm_lookup` | Look up existing CRM records | `enrich_lead` |
| `linkedin_enrich` | Enrich with LinkedIn profile data | `enrich_lead` |
| `score_meddic` | Run MEDDIC scoring pipeline | `meddic_qualify` |
| `route_to_ae` | Route lead to an Account Executive | `strategic_route` |
| `disqualify` | Mark lead as disqualified | Any |

---

## 🏆 Reward Function

Rewards are scalar values in `[0.0, 1.0]` with a component breakdown:

- **Data Completeness** — Fraction of CRM fields populated
- **MEDDIC Coverage** — Composite score across 6 pillars
- **Routing Accuracy** — Quality of AE-to-lead fit
- **Efficiency** — Fewer steps = higher reward bonus

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- A Hugging Face API token
- A Tavily API key

### Setup

```bash
# 1. Clone the repository
git clone <repo-url> && cd Lead-Ops

# 2. Create virtual environment
python -m venv venv && source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your real API keys

# 5. Validate the setup
python check_compliance.py
```

### Run the Server

```bash
uvicorn server.app:app --reload --port 8000
```

---

## 👤 User Persona

### Primary Persona — Sales Operations Leader

| Attribute | Detail |
|---|---|
| **Role** | VP / Director of Sales Operations |
| **Company Stage** | Mid-market to Enterprise (200–5,000 employees) |
| **Industry** | B2B SaaS, FinTech, Enterprise Software |
| **CRM Stack** | Salesforce (primary), HubSpot (secondary) |
| **Sales Methodology** | MEDDIC / MEDDPICC |
| **Team Size** | 15–50 SDRs and AEs across 3+ regions |

### Pain Points

1. **Manual Lead Enrichment** — SDRs spend 30–40% of their time researching leads instead of selling
2. **Inconsistent Qualification** — MEDDIC scoring varies wildly by rep experience and judgment
3. **Suboptimal Routing** — Round-robin assignment ignores deal fit, territory expertise, and historical win rates
4. **Forecast Inaccuracy** — Pipeline is inflated with poorly qualified leads (≥40% slippage)
5. **Data Decay** — CRM records go stale within 90 days; no automated re-enrichment

### Success Metrics

| KPI | Current | Target |
|---|---|---|
| Time-to-first-contact | 4.2 hours | < 1 hour |
| Lead enrichment coverage | 35% | > 90% |
| MEDDIC field completion | 22% | > 85% |
| Qualified-to-Close rate | 12% | > 25% |
| SDR admin time | 40% | < 15% |

### Workflow Requirements

- **Autonomous enrichment** — Agent must fill firmographic + technographic + contact data without human intervention
- **Transparent reasoning** — All qualification decisions must include Chain-of-Thought rationale (audit trail)
- **Human-in-the-loop** — Routing suggestions are presented to managers; auto-routing only after confidence > 0.85
- **CRM sync** — All enrichment and scoring must map back to Salesforce custom fields
- **Compliance** — No PII scraping beyond publicly available business data (LinkedIn, company websites, press releases)

---

## 📁 Project Structure

```
Lead-Ops/
├── openenv.yaml           # OpenEnv manifest
├── models.py              # Pydantic V2 data models
├── config.py              # Environment config loader
├── check_compliance.py    # Validation script
├── requirements.txt       # Pinned dependencies
├── README.md              # This file
├── .env.example           # Environment variable template
├── .env                   # Your secrets (gitignored)
├── .gitignore             # Git ignore rules
└── server/
    └── app.py             # FastAPI entrypoint
```

---

## 🗺️ Roadmap

- [x] **Phase 1:** Environment Foundation — manifest, models, config
- [ ] **Phase 2:** Agent Loop — step engine, tool implementations
- [ ] **Phase 3:** Reward Shaping — composite scoring, feedback loops
- [ ] **Phase 4:** Evaluation — benchmarks, leaderboard integration

---

## 📄 License

MIT
