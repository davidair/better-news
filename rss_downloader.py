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

import os
import hashlib
import sqlite3
import feedparser
import datetime
import xml.etree.ElementTree as ET

class RSSDownloader:
    def __init__(self, source_name, source_uri, db_path, raw_storage_path):
        self.source_name = source_name
        self.source_uri = source_uri
        self.db_path = db_path
        self.raw_storage_path = raw_storage_path

        os.makedirs(self.raw_storage_path, exist_ok=True)
        self._initialize_db()

    def _initialize_db(self):
        """Creates the SQLite table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS rss_items (
                    pubDate TEXT,
                    title TEXT,
                    link TEXT,
                    PRIMARY KEY (pubDate, title)
                )
            ''')
            conn.commit()

    def _generate_filename(self, title, pubDate):
        """Creates an MD5 hash-based filename using title and sanitized timestamp."""
        sanitized_timestamp = datetime.datetime.strptime(pubDate, "%a, %d %b %Y %H:%M:%S %Z").strftime("%Y_%m_%d_%H_%M_%S")
        hash_value = hashlib.md5(title.encode()).hexdigest()
        return f"{sanitized_timestamp}_{hash_value}.xml"

    def download_items(self):
        """Fetches RSS items, stores metadata in SQLite, and saves individual XML files."""
        feed = feedparser.parse(self.source_uri)
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            for entry in feed.entries:
                pubDate = entry.get('published', entry.get('updated', ''))
                title = entry.get('title', '').strip()
                link = entry.get('link', '').strip()
                
                if not pubDate or not title or not link:
                    continue  # Skip incomplete entries
                
                try:
                    cursor.execute('INSERT INTO rss_items (pubDate, title, link) VALUES (?, ?, ?)', (pubDate, title, link))
                    conn.commit()
                except sqlite3.IntegrityError:
                    continue  # Avoid duplicate storage
                
                # Save full RSS entry as an XML file
                filename = self._generate_filename(title, pubDate)
                file_path = os.path.join(self.raw_storage_path, filename)
                self._save_entry_as_xml(file_path, entry)

    def _save_entry_as_xml(self, file_path, entry):
        """Writes the RSS entry as an XML file."""
        root = ET.Element("rss_item")
        for key, value in entry.items():
            sub_element = ET.SubElement(root, key)
            sub_element.text = value if isinstance(value, str) else str(value)

        tree = ET.ElementTree(root)
        tree.write(file_path, encoding='utf-8', xml_declaration=True)

    def archive_old_items(self):
        """Archives monthly items into a larger XML file and removes original files."""
        archive_dir = os.path.join(self.raw_storage_path, "archives")
        os.makedirs(archive_dir, exist_ok=True)
        
        files_by_month = {}
        for filename in os.listdir(self.raw_storage_path):
            if filename.endswith(".xml") and "_" in filename:
                month_key = filename[:7]  # YYYY_MM format
                files_by_month.setdefault(month_key, []).append(os.path.join(self.raw_storage_path, filename))
        
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

# Example usage
if __name__ == "__main__":
    downloader = RSSDownloader(
        source_name="ExampleNews",
        source_uri="https://example.com/rss.xml",
        db_path="rss_storage.sqlite",
        raw_storage_path="rss_raw_data"
    )
    downloader.download_items()
    downloader.archive_old_items()
