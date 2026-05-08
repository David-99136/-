import requests
import pandas as pd

def get_market_institutional_flow():
    url = "https://api.finmindtrade.com/api/v4/data"
    
    # 【系統核心破解】：時間軸同步 (Time-Sync Override)
    # 放棄使用 datetime.now()，避免系統時鐘在 2026 年導致向 API 索求「未來的數據」。
    # 強制將起點鎖定在絕對有資料的過去，並利用 iloc[-1] 抓取資料庫最新的真實交易日。
    start_date = "2024-01-01" 
    
    print(f"\n📡 [戰略層] 啟動時間軸校正 (Override Start: {start_date})...")
    res_data = {"spot": 0.0, "futures": 0}
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        # ==========================================
        # 1. 擷取大盤期貨 (外資空單壓力)
        # ==========================================
        f_res = requests.get(url, params={"dataset": "TaiwanStockFuturesInstitutionalInvestors", "start_date": start_date}, headers=headers, timeout=10)
        f_list = f_res.json().get('data', [])
        
        if f_list:
            df = pd.DataFrame(f_list)
            # 鎖定台股期貨
            if 'item' in df.columns:
                df = df[df['item'].str.contains('台股期貨|TX', na=False)]
            # 鎖定外資
            f_df = df[df['name'].str.contains('Foreign|外資', case=False, na=False)].copy()
            
            if not f_df.empty:
                long_cols = [c for c in f_df.columns if 'long' in c.lower()]
                short_cols = [c for c in f_df.columns if 'short' in c.lower()]
                
                if long_cols and short_cols:
                    f_df['net_oi'] = pd.to_numeric(f_df[long_cols[0]], errors='coerce').fillna(0) - \
                                     pd.to_numeric(f_df[short_cols[0]], errors='coerce').fillna(0)
                    valid_f = f_df[f_df['net_oi'] != 0].dropna(subset=['net_oi'])
                    
                    if not valid_f.empty:
                        res_data["futures"] = int(valid_f.iloc[-1]['net_oi'])
                        print(f"📉 [訊號成功] 大盤期指 ({valid_f.iloc[-1]['date']}): 外資淨部位 {res_data['futures']:+,} 口")

        # ==========================================
        # 2. 擷取大盤現貨 (外資買賣超)
        # ==========================================
        s_res = requests.get(url, params={"dataset": "TaiwanStockMarketInstitutionalInvestorsBuySell", "start_date": start_date}, headers=headers, timeout=10)
        s_list = s_res.json().get('data', [])
        
        if s_list:
            df_s = pd.DataFrame(s_list)
            s_df = df_s[df_s['name'].str.contains('Foreign|外資', case=False, na=False)].copy()
            
            if not s_df.empty:
                s_df['net'] = pd.to_numeric(s_df['buy'], errors='coerce') - pd.to_numeric(s_df['sell'], errors='coerce')
                valid_s = s_df[s_df['net'] != 0].dropna(subset=['net'])
                
                if not valid_s.empty:
                    res_data["spot"] = valid_s.iloc[-1]['net'] / 100000000
                    print(f"🏛️  [訊號成功] 大盤現貨 ({valid_s.iloc[-1]['date']}): 外資買賣超 {res_data['spot']:.2f} 億元")

    except Exception as e:
        print(f"❌ [戰略層] 數據鏈路異常: {e}")
        
    return res_data