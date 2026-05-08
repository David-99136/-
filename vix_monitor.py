import yfinance as yf
import pandas as pd
from datetime import datetime

def get_us_vix_monitor():
    """
    獲取美股 CBOE VIX 指數並進行全球市場情緒診斷
    """
    print("📡 系統啟動：正在對接美股 VIX 指數 (CBOE Volatility Index)...")
    
    # 美股 VIX 的標準代號
    ticker_symbol = "^VIX"
    
    try:
        # 1. 獲取數據
        vix_data = yf.Ticker(ticker_symbol)
        # 獲取最近 5 天的歷史資料
        df = vix_data.history(period="5d")
        
        if df.empty:
            print("❌ 錯誤：無法從 Yahoo Finance 獲取美股 VIX 數據。")
            return

        # 2. 提取最新數值
        latest_vix = float(df['Close'].iloc[-1])
        data_date = df.index[-1].strftime('%Y-%m-%d')
        
        # 3. 輸出報告 (明確標示為美股)
        print("\n" + "="*55)
        print(f"📊 【美股】 VIX 恐慌指標 - 診斷報告")
        print("="*55)
        print(f"📅 美股交易日期: {data_date}")
        print(f"📈 當前美股 VIX 指數: {latest_vix:.2f}")
        print("-" * 55)
        
        # 4. 針對何景澤的 AI 交易系統策略診斷
        # 美股 VIX 通常以 20 為警戒線，30 以上為極度恐慌
        if latest_vix >= 30:
            status = "🚨 【全球極度恐慌】"
            action = f"美股 VIX ({latest_vix:.2f}) 突破 30 大關！"
            strategy = "👉 指令：全球資金避險中。符合左側交易策略，檢查 2330/0050 是否出現 MACD 底背離。"
        elif latest_vix >= 20:
            status = "⚠️ 【市場波動加劇】"
            action = "美股情緒轉趨謹慎。"
            strategy = "👉 指令：監控半導體龍頭 (如 Micron) 支撐，此時 0056/00919 殖利率吸引力增加。"
        else:
            status = "🟢 【情緒樂觀平穩】"
            action = "市場波動率低。"
            strategy = "👉 指令：維持既有配置，定期定額累積高股息或 00830 等半導體 ETF。"

        print(f"🌡️ 市場情緒：{status}")
        print(f"🎯 策略分析：{action}")
        print(f"🚀 行動建議：{strategy}")
        print("="*55)
        
    except Exception as e:
        print(f"❌ 系統錯誤：對接美股數據流時發生異常")
        print(f"錯誤細節：{str(e)}")

if __name__ == "__main__":
    get_us_vix_monitor()