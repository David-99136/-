import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def get_40_days_macd(ticker):
    """計算並強制印出 40 日 MACD 時序表"""
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")
    
    df = yf.download(ticker, start=start_date, end=end_date, progress=False)
    
    if df.empty:
        print(f"❌ [MACD] 無法獲取 {ticker} 數據，請檢查後綴是否為 .TW")
        return None

    # 處理 yfinance 可能產生的 MultiIndex
    close = df['Close'].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df['Close']
    
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    sig_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - sig_line

    result = pd.DataFrame({'Close': close, 'Hist': hist}).tail(40)
    
    # --- 強制終端機輸出表格 ---
    print(f"\n📊 {ticker} 最近 40 個交易日 MACD 表格")
    print("-" * 55)
    print(f"{'日期 (Date)':<12} | {'收盤價':>10} | {'MACD Hist':>15}")
    for idx, row in result.iterrows():
        print(f"{idx.strftime('%Y-%m-%d'):<12} | {row['Close']:>10.2f} | {row['Hist']:>15.4f}")
    print("-" * 55)
    
    return result