import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
import json
import sqlite3
import urllib.request as req
import time
from bs4 import BeautifulSoup
import schedule
from datetime import datetime
from src.LLM.deepLLM import DeepLLM
import collections
import re
import requests
import urllib

llm = DeepLLM()


DB_FILE = "news.db"
CONFIG_FILE = "../../../config/news_config.json"

import sqlite3

DB_FILE = "your_database.db"  # 如果你還沒定義，可以加上這行

def init_db():
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT,
                    original_title TEXT,
                    llm_title TEXT,
                    url TEXT UNIQUE,
                    summary TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
        print("[INFO] Database initialized successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize DB: {e}")

def save_to_db(source, original_title, llm_title, timestamp, article_url, summary):
    try:
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT OR IGNORE INTO summaries (source, original_title, llm_title, url, summary, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (source, original_title, llm_title, article_url, summary, timestamp))
            conn.commit()
        print(f"[INFO] Saved article to DB: {llm_title}")
    except Exception as e:
        print(f"[ERROR] Failed to save article: {e}")


def crawl_site(source, url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
                       AppleWebKit/537.36 (KHTML, like Gecko) \
                       Chrome/110.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive",
    }

    links = []

    try:
        if source == "CNBC":
            sec_request = req.Request(url, headers=headers)
            try:
                with req.urlopen(sec_request) as response:
                    data = response.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    print(f"[WARNING] Skipping URL due to 401 Unauthorized: {url}")
                    return []
                else:
                    raise  # re-raise other HTTP errors
            soup = BeautifulSoup(data, "html.parser")
            holders = soup.find_all('div', class_='Card-textContent')
            for h in holders:
                try:
                    link_tag = h.find('a', class_='Card-title')
                    title = link_tag.get_text(strip=True) if link_tag else None
                    date = h.find('span', class_='Card-time').get_text(strip=True) if h.find('span', class_='Card-time') else None
                    article_url = link_tag['href'] if link_tag else None
                    news_info = {
                        "title": title,
                        "date": date,
                        "url": article_url
                    }
                    links.append(news_info)
                except Exception as e:
                    print(f"[ERROR] Article parse failed: {e}")
                    continue

        elif source == "Reuters":
            try:
                response = requests.get(url, headers=headers)
                if response.status_code == 401:
                    print(f"[WARNING] Skipping URL due to 401 Unauthorized: {url}")
                    return []
                if response.status_code != 200:
                    print(f"[WARNING] Unexpected status code {response.status_code} from {url}")
                    return []
            except Exception as e:
                print(f"[ERROR] Request failed: {e}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            script_tag = soup.find('script', id='fusion-metadata', type='application/javascript')
            if script_tag:
                match = re.search(r'Fusion\.globalContent\s*=\s*(\{.*?\});', script_tag.string, re.DOTALL)
                if match:
                    json_text = match.group(1)
                    try:
                        data = json.loads(json_text)
                        for article in data['result']['articles']:
                            try:
                                title = article.get('title')
                                url_path = article.get('canonical_url')
                                date = article.get('published_time')
                                full_url = f"https://www.reuters.com{url_path}"
                                news_info = {
                                    "title": title,
                                    "date": date,
                                    "url": full_url
                                }
                                links.append(news_info)
                            except Exception as e:
                                print(f"[ERROR] Article parse failed: {e}")
                    except Exception as e:
                        print(f"[ERROR] JSON parsing failed: {e}")
    except Exception as e:
        print(f"[ERROR] Crawl site {url} failed: {e}")

    return links

def fetch_article_text(info: dict) -> str:

    url = info.get("url")
    title = info.get("title")
    date = info.get("date")
    try:
        request = req.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
                        AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        })

        with req.urlopen(request) as response:
            data = response.read().decode("utf-8")
        soup = BeautifulSoup(data, "html.parser")

        contents = soup.find_all('div', class_='group')
        new_contents = []
        for c in contents:
            if c.get_text(strip=True) == '':
                continue
            new_contents.append(c.get_text(strip=True)) # -> chunks
        # content_text = ' '.join([c.get_text(strip=True) for c in contents])
        time_tag = soup.find('time', {'data-testid': 'published-timestamp'})
        if time_tag:
            published_time = time_tag['datetime']
        infoDict = {
            "title": title,
            "date": date,
            "url": url,
            "content": new_contents,
            "published_time": published_time
        }
        return infoDict
    except Exception as e:
        print(f"[ERROR] Fetch content from {url} failed: {e}")
        return ""

def extract_json(response_text: str) -> dict:
    try:
        # 使用正規表達式擷取 JSON 區塊
        json_match = re.search(r'\{.*?\}', response_text, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            return json.loads(json_str)
        else:
            raise ValueError("❌ 沒有找到符合格式的 JSON 區塊")
    except Exception as e:
        print(f"failed to get the JSON error: {e}")
        return {}


def crawl_and_summarize():
    print(f"[{datetime.now()}] - started")
    with open(CONFIG_FILE) as f:
        config = json.load(f)

    for entry in config.values():
        source = entry.get("name")
        base_url = entry.get("url")
        if not base_url:
            continue

        print(f" {source} - {base_url}")
        articles_info = crawl_site(source, base_url)
        limit = 3
        articles_info = articles_info[:limit]
        
        for idx, info in enumerate(articles_info):
            # contentDict = fetch_article_text(info)
            # print(f"contentDict: {contentDict}")

            # 檢查回傳值型別是否為 dict
            # if not isinstance(contentDict, dict):
            #     print(f"[WARNING] Invalid contentDict type: {type(contentDict)}")
            #     continue

            # contentList = contentDict["content"]
            # article_url = contentDict["url"]
            # org_title = contentDict["title"]
            # timestamp = contentDict["published_time"]
            article_url = info["url"]
            org_title = info["title"]
            timestamp = info["date"]
            response = llm.getReport(article_url, [])
            json_response = extract_json(response)

            print(json_response)
            summary = json_response.get("summary", "")
            new_title = json_response.get("title", "") or json_response.get("headline", "")
            if not new_title:
                new_title = org_title
                continue

            print('----------------------')
            # break
            # print(f"✅ 儲存摘要: {article_url[:60]}...")
            # if summary:
                # save_to_db(source, org_title, new_title, timestamp, article_url, summary)

    # print(f"[{datetime.now()}] - finished")

# 設定排程
def run_scheduler():
    init_db()
    schedule.every(1).hours.do(crawl_and_summarize)

    print("Scheduler started...")
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    crawl_and_summarize()
