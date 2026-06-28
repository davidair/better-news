# Better News – Development Plan

## Project Overview

A pipeline that:
1. Downloads RSS feeds → stores metadata in SQLite + raw XML files
2. Runs local LLM sentiment analysis (Ollama or llama.cpp) → stores `-1/0/1` scores in `sentiment` table
3. Sends email digests via Gmail API

Current scripts: `rss_downloader.py`, `download_feeds.py`, `analyze_articles.py`, `mailer.py`, `utils.py`

---

## Goal 1: Finish the MVP Email Digest

**What's missing:** `mailer.py` currently sends a hardcoded test email. It needs to query the DB for unread positives and compose a real digest.

### Tasks

**1a. Add a `sent_items` tracking table**
- New table in `rss_storage.sqlite`: `sent_items (source TEXT, pubDate TEXT, title TEXT, sent_at TEXT, PRIMARY KEY (source, pubDate, title))`
- Prevents duplicate sends across runs.
- Insert a row when an item is successfully included in a sent digest.

**1b. Write `send_digest.py`**
- Query: `SELECT r.source, r.pubDate, r.title, r.link FROM rss_items r JOIN sentiment s ON ... LEFT JOIN sent_items si ON ... WHERE s.sentiment = 1 AND si.source IS NULL ORDER BY r.pubDate ASC`
- Bootstrap behavior: on first run, if no `sent_items` exist, send at most the **20 most recent** positives (prevents a massive first email from flooding the inbox with all historical items).
- Email size cap: hard limit of **50 items per email**. If more unread positives exist, send multiple batches (one email per batch), or just cap at 50 and let the next run catch up.
- Format: HTML email with `<ul>` list, each item as `<li><a href="LINK">TITLE</a> — SOURCE (DATE)</li>`
- Plain-text fallback: same content as bullet list.
- Args: `--to <email> [--db-path PATH] [--max-items N] [--dry-run]`
- `--dry-run` prints the digest without sending — useful for testing.

**1c. Mark sent items atomically**
- Only write to `sent_items` after `send_email()` succeeds (no exception thrown).
- Use a single DB transaction to insert all sent rows.

### Confirmed decisions
- Bootstrap limit: **last 7 days** of positives on first run.
- Batch size cap: **50 items per email**; if more exist, send multiple emails in one run (cap-and-continue). Each email subject includes the date range.
- Subject line includes date range of articles covered.

---

## Goal 2: Wrapper / Scheduler Script

**Problem:** The pipeline has three steps (download → analyze → digest) that need to run in sequence, on a schedule, on a home PC that:
- Is not always on
- Is used for GPU-heavy tasks (gaming, LLMs)
- Should not hog GPU/CPU when the machine is busy

### Tasks

**2a. Write `run_pipeline.py` — the orchestrator**
- Runs all three steps in sequence: download feeds → analyze articles → send digest
- Args: `--feeds-file PATH --runtime {ollama,llama_cpp} --to <email> [--db-path PATH] [--raw-storage-path PATH] [--skip-email] [--force]`
- Checks GPU utilization before starting the LLM analysis step using `nvidia-smi`:
  ```
  nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits
  ```
  - If GPU util > threshold (default: 20%), skip analysis and log a warning. Downloads can still run.
  - `--force` bypasses the GPU check.
- Cross-platform fallback: if `nvidia-smi` is not found, skip the check and proceed.
- Writes a simple log file (`pipeline.log`) with timestamps and outcomes.

**2b. System tray notification (non-obtrusive)**
- Use `plyer` (cross-platform) for toast/tray notifications.
- Notify at: pipeline start, analysis skipped (GPU busy), email sent, errors.
- Windows: `plyer.notification.notify()` → toast notification
- macOS: same API works via `terminal-notifier`
- Linux: same API works via `notify-send`
- Do NOT require a persistent tray icon — just fire-and-forget toast messages.

**2c. Scheduling**

*Windows (primary):*
- Provide a PowerShell script `setup_task.ps1` that registers a Windows Task Scheduler task.
- Schedule: every 4 hours (configurable).
- Run whether or not user is logged in: No (home PC, OK to require session).
- Wake-to-run: No (machine may be off; just run next time it's on and the trigger fires).
- The task runs `.venv\Scripts\python.exe run_pipeline.py ...` from the project directory.

*macOS:*
- Provide a `com.better-news.plist` launchd template.

*Linux:*
- Provide a crontab snippet in the README.

**2d. Concurrency guard**
- Use a lockfile (`pipeline.lock`) to prevent two simultaneous instances.
- `fcntl.flock` on Unix, a manual PID-file approach on Windows (write PID, check if process alive on startup, delete on exit).
- If locked, log and exit cleanly — do NOT error loudly.

**Confirmed decisions:**
- GPU threshold: **20%** utilization → skip LLM analysis if exceeded.
- Scheduling interval: **every 2 hours** via Windows Task Scheduler.
- Notifications: **persistent tray icon** (not toast spam). Icon appears only when pipeline is actively running; hidden otherwise. Consider color states: idle/hidden, running (green), GPU-skipped (yellow), error (red). Use `pystray` + `Pillow` for cross-platform tray icon.
- macOS equivalent: `rumps` library for menu-bar icon.
- Linux equivalent: `pystray` works there too.

---

## Goal 3 (Stretch): Improve Ranking Quality

**Problem:** The current prompt uses `llama3.2` locally and has not been validated for accuracy.

### Tasks

**3a. Build a sampling/export tool**
- `sample_sentiment.py --count N --db-path PATH` — exports N random items with their current sentiment scores to a CSV/JSON file for review.
- Include: `source, pubDate, title, link, description_snippet, local_sentiment, local_explanation`

**3b. Cross-validate with a stronger LLM**
- Use Claude API (claude-sonnet or opus) to re-score the sampled items.
- Script: `validate_sentiment.py --input sample.json --output comparison.json`
- Compare local vs. cloud scores; compute agreement rate and confusion matrix.

**3c. Prompt refinement**
- Based on disagreements, identify failure modes (false positives, false negatives).
- Iterate on the prompt in `analyze_articles.py` and re-validate.
- Consider a few-shot approach: hardcode 3-5 examples directly into the prompt.

---

## Open Questions / Decisions Needed

1. ~~Bootstrap cutoff~~ → **last 7 days**
2. ~~Email batch cap~~ → **50 items/email, cap-and-continue**
3. ~~GPU threshold~~ → **20%**
4. ~~Notification style~~ → **persistent tray icon** (pystray), hidden when idle
5. ~~Scheduling interval~~ → **every 2 hours**
6. ~~Stretch goal LLM~~ → **Gemini free tier** (Flash 2.0, `google-generativeai` SDK)
