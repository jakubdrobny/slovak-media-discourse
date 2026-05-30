import asyncio
import json
import re
import aiohttp
import sqlite3
import random
import pytz
import urllib.parse
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urlparse

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/145.0",
]


def get_base_domain(url: str) -> str:
    netloc = urlparse(url).netloc
    parts = netloc.split(".")
    if len(parts) >= 2:
        return f"{parts[-2]}.{parts[-1]}"
    return netloc


def to_unix_timestamp(datetime_str: str) -> int:
    if not datetime_str:
        return 0
    try:
        local_tz = pytz.timezone("Europe/Bratislava")
        dt = datetime.strptime(datetime_str.strip(), "%d.%m.%Y %H:%M")
        return int(local_tz.localize(dt).timestamp())
    except Exception as e:
        print(f"Time parsing error for '{datetime_str}': {e}")
        return 0


def parse_topky_datetime(date_str: str) -> int:
    now = datetime.now()
    date_str = date_str.lower().strip()
    dt_obj = now

    try:
        if "pred niekoľkými sekundami" in date_str:
            pass
        elif "pred minútou" in date_str:
            dt_obj = now - timedelta(minutes=1)
        elif match_min := re.search(r"pred (\d+) minútami", date_str):
            dt_obj = now - timedelta(minutes=int(match_min.group(1)))
        elif "pred hodinou" in date_str:
            dt_obj = now - timedelta(hours=1)
        elif match_hod := re.search(r"pred (\d+) hodinami", date_str):
            dt_obj = now - timedelta(hours=int(match_hod.group(1)))
        elif match_dnes := re.search(r"dnes o (\d{1,2}):(\d{2})", date_str):
            dt_obj = now.replace(
                hour=int(match_dnes.group(1)), minute=int(match_dnes.group(2)), second=0
            )
        elif match_vcera := re.search(r"včera o (\d{2}):(\d{2})", date_str):
            yesterday = now - timedelta(days=1)
            dt_obj = yesterday.replace(
                hour=int(match_vcera.group(1)),
                minute=int(match_vcera.group(2)),
                second=0,
            )
        elif match_abs := re.search(
            r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{2}):(\d{2})", date_str
        ):
            day, month, year, hour, minute = match_abs.groups()
            dt_obj = datetime(int(year), int(month), int(day), int(hour), int(minute))
    except Exception as e:
        print(f"Topky date parse error for '{date_str}': {e}")

    local_tz = pytz.timezone("Europe/Bratislava")
    return int(local_tz.localize(dt_obj).timestamp())


def parse_sportky_datetime(date_iso_str: str) -> int:
    if not date_iso_str:
        return 0
    try:
        dt = datetime.fromisoformat(date_iso_str)
        if dt.tzinfo is not None:
            return int(dt.timestamp())

        local_tz = pytz.timezone("Europe/Bratislava")
        return int(local_tz.localize(dt).timestamp())
    except Exception as e:
        print(f"Time parsing error for '{date_iso_str}': {e}")
        return 0


