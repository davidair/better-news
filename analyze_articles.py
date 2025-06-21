import re
import sqlite3
import sys

from pathlib import Path
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from ollama_wrapper import OllamaWrapper

from utils import generate_filename


# Define Ollama model and session
MODEL_NAME = "llama3.2"


def parse_sentiment(text):
    # Match an integer at the beginning followed by a space or newline
    match = re.match(r'(-?\d+)[ |\n]+(.+)', text.strip())

    if not match:
        raise ValueError(
            f"Invalid format: Expected an integer followed by a space or newline and some text. Text: {text}")

    sentiment = int(match.group(1))
    explanation = match.group(2).strip()

    # Validate sentiment value
    if sentiment not in {0, -1, 1}:
        raise ValueError("Invalid sentiment value: Must be 0, -1, or 1.")

    # Check if explanation is empty
    if not explanation:
        raise ValueError("Invalid input: Explanation cannot be empty.")

    return sentiment, explanation


def run_analysis(ollama_client, title, description):
    if not description:
        raise ValueError("Description is required for sentiment analysis")

    # Start a chat session with Ollama
    prompt = (f"Analyze the sentiment of this news item:\n\nTitle: {title}\nDescription: {description}\n\n"
              "Is it positive, neutral, or negative? "
              "You must start your response with -1 for negative, 0 for neutral and 1 for positive, followed by an explanation. "
              "Note that the analysis is done for the purpose of determining if the news article is likely "
              "to cause distress to the reader so it's important to annotate anything possibly causing distress as negative. Make sure response always starts with -1, 0 or 1 before the explanation.")


    # Send the prompt to the model and retrieve the response
    response = ollama_client.generate(prompt, options={"temperature": 0})
    sentiment, explanation = parse_sentiment(response)

    return sentiment, explanation


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
    combined_text = " ".join(paragraphs) + \
        (f" {image_title}" if image_title else "")
    return combined_text if combined_text else soup.get_text()


def process_rss_item(item):
    title = item.find('title').text if item.find(
        'title') is not None else "No title"
    description_raw = item.find('description').text if item.find(
        'description') is not None else None
    description = None
    if description_raw:
        description = extract_with_custom_rules(description_raw)

    return title, description


def analyze_sentiment(ollama_client, raw_storage_path, source, pubDate, title):
    article_path = Path(raw_storage_path) / source / \
        generate_filename(title, pubDate)
    if not article_path.exists():
        raise Exception(f"{article_path} does not exist")

    item = ET.parse(article_path)
    title, description = process_rss_item(item)
    sentiment, explanation = run_analysis(ollama_client, title, description)

    return sentiment, explanation


def analyze_articles(ollama_client, raw_storage_path, db_path):
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
        try:
            sentiment, explanation = analyze_sentiment(
                ollama_client, raw_storage_path, source, pubDate, title)

            cursor.execute('''
                INSERT INTO sentiment (source, pubDate, title, sentiment, explanation)
                VALUES (?, ?, ?, ?, ?)
            ''', (source, pubDate, title, sentiment, explanation))
            print(
                f"Processed: source='{source}', pubDate='{pubDate}', title='{title}' → sentiment={sentiment}")
        except Exception as e:
            print(f'Error processing {source}, {pubDate}, {title}: {e}')

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

    ollama_client = OllamaWrapper(MODEL_NAME)

    try:
        ollama_client.start_ollama()
        analyze_articles(ollama_client, raw_storage_path, db_path)
    finally:
        ollama_client.stop_ollama()


if __name__ == "__main__":
    main(sys.argv[1:])
