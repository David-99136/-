import requests
from datetime import datetime

def get_fear_greed_index():
    print("📡 啟動【全球心理感測器】：正在擷取 CNN Fear & Greed Index...")
    
    endpoints = [
        "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
        "https://production.dataviz.cnn.io/index/fearandgreed/v2"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.cnn.com/markets/fear-and-greed",
        "Origin": "https://www.cnn.com"
    }

    data = None
    for url in endpoints:
        try:
            target_url = f"{url}/{datetime.now().strftime('%Y-%m-%d')}" if "graphdata" in url else url
            res = requests.get(target_url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                break
        except Exception:
            continue

    # 若抓取失敗，回傳中性分數 50，避免 agent.py 崩潰
    if not data:
        print("❌ CNN API 拒絕存取，回傳中性預設值 50。")
        return 50.0

    fgi_core = data.get('fear_and_greed', data.get('fear_and_greed_historical', {}))
    
    score = fgi_core.get('score', 50)
    if isinstance(fgi_core.get('data'), list) and len(fgi_core['data']) > 0:
        score = fgi_core['data'][-1].get('y', score)
        
    rating = fgi_core.get('rating', 'unknown')
    
    print(f"🌍 CNN Global Sentiment Index: {score:.1f} ({rating.upper()})")
    return float(score)

if __name__ == "__main__":
    print(f"Test Score: {get_fear_greed_index()}")