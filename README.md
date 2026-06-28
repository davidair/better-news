# Better News
A tool that uses locally-running LLMs to classify news articles from public sources

## Setup

Make sure you have pyenv installed. To install pyenv:

- Windows: `choco install pyenv-win`
- MacOS: `brew install pyenv`

Make sure pyenv is up to date with `pyenv update`.

This project has been tested with Python 3.13.2.
It can be installed with pyenv via `pyenv install 3.13.2`.

Once installed, set the local Python installation with `pyenv local 3.13.2`.

### Install GCloud CLI

Follow the instructions here:
https://cloud.google.com/sdk/docs/install#installation_instructions

Make sure the "gcloud" command works from the command line before proceeding to next steps.

### Initialize GCloud

```
gcloud init
```

### Create the project

```
gcloud projects create better-news-emailer
gcloud config set project better-news-emailer
```

### Enable the Gmail API

```
gcloud services enable gmail.googleapis.com
```

### Create credentials

- Navigate to https://console.cloud.google.com/auth/overview and follow the instructions to configure auth.
- Navigate to https://console.cloud.google.com/auth/clients and create a "Desktop app" client.
- When offered, download the json file and save it as "credentials.json" in this project's root directory.
- Make sure to add your email address as a test user under Audiences!

Important: if it's been a while and mailing script fails with "google.auth.exceptions.RefreshError", delete token.json which will force a re-authorization.


### Create a virtual environment

```
python -m venv .venv
```

### Activate the virtual environment

Windows: `.venv\Scripts\activate.bat`
MacOS and Linux: `source ./venv/bin/activate`

### Install pip-tools

```
pip install pip-tools
```

### Compile and install the requirements

```
pip-compile && pip-sync
```

On macOS, noticed had to do this for sync, per https://stackoverflow.com/a/69290623:
```
pip-sync --python-executable .venv/bin/python requirements.txt
```

## Usage

### rss_downloader.py

Downloads and archives articles from a single source.
Usage:

```
python rss_downloader.py source_name source_url
```

Use https://github.com/plenaryapp/awesome-rss-feeds to find RSS feeds.

This tool will:

- Save each individual feed item under ./rss_raw_data/SOURCE_NAME/item_key
- Save the date and title of each item in the rss_items table (rss_storage.sqlite database)
- For any article older than a month, will move it to a combined archived XML file (one archive per XML)

The key of the article is the sanitized publication date and a hash of the article title

### download_feeds.py

Processes a YAML file defining multiple sources and calls rss_downloader for each of them.

YAML format:

```
- 
 name: SOURCE_1
 url: https://FEED_1
-
  name: SOURCE_2
  url: https://FEED_2
...
```

Usage:

```
python download_feeds.py feeds.yaml
```

### analyze_articles.py

Analyzes the sentiment of each article.
Stores results in the database.

Supports using ollama or llama-cpp.

Usage:

```
python analyze_articles.py --runtime {ollama,llama_cpp} [--raw-storage-path RAW_STORAGE_PATH] [--db-path DB_PATH]
```

Note: for llama-cpp, create a llama-cpp-config.yaml file:

```
server_path: path to a precompiled llama-server binary
model_path: Path to a compatible gguf file
```

### send_digest.py

Sends an HTML email digest of positive-sentiment articles not yet emailed.
Tracks sent items in the database to avoid duplicates.
On first run, only includes articles from the last 7 days.

Usage:

```
python send_digest.py --to your@email.com [--db-path DB_PATH] [--max-items N] [--dry-run]
```

`--dry-run` prints the digest without sending anything.

### run_pipeline.py

Orchestrates the full pipeline: download → analyze → digest.
Designed to run on a schedule. Features:
- Skips LLM analysis if GPU utilization exceeds a threshold (default: 20%)
- Uses a lockfile so concurrent instances exit cleanly
- Shows a system tray icon while running (green = running, yellow = GPU busy, red = error)

Usage:

```
python run_pipeline.py --feeds-file feeds.yaml --runtime {ollama,llama_cpp} --to your@email.com
```

Optional flags:

```
--db-path PATH              (default: rss_storage.sqlite)
--raw-storage-path PATH     (default: rss_raw_data)
--gpu-threshold N           Skip analysis if GPU% > N (default: 20)
--skip-email                Download + analyze only, no digest
--force                     Bypass GPU check
--log-path PATH             (default: pipeline.log)
```

The tray icon requires `pystray` and `Pillow` (included in requirements). If they are
not available the pipeline runs without a tray icon.

### Scheduling

**Windows (Task Scheduler)**

Run once as the user who will own the task:

```powershell
.\setup_task.ps1 -To your@email.com -Runtime ollama -FeedsFile feeds.yaml
```

This registers a task named `BetterNews-Pipeline` that runs every 2 hours.
Use `-IntervalHours N` to change the interval.

To remove the task:
```powershell
Unregister-ScheduledTask -TaskName 'BetterNews-Pipeline' -Confirm:$false
```

**macOS (launchd)**

Create `~/Library/LaunchAgents/com.better-news.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.better-news</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/better-news/.venv/bin/python</string>
    <string>/path/to/better-news/run_pipeline.py</string>
    <string>--feeds-file</string><string>/path/to/better-news/feeds.yaml</string>
    <string>--runtime</string><string>ollama</string>
    <string>--to</string><string>your@email.com</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/path/to/better-news</string>
  <key>StartInterval</key>
  <integer>7200</integer>
  <key>StandardOutPath</key>
  <string>/path/to/better-news/pipeline.log</string>
  <key>StandardErrorPath</key>
  <string>/path/to/better-news/pipeline.log</string>
</dict>
</plist>
```

Load it with:
```
launchctl load ~/Library/LaunchAgents/com.better-news.plist
```

**Linux (cron)**

```
0 */2 * * * cd /path/to/better-news && .venv/bin/python run_pipeline.py \
  --feeds-file feeds.yaml --runtime ollama --to your@email.com >> pipeline.log 2>&1
```