# spravy, sportweb, auto, uzitocna, koktail, zdravie, zena, komercne spravy, cestovanie, ekonomika, kultura, nazory, zahrada, vat, zurnal
def parse_pravda(soup: BeautifulSoup, url: str) -> dict:
    result = {
        "title": "",
        "perex": "",
        "content": "",
        "category": "",
        "timestamp": 0,
        "discussion_url": "",
    }

    headline = soup.find("h1", itemprop="headline")
    if headline:
        result["title"] = headline.get_text(strip=True)

    description = soup.find("p", itemprop="description")
    if description:
        result["perex"] = description.get_text(strip=True)

    small_tag = soup.select_one("span.article-detail-submenu-autor-name small")
    if small_tag:
        raw = small_tag.get_text(strip=True)
        published = raw.split(",")[0]
        result["timestamp"] = to_unix_timestamp(published.strip())

    content_body = soup.find("div", itemprop="articleBody")
    if content_body:
        paragraphs = content_body.find_all("p", recursive=False)
        result["content"] = " ".join(
            [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
        )

    parsed_url = urlparse(url)
    path = parsed_url.path

    if "/clanok/" in path:
        parts = path.split("/clanok/")

        category_raw = parts[0].strip("/")
        result["category"] = category_raw.replace("/", " > ")

        article_slug = parts[-1].strip("/")
        if article_slug:
            result["discussion_url"] = (
                f"https://debata.pravda.sk/debata/{article_slug}/"
            )

    return result


def parse_topky(soup: BeautifulSoup, url: str) -> dict:
    result = {}

    title_el = soup.select_one("div.article-top-info > h1")
    if title_el:
        result["title"] = title_el.get_text(strip=True)

    perex_el = soup.select_one("div.article-perex > p")
    if perex_el:
        result["perex"] = perex_el.get_text(strip=True)

    content = []
    for p_el in soup.select("#article_body > p"):
        p_text = p_el.get_text(strip=True)
        if p_text:
            content.append(p_text)

    result["content"] = " ".join(content)

    bredcrumbs_el = soup.select_one("ul.article-bredcrumbs")
    if bredcrumbs_el:
        categories = []
        for a_el in bredcrumbs_el.select("li > a"):
            cat_text = a_el.get_text(strip=True)
            if cat_text:
                categories.append(cat_text)

        if categories and categories[0] == "Topky":
            categories = categories[1:]

        result["category"] = " > ".join(categories)

    timestamp_el = soup.select_one("time.article-time")
    if timestamp_el:
        timestamp_str = timestamp_el.get_text(strip=True)
        if timestamp_str:
            result["timestamp"] = parse_topky_datetime(timestamp_str)

    encoded_url = urllib.parse.quote(url, safe="")
    match = re.search(r"/cl/\d+/(\d+)(?:/|$)", url)
    t_i_param = f"&t_i={match.group(1)}" if match else ""
    result["discussion_url"] = (
        f"https://disqus.com/embed/comments/?f=topky{t_i_param}&t_u={encoded_url}#version=edbad5dd62b4c9201796cb42e4b24cf7"
    )

    return result


def parse_sportky(soup: BeautifulSoup, url: str) -> dict:
    result = {}

    article_el = soup.select_one("div.main-content > div > article")
    if article_el:
        title_el = article_el.select_one("h1")
        if title_el:
            result["title"] = title_el.get_text(strip=True)

        perex_el = soup.select_one("p.perex")
        if perex_el:
            result["perex"] = perex_el.get_text(strip=True)

        content = []
        for p_el in soup.select("p:not(.perex)"):
            p_text = p_el.get_text(strip=True)
            if p_text:
                content.append(p_text)

        result["content"] = " ".join(content)

    bredcrumbs_el = soup.select_one("div.breadcrumbs > ul")
    if bredcrumbs_el:
        categories = []
        for a_el in bredcrumbs_el.select("li > a"):
            cat_text = a_el.get_text(strip=True)
            if cat_text:
                categories.append(cat_text)

        result["category"] = " > ".join(categories)

    result["timestamp"] = 0

    meta_date = (
        soup.find("meta", attrs={"property": "article:published_time"})
        or soup.find("meta", attrs={"name": "article:published_time"})
        or soup.find("meta", attrs={"property": "article:modified_time"})
        or soup.find("meta", attrs={"name": "article:modified_time"})
    )

    if meta_date:
        content_val = meta_date.get("content")
        if content_val:
            result["timestamp"] = parse_sportky_datetime(str(content_val))

    # fallback timestamp parse from script block
    if result["timestamp"] == 0:
        for script in soup.find_all("script", type="application/ld+json"):
            raw_text = script.get_text(strip=True)
            if not raw_text:
                continue

            try:
                data = json.loads(raw_text, strict=False)
                if isinstance(data, list):
                    for item in data:
                        if item.get("@type", "") in [
                            "NewsArticle",
                            "Article",
                            "SportsArticle",
                        ]:
                            result["timestamp"] = parse_sportky_datetime(
                                item.get("datePublished", "")
                            )
                elif isinstance(data, dict):
                    if data.get("@type", "") in [
                        "NewsArticle",
                        "Article",
                        "SportsArticle",
                    ]:
                        result["timestamp"] = parse_sportky_datetime(
                            data.get("datePublished", "")
                        )
            except json.JSONDecodeError:
                # if json is broken, try to parse raw text
                match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', raw_text)
                if match:
                    result["timestamp"] = parse_sportky_datetime(match.group(1))

            if result["timestamp"] > 0:
                break

    encoded_url = urllib.parse.quote(url, safe="")
    match = re.search(r"/c/(\d+)(?:/|$)", url)
    t_i_param = f"&t_i={match.group(1)}" if match else ""
    result["discussion_url"] = (
        f"https://disqus.com/embed/comments/?f=sportky{t_i_param}&t_u={encoded_url}#version=edbad5dd62b4c9201796cb42e4b24cf7"
    )

    return result


ARTICLE_PARSERS = {
    "pravda.sk": parse_pravda,
    "topky.sk": parse_topky,
    "zoznam.sk": parse_sportky,
}

SKIPPED = [
    "ahojmama.pravda.sk",
    "vino.pravda.sk",
    "noviny.pravda.sk",
    "varecha.pravda.sk",
]


def to_skip(domain):
    return domain in SKIPPED


async def fetch_and_parse(
    url: str, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore
):
    async with semaphore:
        await asyncio.sleep(random.uniform(0.1, 1.0))
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "sk,cs;q=0.89,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(15)
                ) as response:
                    if response.status == 429:
                        await asyncio.sleep(2**attempt)
                        continue

                    response.raise_for_status()
                    html = await response.text()
                    soup = BeautifulSoup(html, "lxml")

                    full_domain = urlparse(url).netloc
                    if to_skip(full_domain):
                        return url, {"status": "failed"}

                    base_domain = get_base_domain(url)
                    parser_func = ARTICLE_PARSERS.get(base_domain)

                    if not parser_func:
                        print(f"No parser found for domain: {base_domain}. URL: {url}")
                        return url, {"status": "failed"}

                    extracted = parser_func(soup, url)

                    article_data = {
                        "url": url,
                        "title": extracted.get("title", ""),
                        "perex": extracted.get("perex", ""),
                        "content": extracted.get("content", ""),
                        "category": extracted.get("category", ""),
                        "timestamp": extracted.get("timestamp", 0),
                    }

                    return url, {
                        "status": "done",
                        "article_data": article_data,
                        "discussion_url": extracted.get("discussion_url", ""),
                    }

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == MAX_RETRIES - 1:
                    print(f"Failed {url}: {e}")
                    return url, {"status": "failed"}
                await asyncio.sleep(2**attempt)

    return url, {"status": "failed"}


