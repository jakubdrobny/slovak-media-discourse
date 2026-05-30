import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# URL = "https://spravy.pravda.sk/svet/clanok/806439-pripustil-putin-koniec-vojny-europe-poslal-jasny-signal-koho-chce-vidiet-pri-rokovacom-stole/"
URL = "https://sportweb.pravda.sk/tenis/clanok/774901-djokovic-sa-vyjadril-k-dopingu-sinnera-jeho-trener-na-slova-srba-reagoval-podrazdene/"
req = requests.get(URL)
html = req.text
soup = BeautifulSoup(html, "lxml")

result = {
    "title": "",
    "perex": "",
    "content": "",
    "category": "",
    "date_string": "",
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
    result["date_string"] = published.strip()

content_body = soup.find("div", itemprop="articleBody")
if content_body:
    paragraphs = content_body.find_all("p", recursive=False)
    result["content"] = " ".join(
        [p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)]
    )

parsed_url = urlparse(URL)
path = parsed_url.path

if "/clanok/" in path:
    parts = path.split("/clanok/")

    category_raw = parts[0].strip("/")
    result["category"] = category_raw.replace("/", " > ")

    article_slug = parts[-1].strip("/")
    if article_slug:
        result["discussion_url"] = f"https://debata.pravda.sk/debata/{article_slug}/"

print(json.dumps(result, sort_keys=True, indent=4, ensure_ascii=False))
