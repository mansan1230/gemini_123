import os
import requests
import json
import google.generativeai as genai
from datetime import datetime, timedelta

# ================= 設定區 =================
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# 【關鍵修正 1】設定 Gemini 強制輸出 JSON 格式，這是解決「無分析」的關鍵
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY.strip())
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

# 市場指數
MARKET_TICKERS = {
    "🇺🇸 S&P 500": "SPY",
    "🇺🇸 Nasdaq": "QQQ",
    "🇭🇰 恒生指數": "2800.HK",
    "🪙 Bitcoin": "BINANCE:BTCUSDT"
}

# ================= 函數 1: 抓市場指數 =================
def get_market_data():
    if not FINNHUB_API_KEY: return []
    market_data = []
    print("📊 正在抓取市場指數...")

    for name, symbol in MARKET_TICKERS.items():
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        try:
            res = requests.get(url).json()
            if res.get('c', 0) != 0:
                market_data.append({
                    "name": name,
                    "price": res['c'],
                    "change": res['d'],
                    "percent": res['dp']
                })
        except Exception as e:
            print(f"❌ 指數失敗 {name}: {e}")
    return market_data

# ================= 函數 2: 抓新聞 + AI 強制中文分析 =================
def get_ai_news():
    final_news = []
    
    for category, query in CATEGORIES.items():
        print(f"正在處理: {category}...")
        
        # 排除垃圾網站
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&excludeDomains=biztoc.com&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
        
        try:
            response = requests.get(url).json()
            articles = response.get("articles", [])
        except:
            continue

        for art in articles:
            # 【關鍵修正 2】Prompt 明確要求「翻譯」與「JSON」
            prompt = f"""
            你是一個專業的財經新聞編輯。請閱讀以下英文新聞：
            標題: {art['title']}
            內容: {art['description']}

            請完成以下任務並輸出 JSON：
            1. 將標題翻譯成繁體中文 (title_zh)。
            2. 將內容總結為 50 字內的繁體中文摘要 (summary_zh)。
            3. 分析對市場影響 (利多/利空/中性) (impact)。
            4. 給予重要性評分 1-10 (score)。

            JSON 格式範例：
            {{
                "title_zh": "中文標題",
                "summary_zh": "中文摘要內容...",
                "impact": "利多",
                "score": 8
            }}
            """
            
            try:
                # 呼叫 AI (因為設定了 json mode，這裡一定會回傳 json)
                ai_response = model.generate_content(prompt)
                analysis = json.loads(ai_response.text)
                
                final_news.append({
                    "category": category,
                    "title": analysis.get("title_zh", art['title']), # 用 AI 翻譯的標題
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": analysis.get("summary_zh", "無摘要"), # 用 AI 寫的中文摘要
                    "impact": analysis.get("impact", "中性"),
                    "score": analysis.get("score", 5)
                })
                print(f"✅ 成功分析: {analysis.get('title_zh')}")
                
            except Exception as e:
                print(f"⚠️ AI 失敗: {e}")
                # 失敗時的回退 (至少顯示原文)
                final_news.append({
                    "category": category,
                    "title": art['title'],
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": art['description'],
                    "impact": "無分析",
                    "score": 0
                })

    return sorted(final_news, key=lambda x: x['score'], reverse=True)

# ================= 函數 3: 抓財經日曆 =================
def get_economic_calendar():
    if not FINNHUB_API_KEY: return []
    
    # 【關鍵修正 3】抓未來 14 天 (避免週末沒數據)
    start = datetime.now().strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    
    url = f"https://finnhub.io/api/v1/calendar/economic?from={start}&to={end}&token={FINNHUB_API_KEY}"
    
    try:
        res = requests.get(url).json()
        data = []
        for item in res.get("economicCalendar", []):
            # 只顯示美國 (US) 且重要性較高 (impact > 2) 或特定的重要數據
            if item['country'] == 'US': 
                data.append({
                    "event": item['event'],
                    "time": item['time'],
                    "actual": str(item['actual'] if item['actual'] is not None else "待公布"),
                    "estimate": str(item['estimate'] if item['estimate'] is not None else "-"),
                    "prev": str(item['prev'] if item['prev'] is not None else "-")
                })
        return data[:10] # 只回傳前 10 筆，避免太長
    except:
        return []

# ================= 主程式 =================
if __name__ == "__main__":
    print("🚀 程式啟動...")
    
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "market": get_market_data(),
        "news": get_ai_news(),
        "calendar": get_economic_calendar()
    }
    
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    
    print("🎉 完成！")
