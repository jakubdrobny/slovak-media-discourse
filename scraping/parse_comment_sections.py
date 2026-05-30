import asyncio
import json
import aiohttp
import sqlite3
import random
import pytz
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re
import urllib.parse

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/145.0",
]


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


def remove_words_from_datetime_str(datetime_str):
    today = datetime.today()
    datetime_str = datetime_str.replace("dnes", today.strftime("%d.%m.%Y"))

    yesterday = today - timedelta(days=1)
    datetime_str = datetime_str.replace("včera", yesterday.strftime("%d.%m.%Y"))
    return datetime_str


def parse_comment_block(comment_el, platform_parent_id=None):
    post_meta_el = comment_el.select_one("div > div > div > div")
    if not post_meta_el:
        return {}, []

    platform_id = None
    post_meta_el_id = post_meta_el.get("id")
    match = re.search(r"\d+$", post_meta_el_id)
    if match:
        platform_id = match.group()

    comment_p = post_meta_el.select_one("div.post > p")
    comment = comment_p.get_text(strip=True) if comment_p else ""

    rating_el = post_meta_el.find("div", title="Hodnotenie príspevku")
    try:
        rating = int(rating_el.get_text(strip=True)) if rating_el else 0
    except ValueError:
        rating = 0

    username_el = post_meta_el.select_one("span.comment-time > a")
    username = username_el.get_text(strip=True) if username_el else "Unknown"

    time_span = post_meta_el.select_one("span.comment-time")
    if time_span:
        datetime_str = " ".join(
            [
                t.strip()
                for t in time_span.find_all(string=True, recursive=False)
                if t.strip()
            ]
        )
        datetime_unix = to_unix_timestamp(remove_words_from_datetime_str(datetime_str))
    else:
        datetime_unix = 0

    profile_link_el = post_meta_el.select_one("span.comment-time > a")
    user_profile_url = (
        f"https://debata.pravda.sk{profile_link_el['href']}"
        if profile_link_el and profile_link_el.get("href")
        else ""
    )

    comments = []
    if comment:
        comments.append(
            {
                "content": comment,
                "timestamp": datetime_unix,
                "username": username,
                "platform_id": platform_id,
                "platform_parent_id": platform_parent_id,
                "upvotes": rating,
            }
        )

    users = {}
    if username != "Unknown":
        users[username] = {"username": username, "url": user_profile_url}

    post_list_el = comment_el.select_one("div > div.postList")
    if post_list_el:
        for subcomment_el in post_list_el.find_all(
            "div", id=re.compile("^prispevok"), recursive=False
        ):
            post_users, post_comments = parse_comment_block(subcomment_el, platform_id)
            users.update(post_users)
            comments.extend(post_comments)

    return users, comments


def extract_from_discussion(parsed):
    users, comments = {}, []
    next_url = None

    post_list_el = parsed.select_one("div.postList")
    if post_list_el:
        for comment_el in post_list_el.find_all(
            "div", id=re.compile("^prispevok"), recursive=False
        ):
            post_users, post_comments = parse_comment_block(comment_el)
            users.update(post_users)
            comments.extend(post_comments)

    next_el = parsed.find(
        lambda tag: (tag.name in ["a", "span"])
        and tag.string
        and re.search(r"Nasledujúce", tag.string)
    )
    if next_el:
        if next_el.name == "span" and "disabled" in next_el.get("class", []):
            pass  # no further comment pages
        elif next_el.name == "a":
            next_url = f"https://debata.pravda.sk{next_el['href']}"
        else:
            pass  # should not happen

    return list(users.values()), comments, next_url


def parse_pravda_discussion_html(soup: BeautifulSoup) -> dict:
    """
    Extracts comments, users, and the next page URL.

    EXPECTED RETURN FORMAT:
    {
        "comments":[
            {
                "content": "This is a comment text",
                "date_string": "10.05.2026 14:30",
                "username": "JozkoMrkvicka",
                "upvotes": 15,
                "platform_id": "prispevok-123456",        # The HTML ID of this comment
                "platform_parent_id": "prispevok-123450"  # The HTML ID of the parent (or None if top-level)
            },
            ...
        ],
        "users": [
            {"username": "JozkoMrkvicka"},
            ...
        ],
        "next_page_url": "https://debata.pravda.sk/debata/806439-slug/strana-2/" # or None
    }
    """
    extracted_users, extracted_comments, next_page_url = extract_from_discussion(soup)

    return {
        "comments": extracted_comments,
        "users": extracted_users,
        "next_page_url": next_page_url,
    }


