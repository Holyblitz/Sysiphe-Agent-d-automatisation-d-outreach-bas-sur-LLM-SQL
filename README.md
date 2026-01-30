# Sysiphe

**Sysiphe** is a lightweight, local-first AI outreach automation system.  
It combines SQL-based targeting, LLM-assisted message drafting and SMTP delivery to automate outbound email campaigns while keeping full human control.

This project is **experimental (V1)** and designed for real-world testing, not as a plug-and-play SaaS.

---

## What Sysiphe Does

Sysiphe automates the outbound workflow in four controlled steps:

1. **Target selection**
   - Prospects are selected from a PostgreSQL database
   - Fully transparent, SQL-driven filtering

2. **Message drafting**
   - Emails are generated using a local or self-hosted LLM
   - Drafts are stored in database for review
   - Human-in-the-loop by design

3. **Contact enrichment (optional)**
   - Attempts to extract public contact emails from company websites
   - No scraping of private or gated data

4. **Email sending**
   - SMTP-based sending (Gmail / Brevo)
   - Rate-limited and batch-controlled
   - Full traceability in database

---

## Key Principles

- Local-first (no SaaS dependency required)
- Human supervision at every critical step
- No black-box automation
- Database as the source of truth
- Designed for freelancers and small-scale operators

---

## Tech Stack

- Python 3
- PostgreSQL

---

## Repository Structure

sysiphe/
├── prospect/
│   ├── run_sysiphe_draft_v1.py
│   ├── sysiphe_enrich_contacts_v1.py
│   ├── send_sysiphe_gmail_v1.py
│   └── send_sysiphe_brevo_v1.py
│
├── db/
│   └── schema.sql
│
├── config/
│   └── .env.example
│
├── requirements.txt
└── README.md
- LLMs (local or API-based)
- SMTP (Gmail / Brevo)
- SQL-first orchestration

