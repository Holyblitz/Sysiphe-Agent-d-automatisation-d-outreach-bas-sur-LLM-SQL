#!/usr/bin/env python3
import os
import sys
import time
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

import psycopg2
from psycopg2.extras import RealDictCursor

# ---------- ENV ----------
DB_HOST = os.getenv("PGHOST", "127.0.0.1")
DB_PORT = int(os.getenv("PGPORT", "5432"))
DB_NAME = os.getenv("PGDATABASE", "commercial_ai")
DB_USER = os.getenv("PGUSER", "romain")
DB_PASS = os.getenv("PGPASSWORD")

SMTP_HOST = os.getenv("SMTP_HOST", "smtp-relay.brevo.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

FROM_EMAIL = os.getenv("FROM_EMAIL", "liblitz.the.one@gmail.com")
FROM_NAME = os.getenv("FROM_NAME", "Romain")
REPLY_TO = os.getenv("REPLY_TO", FROM_EMAIL)

SEND_LIMIT = int(os.getenv("SEND_LIMIT", "10"))
SEND_SLEEP = float(os.getenv("SEND_SLEEP", "25"))
NOTE_FILTER = os.getenv("SEND_NOTE_FILTER", "").strip()

# ---------- SQL ----------
SQL_FETCH = """
SELECT
  outreach_id,
  contact_email,
  COALESCE(email_subject,'') AS email_subject,
  COALESCE(email_body,'') AS email_body
FROM outreach_queue
WHERE status = 'draft_ready'
  AND contact_email IS NOT NULL AND contact_email <> ''
  AND (%s = '' OR notes ILIKE ('%%' || %s || '%%'))
ORDER BY updated_at
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

def die(msg: str):
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)

def build_message(to_email: str, subject: str, body: str) -> MIMEText:
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject.strip() if subject.strip() else "(no subject)"
    msg["From"] = formataddr((FROM_NAME, FROM_EMAIL))
    msg["To"] = to_email
    msg["Reply-To"] = REPLY_TO
    return msg

def smtp_connect():
    # STARTTLS on 587
    smtp = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=45)
    smtp.ehlo()
    smtp.starttls()
    smtp.ehlo()
    smtp.login(SMTP_USER, SMTP_PASSWORD)
    return smtp

def main():
    if not DB_PASS:
        die("PGPASSWORD manquant. Fais: export PGPASSWORD='...'.")
    if not SMTP_USER or not SMTP_PASSWORD:
        die("SMTP_USER/SMTP_PASSWORD manquants (Brevo).")

    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )
    conn.autocommit = False

    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("BEGIN;")
            cur.execute(SQL_FETCH, (NOTE_FILTER, NOTE_FILTER, SEND_LIMIT))
            rows = cur.fetchall()

            if not rows:
                print("No rows to send (status='draft_ready' + contact_email).")
                conn.rollback()
                return

            print(f"[+] Sending {len(rows)} emails via Brevo SMTP...")

            smtp = smtp_connect()
            sent_ok = 0
            sent_fail = 0

            for r in rows:
                outreach_id = r["outreach_id"]
                to_email = (r["contact_email"] or "").strip()
                subject = r["email_subject"] or ""
                body = r["email_body"] or ""

                if not to_email or "@" not in to_email:
                    note = "\nSend_fail=invalid_email"
                    cur.execute(SQL_MARK_FAIL, (note, outreach_id))
                    sent_fail += 1
                    continue

                msg = build_message(to_email, subject, body)

                try:
                    smtp.sendmail(FROM_EMAIL, [to_email], msg.as_string())
                    note = "\nSent_via=brevo_smtp"
                    cur.execute(SQL_MARK_SENT, (note, outreach_id))
                    sent_ok += 1
                    print(f"[✓] sent -> {to_email} ({outreach_id})")
                except Exception as e:
                    note = f"\nSend_fail=brevo_smtp err={type(e).__name__}"
                    cur.execute(SQL_MARK_FAIL, (note, outreach_id))
                    sent_fail += 1
                    print(f"[!] fail -> {to_email} ({outreach_id}) : {e}")

                conn.commit()  # commit each send to not lose progress
                time.sleep(SEND_SLEEP)

            try:
                smtp.quit()
            except Exception:
                pass

            print(f"[✓] Done. ok={sent_ok} fail={sent_fail}")

    finally:
        conn.close()

if __name__ == "__main__":
    main()
