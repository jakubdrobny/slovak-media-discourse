import sqlite3
import pandas as pd
from transformers import AutoTokenizer
from tqdm import tqdm

DB_PATH = "db.sqlite3"
tokenizer = AutoTokenizer.from_pretrained("gerulata/slovakbert")

conn = sqlite3.connect(DB_PATH)

print("Fetching articles...")
articles_df = pd.read_sql_query("SELECT title, perex, content FROM articles", conn)
articles_df = articles_df.fillna("")

articles_df["title_perex"] = articles_df["title"] + " " + articles_df["perex"]
articles_df["title_perex_content"] = (
    articles_df["title_perex"] + " " + articles_df["content"]
)

art_tp_texts = articles_df[articles_df["title_perex"].str.strip() != ""][
    "title_perex"
].tolist()
art_tpc_texts = articles_df[articles_df["title_perex_content"].str.strip() != ""][
    "title_perex_content"
].tolist()

print("Fetching comments...")
comments_df = pd.read_sql_query(
    "SELECT content FROM comments WHERE content IS NOT NULL", conn
)
comment_texts = comments_df["content"].tolist()
conn.close()


def count_over_limit(texts, limit=512, batch_size=10000):
    over_limit = 0
    for i in tqdm(range(0, len(texts), batch_size)):
        batch = texts[i : i + batch_size]
        encodings = tokenizer(
            batch, add_special_tokens=True, truncation=False, padding=False
        )
        lengths = [len(seq) for seq in encodings["input_ids"]]
        over_limit += sum(1 for l in lengths if l > limit)
    return over_limit


print("\nTokenizing Comments...")
com_over = count_over_limit(comment_texts)
com_total = len(comment_texts)

print("\nTokenizing Articles (Title + Perex)...")
art_tp_over = count_over_limit(art_tp_texts)
art_tp_total = len(art_tp_texts)

print("\nTokenizing Articles (Title + Perex + Content)...")
art_tpc_over = count_over_limit(art_tpc_texts)
art_tpc_total = len(art_tpc_texts)

print("\n" + "=" * 60)
print(
    f"COMMENTS > 512 tokens:                 {com_over} / {com_total} ({(com_over / com_total * 100):.4f}%)"
)
print(
    f"TITLE + PEREX > 512 tokens:            {art_tp_over} / {art_tp_total} ({(art_tp_over / art_tp_total * 100):.4f}%)"
)
print(
    f"TITLE + PEREX + CONTENT > 512 tokens:  {art_tpc_over} / {art_tpc_total} ({(art_tpc_over / art_tpc_total * 100):.4f}%)"
)
print("=" * 60)
