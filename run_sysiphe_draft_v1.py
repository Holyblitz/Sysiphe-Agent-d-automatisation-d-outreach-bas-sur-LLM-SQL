#!/usr/bin/env python3
import os
import sys
from pathlib import Path
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

EMAIL_TEMPLATE_PATH = Path.home() / "sysiphe" / "prospect" / "e_mail_v2.txt"
DEFAULT_SUBJECT = "Exploring AI-driven workflow automation"

DB_HOST = os.getenv("PGHOST", "127.0.0.1")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_NAME = os.getenv("PGDATABASE", "commercial_ai")
DB_USER = os.getenv("PGUSER", "romain")
DB_PASS = os.getenv("PGPASSWORD")

BATCH_SIZE = 10

SQL_FETCH = """
SELECT
  oq.outreach_id,
  c.canonical_name AS company_name
FROM outreach_queue oq
JOIN companies c ON c.company_id = oq.company_id
WHERE oq.status = 'qualified'
ORDER BY oq.created_at
LIMIT %s
FOR UPDATE SKIP LOCKED;
"""

SQL_UPDATE = """
UPDATE outreach_queue
SET
  email_subject = %s,
  email_body = %s,
  status = 'draft_ready',
  updated_at = now(),
  notes = COALESCE(notes,'') || %s
WHERE outreach_id = %s;
"""


def load_template() -> str:
    if not EMAIL_TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {EMAIL_TEMPLATE_PATH}")
    return EMAIL_TEMPLATE_PATH.read_text(encoding="utf-8")


def render_email(template: str, company_name: str) -> tuple[str, str]:
    """
    Returns (subject, body). If template contains a 'Subject:' line, we extract it.
    Otherwise we use DEFAULT_SUBJECT.
    """
    txt = template.replace("{company_name}", company_name)

    lines = txt.splitlines()
    subject = DEFAULT_SUBJECT

    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip() or DEFAULT_SUBJECT
        body = "\n".join(lines[1:]).lstrip()
    else:
        body = txt

    return subject, body


def main():
    if not DB_PASS:
        print("❌ PGPASSWORD is not set. Do: export PGPASSWORD='...'", file=sys.stderr)
        sys.exit(1)

    template = load_template()

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
    )
    conn.autocommit = False

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("BEGIN;")
            cur.execute(SQL_FETCH, (BATCH_SIZE,))
            rows = cur.fetchall()

            if not rows:
                print("No rows with status='new' found.")
                conn.rollback()
                return

            print(f"[+] Fetched {len(rows)} rows to draft_ready.")

            for r in rows:
                outreach_id = r["outreach_id"]
                company_name = (r["company_name"] or "").strip() or "(unknown)"

                subject, body = render_email(template, company_name)
                note = f"\nDrafted_by=SysipheV1_at={datetime.now().isoformat(timespec='seconds')}"

                cur.execute(SQL_UPDATE, (subject, body, note, outreach_id))

            conn.commit()
            print("[✓] Updated rows to status='draft_ready' with email_subject + email_body.")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()


