#!/usr/bin/env python3
import os
import sys
import time
import smtplib
from email.message import EmailMessage
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

DB_HOST = os.getenv("PGHOST", "127.0.0.1")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_NAME = os.getenv("PGDATABASE", "commercial_ai")
DB_USER = os.getenv("PGUSER", "romain")
DB_PASS = os.getenv("PGPASSWORD")

# Gmail sender
GMAIL_USER = os.getenv("GMAIL_USER")              # ex: liblitz.xyz@gmail.com
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")  # app password (pas ton mdp normal)
FROM_NAME = os.getenv("FROM_NAME", "Liblitz (AI assistant)")
REPLY_TO = os.getenv("REPLY_TO", GMAIL_USER or "")

# Safety / throttle
SEND_LIMIT = int(os.getenv("SEND_LIMIT", "10"))         # commence à 10
SLEEP_BETWEEN = float(os.getenv("SEND_SLEEP", "25"))    # 25s entre mails (cool)
NOTE_FILTER = os.getenv("SEND_NOTE_FILTER", "google domains (AU mix)")  # cible ton batch

# Gmail SMTP
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465  # SSL

SQL_FETCH = """
SELECT
  oq.outreach_id,
  oq.contact_email,
  oq.email_subject,
  oq.email_body
FROM outreach_queue oq
WHERE oq.status = 'draft_ready'
  AND oq.contact_email IS NOT NULL AND oq.contact_email <> ''
  AND oq.email_subject IS NOT NULL AND oq.email_subject <> ''
  AND oq.email_body IS NOT NULL AND oq.email_body <> ''
  AND oq.notes ILIKE %s
ORDER BY oq.updated_at
LIMIT %s
FOR UPDATE SKIP LOCKED;
"""

SQL_MARK_SENT = """
UPDATE outreach_queue
SET
  status = 'sent',
  sent_at = now(),
  updated_at = now(),
  notes = COALESCE(notes,'') || %s
WHERE outreach_id = %s;
"""

SQL_MARK_FAIL = """
UPDATE outreach_queue
SET
  updated_at = now(),
  notes = COALESCE(notes,'') || %s
WHERE outreach_id = %s;
"""

def build_msg(to_email: str, subject: str, body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["To"] = to_email
    msg["From"] = f"{FROM_NAME} <{GMAIL_USER}>"
    msg["Subject"] = subject
    if REPLY_TO:
        msg["Reply-To"] = REPLY_TO
    # text only pour éviter soucis HTML
    msg.set_content(body)
    return msg

def main():
    if not DB_PASS:
        print("❌ PGPASSWORD manquant. export PGPASSWORD='...'", file=sys.stderr)
        sys.exit(1)
    if not GMAIL_USER or not GMAIL_APP_PASSWORD:
        print("❌ GMAIL_USER ou GMAIL_APP_PASSWORD manquant.", file=sys.stderr)
        sys.exit(1)

    note_like = f"%{NOTE_FILTER}%"

    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )
    conn.autocommit = False

    sent_ok = 0
    sent_fail = 0

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("BEGIN;")
            cur.execute(SQL_FETCH, (note_like, SEND_LIMIT))
            rows = cur.fetchall()

            if not rows:
                print("No draft_ready rows to send (matching note filter).")
                conn.rollback()
                return

            print(f"[+] Sending {len(rows)} emails via Gmail SSL...")

            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
                smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)

                for r in rows:
                    outreach_id = r["outreach_id"]
                    to_email = r["contact_email"].strip()
                    subject = r["email_subject"].strip()
                    body = r["email_body"]

                    try:
                        msg = build_msg(to_email, subject, body)
                        smtp.send_message(msg)

                        note = f"\nSysiphe_send=ok at={datetime.now().isoformat()} via=gmail to={to_email}"
                        cur.execute(SQL_MARK_SENT, (note, outreach_id))
                        conn.commit()

                        sent_ok += 1
                        print(f"[✓] Sent to {to_email} ({sent_ok}/{len(rows)})")

                    except Exception as e:
                        conn.rollback()
                        note = f"\nSysiphe_send=fail at={datetime.now().isoformat()} to={to_email} err={type(e).__name__}"
                        cur.execute(SQL_MARK_FAIL, (note, outreach_id))
                        conn.commit()

                        sent_fail += 1
                        print(f"[!] Failed to {to_email}: {type(e).__name__}")

                    time.sleep(SLEEP_BETWEEN)

            print(f"[✓] Done. ok={sent_ok} fail={sent_fail}")

    finally:
        conn.close()

if __name__ == "__main__":
    main()
