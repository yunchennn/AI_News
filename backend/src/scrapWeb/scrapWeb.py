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


class NewsCrawler:
    def __init__(self, config_path: str):
        with open(config_path) as f:
            self.config = json.load(f)

        self.llm = DeepLLM()
        self.db_path = self.config["db_path"]
        self.news_config_path = self.config["news_config_path"]
        self.limit = self.config.get("limit_per_source", 3)

        self.init_db()

    def init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''
                    CREATE TABLE IF NOT EXISTS summaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT,
                        original_title TEXT,
                        llm_title TEXT,
                        url TEXT UNIQUE,
                        summary TEXT,
                        report_timestamp TEXT,   
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP 
                    )
                ''')
                conn.commit()
            print("[INFO] Database initialized successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to initialize DB: {e}")

    from datetime import datetime

    def save_to_db(self, source, original_title, llm_title, report_timestamp, article_url, summary):
        try:
            now_timestamp = datetime.now()
            with sqlite3.connect(self.db_path) as conn:
                c = conn.cursor()
                c.execute('''
                    INSERT OR IGNORE INTO summaries (source, original_title, llm_title, url, summary, report_timestamp, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (source, original_title, llm_title, article_url, summary, report_timestamp, now_timestamp))
                conn.commit()
            print(f"[INFO] Saved article to DB: {llm_title}")
        except Exception as e:
            print(f"[ERROR] Failed to save article: {e}")


    def extract_json(self, response_text: str) -> dict:
        try:
            return json.loads(response_text.strip())
        except json.JSONDecodeError:
            pass 

        try:
            brace_stack = []
            start_index = None

            for i, char in enumerate(response_text):
                if char == '{':
                    if not brace_stack:
                        start_index = i
                    brace_stack.append(char)
                elif char == '}':
                    if brace_stack:
                        brace_stack.pop()
                        if not brace_stack:
                            json_str = response_text[start_index:i + 1]
                            return json.loads(json_str)
            raise ValueError("no json found")
        except Exception as e:
            print(f"[ERROR] Failed to extract JSON: {e}")
            return {}

    def crawl_site(self, source, url):
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
                        article_url = link_tag['href'] if link_tag else None
                        news_info = {
                            "title": title,
                            "url": article_url
                        }
                        art_request = req.Request(article_url, headers=headers)
                        try:
                            with req.urlopen(art_request) as response:
                                data2 = response.read().decode("utf-8")
                        except urllib.error.HTTPError as e:
                            if e.code == 401:
                                print(f"[WARNING] Skipping URL due to 401 Unauthorized: {url}")
                                return []
                            else:
                                raise  # re-raise other HTTP errors

                        # print(data2)
                        soup2 = BeautifulSoup(data2, "html.parser")
                        time_holders = soup2.find_all('div', class_='ArticleHeader-timeHidden')
                        # print("time_holders: ", time_holders)
                        for t in time_holders:
                            
                            try:
                                time_tag = t.find('time', {"data-testid": "published-timestamp"})
                                if not time_tag:
                                    # fallback，直接找第一個 time tag
                                    time_tag = t.find('time')
                                date = time_tag["datetime"] if time_tag and time_tag.has_attr('datetime') else None
                                news_info["date"] = date
                                # print(f'****date: {date}')
                            except Exception as e:
                                print(f"[ERROR] Article parse failed: {e}")
                                continue
                 

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

    def crawl_and_summarize(self):
        print(f"[{datetime.now()}] - started")
        with open(self.news_config_path) as f:
            config = json.load(f)
        cnt = 0
        for entry in config.values():
            source = entry.get("name")
            base_url = entry.get("url")
            if not base_url:
                continue

            print(f" {source} - {base_url}")
            articles_info = self.crawl_site(source, base_url)
            limit = 5
            articles_info = articles_info[:limit]
            
            for idx, info in enumerate(articles_info):
                article_url = info["url"]
                org_title = info["title"]
                report_timestamp = info["date"]
                response = self.llm.getReport(article_url, [])
                json_response = self.extract_json(response)

                # print(json_response)
                summary = json_response.get("summary", "")
                new_title = json_response.get("title", "") or json_response.get("headline", "")
                if not new_title:
                    new_title = org_title

                if summary:
                    self.save_to_db(source, org_title, new_title, report_timestamp, article_url, summary)
                    cnt += 1
                    print(f"[get news]:{cnt}. [{source}] 📰 {new_title}\n📎 {article_url}\n📝 {summary[:100]}...\n{'-' * 40}")
                else:
                    print(f"[fail get news]:  {new_title}\n📎 {article_url}\n {summary[:100]}...\n{'-' * 40}")

                print('----------------------')
            # break


        print(f"[{datetime.now()}] - finished")

    def run_scheduler(self):
        schedule.every(1).minutes.do(self.crawl_and_summarize)
        print("📅 Scheduler started...")
        while True:
            schedule.run_pending()
            time.sleep(10)

if __name__ == "__main__":
    crawler = NewsCrawler(config_path="../../../config/set_config.json")
    crawler.crawl_and_summarize()
    # crawler.run_scheduler()
