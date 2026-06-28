"""
Pipeline orchestrator: download feeds → analyze articles → send digest.

Designed to run on a schedule (e.g., Windows Task Scheduler every 2 hours).
- Skips LLM analysis if GPU utilization exceeds the threshold.
- Uses a lockfile so concurrent instances exit cleanly without fighting.
- Shows a tray icon while running (green → yellow if GPU busy, red on error).
- Logs all output to pipeline.log alongside a console echo.
"""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

import psutil

from tray_icon import TrayIcon

# ---------------------------------------------------------------------------
# Logging – write to pipeline.log AND stdout
# ---------------------------------------------------------------------------

def _setup_logging(log_path: Path):
    logger = logging.getLogger('pipeline')
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter('%(asctime)s  %(levelname)-8s  %(message)s',
                            datefmt='%Y-%m-%d %H:%M:%S')
    fh = logging.FileHandler(log_path, encoding='utf-8')
    fh.setFormatter(fmt)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


# ---------------------------------------------------------------------------
# Lockfile – PID-based, safe on Windows and Unix
# ---------------------------------------------------------------------------

class Lockfile:
    def __init__(self, path: Path):
        self.path = path

    def acquire(self) -> bool:
        if self.path.exists():
            try:
                pid = int(self.path.read_text().strip())
                if psutil.pid_exists(pid):
                    return False  # another instance is live
            except (ValueError, OSError):
                pass  # stale / corrupt lock — take it
        self.path.write_text(str(os.getpid()))
        return True

    def release(self):
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# GPU check
# ---------------------------------------------------------------------------

def _gpu_utilization() -> int | None:
    """Returns GPU utilization percentage (0-100), or None if unavailable."""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=utilization.gpu',
             '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            values = [int(v.strip()) for v in result.stdout.strip().splitlines() if v.strip().isdigit()]
            return max(values) if values else None
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def _gpu_is_busy(threshold: int) -> bool:
    util = _gpu_utilization()
    if util is None:
        return False  # nvidia-smi not available — assume free
    return util > threshold


# ---------------------------------------------------------------------------
# Pipeline steps (thin wrappers around each script's main())
# ---------------------------------------------------------------------------

def _step_download(feeds_file: str, db_path: Path, raw_storage_path: Path, logger):
    logger.info("Step 1/3: Downloading feeds from %s", feeds_file)
    from download_feeds import main as download_main

    # download_feeds.main() uses hardcoded paths; we patch them via env-style
    # override by monkey-patching RSSDownloader's defaults.
    import rss_downloader as _rsd
    _orig_init = _rsd.RSSDownloader.__init__

    def _patched_init(self, source_name, source_uri, db_path=None, raw_storage_path=None):
        _orig_init(self, source_name, source_uri,
                   str(db_path) if db_path else str(db_path),
                   str(raw_storage_path) if raw_storage_path else str(raw_storage_path))

    # download_feeds calls RSSDownloader with its own hardcoded paths; we need
    # to call it differently. Parse the yaml ourselves and call RSSDownloader
    # with the correct paths.
    import yaml
    from rss_downloader import RSSDownloader

    with open(feeds_file) as f:
        feeds = yaml.safe_load(f)

    for feed in feeds:
        name = feed['name']
        url = feed['url']
        try:
            dl = RSSDownloader(
                source_name=name,
                source_uri=url,
                db_path=str(db_path),
                raw_storage_path=str(raw_storage_path),
            )
            dl.download_items()
            dl.archive_old_items()
            logger.info("  Downloaded: %s", name)
        except Exception as e:
            logger.warning("  Failed to download %s: %s", name, e)


def _step_analyze(runtime: str, db_path: Path, raw_storage_path: Path, logger):
    logger.info("Step 2/3: Analyzing articles with runtime=%s", runtime)
    from analyze_articles import analyze_articles
    from ollama_wrapper import OllamaWrapper
    from llama_cpp_wrapper import LlamaCppWrapper

    MODEL_NAME = 'llama3.2'
    if runtime == 'ollama':
        client = OllamaWrapper(MODEL_NAME)
    else:
        client = LlamaCppWrapper()

    try:
        client.start()
        analyze_articles(client, str(raw_storage_path), str(db_path))
    finally:
        client.stop()


def _step_digest(to: str, db_path: Path, logger):
    logger.info("Step 3/3: Sending digest to %s", to)
    from send_digest import main as digest_main
    digest_main(['--to', to, '--db-path', str(db_path)])


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(args):
    parser = argparse.ArgumentParser(description='Run the better-news pipeline.')
    parser.add_argument('--feeds-file', required=True, help='Path to feeds YAML file')
    parser.add_argument('--runtime', choices=['ollama', 'llama_cpp'], required=True)
    parser.add_argument('--to', required=True, help='Digest recipient email')
    parser.add_argument('--db-path', type=Path, default=Path('rss_storage.sqlite'))
    parser.add_argument('--raw-storage-path', type=Path, default=Path('rss_raw_data'))
    parser.add_argument('--gpu-threshold', type=int, default=20,
                        help='Skip analysis if GPU util%% exceeds this (default: 20)')
    parser.add_argument('--skip-email', action='store_true',
                        help='Run download + analysis but skip the digest email')
    parser.add_argument('--force', action='store_true',
                        help='Bypass GPU check and run analysis regardless')
    parser.add_argument('--log-path', type=Path, default=Path('pipeline.log'))
    parser.add_argument('--lock-path', type=Path, default=Path('pipeline.lock'))
    parsed = parser.parse_args(args)

    logger = _setup_logging(parsed.log_path)
    lock = Lockfile(parsed.lock_path)
    icon = TrayIcon()

    if not lock.acquire():
        logger.info('Another pipeline instance is running (lock: %s). Exiting.', parsed.lock_path)
        sys.exit(0)

    icon.start()
    gpu_skipped = False

    try:
        logger.info('=== Pipeline started ===')

        _step_download(parsed.feeds_file, parsed.db_path, parsed.raw_storage_path, logger)

        if not parsed.force and _gpu_is_busy(parsed.gpu_threshold):
            util = _gpu_utilization()
            logger.warning('GPU utilization is %s%% (threshold %s%%) — skipping analysis.',
                           util, parsed.gpu_threshold)
            icon.set_gpu_skipped()
            gpu_skipped = True
        else:
            _step_analyze(parsed.runtime, parsed.db_path, parsed.raw_storage_path, logger)

        if not parsed.skip_email:
            _step_digest(parsed.to, parsed.db_path, logger)
        else:
            logger.info('Step 3/3: Skipped (--skip-email)')

        logger.info('=== Pipeline finished%s ===',
                    ' (analysis skipped: GPU busy)' if gpu_skipped else '')

    except Exception as e:
        logger.exception('Pipeline error: %s', e)
        icon.set_error()
        import time; time.sleep(10)  # hold red icon briefly so user notices
        lock.release()
        icon.stop()
        sys.exit(1)

    lock.release()
    icon.stop()


if __name__ == '__main__':
    main(sys.argv[1:])
