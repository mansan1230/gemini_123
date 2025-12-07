import os
import requests
import json
import yfinance as yf
import pandas as pd
from datetime import datetime
from deep_translator import GoogleTranslator

# ================= 設定區 =================
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# 初始化翻譯器
translator = GoogleTranslator(source='auto', target='zh-TW')

# Trader 關注清單
WATCHLIST = {
    "indices": {
        "🇺🇸 S&P 500": "^GSPC",
        "🇺🇸 Nasdaq": "^IXIC",
        "🇭🇰 恒生指數": "^HSI",
        "🇯🇵 日經 225": "^N225"
    },
    "crypto": {
        "🟠 Bitcoin": "BTC-USD",
        "🔵 Ethereum": "ETH-USD",
        "☀️ Solana": "SOL-USD"
    },
    "macro": {
        "😰 VIX 恐慌指數": "^VIX",
        "💵 美元指數 (DXY)": "DX-Y.NYB",
        "🇺🇸 10年美債": "^TNX",
        "🛢️ 原油 (WTI)": "CL=F",
        "🥇 黃金": "GC=F"
    }
}

# ================= 1. 技術分析函數 (RSI) =================
def calculate_rsi(series, period=14):
    delta = series.diff(1)
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_trader_data():
    print("📊 正在計算技術指標 & 抓取報價...")
    all_data = {"indices": [], "crypto": [], "macro": []}
    
    for category, items in WATCHLIST.items():
        for name, symbol in items.items():
            try:
                # 抓取過去 30 天數據來算 RSI
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="1mo")
                
                if len(hist) < 2: continue
                
                # 基礎數據
                price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                change = price - prev_close
                pct_change = (change / prev_close) * 100
                
                # 計算 RSI (只針對指數和加密貨幣)
                rsi_val = "-"
                signal = "觀望"
                
                if category in ["indices", "crypto"]:
                    hist['RSI'] = calculate_rsi(hist['Close'])
                    current_rsi = hist['RSI'].iloc[-1]
                    
                    if not pd.isna(current_rsi):
                        rsi_val = f"{current_rsi:.1f}"
                        if current_rsi > 70: signal = "⚠️ 超買 (高風險)"
                        elif current_rsi < 30: signal = "🟢 超賣 (反彈機會)"
                        else: signal = "中性"

                all_data[category].append({
                    "name": name,
                    "price": float(f"{price:.2f}"),
                    "change": float(f"{change:.2f}"),
                    "percent": float(f"{pct_change:.2f}"),
                    "rsi": rsi_val,
                    "signal": signal
                })
                print(f"   ✅ {name}: {price:.2f} | RSI: {rsi_val}")
                
            except Exception as e:
                print(f"   ❌ {name} 失敗: {e}")
                
    return all_data

# ================= 2. 快速新聞 (純翻譯) =================
def get_quick_news():
    if not NEWS_API_KEY: return []
    print("📰 正在抓取市場快訊...")
    
    # Trader 關注的關鍵字
    queries = [
        "crypto market", "bitcoin price", "stock market", 
        "federal reserve", "inflation", "earnings"
    ]
    query_str = " OR ".join(queries)
    
    # 權威媒體
    domains = "bloomberg.com,reuters.com,cnbc.com,coindesk.com,cointelegraph.com"
    
    url = f"https://newsapi.org/v2/everything?q={query_str}&domains={domains}&sortBy=publishedAt&pageSize=10&apiKey={NEWS_API_KEY}"
    
    news_list = []
    try:
        res = requests.get(url).json()
        articles = res.get("articles", [])
        
        for art in articles[:8]: # 只取前 8 篇最新
            try:
                # 直接翻譯標題，不做 AI 分析
                title_zh = translator.translate(art['title'])
                
                news_list.append({
                    "title": title_zh,
                    "source": art['source']['name'],
                    "time": art['publishedAt'][11:16], # 只取時間 HH:MM
                    "link": art['url']
                })
            except: continue
            
    except Exception as e:
        print(f"❌ 新聞錯誤: {e}")
        
    return news_list

# ================= 3. 主程式 =================
if __name__ == "__main__":
    print("🚀 啟動 Trader Dashboard (No-AI)...")
    
    trader_data = get_trader_data()
    
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "indices": trader_data["indices"],
        "crypto": trader_data["crypto"],
        "macro": trader_data["macro"],
        "news": get_quick_news()
    }
    
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
        
    print("🎉 數據聚合完成！")
