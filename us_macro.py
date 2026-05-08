import yfinance as yf
import pandas as pd
from datetime import datetime

def get_us500_trend():
    print("📡 啟動【美股宏觀掃描】：US 500 成交量與多空力道分析...")
    
    result = {
        "score": 0,
        "notes": []
    }
    
    try:
        # 使用 SPY 作為 S&P 500 最佳的成交量代理指標
        spy = yf.Ticker("SPY")
        df = spy.history(period="60d")
        
        if df.empty:
            result["notes"].append("⚠️ 無法獲取 US 500 (SPY) 數據。")
            return result

        # 計算 30 日平均成交量
        df['Vol_30MA'] = df['Volume'].rolling(window=30).mean()
        
        latest_vol = df['Volume'].iloc[-1]
        vol_30ma = df['Vol_30MA'].iloc[-1]
        latest_close = df['Close'].iloc[-1]
        latest_open = df['Open'].iloc[-1]
        
        # 判斷多空：收盤 >= 開盤視為多方力道，反之為空方拋售
        is_bullish = latest_close >= latest_open
        vol_ratio = latest_vol / vol_30ma if vol_30ma > 0 else 1
        
        result["notes"].append(f"📊 US 500 (SPY) 近日成交量: {latest_vol:,.0f} (30日均量: {vol_30ma:,.0f})")
        
        # 左側交易評分邏輯 (滿分 20 分)
        # 尋找恐慌極致：爆量 + 跌勢 = 散戶停損、左側絕佳買點
        if latest_vol > vol_30ma * 1.5:
            if not is_bullish:
                result["score"] = 20
                result["notes"].append(f"🚨 【恐慌拋售】US 500 爆量 ({vol_ratio:.1f}倍) 下殺，空方宣洩至極致，醞釀左側反彈點 (+20)")
            else:
                result["score"] = 5
                result["notes"].append(f"🔥 【強勢表態】US 500 爆量 ({vol_ratio:.1f}倍) 上漲，多方積極追價，左側安全邊際降低 (+5)")
        elif latest_vol > vol_30ma:
            if not is_bullish:
                result["score"] = 15
                result["notes"].append(f"⚠️ 【情緒承壓】US 500 放量跌破均量，空方主導，可留意錯殺機會 (+15)")
            else:
                result["score"] = 5
                result["notes"].append(f"🟢 【穩步墊高】US 500 放量上漲，趨勢偏多，不符左側恐慌條件 (+5)")
        else:
            result["score"] = 10
            result["notes"].append(f"⚖️ 【量能萎縮】US 500 成交量低於 30 日均量，市場觀望氣氛濃厚 (+10)")
            
    except Exception as e:
        result["notes"].append(f"⚠️ US 500 分析異常: {e}")
        result["score"] = 10
        
    return result