def extract_disqus_comments(data: dict):
    comments = []
    users = {}

    response_data = data.get("response", [])
    if isinstance(response_data, dict):
        posts = response_data.get("posts", [])
    elif isinstance(response_data, list):
        posts = response_data
    else:
        posts = []

    for post in posts:
        if not isinstance(post, dict):
            continue

        if post.get("isDeleted"):
            continue

        raw_msg = post.get("message", "")
        msg = BeautifulSoup(raw_msg, "lxml").get_text(strip=True)
        if not msg:
            continue

        author = post.get("author", {})
        username = author.get("name", "Anonymous")

        dt_str = post.get("createdAt")
        timestamp = 0
        if dt_str:
            dt = datetime.fromisoformat(dt_str)
            timestamp = int(dt.timestamp())

        comments.append(
            {
                "content": msg,
                "timestamp": timestamp,
                "upvotes": post.get("likes", 0),
                "downvotes": post.get("dislikes", 0),
                "username": username,
                "platform_id": str(post.get("id")),
                "platform_parent_id": (
                    str(post.get("parent")) if post.get("parent") else None
                ),
            }
        )

        users[username] = {"username": username}

    cursor = data.get("cursor", {})
    next_cursor = cursor.get("next") if cursor.get("hasNext") else None
    return list(users.values()), comments, next_cursor


def parse_disqus_html(soup: BeautifulSoup, url: str, article_url: str):
    script_tag = soup.find("script", id="disqus-threadData")
    if not script_tag:
        return {"comments": [], "users": [], "next_page_url": None}

    data = json.loads(script_tag.get_text(strip=True))
    users, comments, next_cursor = extract_disqus_comments(data)

    next_page_url = None
    if next_cursor and comments:
        thread_id = data["response"]["posts"][0]["thread"]
        forum = data["response"]["posts"][0]["forum"]
        api_key = "E8Uh5l5fHZ6gD8U3KycjAIAk46f68Zw7C6eW8WSjZvCLXebZ7p0r1yrYDrLilk2F"
        safe_article_url = article_url if article_url else ""
        next_page_url = f"https://disqus.com/api/3.0/threads/listPostsThreaded?limit=50&thread={thread_id}&forum={forum}&order=popular&cursor={next_cursor}&api_key={api_key}#t_u={safe_article_url}"

    return {"comments": comments, "users": users, "next_page_url": next_page_url}


def parse_disqus_api(json_data: dict, url: str):
    users, comments, next_cursor = extract_disqus_comments(json_data)
    next_page_url = None
    if next_cursor:
        next_page_url = re.sub(r"cursor=[^&#]+", f"cursor={next_cursor}", url)
    return {"comments": comments, "users": users, "next_page_url": next_page_url}