async def process_batch(urls: list[str], max_concurrent: int = 50):
    semaphore = asyncio.Semaphore(max_concurrent)
    connector = aiohttp.TCPConnector(limit=max_concurrent)
    results = []
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch_and_parse(url, session, semaphore) for url in urls]
        for future in asyncio.as_completed(tasks):
            url, data = await future
            results.append((url, data))
    return results


def main_loop(db_filename: str):
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()
    BATCH_SIZE = 50

    while True:
        cursor.execute(
            "SELECT url FROM scrape_queue WHERE status = 'pending' AND type = 'article' LIMIT ?",
            (BATCH_SIZE,),
        )
        rows = cursor.fetchall()

        if not rows:
            print("No pending articles left.")
            break

        urls = [row[0] for row in rows]
        cursor.executemany(
            "UPDATE scrape_queue SET status = 'processing' WHERE url = ?",
            [(u,) for u in urls],
        )
        conn.commit()

        print(f"Fetching batch of {len(urls)} articles...")
        batch_results = asyncio.run(process_batch(urls))

        queue_updates = []
        article_inserts = []
        new_discussions = []

        for url, result in batch_results:
            queue_updates.append((result["status"], url))

            if result["status"] == "done":
                data = result["article_data"]
                if data["title"] or data["content"]:
                    article_inserts.append(
                        (
                            data["url"],
                            data["title"],
                            data["perex"],
                            data["content"],
                            data["category"],
                            data["timestamp"],
                        )
                    )

                if result.get("discussion_url"):
                    new_discussions.append((result["discussion_url"], "discussion"))

        cursor.executemany(
            "UPDATE scrape_queue SET status = ? WHERE url = ?", queue_updates
        )

        cursor.executemany(
            """
            INSERT INTO articles (url, title, perex, content, category, timestamp) 
            VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(url) DO UPDATE SET 
                title = excluded.title,
                perex = excluded.perex,
                content = excluded.content,
                category = excluded.category,
                timestamp = excluded.timestamp
        """,
            article_inserts,
        )

        cursor.executemany(
            """
            INSERT INTO scrape_queue (url, type) VALUES (?, ?) ON CONFLICT DO NOTHING
        """,
            new_discussions,
        )

        conn.commit()
        print(
            f"Batch complete. Inserted {len(article_inserts)} articles. Queued {len(new_discussions)} discussions."
        )


if __name__ == "__main__":
    main_loop("db.sqlite3")
