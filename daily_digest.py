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
SMA_PERIOD = 50 

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
    "shipping": { # 🔥 新增：航運數據 (運價替代指標)
        "🚢 乾散貨 ETF (BDI)": "BDRY",
        "🌊 全球航運 ETF": "BOAT",
        "📦 ZIM (集裝箱)": "ZIM",
        "⚓ Maersk (馬士基)": "AMKBY"
    },
    "futures": {
        "📈 標普期貨": "ES=F",
        "💻 納指期貨": "NQ=F",
        "🛑 道指期貨": "YM=F"
    },
    "macro": {
        "😰 恐慌指數 (VIX)": "^VIX",
        "🇺🇸 10年美債": "^TNX",
        "💵 美元指數": "DX-Y.NYB",
        "💴 USD/JPY": "JPY=X"
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
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="3mo")
        if len(hist) < SMA_PERIOD: return None

        # 數據
        price = hist['Close'].iloc[-1]
        change = price - hist['Close'].iloc[-2]
        pct_change = (change / hist['Close'].iloc[-2]) * 100

        # RSI
        delta = hist['Close'].diff(1)
        gain = (delta.where(delta > 0, 0)).rolling(window=RSI_PERIOD).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=RSI_PERIOD).mean()
        rs = gain / loss
        current_rsi = (100 - (100 / (1 + rs))).iloc[-1]

        # SMA Trend
        current_sma = hist['Close'].rolling(window=SMA_PERIOD).mean().iloc[-1]
        trend = "震盪"
        if price > current_sma * 1.01: trend = "📈 多頭"
        elif price < current_sma * 0.99: trend = "📉 空頭"

        return {
            "price": float(f"{price:.2f}"),
            "change": float(f"{change:.2f}"),
            "percent": float(f"{pct_change:.2f}"),
            "rsi": f"{current_rsi:.1f}" if not pd.isna(current_rsi) else "-",
            "trend": trend
        }
    except: return None

def get_trader_data():
    print("📊 計算全球數據中...")
    all_data = {k: [] for k in WATCHLIST.keys()}
    
    for category, items in WATCHLIST.items():
        for name, symbol in items.items():
            data = calculate_technicals(symbol)
            if data:
                if "VIX" in name or "=" in symbol: 
                    data["trend"] = "-"
                
                all_data[category].append({"name": name, **data})
                print(f"   ✅ {name} Done")
    return all_data

# ================= 2. 恐慌指數 =================
def get_crypto_sentiment():
    try:
        res = requests.get("https://api.alternative.me/fng/").json()
        return res['data'][0]
    except: return {"value": "-", "status": "Unknown"}

# ================= 3. 新聞 =================
def get_quick_news():
    if not NEWS_API_KEY: return []
    print("📰 抓新聞...")
    # 加入 shipping, freight 關鍵字
    queries = ["market crash", "bitcoin", "nvidia", "federal reserve", "inflation", "shipping rates", "freight cost"]
    query_str = " OR ".join(queries)
    domains = "bloomberg.com,reuters.com,cnbc.com,coindesk.com,wsj.com,finance.yahoo.com,gcaptain.com"
    url = f"https://newsapi.org/v2/everything?q={query_str}&domains={domains}&sortBy=publishedAt&pageSize=30&apiKey={NEWS_API_KEY}"
    
    news_list = []
    try:
        res = requests.get(url).json()
        for art in res.get("articles", [])[:20]: 
            try:
                title_zh = translator.translate(art['title'])
                news_list.append({
                    "title": title_zh, "source": art['source']['name'],
                    "time": art['publishedAt'][11:16], "link": art['url']
                })
            except: continue
    except: pass
    return news_list

# ================= 4. 主程式 =================
if __name__ == "__main__":
    print("🚀 啟動 God Mode v21 (Shipping)...")
    data = get_trader_data()
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "crypto_fng": get_crypto_sentiment(),
        "data": data,
        "news": get_quick_news()
    }
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    print("🎉 完成！")
