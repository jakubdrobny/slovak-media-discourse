import asyncio
import re
import aiohttp
import sqlite3
import random
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/145.0",
]

TARGET_START_DATE = "2025-05-09"


def get_base_domain(url: str) -> str:
    netloc = urlparse(url).netloc
    parts = netloc.split(".")
    if len(parts) >= 2:
        return f"{parts[-2]}.{parts[-1]}"
    return netloc


def parse_topky_datetime(date_str: str) -> datetime:
    now = datetime.now()
    date_str = date_str.lower().strip()

    try:
        if "pred niekoľkými sekundami" in date_str:
            return now

        if "pred minútou" in date_str:
            return now - timedelta(minutes=1)

        match_min = re.search(r"pred (\d+) minútami", date_str)
        if match_min:
            return now - timedelta(minutes=int(match_min.group(1)))

        if "pred hodinou" in date_str:
            return now - timedelta(hours=1)

        match_hod = re.search(r"pred (\d+) hodinami", date_str)
        if match_hod:
            return now - timedelta(hours=int(match_hod.group(1)))

        match_dnes = re.search(r"dnes o (\d{1,2}):(\d{2})", date_str)
        if match_dnes:
            return now.replace(
                hour=int(match_dnes.group(1)), minute=int(match_dnes.group(2)), second=0
            )

        match_vcera = re.search(r"včera o (\d{2}):(\d{2})", date_str)
        if match_vcera:
            yesterday = now - timedelta(days=1)
            return yesterday.replace(
                hour=int(match_vcera.group(1)),
                minute=int(match_vcera.group(2)),
                second=0,
            )

        match_abs = re.search(
            r"(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(\d{2}):(\d{2})", date_str
        )
        if match_abs:
            day, month, year, hour, minute = match_abs.groups()
            return datetime(int(year), int(month), int(day), int(hour), int(minute))

    except Exception as e:
        print(f"Date parse error for '{date_str}': {e}")

    return now


def seed_dates_pravda(db_filename: str, start_date: str, end_date: str):
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    urls = []
    current = start
    while current <= end:
        date_str = current.strftime("%Y-%m-%d")
        url = f"https://www.pravda.sk/chronologia-dna/?datum={date_str}"
        urls.append((url, "article_list"))
        current += timedelta(days=1)

    cursor.executemany(
        "INSERT INTO scrape_queue (url, type) VALUES (?, ?) ON CONFLICT DO NOTHING",
        urls,
    )
    conn.commit()
    conn.close()
    print(f"Seeded {len(urls)} Pravda dates into the queue.")


def seed_categories_topky(db_filename: str):
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()

    # only page 1
    categories = [
        "https://www.topky.sk/se/10/1/Domace",
        "https://www.topky.sk/se/11/1/Zahranicne",
        "https://www.topky.sk/se/15/1/Prominenti",
        "https://www.topky.sk/se/1005133/1/Ekonomika",
        "https://www.topky.sk/se/100157/1/Topky-tv",
    ]

    urls = [(url, "article_list") for url in categories]
    cursor.executemany(
        "INSERT INTO scrape_queue (url, type) VALUES (?, ?) ON CONFLICT DO NOTHING",
        urls,
    )
    conn.commit()
    conn.close()
    print(f"Seeded {len(urls)} Topky categories into the queue.")


def seed_sportky(db_filename: str):
    conn = sqlite3.connect(db_filename)
    cursor = conn.cursor()

    urls = [
        ("https://sportky.zoznam.sk/ajax/get_article_list/0?limit=500", "article_list")
    ]

    cursor.executemany(
        "INSERT INTO scrape_queue (url, type) VALUES (?, ?) ON CONFLICT DO NOTHING",
        urls,
    )
    conn.commit()
    conn.close()
    print("Seeded Sportky into the queue.")


def extract_urls_pravda(soup: BeautifulSoup, url: str, start_date_str: str):
    article_urls = []

    main_div = soup.find(id="box-rubrika-clanky-listing")
    if main_div:
        for child in main_div.find_all(recursive=False):
            a_tag = child.find("a")
            if a_tag and a_tag.get("href"):
                article_url = a_tag["href"]
                if "pravda.sk" in article_url:
                    article_urls.append(article_url)

    return {"article_urls": article_urls, "next_list_url": []}


def extract_urls_topky(soup: BeautifulSoup, url: str, start_date_str: str):
    article_urls = []
    next_list_urls = []
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    oldest_timestamp = datetime.now()
    last_date = None
    found_articles = False

    section_pages_el = soup.find(id="section-pages")
    if section_pages_el:
        article_list_el = section_pages_el.select_one("div.article-list > ul")
        if article_list_el:
            for article_el in article_list_el.select("li"):
                time_el = article_el.select_one("div > div")
                if time_el:
                    timestamp_str = time_el.get_text(strip=True)
                    # do something with the timestamp to parse it
                    article_date = parse_topky_datetime(timestamp_str)

                    # for some reason, article 24-48h before all get format of
                    # vcera o ..., which obviously does not work, when 48h could be
                    # today - 2 days in almost all cases
                    if last_date is not None and article_date > last_date:
                        article_date -= timedelta(days=1)
                    last_date = article_date

                    if article_date < oldest_timestamp:
                        oldest_timestamp = article_date

                    if article_date >= start_date:
                        href_el = article_el.select_one("a")
                        if href_el:
                            href = href_el.get("href")
                            if href:
                                article_urls.append(urljoin(url, str(href)))
                                found_articles = True

    if found_articles and oldest_timestamp >= start_date:
        match = re.search(r"(/se/\d+/)(\d+)(/[^/]+)", url)
        if match:
            current_page = int(match.group(2))
            for i in range(1, 11):
                next_page = current_page + i
                next_list_urls.append(
                    f"https://www.topky.sk{match.group(1)}{next_page}{match.group(3)}"
                )

    return {"article_urls": article_urls, "next_list_urls": next_list_urls}


