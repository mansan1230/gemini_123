import os
import requests
import json
import time # 必須引入 time
import google.generativeai as genai
from datetime import datetime, timedelta

# ================= 1. 設定區 & Debug =================
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# Debug: 檢查 Key 是否讀取成功
print(f"Checking Keys...")
print(f"- NEWS_API_KEY: {'✅ Found' if NEWS_API_KEY else '❌ Missing'}")
print(f"- GEMINI_API_KEY: {'✅ Found' if GEMINI_API_KEY else '❌ Missing'}")
print(f"- FINNHUB_API_KEY: {'✅ Found' if FINNHUB_API_KEY else '❌ Missing'}")

# 【修正 1】改用 gemini-1.5-pro (目前最穩定且支援中文最強的版本)
# 注意：gemini-2.0-pro 目前 API 尚未開放，用了一定會報錯
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"❌ 無法列出模型，原因: {e}")
    print("💡 提示：這通常代表 google-generativeai 套件版本太舊！")
    
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY.strip())
    model = genai.GenerativeModel(
        'gemini-2.0-flash-lite', 
        generation_config={"response_mime_type": "application/json"}
    )

# 新聞關鍵字
CATEGORIES = {
    "🔥 市場頭條": "stock market OR federal reserve OR inflation OR economy",
    "🤖 人工智慧": "Artificial Intelligence OR Nvidia OR OpenAI OR TSMC",
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
    if not FINNHUB_API_KEY:
        print("⚠️ 跳過指數抓取: 缺少 FINNHUB_API_KEY")
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
            print(f"❌ 指數 {name} 失敗: {e}")
            
    return market_data

def get_ai_news():
    if not NEWS_API_KEY:
        print("⚠️ 跳過新聞抓取: 缺少 NEWS_API_KEY")
        return []

    final_news = []
    # 排除垃圾農場文
    bad_domains = "biztoc.com,globenewswire.com,prnewswire.com,businesswire.com,prweb.com,marketwatch.com"
    
    for category, query in CATEGORIES.items():
        print(f"🔍 處理分類: {category}...")
        
        # 使用 category=business 確保是財經新聞
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&excludeDomains={bad_domains}&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
        
        try:
            response = requests.get(url).json()
            articles = response.get("articles", [])
            print(f"   -> 找到 {len(articles)} 篇原始文章")
        except Exception as e:
            print(f"❌ NewsAPI 連線失敗: {e}")
            continue

        for art in articles:
            # Prompt: 強制翻譯與中文分析
            prompt = f"""
            你是一位專業的華爾街分析師。請閱讀以下英文新聞：
            標題: {art['title']}
            內容: {art['description']}

            請輸出標準 JSON 格式 (必須使用繁體中文 Traditional Chinese)：
            {{
                "title_zh": "翻譯後的中文標題",
                "summary_zh": "50字內的中文深度摘要 (請包含數據)",
                "impact": "利多 / 利空 / 中性",
                "score": 8 (重要性評分 1-10, 純數字)
            }}
            """
            
            try:
                # 呼叫 AI
                ai_response = model.generate_content(prompt)
                analysis = json.loads(ai_response.text)
                
                final_news.append({
                    "category": category,
                    "title": analysis.get("title_zh", art['title']), # 用中文標題
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": analysis.get("summary_zh", "AI 未能生成摘要"), # 用中文摘要
                    "impact": analysis.get("impact", "中性"),
                    "score": analysis.get("score", 5)
                })
                print(f"   ✅ AI 成功翻譯: {analysis.get('title_zh')}")
                
                # 【修正 2】避免 Rate Limit (Pro 模型必須加這個)
                time.sleep(2)
                
            except Exception as e:
                # 【修正 3】印出具體錯誤原因，方便除錯
                print(f"   ❌ AI 分析失敗 (原因: {e})")
                
                # Fallback: 雖然 AI 失敗，但我們至少顯示原文
                final_news.append({
                    "category": category,
                    "title": f"(英) {art['title']}",
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": f"AI 暫時無法翻譯。原文: {art['description']}",
                    "impact": "無分析",
                    "score": 0
                })

    return sorted(final_news, key=lambda x: x['score'], reverse=True)

def get_economic_calendar():
    if not FINNHUB_API_KEY:
        print("⚠️ 跳過日曆: 缺少 FINNHUB_API_KEY")
        return []
    
    print("📅 正在抓取財經日曆...")
    
    # 抓未來 14 天 (擴大範圍)
    start = datetime.now().strftime("%Y-%m-%d")
    end = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")
    
    url = f"https://finnhub.io/api/v1/calendar/economic?from={start}&to={end}&token={FINNHUB_API_KEY}"
    
    try:
        res = requests.get(url).json()
        raw_data = res.get("economicCalendar", [])
        
        data = []
        for item in raw_data:
            # 只要是美國 (US) 就抓
            if item['country'] == 'US': 
                data.append({
                    "event": item['event'],
                    "time": item['time'],
                    "actual": str(item['actual'] if item['actual'] is not None else "待公布"),
                    "estimate": str(item['estimate'] if item['estimate'] is not None else "-"),
                    "prev": str(item['prev'] if item['prev'] is not None else "-")
                })
        
        return data[:10]
    except Exception as e:
        print(f"❌ 日曆抓取失敗: {e}")
        return []

# ================= 3. 主程式 =================
if __name__ == "__main__":
    print("🚀 啟動 v7.0 修復版...")
    
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "market": get_market_data(),
        "news": get_ai_news(),
        "calendar": get_economic_calendar()
    }
    
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    
    print("🎉 完成！請檢查 daily_news.json")
