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

    # 計算原始 RSI (紫線)
    delta = close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # --- 新增：計算 RSI 的 14日簡單移動平均線 (黃線) ---
    rsi_ma = rsi.rolling(window=14).mean()
    
    result = pd.DataFrame({
        'Close': close, 
        'RSI': rsi,
        'RSI_MA': rsi_ma
    }).tail(40)
    
    return result

def calculate_rsi_signals(data_input):
    """
    提供給 agent.py 呼叫的邏輯運算模組
    回傳字典：包含是否發生底部黃金交叉(看漲)、頂部死亡交叉(看跌)
    """
    df = get_40_days_rsi(data_input)
    if df is None or df.empty or len(df) < 2:
        return None

    # 取得最近兩天的 RSI 與 RSI_MA 數值
    rsi_prev = df['RSI'].iloc[-2]
    rsi_curr = df['RSI'].iloc[-1]
    ma_prev = df['RSI_MA'].iloc[-2]
    ma_curr = df['RSI_MA'].iloc[-1]

    # 1. 定義交叉 (Crossover & Crossunder)
    cross_up = (rsi_curr > ma_curr) and (rsi_prev <= ma_prev)
    cross_down = (rsi_curr < ma_curr) and (rsi_prev >= ma_prev)

    # 2. 結合極端區域條件 (確保上漲/下跌發生在交叉產生後)
    # 底部看漲：RSI 向上交叉 MA，且交叉前的 RSI 在 32 以下 (包含你的 28-32 區間)
    bullish_reversal = cross_up and (rsi_prev <= 32)

    # 頂部看跌/回調：RSI 向下交叉 MA，且交叉前的 RSI 在 70 以上
    bearish_reversal = cross_down and (rsi_prev >= 70)

    return {
        'bullish_reversal': bullish_reversal,
        'bearish_reversal': bearish_reversal,
        'current_rsi': rsi_curr,
        'current_ma': ma_curr
    }