async def fetch_and_parse(
    url: str, session: aiohttp.ClientSession, semaphore: asyncio.Semaphore
):
    async with semaphore:
        await asyncio.sleep(random.uniform(0.1, 1.0))
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "sk,cs;q=0.89,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        if "disqus.com" in url:
            headers["Referer"] = "https://disqus.com/"
            headers["Origin"] = "https://disqus.com"

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
                    content_type = response.headers.get("Content-Type", "")

                    if "application/json" in content_type:
                        json_data = await response.json()
                        data = parse_disqus_api(json_data, url)
                        match = re.search(r"t_u=([^&#]+)", url)
                        article_url = (
                            urllib.parse.unquote(match.group(1)) if match else ""
                        )
                        return url, {
                            "status": "done",
                            "data": data,
                            "article_url": article_url,
                        }

                    html = await response.text()
                    soup = BeautifulSoup(html, "lxml")

                    if "disqus.com" in url:
                        parsed_url = urllib.parse.urlparse(url)
                        qs = urllib.parse.parse_qs(parsed_url.query)
                        article_url = qs.get("t_u", [""])[0]
                        data = parse_disqus_html(soup, url, article_url)
                        return url, {
                            "status": "done",
                            "data": data,
                            "article_url": article_url,
                        }
                    else:
                        data = parse_pravda_discussion_html(soup)
                        match = re.search(r"/debata/([^/]+)", url)
                        article_slug = match.group(1) if match else ""
                        return url, {
                            "status": "done",
                            "data": data,
                            "article_slug": article_slug,
                        }

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == MAX_RETRIES - 1:
                    print(f"Network failed for {url}: {e}")
                    return url, {"status": "failed"}
                await asyncio.sleep(2**attempt)
            except Exception as e:
                print(f"Parsing crashed for URL: {url} | Error: {e}")
                return url, {"status": "failed"}

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

    cursor.execute(
        "UPDATE scrape_queue SET status = 'pending' WHERE status = 'processing' AND type = 'discussion'"
    )
    conn.commit()
    print("Startup: Reset interrupted 'processing' tasks back to 'pending'.")

    while True:
        cursor.execute(
            "SELECT COUNT(*) FROM scrape_queue WHERE status = 'pending' AND type = 'discussion'"
        )
        remaining_count = cursor.fetchone()[0]

        if remaining_count == 0:
            print("No pending discussions left.")
            break

        cursor.execute(
            "SELECT url FROM scrape_queue WHERE status = 'pending' AND type = 'discussion' LIMIT ?",
            (BATCH_SIZE,),
        )
        rows = cursor.fetchall()

        if not rows:
            print("No pending discussions left.")
            break

        urls = [row[0] for row in rows]
        cursor.executemany(
            "UPDATE scrape_queue SET status = 'processing' WHERE url = ?",
            [(u,) for u in urls],
        )
        conn.commit()

        print(
            f"Fetching batch of {len(urls)} discussions... ({remaining_count} remaining in queue)"
        )

        batch_results = asyncio.run(process_batch(urls))

        queue_updates = []
        new_queue_items = []

        for url, result in batch_results:
            queue_updates.append((result["status"], url))

            if result["status"] == "failed":
                print(f"Marked as FAILED in DB: {url}")

            if result["status"] == "done":
                data = result["data"]
                if "disqus.com" in url:
                    article_url = result.get("article_url", "")
                    cursor.execute(
                        "SELECT id FROM articles WHERE url = ?", (article_url,)
                    )
                else:
                    article_slug = result.get("article_slug", "")
                    cursor.execute(
                        "SELECT id FROM articles WHERE url LIKE ?",
                        (f"%{article_slug}%",),
                    )

                article_row = cursor.fetchone()
                if not article_row:
                    continue
                article_id = article_row[0]

                for user in data["users"]:
                    cursor.execute(
                        "INSERT INTO users (name) VALUES (?) ON CONFLICT DO NOTHING",
                        (user["username"],),
                    )

                for comment in data["comments"]:
                    cursor.execute(
                        "SELECT id FROM users WHERE name = ?", (comment["username"],)
                    )
                    user_row = cursor.fetchone()
                    if not user_row:
                        continue
                    user_id = user_row[0]

                    cursor.execute(
                        """
                        INSERT INTO comments 
                        (content, timestamp, upvotes, downvotes, userId, articleId, platformId, platformParentId)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT DO NOTHING
                        """,
                        (
                            comment["content"],
                            comment.get("timestamp", 0),
                            comment.get("upvotes", 0),
                            comment.get("downvotes", 0),
                            user_id,
                            article_id,
                            comment.get("platform_id"),
                            comment.get("platform_parent_id"),
                        ),
                    )

                if data["next_page_url"]:
                    new_queue_items.append((data["next_page_url"], "discussion"))

        cursor.executemany(
            "UPDATE scrape_queue SET status = ? WHERE url = ?", queue_updates
        )
        cursor.executemany(
            "INSERT INTO scrape_queue (url, type) VALUES (?, ?) ON CONFLICT DO NOTHING",
            new_queue_items,
        )
        conn.commit()
        print(f"Batch complete. Queued {len(new_queue_items)} new discussion pages.")


if __name__ == "__main__":
    main_loop("db.sqlite3")
