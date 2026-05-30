import sqlite3
import re
from collections import defaultdict

DB_PATH = "db.sqlite3"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

cursor = conn.cursor()

cursor.execute("""
    SELECT
        CASE
            WHEN url LIKE '%pravda.sk%' THEN 'pravda.sk'
            ELSE 'topky.sk'
        END AS domain,
        macro_category,
        content
    FROM articles
    WHERE content IS NOT NULL
""")

domain_stats = defaultdict(
    lambda: {
        "articles": 0,
        "total_words": 0,
        "total_chars": 0,
        "total_sentences": 0,
    }
)

pair_stats = defaultdict(
    lambda: {
        "articles": 0,
        "total_words": 0,
        "total_chars": 0,
        "total_sentences": 0,
    }
)

for row in cursor:
    domain = row["domain"]
    macro_category = row["macro_category"] or "UNKNOWN"
    content = row["content"]

    word_count = len(content.split())
    char_count = len(content)

    sentences = re.split(r"[.!?]+", content)
    sentences = [s.strip() for s in sentences if s.strip()]
    sentence_count = len(sentences)

    domain_stats[domain]["articles"] += 1
    domain_stats[domain]["total_words"] += word_count
    domain_stats[domain]["total_chars"] += char_count
    domain_stats[domain]["total_sentences"] += sentence_count

    key = (domain, macro_category)

    pair_stats[key]["articles"] += 1
    pair_stats[key]["total_words"] += word_count
    pair_stats[key]["total_chars"] += char_count
    pair_stats[key]["total_sentences"] += sentence_count

conn.close()

print("\n=== PER-DOMAIN STATISTICS ===\n")

for domain, s in sorted(domain_stats.items()):

    article_count = s["articles"]

    mean_word_count = s["total_words"] / article_count if article_count else 0

    mean_character_count = s["total_chars"] / article_count if article_count else 0

    mean_sentence_count = s["total_sentences"] / article_count if article_count else 0

    print(f"Domain: {domain}")
    print(f"Total articles: {article_count}")
    print(f"Mean word count per article: {mean_word_count:.2f}")
    print(f"Mean character count per article: {mean_character_count:.2f}")
    print(f"Mean sentence count per article: {mean_sentence_count:.2f}")
    print("-" * 50)

print("\n=== PER (DOMAIN, MACRO_CATEGORY) STATISTICS ===\n")

for (domain, macro_category), s in sorted(pair_stats.items()):

    article_count = s["articles"]

    mean_word_count = s["total_words"] / article_count if article_count else 0

    mean_character_count = s["total_chars"] / article_count if article_count else 0

    mean_sentence_count = s["total_sentences"] / article_count if article_count else 0

    print(f"Domain: {domain}")
    print(f"Macro category: {macro_category}")
    print(f"Total articles: {article_count}")
    print(f"Mean word count per article: {mean_word_count:.2f}")
    print(f"Mean character count per article: {mean_character_count:.2f}")
    print(f"Mean sentence count per article: {mean_sentence_count:.2f}")
    print("-" * 50)
