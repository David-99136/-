import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def get_40_days_rsi(ticker):
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
    df = yf.download(ticker, start=start_date, end=end_date, progress=False)
    
    if df.empty:
        print(f"❌ [RSI] {ticker} 資料源空值")
        return None

    # 強制修正：相容 MultiIndex 與 SingleIndex
    if isinstance(df.columns, pd.MultiIndex):
        close = df['Close'][ticker]
    else:
        close = df['Close']

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    result = pd.DataFrame({'Close': close, 'RSI': rsi}).tail(40)
    
    # --- 強制輸出：確保終端機一定看得到 ---
    print(f"\n📊 {ticker} 最近 40 個交易日 RSI 趨勢表")
    print("-" * 50)
    for idx, row in result.iterrows():
        print(f"{idx.strftime('%Y-%m-%d'):<12} | {row['Close']:>10.2f} | {row['RSI']:>10.2f}")
    print("-" * 50)
    
    return result