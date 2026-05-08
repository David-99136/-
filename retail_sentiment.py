import requests
import pandas as pd
from datetime import datetime, timedelta

def get_retail_sentiment_fixed():
    print("📡 系統啟動：正在精確對接【小台 MTX】與【微台 TMF】真實散戶多空比...")
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    
    targets = {"MTX": "小台指", "TMF": "微台指"}
    url = "https://api.finmindtrade.com/api/v4/data"
    
    # 回傳給 agent 的最終數據
    final_result = {"ratio": 0.0, "label": "中性"}

    try:
        for code, label in targets.items():
            # ==========================================
            # 1. 取得法人未平倉量 (計算散戶淨部位)
            # ==========================================
            params_inst = {
                "dataset": "TaiwanFuturesInstitutionalInvestors",
                "data_id": code,
                "start_date": start_date,
                "end_date": end_date
            }
            res_inst = requests.get(url, params=params_inst, timeout=15)
            data_inst = res_inst.json()
            
            if not data_inst.get('data'):
                # 備援：若 MTX 沒抓到，嘗試 MXF
                if code == "MTX":
                    params_inst["data_id"] = "MXF"
                    res_inst = requests.get(url, params=params_inst, timeout=15)
                    data_inst = res_inst.json()
                    if not data_inst.get('data'): continue
                else: continue
                
            df_inst = pd.DataFrame(data_inst['data'])
            latest_date = df_inst['date'].max()
            current_inst_df = df_inst[df_inst['date'] == latest_date]

            l_col = 'long_open_interest_balance_volume'
            s_col = 'short_open_interest_balance_volume'

            # 三大法人淨部位
            inst_net = current_inst_df[l_col].sum() - current_inst_df[s_col].sum()
            
            # 散戶淨部位 = -(三大法人淨部位)
            retail_net = -inst_net

            # ==========================================
            # 2. 取得全市場未平倉量 (全市場 OI 作為真實分母)
            # ==========================================
            params_daily = {
                "dataset": "TaiwanFuturesDaily",
                "data_id": code,
                "start_date": latest_date,
                "end_date": latest_date
            }
            res_daily = requests.get(url, params=params_daily, timeout=15)
            data_daily = res_daily.json()
            
            total_market_oi = 0
            if data_daily.get('data'):
                df_daily = pd.DataFrame(data_daily['data'])
                if 'open_interest' in df_daily.columns:
                    # 加總各個合約月份(近月、遠月)的未平倉量
                    total_market_oi = df_daily['open_interest'].sum()

            # ==========================================
            # 3. 計算真實散戶多空比
            # ==========================================
            if total_market_oi > 0:
                # 正確公式：散戶淨部位 / 全市場未平倉量
                retail_ratio = (retail_net / total_market_oi) * 100
            else:
                retail_ratio = 0.0

            print("\n" + "="*50)
            print(f"📊 標的：{label} ({code})")
            print(f"📅 數據日期: {latest_date}")
            print(f"📈 散戶淨部位：{retail_net:+,} 口")
            
            if total_market_oi > 0:
                print(f"🏛️ 全市場 OI：{total_market_oi:,.0f} 口")
                print(f"📉 真實多空比：{retail_ratio:.2f}%")
            else:
                print("⚠️ 無法獲取全市場 OI，切換為口數模式。")

            # 判斷邏輯 (依照真實多空比，通常 ±10%~15% 就屬於極端狀態)
            if retail_ratio >= 15:
                status = "⚠️ 【過度看多】 (散戶追高，提防反轉)"
            elif retail_ratio <= -15:
                status = "🚨 【極度看空】 (散戶停損，醞釀買點)"
            else:
                status = "🟢 【情緒中性】"

            print(f"⚖️ 市場情緒：{status}")
            print("="*50)
            
            # 將指標回傳給 agent
            if code in ["MTX", "MXF"] and total_market_oi > 0:
                final_result["ratio"] = retail_ratio
                final_result["label"] = status

    except Exception as e:
        print(f"❌ 系統錯誤：{str(e)}")
        
    return final_result

if __name__ == "__main__":
    get_retail_sentiment_fixed()