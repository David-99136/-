import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import RSI  # 沿用您現有的 RSI 模組

def get_sp500_status():
    """獲取 S&P 500 的最新趨勢與 RSI 狀態"""
    try:
        # 抓取 S&P 500 數據
        sp500 = yf.Ticker("^GSPC")
        df = sp500.history(period="60d")
        
        if df.empty:
            return 50, 'FLAT'

        # 計算 RSI
        rsi_df = RSI.get_40_days_rsi("^GSPC")
        current_rsi = rsi_df['RSI'].iloc[-1] if (rsi_df is not None and not rsi_df.empty) else 50
        
        # 判斷趨勢：如果現價大於 20 日均線且接近 60 日最高點，視為創新高
        current_price = df['Close'].iloc[-1]
        highest_60d = df['High'].max()
        ma20 = df['Close'].rolling(window=20).mean().iloc[-1]
        
        if current_price < df['Close'].rolling(window=240).mean().iloc[-1] if len(df) >= 240 else (ma20 * 0.9):
            trend = 'DOWNTREND'
        elif current_price >= highest_60d * 0.98 and current_price > ma20:
            trend = 'NEW_HIGH'
        else:
            trend = 'FLAT'
            
        return current_rsi, trend
    except Exception as e:
        print(f"⚠️ S&P 500 狀態獲取異常: {e}")
        return 50, 'FLAT'

def evaluate_naaim_sp500_logic(naaim_current, naaim_trend):
    """
    評估 NAAIM 經理人持倉與 S&P 500 的聯動關係
    """
    print("📡 啟動【聰明錢籌碼追蹤】：分析 NAAIM 經理人持倉與大盤背離狀態...")
    
    # 獲取標普 500 狀態
    sp500_rsi, sp500_trend = get_sp500_status()
    
    score = 0
    log_msg = ""
    
    # 1. 左側恐慌買點：經理人極度悲觀 + 大盤處於跌勢
    if naaim_current < 40 and sp500_trend == 'DOWNTREND':
        score = 15
        log_msg = f"🩸 【聰明錢恐慌】NAAIM 極低 ({naaim_current}) 且 S&P 500 走跌。機構已認輸清倉，觸發絕佳左側雷劈買點！(+15)"
        
    # 2. 高檔背離警戒：大盤創新高，但經理人正在撤退
    elif sp500_trend == 'NEW_HIGH' and naaim_trend == 'DOWN' and naaim_current < 80:
        score = -15
        log_msg = f"⚠️ 【聰明錢背離】S&P 500 創新高，但 NAAIM 呈現下降趨勢 ({naaim_current})。經理人正逢高減碼，防範大逃殺風險！(-15)"
        
    # 3. 絕對過熱警戒：經理人滿倉 + RSI 超買
    elif naaim_current >= 90 and sp500_rsi >= 70:
        score = -5  # 適度扣分以抑制追高衝動
        log_msg = f"🔥 【籌碼極度擁擠】NAAIM 滿倉 ({naaim_current}) 且 S&P 500 RSI 超買 ({sp500_rsi:.1f})。符合過熱週期特徵，不宜追高。(-5)"
        
    # 4. 中性偏多：大盤穩健，經理人持倉健康
    elif 60 <= naaim_current < 90 and sp500_trend != 'DOWNTREND':
        score = 5
        log_msg = f"🌊 【籌碼健康】NAAIM 維持在合理高位 ({naaim_current})，機構資金具備支撐力道。(+5)"
        
    else:
        score = 0
        log_msg = f"⚖️ 【籌碼中性】NAAIM 報 {naaim_current}，大盤 RSI ({sp500_rsi:.1f})，無極端偏離跡象。(+0)"

    return {"score": score, "log": log_msg, "sp500_trend": sp500_trend, "sp500_rsi": sp500_rsi}

if __name__ == "__main__":
    # 測試您圖中的情境 (2026/05 模擬)
    res = evaluate_naaim_sp500_logic(naaim_current=78, naaim_trend='DOWN')
    print(res['log'])