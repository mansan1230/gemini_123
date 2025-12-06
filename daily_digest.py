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
    
    # 【改動 1】定義「權威媒體」名單 (Whitelist)
    # 與其過濾垃圾，不如直接指定只看大佬。這樣抓到的新聞 99% 都是重點。
    # 包含：路透、CNBC、彭博、雅虎財經、華爾街日報、TechCrunch (科技)、CoinDesk (幣圈)
    trusted_domains = "reuters.com,cnbc.com,bloomberg.com,finance.yahoo.com,wsj.com,techcrunch.com,coindesk.com,decrypt.co"
    
    for category, query in CATEGORIES.items():
        print(f"🔍 處理新聞: {category} (篩選權威媒體)...")
        
        # 【改動 2】API 參數大升級
        # - domains={trusted_domains}: 只從上面的權威媒體抓
        # - sortBy=popularity: 改抓「熱門度」最高的新聞，確保是市場焦點
        # - pageSize=10: 擴大搜尋範圍到 10 篇 (讀多啲)
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&domains={trusted_domains}&sortBy=popularity&pageSize=10&apiKey={NEWS_API_KEY}"
        
        try:
            response = requests.get(url).json()
            articles = response.get("articles", [])
            print(f"   -> 從權威媒體找到 {len(articles)} 篇熱門報導")
        except: continue

        # 【改動 3】雖然抓了 10 篇，但為了不爆 AI 額度，我們只分析「前 5 篇」
        # 因為已經按熱門度排序了，前 5 篇一定是最重要的
        for art in articles[:5]:
            prompt = f"""
            你是一位華爾街基金經理。請閱讀以下重要財經新聞：
            標題: {art['title']}
            內容: {art['description']}

            請嚴格判斷：這則新聞對市場有多重要？
            - 如果是重大政策、財報、併購或崩盤，score 給 8-10 分。
            - 如果只是普通觀點或小新聞，score 給 1-4 分。

            請回傳單一 JSON 物件 (繁體中文)：
            {{
                "title_zh": "中文標題",
                "summary_zh": "50字內中文精華摘要",
                "impact": "利多 / 利空 / 中性",
                "score": 8
            }}
            """
            
            try:
                ai_response = model.generate_content(prompt)
                analysis = json.loads(ai_response.text)
                
                if isinstance(analysis, list): analysis = analysis[0]
                
                # 只有分數大於 0 的才加入 (過濾掉 AI 認為完全不重要的)
                if analysis.get("score", 0) > 0:
                    final_news.append({
                        "category": category,
                        "title": analysis.get("title_zh", art['title']),
                        "link": art['url'],
                        "date": art['publishedAt'][:10],
                        "summary": analysis.get("summary_zh", "AI 未能生成摘要"),
                        "impact": analysis.get("impact", "中性"),
                        "score": analysis.get("score", 5)
                    })
                    print(f"   ✅ 分析成功 (分): {analysis.get('title_zh')} (Score: {analysis.get('score')})")
                
                time.sleep(2) # 休息一下
                
            except Exception as e:
                print(f"   ⚠️ 分析失敗: {e}")
                continue

    # 最後排序：分數高的放最前面
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
