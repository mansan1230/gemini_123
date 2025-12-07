import os
import requests
import json
import yfinance as yf
import pandas as pd
from datetime import datetime
from deep_translator import GoogleTranslator

# ================= 設定區 =================
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
translator = GoogleTranslator(source='auto', target='zh-TW')

RSI_PERIOD = 14 
SMA_PERIOD = 50 # 用 50日線看中期趨勢

WATCHLIST = {
    "indices": {
        "🇺🇸 S&P 500": "^GSPC",
        "🇺🇸 Nasdaq": "^IXIC",
        "🇭🇰 恒生指數": "^HSI",
        "🇯🇵 日經 225": "^N225",
        "🇪🇺 德國 DAX": "^GDAXI"
    },
    "crypto": {
        "🟠 Bitcoin": "BTC-USD",
        "🔵 Ethereum": "ETH-USD",
        "☀️ Solana": "SOL-USD"
    },
    "macro": {
        "😰 恐慌指數 (VIX)": "^VIX",
        "🇺🇸 10年美債": "^TNX",
        "💵 美元指數": "DX-Y.NYB",
        "💴 USD/JPY": "JPY=X",
        "💶 EUR/USD": "EURUSD=X"
    },
    "commodities": {
        "🥇 黃金": "GC=F",
        "🛢️ 原油 (WTI)": "CL=F",
        "🏭 銅": "HG=F",
        "💻 科技 (XLK)": "XLK",
        "🏦 金融 (XLF)": "XLF"
    }
}

# ================= 1. 技術分析函數 =================
def calculate_technicals(ticker_symbol):
    try:
        # 抓取足夠計算 SMA50 的數據 (大約 3 個月)
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="3mo")
        
        if len(hist) < SMA_PERIOD: return None

        # 1. 基礎數據
        price = hist['Close'].iloc[-1]
        prev_close = hist['Close'].iloc[-2]
        change = price - prev_close
        pct_change = (change / prev_close) * 100

        # 2. RSI 計算
        delta = hist['Close'].diff(1)
        gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
        rs = gain / loss
        rsi_series = 100 - (100 / (1 + rs))
        current_rsi = rsi_series.iloc[-1]

        # 3. SMA 趨勢計算 (50日線)
        sma_series = hist['Close'].rolling(window=SMA_PERIOD).mean()
        current_sma = sma_series.iloc[-1]
        
        # 判斷趨勢
        trend = "震盪"
        if price > current_sma * 1.01: trend = "📈 多頭"  # 價格在均線上方 1%
        elif price < current_sma * 0.99: trend = "📉 空頭" # 價格在均線下方 1%

        return {
            "price": float(f"{price:.2f}"),
            "change": float(f"{change:.2f}"),
            "percent": float(f"{pct_change:.2f}"),
            "rsi": f"{current_rsi:.1f}" if not pd.isna(current_rsi) else "-",
            "trend": trend,
            "sma": f"{current_sma:.2f}"
        }
    except Exception as e:
        print(f"Error {ticker_symbol}: {e}")
        return None

def get_trader_data():
    print("📊 正在計算 RSI + SMA 趨勢...")
    all_data = {"indices": [], "crypto": [], "macro": [], "commodities": []}
    
    for category, items in WATCHLIST.items():
        for name, symbol in items.items():
            data = calculate_technicals(symbol)
            if data:
                # VIX 不算趨勢，稍微處理一下
                if "VIX" in name: 
                    data["trend"] = "-"
                    data["rsi"] = "-"

                all_data[category].append({
                    "name": name,
                    **data # 展開字典
                })
                print(f"   ✅ {name}: {data['price']} | {data['trend']}")
                
    return all_data

# ================= 2. 額外：Crypto 恐慌貪婪指數 =================
def get_crypto_sentiment():
    try:
        url = "https://api.alternative.me/fng/"
        res = requests.get(url).json()
        data = res['data'][0]
        return {
            "value": data['value'],
            "status": data['value_classification']
        }
    except:
        return {"value": "-", "status": "Unknown"}

# ================= 3. 新聞 (保持不變) =================
def get_quick_news():
    if not NEWS_API_KEY: return []
    print("📰 抓取新聞...")
    queries = ["market crash", "bitcoin", "nvidia", "federal reserve", "inflation", "recession", "gold price"]
    query_str = " OR ".join(queries)
    domains = "bloomberg.com,reuters.com,cnbc.com,coindesk.com,wsj.com,finance.yahoo.com"
    url = f"https://newsapi.org/v2/everything?q={query_str}&domains={domains}&sortBy=publishedAt&pageSize=20&apiKey={NEWS_API_KEY}"
    
    news_list = []
    try:
        res = requests.get(url).json()
        for art in res.get("articles", [])[:15]: 
            try:
                title_zh = translator.translate(art['title'])
                news_list.append({
                    "title": title_zh,
                    "source": art['source']['name'],
                    "time": art['publishedAt'][11:16], 
                    "link": art['url']
                })
            except: continue
    except: pass
    return news_list

# ================= 4. 主程式 =================
if __name__ == "__main__":
    print("🚀 啟動 v18.0 趨勢增強版...")
    
    trader_data = get_trader_data()
    fng = get_crypto_sentiment() # 抓取貪婪指數
    
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "crypto_fng": fng, # 新增這個欄位
        "indices": trader_data["indices"],
        "crypto": trader_data["crypto"],
        "macro": trader_data["macro"],
        "commodities": trader_data["commodities"],
        "news": get_quick_news()
    }
    
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
        
    print("🎉 完成！")
