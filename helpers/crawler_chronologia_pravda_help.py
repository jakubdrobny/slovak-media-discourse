import requests
from bs4 import BeautifulSoup

URL = "https://www.pravda.sk/chronologia-dna/?datum=2026-05-08"
req = requests.get(URL)
html = req.text
soup = BeautifulSoup(html, "lxml")

main_div = soup.find(id="box-rubrika-clanky-listing")
if not main_div:
    print("Section with articles not found.")
    exit(1)

article_urls = []
for child in main_div.find_all(recursive=False):
    a_tag = child.find("a")
    if a_tag and a_tag.get("href"):
        article_url = a_tag["href"]
        if "pravda.sk" in article_url:
            article_urls.append(article_url)
