import requests
import pandas as pd
from datetime import datetime, timedelta

def get_institutional_flow(stock_id):
    """擷取個股外資買賣超 (個股戰術)"""
    stock_code = stock_id.split('.')[0] 
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {
        "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id": stock_code,
        "start_date": (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
    }
    
    try:
        res = requests.get(url, params=params, timeout=15)
        data = res.json().get('data', [])
        if not data: return None
        
        df = pd.DataFrame(data)
        foreign = df[df['name'] == 'Foreign_Investor'].tail(3)
        return foreign
    except:
        return None