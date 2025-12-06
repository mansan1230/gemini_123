import os
import requests
import json
import time  # <--- 新增這個，用 Pro 模型必須要識得「抖氣」
import google.generativeai as genai
from datetime import datetime, timedelta

# ================= 設定區 =================
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# 【升級重點】改用 gemini-1.5-pro (最勁模型)
# 強制 JSON 模式依然要保留，保證格式正確
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY.strip())
    model = genai.GenerativeModel(
        'gemini-3-pro-preview',  # <--- 改左呢度！由 flash 變 pro
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

# ================= 函數 2: 抓新聞 + AI Pro 分析 =================
def get_ai_news():
    final_news = []
    
    for category, query in CATEGORIES.items():
        print(f"正在處理: {category} (使用 Pro 模型)...")
        
        # 排除垃圾網站
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&excludeDomains=biztoc.com&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
        
        try:
            response = requests.get(url).json()
            articles = response.get("articles", [])
        except:
            continue

        for art in articles:
            # Prompt 微調：既然用 Pro，要求可以更高一點
            prompt = f"""
            你是一位華爾街資深分析師。請閱讀以下英文新聞：
            標題: {art['title']}
            內容: {art['description']}

            請完成以下任務並輸出 JSON：
            1. title_zh: 將標題翻譯成專業的「繁體中文」。
            2. summary_zh: 用「繁體中文」撰寫 50 字內的深度摘要，重點在於背後的商業邏輯。
            3. impact: 判斷對市場影響 (利多/利空/中性)。
            4. score: 給予重要性評分 1-10。

            JSON 範例：
            {{
                "title_zh": "中文標題",
                "summary_zh": "中文深度摘要...",
                "impact": "利多",
                "score": 9
            }}
            """
            
            try:
                # 呼叫 AI
                ai_response = model.generate_content(prompt)
                analysis = json.loads(ai_response.text)
                
                final_news.append({
                    "category": category,
                    "title": analysis.get("title_zh", art['title']),
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": analysis.get("summary_zh", "無摘要"),
                    "impact": analysis.get("impact", "中性"),
                    "score": analysis.get("score", 5)
                })
                print(f"✅ Pro 分析成功: {analysis.get('title_zh')}")
                
                # 【重要】Pro 模型限制較嚴，每跑完一次休息 2 秒，避免被 Google Block
                time.sleep(2) 
                
            except Exception as e:
                print(f"⚠️ Pro 分析失敗: {e}")
                # 失敗時的回退
                final_news.append({
                    "category": category,
                    "title": f"(原文) {art['title']}",
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
    
    # 抓未來 14 天
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
                    "actual": str(item['actual'] if item['actual'] is not None else "待公布"),
                    "estimate": str(item['estimate'] if item['estimate'] is not None else "-"),
                    "prev": str(item['prev'] if item['prev'] is not None else "-")
                })
        return data[:10]
    except:
        return []

# ================= 主程式 =================
if __name__ == "__main__":
    print("🚀 啟動 Pro 模型分析引擎...")
    
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "market": get_market_data(),
        "news": get_ai_news(),
        "calendar": get_economic_calendar()
    }
    
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    
    print("🎉 完成！")
