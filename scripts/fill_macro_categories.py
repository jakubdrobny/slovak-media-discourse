import sqlite3


def get_macro_category(category_str):
    if not category_str:
        return "other"

    cat = category_str.lower()

    sports_keywords = [
        "sport",
        "futbal",
        "hokej",
        "tenis",
        "cyklistika",
        "atletika",
        "zoh",
        "ms ",
        "ms-",
        "nhl",
        "nba",
        "liga",
        "wimbledon",
        "lyzovani",
        "biatlon",
        "basketbal",
        "box",
        "florbal",
        "futsal",
        "gymnastika",
        "hadzana",
        "olympij",
        "volejbal",
        "motorizmus",
        "formula",
        "motogp",
        "rely",
        "ofsajd",
        "prenos",
        "sampion",
        "me v",
    ]
    if any(k in cat for k in sports_keywords):
        return "sports"

    tabloid_keywords = [
        "prominenti",
        "kauzy",
        "reality",
        "influencer",
        "soubiznis",
        "koberc",
        "modelk",
        "muz-dna",
        "modn",
        "sex",
    ]
    if any(k in cat for k in tabloid_keywords):
        return "tabloid"

    hobbies_keywords = [
        "krasa",
        "moda",
        "zena",
        "zdravie",
        "zahrada",
        "magazin",
        "ludia",
        "jedlo",
        "cestov",
        "koktail",
        "hudba",
        "film",
        "televizia",
        "kultura",
        "kniha",
        "divadlo",
        "umenie",
        "festival",
        "obrazovk",
        "more",
        "hory",
        "exotika",
        "krajina",
        "byvanie",
        "dom-a-byt",
        "balkon",
        "relax",
        "vyziva",
        "dusa",
        "zivot",
        "poradna",
        "potraviny",
        "auto",
        "tech",
        "veda",
        "ekologia",
        "startupy",
        "spotrebitel",
        "doprav",
        "vesmir",
        "zem",
        "ako-vybavit",
    ]
    if any(k in cat for k in hobbies_keywords):
        return "hobbies_soft"

    hard_news_keywords = [
        "domac",
        "svet",
        "zahranicn",
        "regiony",
        "politik",
        "komentar",
        "glos",
        "esej",
        "spolocnost",
        "konflikt",
        "spravy",
        "analyz",
        "postreh",
        "dnes-pise",
        "rozhovor",
        "reportaz",
        "instituci",
        "mesta",
        "charita",
        "csr",
        "novinky",
        "ekonomika",
        "hypoteky",
        "peniaz",
        "energeti",
        "priemysel",
        "firmy",
        "trhy",
        "obchod",
        "podnikan",
        "zivnost",
        "inovaci",
        "kariera",
        "praca",
        "vzdelavanie",
        "dochod",
        "senior",
    ]
    if any(k in cat for k in hard_news_keywords):
        return "hard_news"

    return "other"


conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()

cursor.execute("SELECT DISTINCT category FROM articles WHERE category IS NOT NULL")
rows = cursor.fetchall()

updates = []
for row in rows:
    original_cat = row[0]
    macro_cat = get_macro_category(original_cat)
    updates.append((macro_cat, original_cat))

cursor.executemany("UPDATE articles SET macro_category = ? WHERE category = ?", updates)
conn.commit()

print(f"Mapped {len(updates)} distinct micro-categories into behavioral buckets.")

cursor.execute(
    "SELECT macro_category, COUNT(id) FROM articles GROUP BY macro_category ORDER BY COUNT(id) DESC"
)
print("\nNew Behavioral Distribution:")
for row in cursor.fetchall():
    print(f"{row[0]}: {row[1]} articles")

conn.close()
