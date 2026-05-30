from datetime import datetime, timedelta
import random
import re
import time
import pytz
import requests
from bs4 import BeautifulSoup

URL = "https://debata.pravda.sk/debata/806439-pripustil-putin-koniec-vojny-europe-poslal-jasny-signal-koho-chce-vidiet-pri-rokovacom-stole/"
req = requests.get(URL)
html = req.text
soup = BeautifulSoup(html, "lxml")


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

    platform_id = None
    post_meta_el_id = post_meta_el.get("id")
    match = re.search(r"\d+$", post_meta_el_id)
    if match:
        platform_id = match.group()

    comment = post_meta_el.select_one("div.post > p").get_text(strip=True)

    rating = int(
        post_meta_el.find("div", title="Hodnotenie príspevku").get_text(strip=True)
    )

    username = post_meta_el.select_one("span.comment-time > a").get_text(strip=True)

    datetime_str = " ".join(
        [
            t.strip()
            for t in post_meta_el.select_one("span.comment-time").find_all(
                string=True, recursive=False
            )
            if t.strip()
        ]
    )
    datetime_unix = to_unix_timestamp(remove_words_from_datetime_str(datetime_str))

    profile_link_el = post_meta_el.select_one("span.comment-time > a")
    user_profile_url = f"https://debata.pravda.sk{profile_link_el['href']}"

    comments = [
        {
            "content": comment,
            "datetime": datetime_unix,
            "username": username,
            "platform_id": platform_id,
            "platform_parent_id": platform_parent_id,
            "upvotes": rating,
        }
    ]
    users = {}
    users[username] = {"name": username, "url": user_profile_url}

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

    return users, comments, next_url


users, comments, next_url = extract_from_discussion(soup)
print(comments, next_url)
