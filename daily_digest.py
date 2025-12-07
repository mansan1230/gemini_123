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

# Debug
print(f"Checking Keys...")
print(f"- NEWS: {'✅' if NEWS_API_KEY else '❌'}")
print(f"- GEMINI: {'✅' if GEMINI_API_KEY else '❌'}")
print(f"- FINNHUB: {'✅' if FINNHUB_API_KEY else '❌'}")

# 【修正 1】改回 gemini-1.5-flash (免費額度最高，最不容易 429)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY.strip())
    model = genai.GenerativeModel(
        'gemini-2.0-flash-lite', 
        generation_config={"response_mime_type": "application/json"}
    )

CATEGORIES = {
    "🔥 市場頭條": "stock market OR federal reserve OR economy OR inflation",
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
    
    trusted_domains = "reuters.com,cnbc.com,bloomberg.com,finance.yahoo.com,wsj.com,techcrunch.com,coindesk.com"
    
    for category, query in CATEGORIES.items():
        print(f"🔍 處理分類: {category} (打包模式)...")
        
        # 抓取 10 篇原文
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&domains={trusted_domains}&sortBy=popularity&pageSize=10&apiKey={NEWS_API_KEY}"
        
        try:
            response = requests.get(url).json()
            articles = response.get("articles", [])
            if not articles: continue
        except: continue

        # 【修正 2】打包處理 (Batch Processing)
        # 我們不逐篇問，而是把 10 篇標題打包成一個字串
        news_list_text = ""
        for i, art in enumerate(articles):
            news_list_text += f"{i+1}. {art['title']} (URL: {art['url']})\n"

        # Prompt: 一次過叫 AI 挑選並翻譯
        prompt = f"""
        你是一位專業的主編。這裡有該分類下的 10 篇熱門新聞標題：
        
        {news_list_text}

        請執行以下步驟：
        1. 從中挑選 **3 篇** 最重要、最不重複的新聞。
        2. 將它們翻譯成繁體中文。
        3. 判斷利多/利空。

        請回傳一個 JSON 列表 (List of Objects)：
        [
            {{
                "title_zh": "中文標題1",
                "summary_zh": "中文摘要1",
                "impact": "利多",
                "score": 9,
                "original_index": 1 (對應上面清單的編號)
            }},
            ...
        ]
        """
        
        try:
            # 整個分類只呼叫 1 次 AI (極度節省額度)
            ai_response = model.generate_content(prompt)
            analysis_list = json.loads(ai_response.text)
            
            # 確保 AI 回傳的是列表
            if not isinstance(analysis_list, list):
                analysis_list = [analysis_list]

            for item in analysis_list:
                # 根據 AI 回傳的 index 找回原文連結和日期
                idx = item.get("original_index", 1) - 1
                if 0 <= idx < len(articles):
                    original_art = articles[idx]
                    
                    final_news.append({
                        "category": category,
                        "title": item.get("title_zh", original_art['title']),
                        "link": original_art['url'],
                        "date": original_art['publishedAt'][:10],
                        "summary": item.get("summary_zh", "重點新聞"),
                        "impact": item.get("impact", "中性"),
                        "score": item.get("score", 5)
                    })
            
            print(f"   ✅ 成功打包處理 {len(analysis_list)} 篇新聞")
            
            # 雖然只呼叫一次，還是休息一下比較安全
            time.sleep(5)
            
        except Exception as e:
            print(f"   ⚠️ AI 失敗: {e}")
            # Fallback: 如果打包失敗，就只拿第一篇原文充數
            if articles:
                final_news.append({
                    "category": category,
                    "title": articles[0]['title'],
                    "link": articles[0]['url'],
                    "date": articles[0]['publishedAt'][:10],
                    "summary": "AI 忙碌中，請看原文。",
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
    print("🚀 啟動 v12.0 慳家打包版...")
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "market": get_market_data(),
        "news": get_ai_news(),
        "calendar": get_economic_calendar()
    }
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    print("🎉 完成！")
