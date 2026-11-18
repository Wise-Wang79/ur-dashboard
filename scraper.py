import json
import re
from datetime import datetime, timedelta
import urllib.parse
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# 1. 抓取國土署都市更新入口網公告 (前 5 頁)
def fetch_twur_projects():
    base_url = "https://twur.nlma.gov.tw/zh/merchant/announcement/"
    cases_dict = {}
    today = datetime.now()
    six_months_ago = today - timedelta(days=180)

    print("開始抓取國土署都更招商公告...")
    for page in range(5):
        url = f"{base_url}{page}"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")
            
            # 解析公告列表表格列
            rows = soup.select("table tbody tr")
            if not rows:
                rows = soup.select("tr")

            for r in rows:
                cols = [td.get_text(strip=True) for td in r.select("td")]
                if len(cols) < 5:
                    continue
                
                # 欄位通常為：案號/項次、縣市、案件名稱、公告類別、公告日期
                raw_city = cols[1] if len(cols) > 1 else ""
                raw_name = cols[2] if len(cols) > 2 else ""
                raw_type = cols[3] if len(cols) > 3 else "招商公告"
                raw_date = cols[4] if len(cols) > 4 else ""

                # 提取案件編號與縣市主鍵
                case_id_match = re.search(r'(UR\d+|\d+)', raw_name)
                case_id = case_id_match.group(1) if case_id_match else raw_name[:15]
                composite_key = f"{case_id}_{raw_city}"

                # 嘗試解析公告開始日期
                date_match = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', raw_date)
                ann_date_dt = None
                if date_match:
                    try:
                        ann_date_dt = datetime(int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3)))
                    except:
                        pass

                # 僅保留近 6 個月內有公告或異動的案件
                if ann_date_dt and ann_date_dt < six_months_ago:
                    continue

                if composite_key not in cases_dict:
                    cases_dict[composite_key] = {
                        "id": composite_key,
                        "case_id": case_id,
                        "city": raw_city,
                        "name": raw_name,
                        "current_status": raw_type,
                        "publish_date": raw_date,
                        "source_url": url,
                        "history": [f"{raw_date}：{raw_type}"]
                    }
                else:
                    # 案件重複歸戶：追加歷史釋疑/評選進度
                    hist_entry = f"{raw_date}：{raw_type}"
                    if hist_entry not in cases_dict[composite_key]["history"]:
                        cases_dict[composite_key]["history"].append(hist_entry)
                        cases_dict[composite_key]["current_status"] = raw_type
        except Exception as e:
            print(f"解析第 {page} 頁時發生例外: {e}")

    return list(cases_dict.values())

# 2. 抓取都更相關即時新聞 (Google News RSS)
def fetch_urban_news():
    news_items = []
    queries = ["公辦都更", "都市更新 招商", "捷運聯開 招商"]
    
    print("開始抓取都市更新相關新聞...")
    for q in queries:
        encoded_q = urllib.parse.quote(q)
        rss_url = f"[suspicious link removed]{encoded_q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
        try:
            resp = requests.get(rss_url, headers=HEADERS, timeout=10)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.findall(".//item")[:5]:
                    title = item.find("title").text if item.find("title") is not None else ""
                    link = item.find("link").text if item.find("link") is not None else ""
                    pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
                    source = item.find("source").text if item.find("source") is not None else "綜合報導"
                    
                    if title and link:
                        news_items.append({
                            "title": title,
                            "link": link,
                            "date": pub_date[:16] if pub_date else "",
                            "source": source
                        })
        except Exception as e:
            print(f"抓取關鍵字 {q} 新聞時發生例外: {e}")

    # 標題去重
    seen_titles = set()
    unique_news = []
    for n in news_items:
        if n["title"] not in seen_titles:
            seen_titles.add(n["title"])
            unique_news.append(n)
    return unique_news[:15]

def main():
    projects = fetch_twur_projects()
    news = fetch_urban_news()
    
    payload = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_projects": len(projects),
        "projects": projects,
        "news": news
    }
    
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"更新完成！共抓取 {len(projects)} 個案件與 {len(news)} 則新聞，已儲存至 data.json")

if __name__ == "__main__":
    main()
