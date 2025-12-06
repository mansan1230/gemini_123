import os
import requests
import json
import google.generativeai as genai
from datetime import datetime, timedelta

# ================= 設定區 =================
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# 設定 Gemini (使用 Flash 模型 + 強制 JSON 模式)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY.strip())
    # 關鍵修正：response_mime_type 強制輸出 JSON，不再會解析失敗
    model = genai.GenerativeModel(
        'gemini-1.5-flash',
        generation_config={"response_mime_type": "application/json"}
    )

# 新聞關鍵字
CATEGORIES = {
    "🔥 市場頭條": "finance OR stock market OR economy",
    "🤖 人工智慧": "Artificial Intelligence OR Nvidia OR OpenAI",
    "💰 加密貨幣": "Bitcoin OR Ethereum OR Crypto"
}

# 市場指數 (ETF 代碼，確保 Finnhub 免費版能抓)
MARKET_TICKERS = {
    "🇺🇸 S&P 500": "SPY",
    "🇺🇸 Nasdaq": "QQQ",
    "🇭🇰 恒生指數": "2800.HK",
    "🪙 Bitcoin": "BINANCE:BTCUSDT"
}

# ================= 函數 1: 抓市場指數 =================
def get_market_data():
    if not FINNHUB_API_KEY:
        print("⚠️ 警告：沒有設定 FINNHUB_API_KEY，無法抓取指數。")
        return []
    
    market_data = []
    print("📊 正在抓取市場指數...")

    for name, symbol in MARKET_TICKERS.items():
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        try:
            res = requests.get(url).json()
            # 檢查是否有回傳有效價格 (c = Current Price)
            if res.get('c', 0) != 0:
                market_data.append({
                    "name": name,
                    "price": res['c'],
                    "change": res['d'],
                    "percent": res['dp']
                })
            else:
                print(f"❌ {name} ({symbol}) 無數據，可能市場休市或代碼錯誤。")
        except Exception as e:
            print(f"❌ 抓取 {name} 失敗: {e}")

    return market_data

# ================= 函數 2: 抓新聞 + AI 分析 =================
def get_ai_news():
    final_news = []
    
    for category, query in CATEGORIES.items():
        print(f"正在處理分類: {category}...")
        
        # 排除 biztoc.com 這種會擋爬蟲的網站
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&excludeDomains=biztoc.com&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
        
        try:
            response = requests.get(url).json()
            articles = response.get("articles", [])
        except Exception as e:
            print(f"NewsAPI 連線錯誤: {e}")
            continue

        for art in articles:
            # Prompt 工程：明確要求 JSON 結構
            prompt = f"""
            你是一個專業財經記者。請閱讀以下新聞：
            標題: {art['title']}
            內容: {art['description']}

            請輸出一個 JSON 物件，包含以下欄位 (必須使用繁體中文 Traditional Chinese)：
            - summary: 50字內的精簡摘要
            - impact: 對市場的影響 (利多/利空/中性)
            - score: 重要性評分 (1-10，數字)
            """
            
            try:
                # 因為設定了 response_mime_type，AI 必定回傳標準 JSON
                ai_response = model.generate_content(prompt)
                analysis = json.loads(ai_response.text)
                
                final_news.append({
                    "category": category,
                    "title": art['title'],
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": analysis.get("summary", "摘要生成失敗"),
                    "impact": analysis.get("impact", "一般"),
                    "score": analysis.get("score", 5)
                })
                print(f"✅ AI 成功摘要: {art['title'][:15]}...")
                
            except Exception as e:
                print(f"⚠️ AI 分析失敗 (轉為原文): {e}")
                # 失敗時的回退方案
                final_news.append({
                    "category": category,
                    "title": art['title'],
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": art['description'] or "無內容", # 這裡就是為什麼你之前看到英文
                    "impact": "無分析",
                    "score": 0
                })

    return sorted(final_news, key=lambda x: x['score'], reverse=True)

# ================= 函數 3: 抓財經日曆 =================
def get_economic_calendar():
    if not FINNHUB_API_KEY: return []
    
    # 抓未來 7 天
    start = datetime.now().strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    
    url = f"https://finnhub.io/api/v1/calendar/economic?from={start}&to={end}&token={FINNHUB_API_KEY}"
    
    try:
        res = requests.get(url).json()
        data = []
        for item in res.get("economicCalendar", []):
            if item['country'] == 'US': # 只看美國
                data.append({
                    "event": item['event'],
                    "time": item['time'],
                    "actual": str(item['actual'] if item['actual'] is not None else "待公布"),
                    "estimate": str(item['estimate'] if item['estimate'] is not None else "-"),
                    "prev": str(item['prev'] if item['prev'] is not None else "-")
                })
        return data
    except Exception as e:
        print(f"日曆抓取失敗: {e}")
        return []

# ================= 主程式 =================
if __name__ == "__main__":
    print("🚀 程式啟動...")
    
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "market": get_market_data(),       # 1. 指數
        "news": get_ai_news(),             # 2. 新聞
        "calendar": get_economic_calendar() # 3. 日曆
    }
    
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    
    print("🎉 完成！檔案已更新。")
