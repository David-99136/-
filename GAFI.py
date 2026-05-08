import requests
from datetime import datetime

def get_gafi_v2026():
    print("📡 啟動【全球心理感測器】：偵測到 404 偏移，正在切換備援路徑...")
    
    # 2026 年修正後的數據路徑 (嘗試 graphdata 與 v2 結構)
    # CNN 現在會檢查特定的 Referer 與 User-Agent
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
    success_url = ""
    
    for url in endpoints:
        try:
            # 針對 graphdata 路徑，CNN 有時要求加上起始日期
            target_url = f"{url}/{datetime.now().strftime('%Y-%m-%d')}" if "graphdata" in url else url
            res = requests.get(target_url, headers=headers, timeout=10)
            
            if res.status_code == 200:
                data = res.json()
                success_url = target_url
                break
        except Exception:
            continue

    if not data:
        print("❌ 訊號全數中斷：CNN 已變更 API 架構。")
        print("💡 建議：改用第三方庫 `pip install fear-greed` 或手動檢查瀏覽器 Network 標籤。")
        return

    # 解析核心數據 (依據 2026 最新 JSON 結構)
    # 部分版本數據封裝在 'fear_and_greed' 或 'fear_and_greed_historical' 中
    fgi_core = data.get('fear_and_greed', data.get('fear_and_greed_historical', {}))
    
    # 獲取當前分數 (若為歷史數據則取最後一筆)
    score = fgi_core.get('score', 0)
    if isinstance(fgi_core.get('data'), list):
        score = fgi_core['data'][-1].get('y', 0)
        
    rating = fgi_core.get('rating', 'unknown')
    
    print("\n" + "="*50)
    print(f"🌍 CNN Global Sentiment Index - GAFI")
    print("="*50)
    print(f"📅 擷取時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📈 當前指數: {score:.1f} ({rating.upper()})")
    print("-" * 50)
    
    # 策略決策系統
    if score <= 25:
        status = "🚨 【極度恐慌 (Extreme Fear)】"
        advice = "市場情緒探底，通常是反向買進良機。檢查 2330 是否有 MACD 底背離！"
    elif score >= 75:
        status = "🔥 【極度貪婪 (Extreme Greed)】"
        advice = "市場過熱，建議檢查 0050/00919 是否出現 RSI 過熱訊號。"
    else:
        status = "🟢 【情緒中性】"
        advice = "市場波動平穩，按計畫進行配置。"

    print(f"🌡️ 心理狀態：{status}")
    print(f"🚀 指令建議：{advice}")
    print("="*50 + "\n")

if __name__ == "__main__":
    get_gafi_v2026()