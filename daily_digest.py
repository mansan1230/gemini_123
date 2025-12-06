import os
import requests
import json
import time
import google.generativeai as genai
from datetime import datetime, timedelta

# ================= 1. 設定區 =================
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# Debug: 檢查 Key
print(f"Checking Keys...")
print(f"- NEWS: {'✅' if NEWS_API_KEY else '❌'}")
print(f"- GEMINI: {'✅' if GEMINI_API_KEY else '❌'}")
print(f"- FINNHUB: {'✅' if FINNHUB_API_KEY else '❌'}")

# 【改回舊版救星】使用 gemini-pro
# 注意：舊版不支援 response_mime_type，所以這裡不能加 generation_config
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY.strip())
    model = genai.GenerativeModel('gemini-pro') 

# 新聞關鍵字
CATEGORIES = {
    "🔥 市場頭條": "stock market OR federal reserve OR economy",
    "🤖 人工智慧": "Artificial Intelligence OR Nvidia OR OpenAI",
    "💰 加密貨幣": "Bitcoin OR Ethereum OR Crypto"
}

# 市場指數
MARKET_TICKERS = {
    "🇺🇸 S&P 500": "SPY",
    "🇺🇸 Nasdaq": "QQQ",
    "🇭🇰 恒生指數": "2800.HK",
    "🪙 Bitcoin": "BINANCE:BTCUSDT"
}

# ================= 2. 抓取函數 =================

def get_market_data():
    if not FINNHUB_API_KEY: return []
    market_data = []
    print("📊 抓取指數...")
    for name, symbol in MARKET_TICKERS.items():
        try:
            url = f"[https://finnhub.io/api/v1/quote?symbol=](https://finnhub.io/api/v1/quote?symbol=){symbol}&token={FINNHUB_API_KEY}"
            res = requests.get(url).json()
            if res.get('c', 0) != 0:
                market_data.append({
                    "name": name, 
                    "price": res['c'], 
                    "change": res['d'], 
                    "percent": res['dp']
                })
        except: pass
    return market_data

def get_ai_news():
    if not NEWS_API_KEY: return []
    final_news = []
    bad_domains = "biztoc.com,globenewswire.com,prnewswire.com,businesswire.com,prweb.com,marketwatch.com"
    
    for category, query in CATEGORIES.items():
        print(f"🔍 處理: {category}...")
        url = f"[https://newsapi.org/v2/everything?q=](https://newsapi.org/v2/everything?q=){query}&language=en&excludeDomains={bad_domains}&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
        
        try:
            response = requests.get(url).json()
            articles = response.get("articles", [])
        except: continue

        for art in articles:
            # Prompt: 特別叮囑舊模型不要亂加符號
            prompt = f"""
            你是一位華爾街分析師。請閱讀新聞：
            標題: {art['title']}
            內容: {art['description']}

            請"只"輸出一個純 JSON 字串 (不要 Markdown，不要 ```json)：
            {{
                "title_zh": "中文標題",
                "summary_zh": "50字內中文摘要",
                "impact": "利多 / 利空 / 中性",
                "score": 8
            }}
            """
            
            try:
                ai_response = model.generate_content(prompt)
                text = ai_response.text.strip()
                
                # 【手動清理】舊模型 gemini-pro 很喜歡加 markdown 符號，我們要手動刪除
                if text.startswith("```"):
                    text = text.replace("```json", "").replace("```", "")
                
                analysis = json.loads(text)
                
                final_news.append({
                    "category": category,
                    "title": analysis.get("title_zh", art['title']),
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": analysis.get("summary_zh", "AI 未能生成摘要"),
                    "impact": analysis.get("impact", "中性"),
                    "score": analysis.get("score", 5)
                })
                print(f"   ✅ 成功翻譯: {analysis.get('title_zh')}")
                time.sleep(1)
                
            except Exception as e:
                print(f"   ⚠️ AI 失敗: {e}")
                final_news.append({
                    "category": category,
                    "title": f"(英) {art['title']}",
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": f"原文: {art['description']}",
                    "impact": "無分析",
                    "score": 0
                })

    return sorted(final_news, key=lambda x: x['score'], reverse=True)

def get_economic_calendar():
    if not FINNHUB_API_KEY: return []
    print("📅 抓取日曆...")
    start = datetime.now().strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    url = f"[https://finnhub.io/api/v1/calendar/economic?from=](https://finnhub.io/api/v1/calendar/economic?from=){start}&to={end}&token={FINNHUB_API_KEY}"
    try:
        res = requests.get(url).json()
        data = []
        for item in res.get("economicCalendar", []):
            if item['country'] == 'US': 
                data.append({
                    "event": item['event'],
                    "time": item['time'],
                    "actual": str(item['actual'] or "待公布"),
                    "estimate": str(item['estimate'] or "-"),
                    "prev": str(item['prev'] or "-")
                })
        return data[:10]
    except: return []

# ================= 3. 主程式 =================
if __name__ == "__main__":
    print("🚀 啟動 v9.0 舊版兼容模式...")
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "market": get_market_data(),
        "news": get_ai_news(),
        "calendar": get_economic_calendar()
    }
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    print("🎉 完成！")
