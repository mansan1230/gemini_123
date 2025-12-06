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

# Debug: 顯示 Key 狀態
print(f"Checking Keys...")
print(f"- NEWS: {'✅' if NEWS_API_KEY else '❌'}")
print(f"- GEMINI: {'✅' if GEMINI_API_KEY else '❌'}")
print(f"- FINNHUB: {'✅' if FINNHUB_API_KEY else '❌'}")

# 【模型設定】
# 既然你的 log 顯示它跑通了，代表 gemini-2.0-flash-lite 是可用的！
# 我們繼續用它，或者改用 gemini-2.0-flash (通常更聰明一點)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY.strip())
    model = genai.GenerativeModel(
        'gemini-2.0-flash', # 建議用 flash 標準版，比 lite 更穩
        generation_config={"response_mime_type": "application/json"}
    )

# 新聞關鍵字
CATEGORIES = {
    "🔥 市場頭條": "stock market OR federal reserve OR inflation OR economy",
    "🤖 人工智慧": "Artificial Intelligence OR Nvidia OR OpenAI OR TSMC",
    "💰 加密貨幣": "Bitcoin OR Ethereum OR Crypto"
}

MARKET_TICKERS = {
    "🇺🇸 S&P 500": "SPY",
    "🇺🇸 Nasdaq": "QQQ",
    "🇭🇰 恒生指數": "2800.HK",
    "🪙 Bitcoin": "BINANCE:BTCUSDT"
}

# ================= 2. 抓取函數 =================

def get_market_data():
    if not FINNHUB_API_KEY:
        print("⚠️ 跳過指數: 缺 Key")
        return []
    
    market_data = []
    print("📊 抓取指數...")
    for name, symbol in MARKET_TICKERS.items():
        try:
            url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
            res = requests.get(url).json()
            if res.get('c', 0) != 0:
                market_data.append({
                    "name": name, "price": res['c'], "change": res['d'], "percent": res['dp']
                })
        except: pass
    return market_data

def get_ai_news():
    if not NEWS_API_KEY: return []
    final_news = []
    bad_domains = "biztoc.com,globenewswire.com,prnewswire.com,businesswire.com,prweb.com,marketwatch.com"
    
    for category, query in CATEGORIES.items():
        print(f"🔍 處理: {category}...")
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&excludeDomains={bad_domains}&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
        
        try:
            response = requests.get(url).json()
            articles = response.get("articles", [])
        except: continue

        for art in articles:
            # Prompt: 強調只要單一物件
            prompt = f"""
            你是一位華爾街分析師。請閱讀新聞：
            標題: {art['title']}
            內容: {art['description']}

            請回傳一個單一 JSON 物件 (不要列表 List)：
            {{
                "title_zh": "中文標題",
                "summary_zh": "50字內中文摘要",
                "impact": "利多 / 利空 / 中性",
                "score": 8
            }}
            """
            
            try:
                # 呼叫 AI
                ai_response = model.generate_content(prompt)
                analysis = json.loads(ai_response.text)
                
                # 【🔥 關鍵修正 9.0】解決 list object has no attribute get
                # 如果 AI 回傳的是列表 [ {...} ]，我們自動取第 0 個
                if isinstance(analysis, list):
                    analysis = analysis[0]
                
                final_news.append({
                    "category": category,
                    "title": analysis.get("title_zh", art['title']),
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": analysis.get("summary_zh", "AI 未能生成摘要"),
                    "impact": analysis.get("impact", "中性"),
                    "score": analysis.get("score", 5)
                })
                print(f"   ✅ 成功: {analysis.get('title_zh')}")
                time.sleep(2) # 休息一下
                
            except Exception as e:
                print(f"   ⚠️ 失敗: {e}")
                # Fallback
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
    url = f"https://finnhub.io/api/v1/calendar/economic?from={start}&to={end}&token={FINNHUB_API_KEY}"
    try:
        res = requests.get(url).json()
        data = []
        for item in res.get("economicCalendar", []):
            if item['country'] == 'US': 
                data.append({
                    "event": item['event'], "time": item['time'],
                    "actual": str(item['actual'] or "待公布"),
                    "estimate": str(item['estimate'] or "-"),
                    "prev": str(item['prev'] or "-")
