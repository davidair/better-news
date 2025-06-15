# Generated via a Copilot Prompt:
#
# Let's start with a Python module that defines an RSSDownloader class.
# It should be constructed with a source name and source URI, as well as a path to SQLite3 db and path for raw storage.
# Since the original items are XML, let's stick to that format.
# Additionally, I think we can have a different approach for storing data:
#   1. The RSSDownloader class with expose a single method called download_items
#   2. It will save the core metadata (title, link, pubDate) to sqlite
#   3. It will use pubDate+title as the primary key, feels safe enough
#   4. It will store each item as an individual file, with the name being an MD5 hash to the title and a sanitized timestamp (in yyyy_mm_dd_hh_mm_ss format).
#   5. Define another method that will "archive" older files by simply combining them in a larger XML file and delete the original files - we can make archives monthly, so we will never have too many archive and never too many individual files.
#
# Can you please provide me with the complete implementation of RSSDownloader?   

import dateparser
import hashlib
import os
import time
import requests
import sqlite3
import sys
import xml.etree.ElementTree as ET

from utils import generate_filename

class RSSDownloader:
    def __init__(self, source_name, source_uri, db_path, raw_storage_path):
        self.source_name = source_name
        self.source_uri = source_uri
        self.db_path = db_path
        self.raw_storage_path = raw_storage_path

        os.makedirs(os.path.join(self.raw_storage_path, self.source_name), exist_ok=True)
        self._initialize_db()

    def _initialize_db(self):
        """Creates the SQLite table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rss_items (
                    source TEXT,
                    pubDate TEXT,
                    title TEXT,
                    link TEXT,
                    PRIMARY KEY (source, pubDate, title)
                )
            ''')
            conn.commit()


    def _fetch_rss_feed(self, url):
        """Fetch the RSS feed from the given URL and return the XML payload."""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.183 Safari/537.36'
        }    
        try:
            print(f"Fetching the RSS feed from {url}...")
            response = requests.get(url, headers=headers)
            response.raise_for_status()  # Raises an error for bad status codes
            return response.text
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch RSS feed: {e}")


    def _get_item_text(self, item, sub_item_key, default_value):
        sub_item = item.find(sub_item_key)
        if sub_item is None:
            return default_value
        else:
            return sub_item.text


    def download_items(self):
        """Fetches RSS items, stores metadata in SQLite, and saves individual XML files."""
        raw_feed = self._fetch_rss_feed(self.source_uri)
        feed_root = ET.fromstring(raw_feed)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for item in feed_root.findall('./channel/item'):
                title = self._get_item_text(item, 'title', None)
                pubDate = self._get_item_text(item, 'pubDate', None)
                link = self._get_item_text(item, 'link', None)
                
                if not pubDate or not title or not link:
                    continue  # Skip incomplete entries
                
                try:
                    cursor.execute('INSERT INTO rss_items (source, pubDate, title, link) VALUES (?, ?, ?, ?)', (self.source_name, pubDate, title, link))
                    conn.commit()
                except sqlite3.IntegrityError:
                    continue  # Avoid duplicate storage
                
                # Save full RSS entry as an XML file
                filename = generate_filename(title, pubDate)
                file_path = os.path.join(self.raw_storage_path, self.source_name, filename)
                self._save_entry_as_xml(file_path, item)

    def _save_entry_as_xml(self, file_path, item):
        """Writes the RSS entry as an XML file."""
        tree = ET.ElementTree(item)
        tree.write(file_path, encoding='utf-8', xml_declaration=True)

    def archive_old_items(self):
        """Archives monthly items into a larger XML file and removes original files."""
        archive_dir = os.path.join(self.raw_storage_path, "archives", self.source_name)
        os.makedirs(archive_dir, exist_ok=True)
        
        one_month_ago = time.time() - (30 * 24 * 60 * 60)  # Approx. one month in seconds
        files_by_month = {}
        for filename in os.listdir(os.path.join(self.raw_storage_path, self.source_name)):
            if filename.endswith(".xml") and "_" in filename:
                file_path = os.path.join(self.raw_storage_path, self.source_name, filename)
                file_timestamp = os.path.getmtime(file_path)  # Get file modification time

                if file_timestamp > one_month_ago:
                    continue  # Skip files newer than one month

                month_key = filename[:7]  # YYYY_MM format
                files_by_month.setdefault(month_key, []).append(file_path)
        
        for month, files in files_by_month.items():
            archive_filename = f"archive_{month}.xml"
            archive_path = os.path.join(archive_dir, archive_filename)

            root = ET.Element("rss_archive")
            for file_path in files:
                tree = ET.parse(file_path)
                root.append(tree.getroot())

            archive_tree = ET.ElementTree(root)
            archive_tree.write(archive_path, encoding='utf-8', xml_declaration=True)

            # Delete individual files after archiving
            for file_path in files:
                os.remove(file_path)


def main(args):
    if len(args) != 2:
        print("Usage: rss_downloader source_name source_uri")
        sys.exit(1)

    downloader = RSSDownloader(
        source_name=args[0],
        source_uri=args[1],
        db_path="rss_storage.sqlite",
        raw_storage_path="rss_raw_data"
    )
    downloader.download_items()
    downloader.archive_old_items()


if __name__ == "__main__":
    main(sys.argv[1:])
