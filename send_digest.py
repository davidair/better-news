import argparse
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import dateparser

from mailer import authenticate_gmail, send_email

BATCH_SIZE = 50
BOOTSTRAP_DAYS = 7


def init_sent_items_table(conn):
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sent_items (
            source TEXT,
            pubDate TEXT,
            title TEXT,
            sent_at TEXT,
            PRIMARY KEY (source, pubDate, title)
        )
    ''')
    conn.commit()


def is_first_run(conn):
    row = conn.execute('SELECT COUNT(*) FROM sent_items').fetchone()
    return row[0] == 0


def fetch_unread_positives(conn, bootstrap_cutoff=None):
    """Returns all positive-sentiment items not yet sent, sorted oldest-first."""
    rows = conn.execute('''
        SELECT r.source, r.pubDate, r.title, r.link
        FROM rss_items r
        JOIN sentiment s
            ON r.source = s.source AND r.pubDate = s.pubDate AND r.title = s.title
        LEFT JOIN sent_items si
            ON r.source = si.source AND r.pubDate = si.pubDate AND r.title = si.title
        WHERE s.sentiment = 1 AND si.source IS NULL
    ''').fetchall()

    items = []
    for source, pubDate, title, link in rows:
        parsed = dateparser.parse(pubDate, settings={'RETURN_AS_TIMEZONE_AWARE': True})
        if parsed is None:
            continue
        if bootstrap_cutoff and parsed < bootstrap_cutoff:
            continue
        items.append((parsed, source, pubDate, title, link))

    items.sort(key=lambda x: x[0])
    return items


def build_email_body(batch):
    """Returns (plain_text, html) for a batch of items."""
    plain_lines = []
    html_items = []

    for parsed_date, source, pubDate, title, link in batch:
        date_str = parsed_date.strftime('%b %d')
        plain_lines.append(f"• {title} ({source}, {date_str})\n  {link}")
        html_items.append(
            f'<li><a href="{link}">{title}</a>'
            f' <span style="color:#888;font-size:0.9em">— {source}, {date_str}</span></li>'
        )

    plain = "Your positive news digest:\n\n" + "\n\n".join(plain_lines)
    html = (
        "<html><body>"
        "<h2 style='font-family:sans-serif'>Your positive news digest</h2>"
        "<ul style='font-family:sans-serif;line-height:1.8'>"
        + "".join(html_items)
        + "</ul></body></html>"
    )
    return plain, html


def subject_for_batch(batch, batch_num, total_batches):
    dates = [item[0] for item in batch]
    lo = min(dates).strftime('%b %d')
    hi = max(dates).strftime('%b %d')
    date_range = lo if lo == hi else f"{lo} – {hi}"
    suffix = f" ({batch_num}/{total_batches})" if total_batches > 1 else ""
    return f"Better News: {date_range}{suffix}"


def mark_sent(conn, batch, sent_at):
    conn.executemany(
        'INSERT OR IGNORE INTO sent_items (source, pubDate, title, sent_at) VALUES (?, ?, ?, ?)',
        [(source, pubDate, title, sent_at) for _, source, pubDate, title, _ in batch]
    )
    conn.commit()


def main(args):
    parser = argparse.ArgumentParser(description="Send positive news digest emails.")
    parser.add_argument('--to', required=True, help='Recipient email address')
    parser.add_argument('--db-path', type=Path, default=Path('rss_storage.sqlite'))
    parser.add_argument('--max-items', type=int, default=BATCH_SIZE,
                        help=f'Max items per email batch (default: {BATCH_SIZE})')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print digest without sending')
    parsed = parser.parse_args(args)

    if not parsed.db_path.exists():
        print(f"Database not found: {parsed.db_path}")
        sys.exit(1)

    conn = sqlite3.connect(parsed.db_path)
    init_sent_items_table(conn)

    bootstrap_cutoff = None
    if is_first_run(conn):
        bootstrap_cutoff = datetime.now(timezone.utc) - timedelta(days=BOOTSTRAP_DAYS)
        print(f"First run — limiting to items from the last {BOOTSTRAP_DAYS} days.")

    items = fetch_unread_positives(conn, bootstrap_cutoff)

    if not items:
        print("No new positive items to send.")
        conn.close()
        return

    # Split into batches
    batches = [items[i:i + parsed.max_items] for i in range(0, len(items), parsed.max_items)]
    total_batches = len(batches)
    print(f"Found {len(items)} item(s) across {total_batches} email(s).")

    service = None if parsed.dry_run else authenticate_gmail()
    sent_at = datetime.now(timezone.utc).isoformat()

    for i, batch in enumerate(batches, 1):
        subject = subject_for_batch(batch, i, total_batches)
        plain, html = build_email_body(batch)

        if parsed.dry_run:
            print(f"\n--- DRY RUN: Email {i}/{total_batches} ---")
            print(f"Subject: {subject}")
            print(plain)
            continue

        send_email(service, parsed.to, subject, plain, html)
        mark_sent(conn, batch, sent_at)
        print(f"Sent batch {i}/{total_batches}: {subject}")

    conn.close()


if __name__ == '__main__':
    main(sys.argv[1:])
