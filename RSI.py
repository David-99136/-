import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

def get_40_days_rsi(data_input):
    """
    相容性升級：
    data_input 可以是股票代號 (str) 或已下載的歷史數據 (pd.DataFrame)
    """
    if isinstance(data_input, pd.DataFrame):
        df = data_input.copy()
        ticker_name = "Target"
    else:
        ticker_name = data_input
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=100)).strftime("%Y-%m-%d")
        df = yf.download(ticker_name, start=start_date, end=end_date, progress=False)
    
    if df is None or df.empty:
        print(f"❌ [RSI] 資料源空值")
        return None

    # 強制修正：相容 MultiIndex 與 SingleIndex
    if isinstance(df.columns, pd.MultiIndex):
        close = df['Close'].iloc[:, 0]
    elif 'Close' in df.columns:
        close = df['Close']
    else:
        close = df.iloc[:, 0]

    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    result = pd.DataFrame({'Close': close, 'RSI': rsi}).tail(40)
    return result