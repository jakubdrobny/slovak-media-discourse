import sqlite3
import urllib.parse
import re

conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()

cursor.execute(
    "SELECT url FROM scrape_queue WHERE type = 'discussion' AND url LIKE '%disqus.com%'"
)
rows = cursor.fetchall()

updates = []
for row in rows:
    old_url = row[0]

    if "&t_i=" in old_url:
        continue

    parsed = urllib.parse.urlparse(old_url)
    qs = urllib.parse.parse_qs(parsed.query)
    article_url = qs.get("t_u", [""])[0]

    article_id = None

    match_topky = re.search(r"/cl/\d+/(\d+)(?:/|$)", article_url)
    if match_topky:
        article_id = match_topky.group(1)

    elif match_sportky := re.search(r"/c/(\d+)(?:/|$)", article_url):
        article_id = match_sportky.group(1)

    if article_id:
        f_param = qs.get("f", ["topky"])[0]
        new_url = old_url.replace(
            f"?f={f_param}&t_u=", f"?f={f_param}&t_i={article_id}&t_u="
        )
        updates.append((new_url, old_url))

cursor.executemany("UPDATE scrape_queue SET url = ? WHERE url = ?", updates)
conn.commit()
conn.close()

print(f"Successfully added 't_i' to {len(updates)} Disqus URLs.")
