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

# RSI 設定：標準為 14 天
RSI_PERIOD = 14 

# Trader 全球戰情室關注清單
WATCHLIST = {
    "indices": {
        "🇺🇸 S&P 500": "^GSPC",
        "🇺🇸 Nasdaq": "^IXIC",
        "🇭🇰 恒生指數": "^HSI",
        "🇯🇵 日經 225": "^N225",
        "🇪🇺 德國 DAX": "^GDAXI"  # 新增歐洲指標
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
        "💴 USD/JPY (日圓)": "JPY=X",   # 新增匯率
        "💶 EUR/USD (歐元)": "EURUSD=X" # 新增匯率
    },
    "commodities": { # 新增商品與板塊
        "🥇 黃金": "GC=F",
        "🛢️ 原油 (WTI)": "CL=F",
        "🏭 銅 (經濟指標)": "HG=F",
        "💻 美股科技 (XLK)": "XLK",
        "🏦 美股金融 (XLF)": "XLF"
    }
}

# ================= 1. 技術分析函數 =================
def calculate_rsi(series, period=14):
    delta = series.diff(1)
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_trader_data():
    print("📊 正在計算全球市場數據 & RSI...")
    all_data = {"indices": [], "crypto": [], "macro": [], "commodities": []}
    
    for category, items in WATCHLIST.items():
        for name, symbol in items.items():
            try:
                # 抓取過去 2 個月數據 (確保夠算 RSI)
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period="2mo")
                
                if len(hist) < 2: continue
                
                # 基礎數據
                price = hist['Close'].iloc[-1]
                prev_close = hist['Close'].iloc[-2]
                change = price - prev_close
                pct_change = (change / prev_close) * 100
                
                # 計算 RSI
                rsi_val = "-"
                signal = "中性"
                
                # 所有資產都算 RSI，除了 VIX (VIX 算 RSI 意義不大)
                if "VIX" not in name:
                    hist['RSI'] = calculate_rsi(hist['Close'], period=RSI_PERIOD)
                    current_rsi = hist['RSI'].iloc[-1]
                    
                    if not pd.isna(current_rsi):
                        rsi_val = f"{current_rsi:.1f}"
                        if current_rsi > 70: signal = "⚠️ 超買"
                        elif current_rsi < 30: signal = "🟢 超賣"
                        elif current_rsi > 60: signal = "強勢"
                        elif current_rsi < 40: signal = "弱勢"

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

# ================= 2. 快速新聞 (加量版) =================
def get_quick_news():
    if not NEWS_API_KEY: return []
    print("📰 正在抓取大量市場快訊...")
    
    # 增加關鍵字廣度
    queries = [
        "market crash", "bitcoin", "nvidia", "federal reserve", 
        "inflation", "recession", "gold price", "oil price", "china economy"
    ]
    query_str = " OR ".join(queries)
    
    # 權威媒體
    domains = "bloomberg.com,reuters.com,cnbc.com,coindesk.com,wsj.com,finance.yahoo.com"
    
    # pageSize 改成 30 (抓多一點)
    url = f"https://newsapi.org/v2/everything?q={query_str}&domains={domains}&sortBy=publishedAt&pageSize=30&apiKey={NEWS_API_KEY}"
    
    news_list = []
    try:
        res = requests.get(url).json()
        articles = res.get("articles", [])
        
        # 處理前 20 篇 (太多會翻譯太久)
        for art in articles[:20]: 
            try:
                title_zh = translator.translate(art['title'])
                
                news_list.append({
                    "title": title_zh,
                    "source": art['source']['name'],
                    "time": art['publishedAt'][11:16], 
                    "link": art['url']
                })
            except: continue
            
    except Exception as e:
        print(f"❌ 新聞錯誤: {e}")
        
    return news_list

# ================= 3. 主程式 =================
if __name__ == "__main__":
    print("🚀 啟動 v14.0 宏觀 Trader 面板...")
    
    trader_data = get_trader_data()
    
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "indices": trader_data["indices"],
        "crypto": trader_data["crypto"],
        "macro": trader_data["macro"],
        "commodities": trader_data["commodities"], # 新增這欄
        "news": get_quick_news()
    }
    
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
        
    print("🎉 數據聚合完成！")
