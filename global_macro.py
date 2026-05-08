import yfinance as yf
import pandas as pd
from datetime import datetime

def get_capital_flow_status():
    print("📡 啟動【全球資金輪動與避險掃描】：DXY, US10Y, 黃金, 台幣匯率...")
    
    result = {
        "macro_score": 0, 
        "notes": [],
        "is_black_swan": False
    }
    
    tickers = {
        "DXY": "DX-Y.NYB",   # 美元指數
        "US10Y": "^TNX",     # 美國10年期公債殖利率
        "GOLD": "GC=F",      # 黃金期貨
        "USDTWD": "TWD=X"    # 美元兌台幣
    }
    
    data = {}
    
    try:
        for name, ticker in tickers.items():
            df = yf.Ticker(ticker).history(period="1mo")
            if not df.empty:
                current = df['Close'].iloc[-1]
                ma20 = df['Close'].mean()
                roc = ((current - df['Close'].iloc[0]) / df['Close'].iloc[0]) * 100 
                data[name] = {"current": current, "ma20": ma20, "roc": roc}
        
        # A. 資金流向判定 (DXY 與 US10Y)
        if "DXY" in data and "US10Y" in data:
            dxy = data["DXY"]
            us10y = data["US10Y"]
            result["notes"].append(f"🌍 【資金水位】美元指數: {dxy['current']:.2f} | 10年期美債殖利率: {us10y['current']:.2f}%")
            
            if dxy['current'] > dxy['ma20'] and us10y['current'] > 4.2:
                result["macro_score"] -= 15
                result["notes"].append("⚠️ 警訊 (流動性收縮)：美元轉強且無風險利率高企，資金正流出風險資產 (-15)")
            elif dxy['current'] < dxy['ma20'] and us10y['current'] < 4.0:
                result["macro_score"] += 10
                result["notes"].append("🟢 利多 (流動性擴張)：美元走弱、殖利率下滑，有利估值修復 (+10)")
            else:
                result["notes"].append("⚖️ 宏觀水位：資金流向中性，無極端單邊趨勢。")

        # B. 台幣匯率判定 (外資熱錢動向)
        if "USDTWD" in data:
            twd = data["USDTWD"]
            result["notes"].append(f"💱 【熱錢動向】美元兌台幣: {twd['current']:.2f}")
            if twd['current'] > 32.5:
                result["macro_score"] -= 10
                result["notes"].append("🚨 警訊 (台幣弱勢)：匯率處於貶值區間，外資匯出壓力沉重，不利大盤 (-10)")
            elif twd['roc'] < -1.0:
                result["macro_score"] += 5
                result["notes"].append("🤝 利多 (台幣升值)：熱錢匯入，資金面具備支撐 (+5)")

        # C. 黑天鵝與避險情緒 (黃金極端波動)
        if "GOLD" in data:
            gold = data["GOLD"]
            result["notes"].append(f"🛡️ 【避險雷達】黃金期貨: ${gold['current']:.1f}/oz (月變動: {gold['roc']:+.2f}%)")
            
            if gold['roc'] > 8.0:
                result["is_black_swan"] = True
                result["notes"].append("🦅 🚨 【黑天鵝警告】：黃金異常噴出！偵測到極端地緣政治風險或避險情緒！")

    except Exception as e:
        result["notes"].append(f"❌ 宏觀數據抓取異常: {str(e)}")
        
    return result

if __name__ == "__main__":
    res = get_capital_flow_status()
    for n in res["notes"]:
        print(n)