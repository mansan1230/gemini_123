import os
import requests
import json
import google.generativeai as genai
from datetime import datetime, timedelta

# ================= 設定區 =================
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")

# 檢查 Key 是否存在 (除錯用)
if not GEMINI_API_KEY:
    print("⚠️ 警告: 找不到 GEMINI_API_KEY")
if not FINNHUB_API_KEY:
    print("⚠️ 警告: 找不到 FINNHUB_API_KEY")

# 設定 Gemini (改用 gemini-1.5-flash，速度快且便宜)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY.strip())
    model = genai.GenerativeModel('gemini-1.5-flash')

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
        # 加入 excludeDomains 避免抓到擋爬蟲的網站
        url = f"https://newsapi.org/v2/everything?q={query}&language=en&excludeDomains=biztoc.com&sortBy=publishedAt&pageSize=3&apiKey={NEWS_API_KEY}"
        
        try:
            response = requests.get(url).json()
            articles = response.get("articles", [])
        except Exception as e:
            print(f"❌ NewsAPI 連線失敗: {e}")
            continue

        for art in articles:
            # 簡化 Prompt，提高成功率
            prompt = f"""
            請擔任財經分析師。閱讀以下新聞：
            標題: {art['title']}
            內容: {art['description']}

            請用「繁體中文」回答，並嚴格依照 JSON 格式輸出：
            {{
                "summary": "50字內的中文摘要",
                "impact": "對市場影響 (利多/利空/中性)",
                "score": 評分 (1-10, 數字)
            }}
            注意：直接回傳 JSON，不要加 ```json 或其他文字。
            """
            
            try:
                # 呼叫 AI
                ai_response = model.generate_content(prompt)
                ai_text = ai_response.text.strip()
                
                # 清理可能出現的 markdown 符號
                if ai_text.startswith("```"):
                    ai_text = ai_text.replace("```json", "").replace("```", "")
                
                analysis = json.loads(ai_text)
                
                final_news.append({
                    "category": category,
                    "title": art['title'],
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": analysis.get("summary", "AI 未生成摘要"),
                    "impact": analysis.get("impact", "一般"),
                    "score": analysis.get("score", 5)
                })
                print(f"✅ AI 成功分析: {art['title'][:10]}...")
                
            except Exception as e:
                # 這裡會印出為什麼 AI 失敗，很重要！
                print(f"❌ AI 分析失敗 (原因: {e})")
                print(f"   AI 回傳內容: {ai_response.text if 'ai_response' in locals() else '無回應'}")
                
                # 失敗時的回退方案 (保留原文)
                final_news.append({
                    "category": category,
                    "title": art['title'],
                    "link": art['url'],
                    "date": art['publishedAt'][:10],
                    "summary": f"(AI 分析失敗，顯示原文) {art['description']}",
                    "impact": "無分析",
                    "score": 0
                })
                
    return sorted(final_news, key=lambda x: x['score'], reverse=True)

# ================= 函數 2: 抓財經日曆 =================
def get_economic_calendar():
    if not FINNHUB_API_KEY:
        print("⚠️ 沒設定 FINNHUB_API_KEY，跳過日曆抓取")
        return []
    
    start_date = datetime.now().strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d") # 抓未來 7 天試試
    
    url = f"https://finnhub.io/api/v1/calendar/economic?from={start_date}&to={end_date}&token={FINNHUB_API_KEY}"
    
    try:
        res = requests.get(url).json()
        if "economicCalendar" not in res:
            print(f"⚠️ Finnhub 回傳異常: {res}")
            return []
            
        economic_data = res.get("economicCalendar", [])
        
        # 篩選重要數據 (例如 impact 比較高的，或者只要 US)
        important_data = []
        for item in economic_data:
            if item['country'] == 'US': 
                important_data.append({
                    "event": item['event'],
                    "time": item['time'],
                    "actual": str(item['actual']) if item['actual'] is not None else "待公布",
                    "estimate": str(item['estimate']) if item['estimate'] is not None else "-",
                    "prev": str(item['prev']) if item['prev'] is not None else "-"
                })
        print(f"✅ 成功抓到 {len(important_data)} 筆財經數據")
        return important_data
    except Exception as e:
        print(f"❌ 抓取日曆失敗: {e}")
        return []

# ================= 主程式 =================
if __name__ == "__main__":
    print("🚀 開始執行自動化新聞...")
    
    news_data = get_ai_news()
    calendar_data = get_economic_calendar()
    
    final_output = {
        "update_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "news": news_data,
        "calendar": calendar_data
    }
    
    with open("daily_news.json", "w", encoding="utf-8") as f:
        json.dump(final_output, f, ensure_ascii=False, indent=2)
    
    print("🎉 完成！daily_news.json 已更新。")
