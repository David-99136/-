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

    close = df['Close'].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df['Close']
    
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    sig_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - sig_line

    result = pd.DataFrame({'Close': close, 'Hist': hist}).tail(40)
    
    print(f"\n📊 {ticker} 最近 40 個交易日 MACD 表格")
    print("-" * 55)
    for idx, row in result.iterrows():
        print(f"{idx.strftime('%Y-%m-%d'):<12} | {row['Close']:>10.2f} | {row['Hist']:>15.4f}")
    print("-" * 55)
    
    return result

def calculate_macd_signals(data_input):
    """
    提供給 agent.py 呼叫的邏輯運算模組
    回傳字典：包含是否黃金交叉、柱狀圖是否翻正
    """
    if isinstance(data_input, pd.DataFrame):
        df = data_input.copy()
    else:
        df = yf.download(data_input, period="120d", progress=False)
        
    if df is None or df.empty:
        return None

    close = df['Close'].iloc[:, 0] if isinstance(df.columns, pd.MultiIndex) else df['Close']

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    sig_line = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - sig_line

    if len(hist) >= 2:
        # DIF (macd_line) 向上突破 DEM (sig_line)
        golden_cross = bool(macd_line.iloc[-1] > sig_line.iloc[-1] and macd_line.iloc[-2] <= sig_line.iloc[-2])
        # 柱狀圖由負轉正
        histogram_positive_flip = bool(hist.iloc[-1] > 0 and hist.iloc[-2] <= 0)
    else:
        golden_cross = False
        histogram_positive_flip = False

    return {
        'golden_cross': golden_cross,
        'histogram_positive_flip': histogram_positive_flip
    }