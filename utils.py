import dateparser
import hashlib
import sys

def generate_filename(title, pubDate):
    """Creates an MD5 hash-based filename using title and sanitized timestamp."""
    sanitized_timestamp = dateparser.parse(pubDate).strftime("%Y_%m_%d_%H_%M_%S")
    hash_value = hashlib.md5(title.encode()).hexdigest()
    return f"{sanitized_timestamp}_{hash_value}.xml"

def main(_):
    print(generate_filename("Man bites dog", "Sun, 15 Jun 2025 16:52:25 +0000"))

if __name__ == "__main__":
    main(sys.argv[1:])
