import os
import requests
import json
import google.generativeai as genai
from datetime import datetime

NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# 設定 Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash') # 使用 Flash 模型省錢且快

def fetch_crypto_news():
    """從 CoinGecko 或 NewsAPI 抓取加密貨幣新聞"""
    url = f"https://newsapi.org/v2/everything?q=crypto OR bitcoin OR ethereum&sortBy=publishedAt&language=en&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    return response.json().get('articles', [])[:10] # 取最新的 10 條作為範例

def fetch_stock_news():
    """抓取股市宏觀新聞 (Fed, rate hike, S&P500)"""
    url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey={NEWS_API_KEY}"
    response = requests.get(url)
    return response.json().get('articles', [])[:10]

def analyze_with_ai(news_data):
    """將新聞餵給 AI 進行分析與過濾"""
    
    prompt = f"""
    You are a professional financial analyst. Here is a list of recent news headlines:
    {json.dumps(news_data)}

    Task:
    1. Filter out noise. Pick the TOP 3 stories that will genuinely impact the Market (Stocks or Crypto) in the next 24 hours.
    2. Format the output strictly as a JSON list.
    3. Each item must have: 'title', 'impact_score' (1-10), 'market_type' (Crypto/Stock/Both), and 'summary' (Explain WHY it moves the market in Traditional Chinese 繁體中文).
    
    JSON Output only:
    """
    
    response = model.generate_content(prompt)
    # 這裡通常需要清理 markdown 格式，簡單起見直接回傳 text
    return response.text.strip().replace('```json', '').replace('```', '')

def main():
    print("正在抓取新聞...")
    crypto_news = fetch_crypto_news()
    stock_news = fetch_stock_news()
    
    combined_news = []
    # 提取標題以減少 token 消耗
    for n in crypto_news + stock_news:
        combined_news.append({"title": n['title'], "source": n['source']['name']})
    
    print("正在進行 AI 分析...")
    analysis_json = analyze_with_ai(combined_news)
    
    # 儲存結果為 JSON 供網頁讀取
    output_data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "analysis": json.loads(analysis_json)
    }
    
    with open("daily_news.json", "w", encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print("完成！報告已生成: daily_news.json")

if __name__ == "__main__":
    main()