def extract_urls_sportky(soup: BeautifulSoup, url: str, start_date_str: str):
    article_urls = []
    next_list_urls = []
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    oldest_timestamp = datetime.now()

    for col_el in soup.select("div.col"):
        time_el = col_el.find("time")
        if time_el:
            date_str = time_el.get_text(strip=True)
            article_date = parse_topky_datetime(date_str)

            if article_date < oldest_timestamp:
                oldest_timestamp = article_date

            if article_date >= start_date:
                a_tag = col_el.find("a", class_="article-item-title")
                if a_tag:
                    href = a_tag.get("href")
                    if href:
                        article_urls.append(urljoin(url, str(href)))

    if oldest_timestamp >= start_date:
        match = re.search(r"(/ajax/get_article_list/)(\d+)(\?limit=\d+)", url)
        if match:
            current_page = int(match.group(2))
            next_page = current_page + 1
            next_list_urls.append(
                f"https://sportky.zoznam.sk{match.group(1)}{next_page}{match.group(3)}"
            )

    return {"article_urls": article_urls, "next_list_urls": next_list_urls}


ARTICLE_URLS_PARSERS = {
    "pravda.sk": extract_urls_pravda,
    "topky.sk": extract_urls_topky,
    "zoznam.sk": extract_urls_sportky,
}


async def fetch_and_parse(
    url: str, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore
):
    async with semaphore:
        # idea 1 to avoid rate limiting: jitter
        await asyncio.sleep(random.uniform(0.1, 1.5))

        # idea 2 to avoid rate limiting: mimic browser (header spoofing)
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "sk,cs;q=0.89,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "DNT": "1",
        }

        # idea 3 to avoid rate limiting: exponential backoff
        MAX_RETRIES = 3
        for attempt in range(MAX_RETRIES):
            try:
                async with session.get(
                    url, headers=headers, timeout=aiohttp.ClientTimeout(15)
                ) as response:
                    if response.status == 429:
                        print(f"429 Too Many Requests for {url}. Backing off...")
                        await asyncio.sleep(2**attempt)
                        continue

                    response.raise_for_status()
                    html = await response.text()

                    soup = BeautifulSoup(html, "lxml")
                    domain = get_base_domain(url)
                    parser_func = ARTICLE_URLS_PARSERS.get(domain)

                    if not parser_func:
                        print(f"No parser found for domain: {domain}")
                        return url, {"status": "failed"}

                    data = parser_func(soup, url, TARGET_START_DATE)

                    return url, {"status": "done", "data": data}

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == MAX_RETRIES - 1:
                    print(f"Failed {url} after {MAX_RETRIES} attempts: {e}")
                    return url, {"status": "failed"}

                await asyncio.sleep(2**attempt)

    return url, {"status": "failed"}


async def process_batch(urls: list[str], max_concurrent: int = 20):
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
            "SELECT url FROM scrape_queue WHERE status = 'pending' AND type = 'article_list' LIMIT ?",
            (BATCH_SIZE,),
        )
        rows = cursor.fetchall()

        if not rows:
            print("No pending article_list URLs left.")
            break

        urls = [row[0] for row in rows]
        cursor.executemany(
            "UPDATE scrape_queue SET status = 'processing' WHERE url = ?",
            [(u,) for u in urls],
        )
        conn.commit()

        print(f"Fetching batch of {len(urls)} lists...")
        batch_results = asyncio.run(process_batch(urls))

        queue_updates = []
        new_queue_items = []

        for url, result in batch_results:
            queue_updates.append((result["status"], url))

            if result["status"] == "done":
                for article_url in result["data"]["article_urls"]:
                    new_queue_items.append((article_url, "article"))

                next_list_urls = result["data"].get("next_list_urls", [])
                if next_list_urls:
                    for next_list_url in next_list_urls:
                        new_queue_items.append((next_list_url, "article_list"))

        cursor.executemany(
            "UPDATE scrape_queue SET status = ? WHERE url = ?", queue_updates
        )
        cursor.executemany(
            "INSERT INTO scrape_queue (url, type) VALUES (?, ?) ON CONFLICT DO NOTHING",
            new_queue_items,
        )
        conn.commit()

        articles_queued = sum(1 for item in new_queue_items if item[1] == "article")
        pages_queued = len(new_queue_items) - articles_queued
        print(
            f"Batch complete. Queued {articles_queued} articles and {pages_queued} next pages."
        )


if __name__ == "__main__":
    DB_FILE = "db.sqlite3"

    # generate URLs (run only once)
    # seed_dates_pravda(DB_FILE, "2025-05-09", "2026-05-09")
    # seed_categories_topky(DB_FILE)
    # seed_sportky(DB_FILE)

    main_loop(DB_FILE)
