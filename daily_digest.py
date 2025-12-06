import os
import requests
import json
import google.generativeai as genai
from datetime import datetime, timedelta

# ================= 設定區 =================
# 從環境變數讀取 Keys
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY") # 新增這個

# 設定 Gemini
genai.configure(api_key=GEMINI_API_KEY.strip())
model = genai.GenerativeModel('gemini-pro')

# 定義你想抓的新聞分類 (關鍵字)
CATEGORIES = {
    "🔥 市場頭條": "finance OR stock market OR economy",
    "🤖 人工智慧": "Artificial Intelligence OR Nvidia OR OpenAI",
    "💰 加密貨幣": "Bitcoin OR Ethereum OR Crypto"
}

# ================= 函數 1: 抓新聞並用 AI 分析 =================
def get_ai_news():
    final_news = []
    
    for category, query in CATEGORIES.items():
        print(f"正在抓取: {category}...")
        # 加入 &excludeDomains=biztoc.com 來過濾掉這個網站
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&excludeDomains=biztoc.com&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
        response = requests.get(url).json()
        
        articles = response.get("articles", [])
        
        for art in articles:
            # 讓 Gemini 變身專業分析師
            prompt = f"""
            你是一位專業的華爾街分析師。請閱讀以下新聞並以繁體中文 (Traditional Chinese) 回覆。
            
            新聞標題: {art['title']}
            內容: {art['description']}
            
            請輸出一段 JSON 格式 (不要 Markdown)，包含以下欄位：
            1. summary: 簡短摘要 (50字內)
            2. impact: 這則新聞對市場的影響 (例如：利好美股、利空科技股、中性)
            3. score: 重要性評分 (1-10分)
            """
            
            try:
                # 呼叫 Gemini
                ai_response = model.generate_content(prompt)
                ai_text = ai_response.text.strip().replace("```json", "").replace("```", "")
                analysis = json.loads(ai_text) # 嘗試轉成 JSON
                
                final_news.append({
                    "category": category,
                    "title": art['title'],
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": analysis.get("summary", "無法生成摘要"),
                    "impact": analysis.get("impact", "一般"),
                    "score": analysis.get("score", 5)
                })
            except Exception as e:
                print(f"AI 分析失敗: {e}")
                # 失敗時的回退方案
                final_news.append({
                    "category": category,
                    "title": art['title'],
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": art['description'],
                    "impact": "無分析",
                    "score": 0
                })
                
    # 根據分數排序，重要的放前面
    return sorted(final_news, key=lambda x: x['score'], reverse=True)

# ================= 函數 2: 抓財經日曆 (Finnhub) =================
def get_economic_calendar():
    if not FINNHUB_API_KEY:
        return []
    
    # 抓今天到未來 3 天的數據
    start_date = datetime.now().strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    
    url = f"https://finnhub.io/api/v1/calendar/economic?from={start_date}&to={end_date}&token={FINNHUB_API_KEY}"
    
    try:
        res = requests.get(url).json()
        economic_data = res.get("economicCalendar", [])
        
        # 只過濾重要數據 (例如 impact 比較高的，或者只要 US 數據)
        important_data = []
        for item in economic_data:
            if item['country'] == 'US': # 只看美國數據
                important_data.append({
                    "event": item['event'],
                    "time": item['time'],
                    "actual": item['actual'] if item['actual'] else "待公布",
                    "estimate": item['estimate'] if item['estimate'] else "-",
                    "prev": item['prev'] if item['prev'] else "-"
                })
        return important_data
    except Exception as e:
        print(f"抓取日曆失敗: {e}")
        return []

# ================= 主程式 =================
if __name__ == "__main__":
    print("開始執行...")
    
    news_data = get_ai_news()
    calendar_data = get_economic_calendar()
    
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "news": news_data,
        "calendar": calendar_data
    }
    
    # 存檔
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    
    print("完成！資料已更新。")
