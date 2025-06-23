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

Runs llama3.2 (using ollama) and analyzes the sentiment of each article.
Stores results in the database.

Usage:

```
python analyze_articles.py rss_raw_data rss_storage.sqlite
```
