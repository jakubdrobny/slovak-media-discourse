import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import urllib.parse

URL = "https://disqus.com/embed/comments/?f=topky&t_u=https://www.topky.sk/cl/100313/9394987/Slovensky-exmoderator-po-svadbe-s-partnerom--Poslal-drsny-odkaz-neprajnym-Slovakom-#version=edbad5dd62b4c9201796cb42e4b24cf7"
req = requests.get(URL)
html = req.text
soup = BeautifulSoup(html, "lxml")

script_el = soup.find("script", id="disqus-threadData")
if script_el:
    cntnt = script_el.get_text(strip=True)
    if cntnt:
        obj = json.loads(cntnt)

        comments = []
        users = {}

        posts = obj.get("response", {}).get("posts", [])
        for post in posts:
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

            users[username] = {"name": username}

        print(f"Extracted {len(comments)} comments.")

        cursor = obj.get("cursor", {})
        if cursor.get("hasNext"):
            next_cursor = cursor.get("next")
            thread_id = posts[0]["thread"]
            forum = posts[0]["forum"]

            # some public api key
            api_key = "E8Uh5l5fHZ6gD8U3KycjAIAk46f68Zw7C6eW8WSjVNeq28ROeY2KrvK5tN6x"

            parsed_url = urllib.parse.urlparse(URL)
            qs = urllib.parse.parse_qs(parsed_url.query)
            article_url = qs.get("t_u", [""])[0]

            next_url = f"https://disqus.com/api/3.0/threads/listPostsThreaded?limit=50&thread={thread_id}&forum={forum}&order=popular&cursor={next_cursor}&api_key={api_key}&t_u={article_url}"

            print("Next API URL to fetch:")
            print(next_url)
