import sqlite3
from collections import defaultdict

DB_PATH = "db.sqlite3"

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

query = """
    SELECT
        CASE
            WHEN a.url LIKE '%pravda.sk%' THEN 'pravda.sk'
            ELSE 'topky.sk'
        END AS domain,
        IFNULL(a.macro_category, 'UNKNOWN') AS macro_category,
        COUNT(DISTINCT a.id) AS total_articles,
        COUNT(c.id) AS total_comments,
        SUM(LENGTH(c.content)) AS total_chars,
        SUM(CASE WHEN c.replyToId IS NOT NULL THEN 1 ELSE 0 END) AS total_replies,
        SUM(c.upvotes) AS total_upvotes,
        SUM(c.downvotes) AS total_downvotes
    FROM articles a
    LEFT JOIN comments c ON a.id = c.articleId
    GROUP BY domain, a.macro_category
"""

cursor.execute(query)
rows = cursor.fetchall()
conn.close()

domain_stats = defaultdict(
    lambda: {
        "total_articles": 0,
        "total_comments": 0,
        "total_chars": 0,
        "total_replies": 0,
        "total_upvotes": 0,
        "total_downvotes": 0,
    }
)

pair_stats = {}

for row in rows:
    domain = row["domain"]
    macro = row["macro_category"]

    domain_stats[domain]["total_articles"] += row["total_articles"]
    domain_stats[domain]["total_comments"] += row["total_comments"]
    domain_stats[domain]["total_chars"] += row["total_chars"] or 0
    domain_stats[domain]["total_replies"] += row["total_replies"] or 0
    domain_stats[domain]["total_upvotes"] += row["total_upvotes"] or 0
    domain_stats[domain]["total_downvotes"] += row["total_downvotes"] or 0

    pair_stats[(domain, macro)] = {
        "total_articles": row["total_articles"],
        "total_comments": row["total_comments"],
        "total_chars": row["total_chars"] or 0,
        "total_replies": row["total_replies"] or 0,
        "total_upvotes": row["total_upvotes"] or 0,
        "total_downvotes": row["total_downvotes"] or 0,
    }

print("\n=== PER-DOMAIN COMMENT STATISTICS ===\n")

for domain, s in sorted(domain_stats.items()):
    comments = s["total_comments"]
    articles = s["total_articles"]

    density = comments / articles if articles else 0
    avg_len = s["total_chars"] / comments if comments else 0
    reply_ratio = (s["total_replies"] / comments) * 100 if comments else 0
    avg_up = s["total_upvotes"] / comments if comments else 0
    avg_down = s["total_downvotes"] / comments if comments else 0

    print(f"Domain: {domain}")
    print(f"Total comments: {comments}")
    print(f"Density (comments per article): {density:.2f}")
    print(f"Mean character length: {avg_len:.2f}")
    print(f"Reply ratio: {reply_ratio:.2f}%")
    print(f"Mean upvotes per comment: {avg_up:.2f}")
    print(f"Mean downvotes per comment: {avg_down:.2f}")
    print("-" * 50)


print("\n=== PER (DOMAIN, MACRO_CATEGORY) COMMENT STATISTICS ===\n")

for (domain, macro), s in sorted(pair_stats.items()):
    comments = s["total_comments"]
    articles = s["total_articles"]

    density = comments / articles if articles else 0
    avg_len = s["total_chars"] / comments if comments else 0
    reply_ratio = (s["total_replies"] / comments) * 100 if comments else 0
    avg_up = s["total_upvotes"] / comments if comments else 0
    avg_down = s["total_downvotes"] / comments if comments else 0

    print(f"Domain: {domain}")
    print(f"Macro category: {macro}")
    print(f"Total comments: {comments}")
    print(f"Density (comments per article): {density:.2f}")
    print(f"Mean character length: {avg_len:.2f}")
    print(f"Reply ratio: {reply_ratio:.2f}%")
    print(f"Mean upvotes per comment: {avg_up:.2f}")
    print(f"Mean downvotes per comment: {avg_down:.2f}")
    print("-" * 50)
