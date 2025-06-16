import sys
import yaml

from rss_downloader import RSSDownloader


def main(args):
    if len(args) != 1:
        print("Usage: download_feeds.py feeds.yaml")
        sys.exit(1)

    feeds_path = args[0]
    try:
        with open(feeds_path) as f:
            data = yaml.safe_load(f)
    except BaseException as ex:
        print(f"Error parsing feeds: {ex}")
        sys.exit(1)

    for feed in data:
        feed_name = feed["name"]
        feel_url = feed["url"]

        try:        
            downloader = RSSDownloader(
                source_name=feed_name,
                source_uri=feel_url,
                db_path="rss_storage.sqlite",
                raw_storage_path="rss_raw_data"
            )
            downloader.download_items()
            downloader.archive_old_items()
        except BaseException as ex:
            print(f"Error downloading feed {feed_name}@{feel_url}: {ex}")


if __name__ == "__main__":
    main(sys.argv[1:])
