from datetime import datetime
import json
import pytz
import requests
from bs4 import BeautifulSoup

URL = "https://sportky.zoznam.sk/c/457579/kolko-zaraba-lionel-messi-zverejnili-skutocny-plat-argentinskeho-klenotu-v-mls"
req = requests.get(URL)
html = req.text
soup = BeautifulSoup(html, "lxml")


def parse_sportky_datetime(date_iso_str: str) -> int:
    if not date_iso_str:
        return 0
    try:
        dt = datetime.fromisoformat(date_iso_str)
        return int(dt.timestamp())
    except Exception as e:
        print(f"Time parsing error for '{date_iso_str}': {e}")
        return 0


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


for script in soup.find_all("script", type="application/ld+json"):
    data = json.loads(script.get_text(strip=True))
    if data.get("@type", "") == "NewsArticle":
        result["timestamp"] = parse_sportky_datetime(data.get("datePublished", ""))

result["discussion_url"] = (
    f"https://disqus.com/embed/comments/?f=topky&t_u={URL}#version=edbad5dd62b4c9201796cb42e4b24cf7"
)

print(json.dumps(result, sort_keys=True, indent=4, ensure_ascii=False))
