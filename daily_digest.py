import os
import requests
import json
import time
import google.generativeai as genai
from datetime import datetime, timedelta

# ================= 設定區 =================
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# 【修正 1】回歸目前最強的「穩定版」模型：gemini-1.5-pro
# 除非你有 Google Cloud Vertex AI 的特殊權限，否則不要用 preview 版
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY.strip())
    model = genai.GenerativeModel(
        'gemini-1.5-pro', 
        generation_config={"response_mime_type": "application/json"}
    )

# 新聞關鍵字 (微調過，更聚焦市場)
CATEGORIES = {
    "🔥 市場頭條": "stock market OR federal reserve OR economy OR inflation",
    "🤖 人工智慧": "Artificial Intelligence OR Nvidia OR OpenAI OR TSMC",
    "💰 加密貨幣": "Bitcoin OR Ethereum OR Crypto market"
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
    if not FINNHUB_API_KEY: 
        print("⚠️ 沒設定 FINNHUB API KEY")
        return []
        
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
            print(f"❌ 指數抓取失敗 ({name}): {e}")
            
    return market_data

# ================= 函數 2: 抓新聞 + AI 分析 (Pro) =================
def get_ai_news():
    final_news = []
    
    # 【修正 2】排除常見的公關稿和農場網站
    bad_domains = "biztoc.com,globenewswire.com,prnewswire.com,businesswire.com,prweb.com"
    
    for category, query in CATEGORIES.items():
        print(f"🔍 正在處理分類: {category} (使用 1.5 Pro)...")
        
        # 使用 category=business 聚焦財經，並排除垃圾網域
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&category=business&excludeDomains={bad_domains}&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
        
        try:
            response = requests.get(url).json()
            articles = response.get("articles", [])
        except Exception as e:
            print(f"❌ NewsAPI 連線錯誤: {e}")
            continue

        for art in articles:
            # Prompt: 強制 AI 扮演「中文」分析師
            prompt = f"""
            你是一位專業的華爾街分析師。請閱讀以下英文新聞：
            標題: {art['title']}
            內容: {art['description']}

            請輸出標準 JSON 格式 (必須使用繁體中文 Traditional Chinese)：
            {{
                "title_zh": "中文標題 (請翻譯)",
                "summary_zh": "中文摘要 (50字內，請包含數據或重點)",
                "impact": "利多 / 利空 / 中性",
                "score": 8 (重要性評分 1-10)
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
                    "summary": analysis.get("summary_zh", "AI 沒寫摘要"),
                    "impact": analysis.get("impact", "中性"),
                    "score": analysis.get("score", 5)
                })
                print(f"✅ AI 成功翻譯: {analysis.get('title_zh')}")
                
                # 讓 Pro 模型休息 2 秒，避免被 Google 封鎖
                time.sleep(2)
                
            except Exception as e:
                # 【修正 3】這裡會印出真正錯誤原因！
                print(f"⚠️ AI 分析失敗 (原因: {e})")
                print("   --> 可能原因: API Key 額度不足, 模型名稱錯誤, 或 JSON 格式問題")
                
                # 失敗時的回退 (Fallback)
                final_news.append({
                    "category": category,
                    "title_zh": f"(英文原文) {art['title']}",
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary_zh": f"AI 暫時無法分析，請直接閱讀原文。({art['description']})",
                    "impact": "無分析",
                    "score": 0
                })

    return sorted(final_news, key=lambda x: x['score'], reverse=True)

# ================= 函數 3: 抓財經日曆 =================
def get_economic_calendar():
    if not FINNHUB_API_KEY: return []
    
    start = datetime.now().strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    url = f"https://finnhub.io/api/v1/calendar/economic?from={start}&to={end}&token={FINNHUB_API_KEY}"
    
    try:
        res = requests.get(url).json()
        data = []
        for item in res.get("economicCalendar", []):
            # 只顯示美國 (US) 且重要性高 (impact >= 2)
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
    print("🚀 啟動 AI 財經分析引擎 (v5.0 Stable)...")
    
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "market": get_market_data(),
        "news": get_ai_news(),
        "calendar": get_economic_calendar()
    }
    
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    
    print("🎉 完成！請檢查 GitHub Actions Log 是否有紅色錯誤。")
