import os
import requests
import json
import time
import yfinance as yf # 引入 Yahoo Finance
import google.generativeai as genai
from datetime import datetime

# ================= 1. 設定區 =================
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Debug
print(f"Checking Keys...")
print(f"- NEWS: {'✅' if NEWS_API_KEY else '❌'}")
print(f"- GEMINI: {'✅' if GEMINI_API_KEY else '❌'}")

# 模型設定 (Gemini 1.5 Flash)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY.strip())
    model = genai.GenerativeModel(
        'gemini-2.0-flash',
        generation_config={"response_mime_type": "application/json"}
    )

# 新聞關鍵字
CATEGORIES = {
    "🔥 市場頭條": "stock market OR federal reserve OR economy",
    "🤖 人工智慧": "Artificial Intelligence OR Nvidia OR OpenAI",
    "💰 加密貨幣": "Bitcoin OR Ethereum OR Crypto"
}

# ================= 2. 抓取函數 (yfinance 版) =================

def get_market_and_macro():
    """
    一次過抓取「市場指數」同「宏觀指標」
    使用 yfinance，完全免費，不用 Key
    """
    print("📊 正在透過 Yahoo Finance 抓取數據...")
    
    # 定義代碼
    tickers = {
        # --- 市場指數 ---
        "🇺🇸 S&P 500": "^GSPC",
        "🇺🇸 Nasdaq": "^IXIC",
        "🇭🇰 恒生指數": "^HSI",
        "🪙 Bitcoin": "BTC-USD",
        
        # --- 宏觀指標 (取代日曆) ---
        "😰 恐慌指數 (VIX)": "^VIX",
        "🇺🇸 10年美債": "^TNX",
        "💵 美元指數": "DX-Y.NYB",
        "🛢️ 原油 (WTI)": "CL=F"
    }
    
    data_list = []
    
    for name, symbol in tickers.items():
        try:
            # 抓取 Ticker
            ticker = yf.Ticker(symbol)
            # 取得歷史資料 (拿最後兩天來計算漲跌)
            hist = ticker.history(period="5d")
            
            if len(hist) >= 2:
                price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                change = price - prev_close
                percent = (change / prev_close) * 100
                
                # 分類：是用於上方 Bar 還是右側列表
                is_macro = name in ["😰 恐慌指數 (VIX)", "🇺🇸 10年美債", "💵 美元指數", "🛢️ 原油 (WTI)"]
                
                data_list.append({
                    "name": name,
                    "price": float(f"{price:.2f}"),
                    "change": float(f"{change:.2f}"),
                    "percent": float(f"{percent:.2f}"),
                    "is_macro": is_macro # 標記一下，方便前端分開顯示
                })
                print(f"   ✅ {name}: {price:.2f}")
            else:
                print(f"   ⚠️ {name} 數據不足")
                
        except Exception as e:
            print(f"   ❌ {name} 失敗: {e}")
            
    return data_list

def get_ai_news():
    if not NEWS_API_KEY: return []
    final_news = []
    bad_domains = "biztoc.com,globenewswire.com,prnewswire.com,businesswire.com,prweb.com,marketwatch.com"
    
    for category, query in CATEGORIES.items():
        print(f"🔍 處理新聞: {category}...")
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&excludeDomains={bad_domains}&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
        
        try:
            response = requests.get(url).json()
            articles = response.get("articles", [])
        except: continue

        for art in articles:
            prompt = f"""
            你是一位華爾街分析師。請閱讀新聞：
            標題: {art['title']}
            內容: {art['description']}

            請回傳單一 JSON 物件 (繁體中文)：
            {{
                "title_zh": "中文標題",
                "summary_zh": "50字內中文摘要",
                "impact": "利多 / 利空 / 中性",
                "score": 8
            }}
            """
            try:
                ai_response = model.generate_content(prompt)
                analysis = json.loads(ai_response.text)
                if isinstance(analysis, list): analysis = analysis[0]
                
                final_news.append({
                    "category": category,
                    "title": analysis.get("title_zh", art['title']),
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": analysis.get("summary_zh", "AI 未能生成摘要"),
                    "impact": analysis.get("impact", "中性"),
                    "score": analysis.get("score", 5)
                })
                print(f"   ✅ 新聞分析成功: {analysis.get('title_zh')}")
                time.sleep(2)
            except Exception as e:
                print(f"   ⚠️ 新聞失敗: {e}")
                # Fallback
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

# ================= 3. 主程式 =================
if __name__ == "__main__":
    print("🚀 啟動 No-Finnhub 免費版 (yfinance)...")
    
    # 抓取所有數據
    all_market_data = get_market_and_macro()
    
    # 分拆數據給前端
    market_indices = [x for x in all_market_data if not x['is_macro']]
    macro_indicators = [x for x in all_market_data if x['is_macro']]
    
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "market": market_indices, # 上方的指數
        "news": get_ai_news(),    # 中間的新聞
        "macro": macro_indicators # 右邊的宏觀數據 (取代日曆)
    }
    
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    print("🎉 完成！")
