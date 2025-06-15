import ollama
import sqlite3
import sys
from pathlib import Path

from utils import generate_filename
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup


# Define Ollama model and session
MODEL_NAME = "llama3.2"


def run_analysis(title, description):
    # Start a chat session with Ollama
    client = ollama.Client()
    prompt = f"Analyze the sentiment of this news item:\n\nTitle: {title}\nDescription: {description}\n\nIs it positive, neutral, or negative? You must start your response with -1 for negative, 0 for neutral and 1 for positive, followed by an explanation"
    
    # Send the prompt to the model and retrieve the response
    response = client.generate(MODEL_NAME, prompt)
    return response["response"]


def extract_with_custom_rules(raw_html):
    soup = BeautifulSoup(raw_html, "html.parser")
    
    # Get text within <p> tags
    paragraphs = [p.get_text() for p in soup.find_all("p")]
    
    # Optionally, get 'title' attribute from the first image, if present
    image_title = ""
    image = soup.find("img", title=True)
    if image:
        image_title = image["title"]
    
    # Combine both
    combined_text = " ".join(paragraphs) + (f" {image_title}" if image_title else "")
    return combined_text if combined_text else soup.get_text()


def process_rss_item(item):
    title = item.find('title').text if item.find('title') is not None else "No title"
    description_raw = item.find('description').text if item.find('description') is not None else "No description"
    description = extract_with_custom_rules(description_raw)
    return title, description


def analyze_sentiment(raw_storage_path, source, pubDate, title):
    sentiment = 0
    explanation = ""

    article_path = Path(raw_storage_path) / source / generate_filename(title, pubDate)
    if not article_path.exists():
        raise Exception(f"{article_path} does not exist")

    item = ET.parse(article_path)
    title, description = process_rss_item(item)
    response = run_analysis(title, description)
    print(response)

    # TODO: Do not exit here
    sys.exit(1)

    return sentiment, explanation

def analyze_articles(raw_storage_path, db_path):
    # Connect to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the sentiment table if it doesn't exist
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sentiment (
            source TEXT,
            pubDate TEXT,
            title TEXT,
            sentiment INTEGER,  -- 0, 1, or 2
            explanation TEXT,
            PRIMARY KEY (source, pubDate, title)
        )
    ''')

    # Find rss_items that do NOT have a matching entry in sentiment
    cursor.execute('''
        SELECT r.source, r.pubDate, r.title
        FROM rss_items r
        LEFT JOIN sentiment s
        ON r.source = s.source AND r.pubDate = s.pubDate AND r.title = s.title
        WHERE s.source IS NULL
    ''')

    rows_to_process = cursor.fetchall()

    for source, pubDate, title in rows_to_process:
        sentiment, explanation = analyze_sentiment(raw_storage_path, source, pubDate, title)

        # TODO: Uncomment
        
        # cursor.execute('''
        #     INSERT INTO sentiment (source, pubDate, title, sentiment, explanation)
        #     VALUES (?, ?, ?, ?, ?)
        # ''', (source, pubDate, title, sentiment, explanation))
        print(f"Processed: source='{source}', pubDate='{pubDate}', title='{title}' → sentiment={sentiment}")

    # Commit changes and close the connection
    conn.commit()
    conn.close()


def main(args):
    if len(args) != 2:
        print("Usage: analyze_articles raw_storage_path db_path")
        sys.exit(1)

    raw_storage_path = Path(args[0])    
    if not raw_storage_path.exists():
        print(f"{raw_storage_path} does not exist")
        sys.exit(1)

    db_path = Path(args[1])
    if not db_path.exists():
        print(f"{db_path} does not exist")
        sys.exit(1)


    analyze_articles(raw_storage_path, db_path)


if __name__ == "__main__":
    main(sys.argv[1:])
