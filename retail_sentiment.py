import requests
import pandas as pd
from datetime import datetime, timedelta

# ====================================================================
# 🔑 FinMind 官方認證 Token 安全鎖 (已直接內嵌整合)
# ====================================================================
DEFAULT_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiRGF2aWQiLCJlbWFpbCI6ImRhdmlkLjE5NzA0MDM1QGdtYWlsLmNvbSIsInRva2VuX3ZlcnNpb24iOjB9.B2xbE3_8MixVtAAlNFeho9EnNrGOQ9ijwBWgckT0B3o"

def get_valid_trading_date():
    """
    【核心防呆機制】：自動避開週末與資料未公布的時間
    """
    now = datetime.now()
    if now.weekday() == 5: target = now - timedelta(days=1)
    elif now.weekday() == 6: target = now - timedelta(days=2)
    elif now.weekday() == 0 and now.hour < 15: target = now - timedelta(days=3)
    elif now.hour < 15: target = now - timedelta(days=1)
    else: target = now
    return target

def get_retail_sentiment_fixed(manual_mtx_ratio=None, manual_tmf_ratio=None, api_token=None):
    """
    獲取最新真實散戶多空比 
    (時序動態對比版：完美計算昨日與前日差額，輸出 增減% 數)
    """
    print("\n📡 [Matrix V3] 啟動即時籌碼監控模組：對接真實世界最新【小台】與【微台】留倉...")
    
    final_result = {"ratio": 0.0, "label": "中性", "change": 0.0}
    
    # 優先權 1：手動輸入強制覆蓋邏輯
    if manual_mtx_ratio is not None and manual_tmf_ratio is not None:
        print("⚡ 【安全機制】偵測到使用者執行手動覆蓋，直接導向指定數值。")
        if manual_mtx_ratio >= 10: status = "⚠️ 【散戶過度看多】"
        elif manual_mtx_ratio <= -10: status = "🩸 【散戶極度看空】"
        else: status = "🟢 【散戶情緒中性】"
        final_result["ratio"] = manual_mtx_ratio
        final_result["label"] = status
        return final_result

    token_to_use = api_token if api_token else DEFAULT_TOKEN
    target_date = get_valid_trading_date()
    end_date = target_date.strftime("%Y-%m-%d")
    start_date = (target_date - timedelta(days=25)).strftime("%Y-%m-%d") # 擴大範圍以確保抓到足夠的歷史交易日
    
    targets = {
        "小台指": {"inst_id": "MXF", "daily_id": "MTX"},
        "微台指": {"inst_id": "TMF", "daily_id": "TMF"}
    }
    url = "https://api.finmindtrade.com/api/v4/data"

    try:
        for name, codes in targets.items():
            # --------------------------------------------------
            # 1. 抓取三大法人歷史未平倉序列
            # --------------------------------------------------
            params_inst = {
                "dataset": "TaiwanFuturesInstitutionalInvestors",
                "data_id": codes["inst_id"],
                "start_date": start_date,
                "end_date": end_date,
                "token": token_to_use
            }
            res_inst = requests.get(url, params=params_inst, timeout=15).json()
            
            # 備援機制
            if not res_inst.get('data') and codes["inst_id"] == "MXF":
                params_inst["data_id"] = "MTX"
                res_inst = requests.get(url, params=params_inst, timeout=15).json()
                
            if not res_inst.get('data'): continue
            
            df_inst = pd.DataFrame(res_inst['data'])
            
            # 按日期加總三大法人部位 (不分法人別)，反推散戶淨留倉
            df_inst_daily = df_inst.groupby('date').apply(
                lambda x: -(x['long_open_interest_balance_volume'].sum() - x['short_open_interest_balance_volume'].sum())
            ).reset_index(name='retail_net')
            df_inst_daily = df_inst_daily.sort_values('date').reset_index(drop=True)

            # --------------------------------------------------
            # 2. 抓取全市場總未平倉量序列 (OI)
            # --------------------------------------------------
            params_daily = {
                "dataset": "TaiwanFuturesDaily",
                "data_id": codes["daily_id"],
                "start_date": start_date,
                "end_date": end_date,
                "token": token_to_use
            }
            res_daily = requests.get(url, params=params_daily, timeout=15).json()
            
            if not res_daily.get('data') and codes["daily_id"] == "MTX":
                params_daily["data_id"] = "MXF"
                res_daily = requests.get(url, params=params_daily, timeout=15).json()
                
            if not res_daily.get('data'): continue
            
            df_daily = pd.DataFrame(res_daily['data'])
            df_daily_sum = df_daily.groupby('date')['open_interest'].sum().reset_index(name='total_oi')
            
            # --------------------------------------------------
            # 3. 合併數據，計算最新兩天的多空比與增減差額
            # --------------------------------------------------
            df_merged = pd.merge(df_inst_daily, df_daily_sum, on='date', how='inner')
            df_merged['retail_ratio'] = (df_merged['retail_net'] / df_merged['total_oi']) * 100
            df_merged = df_merged.sort_values('date').reset_index(drop=True)

            if len(df_merged) < 2:
                print(f"⚠️ {name} 歷史序列長度不足，無法計算增減比例。")
                continue

            # 提取最新一天(T)與前一天(T-1)的資料
            row_latest = df_merged.iloc[-1]
            row_prev = df_merged.iloc[-2]

            latest_date = row_latest['date']
            ratio_latest = row_latest['retail_ratio']
            ratio_prev = row_prev['retail_ratio']
            
            # 計算增減百分點 (本日多空比 - 昨日多空比)
            ratio_change = ratio_latest - ratio_prev

            # 格式化正負號字串
            change_str = f"+{ratio_change:.2f}%" if ratio_change >= 0 else f"{ratio_change:.2f}%"

            print("\n" + "✨"*25)
            print(f"📊 籌碼監測：{name}")
            print(f"📅 觀測交易日: {latest_date}")
            print(f"📉 真實散戶多空比: {ratio_latest:.2f}% (較前日變動: {change_str})")
            print(f"🏛️ 散戶留倉淨部位: {row_latest['retail_net']:+,} 口 / 全市場 OI: {row_latest['total_oi']:,.0f} 口")
            
            # 決策矩陣評語
            if ratio_latest >= 10: status = "⚠️ 【散戶過度看多】 (市場擁擠，防範高檔反轉)"
            elif ratio_latest <= -10: status = "🩸 【散戶極度看空】 (市場恐慌，醞釀左側買點)"
            else: status = "🟢 【散戶情緒中性】"
            print(f"⚖️ 決策矩陣評語：{status}")
            print("✨"*25)

            # 將主要指標（小台指）傳遞給主引擎 agent.py
            if name == "小台指":
                final_result["ratio"] = ratio_latest
                final_result["label"] = status
                final_result["change"] = ratio_change

    except Exception as e:
        print(f"❌ 數據差額動態解析異常：{str(e)}")
        
    return final_result

if __name__ == "__main__":
    get_retail_sentiment_fixed()