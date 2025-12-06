import os
import requests
import json
import google.generativeai as genai
from datetime import datetime, timedelta

# ================= 設定區 =================
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY.strip())
    model = genai.GenerativeModel('gemini-1.5-flash')

# 1. 新聞關鍵字
CATEGORIES = {
    "🔥 市場頭條": "finance OR stock market OR economy",
    "🤖 人工智慧": "Artificial Intelligence OR Nvidia OR OpenAI",
    "💰 加密貨幣": "Bitcoin OR Ethereum OR Crypto"
}

# 2. 市場指數代碼 (使用 ETF 作為替代，確保免費版能抓到)
MARKET_TICKERS = {
    "🇺🇸 S&P 500": "SPY",         # 標普500 ETF
    "🇺🇸 Nasdaq": "QQQ",          # 納指 ETF
    "🇭🇰 恆生指數": "2800.HK",    # 盈富基金 (代表港股)
    "🪙 Bitcoin": "BINANCE:BTCUSDT" # 比特幣
}

# ================= 函數 1: 抓市場指數 (新增!) =================
def get_market_data():
    if not FINNHUB_API_KEY:
        return []
    
    market_data = []
    print("📊 正在抓取市場指數...")

    for name, symbol in MARKET_TICKERS.items():
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_API_KEY}"
        try:
            res = requests.get(url).json()
            # Finnhub 回傳: c=current price, d=change, dp=percent change
            if res.get('c', 0) != 0:
                market_data.append({
                    "name": name,
                    "price": res['c'],           # 現價
                    "change": res['d'],          # 漲跌額
                    "percent": res['dp']         # 漲跌幅 (%)
                })
        except Exception as e:
            print(f"❌ 抓取 {name} 失敗: {e}")

    return market_data

# ================= 函數 2: 抓新聞 + AI =================
def get_ai_news():
    final_news = []
    for category, query in CATEGORIES.items():
        # 加入 excludeDomains
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&excludeDomains=biztoc.com&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
        try:
            response = requests.get(url).json()
            articles = response.get("articles", [])
            for art in articles:
                prompt = f"""
                請擔任財經分析師。閱讀以下新聞：
                標題: {art['title']}
                內容: {art['description']}
                請用「繁體中文」回答，並嚴格依照 JSON 格式輸出：
                {{
                    "summary": "50字內中文摘要",
                    "impact": "利多/利空/中性",
                    "score": 評分 (1-10)
                }}
                直接回傳 JSON。
                """
                try:
                    ai_response = model.generate_content(prompt)
                    ai_text = ai_response.text.strip().replace("```json", "").replace("```", "")
                    analysis = json.loads(ai_text)
                    final_news.append({
                        "category": category,
                        "title": art['title'],
                        "link": art['url'],
                        "date": art['publishedAt'][:10],
                        "summary": analysis.get("summary", "AI 未生成"),
                        "impact": analysis.get("impact", "一般"),
                        "score": analysis.get("score", 5)
                    })
                except:
                    # 失敗回退
                    final_news.append({
                        "category": category,
                        "title": art['title'],
                        "link": art['url'],
                        "date": art['publishedAt'][:10],
                        "summary": art['description'],
                        "impact": "無分析",
                        "score": 0
                    })
        except Exception as e:
            print(f"NewsAPI Error: {e}")
            
    return sorted(final_news, key=lambda x: x['score'], reverse=True)

# ================= 函數 3: 抓財經日曆 =================
def get_economic_calendar():
    if not FINNHUB_API_KEY: return []
    start = datetime.now().strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
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
        return data
    except: return []

# ================= 主程式 =================
if __name__ == "__main__":
    print("🚀 開始執行...")
    
    # 1. 抓指數
    market_data = get_market_data() 
    # 2. 抓新聞
    news_data = get_ai_news()
    # 3. 抓日曆
    calendar_data = get_economic_calendar()
    
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "market": market_data,     # 新增這個欄位
        "news": news_data,
        "calendar": calendar_data
    }
    
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    
    print("🎉 完成！")
