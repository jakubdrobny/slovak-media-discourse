from datetime import datetime, timedelta
import json
import re
import pytz
import requests
from bs4 import BeautifulSoup

URL = "https://www.topky.sk/cl/100313/9394987/Slovensky-exmoderator-po-svadbe-s-partnerom--Poslal-drsny-odkaz-neprajnym-Slovakom-"
req = requests.get(URL)
html = req.text
soup = BeautifulSoup(html, "lxml")


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

result["discussion_url"] = (
    f"https://disqus.com/embed/comments/?f=topky&t_u={URL}#version=edbad5dd62b4c9201796cb42e4b24cf7"
)

print(json.dumps(result, sort_keys=True, indent=4, ensure_ascii=False))
