import sqlite3
import unicodedata


def normalize_text(text):
    if not text:
        return text
    return (
        unicodedata.normalize("NFKD", text)
        .encode("ASCII", "ignore")
        .decode("utf-8")
        .lower()
    )


conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()

cursor.execute("SELECT DISTINCT category FROM articles WHERE category IS NOT NULL")
rows = cursor.fetchall()

updates = []
for row in rows:
    original_category = row[0]
    normalized_category = normalize_text(original_category)

    if original_category != normalized_category:
        updates.append((normalized_category, original_category))

print(f"Found {len(updates)} distinct categories to normalize...")

cursor.executemany("UPDATE articles SET category = ? WHERE category = ?", updates)
conn.commit()
conn.close()

print("Normalization complete!")
