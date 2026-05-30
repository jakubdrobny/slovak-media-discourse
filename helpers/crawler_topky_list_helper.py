from urllib.parse import urljoin
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re

import requests


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


def extract_urls_topky(soup: BeautifulSoup, url: str, start_date_str: str):
    article_urls = []
    next_list_urls = []
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    oldest_timestamp = datetime.now()
    last_date = None

    section_pages_el = soup.find(id="section-pages")
    if section_pages_el:
        article_list_el = soup.select_one("div.article_list > ul")
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
    else:
        print("section-pages not found")

    if oldest_timestamp >= start_date:
        match = re.search(r"(/se/\d+/)(\d+)(/[^/]+)", url)
        if match:
            current_page = int(match.group(2))
            for i in range(1, 11):
                next_page = current_page + i
                next_list_urls.append(
                    f"https://www.topky.sk{match.group(1)}{next_page}{match.group(3)}"
                )

    return {"article_urls": article_urls, "next_list_urls": next_list_urls}
