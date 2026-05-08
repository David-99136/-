import GAFI, vix_monitor, retail_sentiment, MACD, RSI, foreign_flow, foreign_flow_stock
import fundamental_agent
import us_macro
import global_macro
import yfinance as yf
import pandas as pd
import numpy as np

def calculate_dynamic_score(current_val, min_val, max_val, max_score, inverse=False):
    """動態歸一化引擎 (Dynamic Normalizer)"""
    if max_val == min_val: return 0
    ratio = max(0, min(1, (current_val - min_val) / (max_val - min_val)))
    if inverse:
        ratio = 1 - ratio
    return int(ratio * max_score)

def calculate_vix_score(vix_val):
    """
    【升級】分段式 VIX 評分引擎：
    - 15 ~ 35 (常態恐慌區間): 滿分 60 分
    - 35 ~ 80 (極端黑天鵝區): 剩下的 40 分 (解決 35 與 50+ 無法分辨的問題)
    """
    if vix_val <= 15: return 0
    elif vix_val <= 35: 
        return calculate_dynamic_score(vix_val, 15, 35, 60)
    else: 
        return 60 + calculate_dynamic_score(vix_val, 35, 80, 40)

def calculate_vix_roc_score(roc_percent):
    """
    【升級】VIX 變化率 (ROC) 評分：
    只有 VIX 短期急速飆升 (ROC > 10%) 才會給予情緒加分。
    若 VIX 正在下降 (ROC <= 0)，表示恐慌降溫，給 0 分以拖低群組平均。
    """
    if roc_percent <= 0: return 0
    return calculate_dynamic_score(roc_percent, 10, 60, 100) # 飆升 60% 給滿分

# ==========================================
# 模組 1：市場狀態機 (Regime Detector)
# ==========================================
def detect_market_regime(macro_data, primary_vix, is_tw_stock):
    is_black_swan = macro_data.get("is_black_swan", False)
    macro_score = macro_data.get("macro_score", 0)
    
    # 使用主要 VIX 判斷 Regime
    if is_black_swan or primary_vix >= 35:
        return {"regime": "PANIC_CRISIS", "desc": "🚨 恐慌崩盤 (左側主場，準備受雷)"}
    elif macro_score < -10 and primary_vix >= 25:
        return {"regime": "BEAR_TREND", "desc": "📉 空頭趨勢 (保守防禦，尋找錯殺)"}
    elif macro_score > 0 and primary_vix < 20:
        return {"regime": "BULL_TREND", "desc": "📈 多頭趨勢 (順勢右側)"}
    else:
        return {"regime": "NEUTRAL_CHOPPY", "desc": "⚖️ 震盪整理 (區間操作)"}

# ==========================================
# 模組 2：動態倉位計算器 (Pyramid Entry Engine)
# ==========================================
def calculate_position_size(regime, final_score, is_crisis_mode):
    if regime == "PANIC_CRISIS":
        if final_score >= 70: return "20% - 25% (火力全開，雷劈核心區)"
        elif final_score >= 40: return "10% - 15% (左側分批受雷)"
        else: return "5% (基礎守候位，確保在場)" 
    elif regime == "BULL_TREND":
        if final_score >= 70: return "20% - 30% (順勢加碼，右側突破)"
        elif final_score >= 50: return "10% - 15% (持倉續抱)"
        else: return "5% (動能減弱，準備減碼)"
    else:
        if final_score >= 75: return "10% (區間錯殺低接)"
        else: return "0% - 5% (保留現金實力)"

# ==========================================
# 主程式：多模組聚合與策略路由
# ==========================================
def run_diagnosis(ticker, manual_futures, is_tw_stock, manual_vix, futures_history_5d=None, bias_ratio_240ma=None, futures_min=-50000, futures_max=10000):
    market_str = "台股" if is_tw_stock else "美股"
    print(f"\n[何景澤 AI 交易探員 - 量化架構升級版] 標的：{ticker} ({market_str})")
    print("="*70)
    
    agent_notes = []
    
    # 1. 獲取宏觀數據
    macro_data = global_macro.get_capital_flow_status()
    for n in macro_data.get("notes", []): agent_notes.append(n)
        
    # 2. 自動抓取美股 VIX 與計算 5 日 ROC
    us_vix_val = 20.0 
    vix_roc = 0.0
    try:
        vix_df = yf.Ticker("^VIX").history(period="6d") 
        if not vix_df.empty and len(vix_df) >= 2:
            us_vix_val = float(vix_df['Close'].iloc[-1])
            prev_us_vix = float(vix_df['Close'].iloc[0])
            vix_roc = ((us_vix_val - prev_us_vix) / prev_us_vix) * 100
    except: pass

    # 狀態機判定：取 台股/美股 較高的 VIX 作為風險警報依據
    primary_vix = max(manual_vix, us_vix_val) if is_tw_stock else us_vix_val
    regime_info = detect_market_regime(macro_data, primary_vix, is_tw_stock)
    current_regime = regime_info["regime"]
    is_crisis_mode = (current_regime == "PANIC_CRISIS")
    
    print(f"🌍 【市場狀態機 (Regime)】: {regime_info['desc']}")
    
    # ==========================================
    # 3. 因子群組化 (Factor Groups)
    # ==========================================
    groups = {
        "Sentiment": [], "Flow": [], "Fundamental": [], "Technical": []
    }

    # -- A. 基本面因子 --
    fund_data = fundamental_agent.get_fundamentals(ticker, is_crisis_mode=is_crisis_mode)
    groups["Fundamental"].append(fund_data.get("pe_score", 0) * 100 / 15) 
    groups["Fundamental"].append(fund_data.get("fibo_score", 0) * 100 / 15) 
    groups["Fundamental"].append(fund_data.get("sd_score", 0) * 10) 
    for n in fund_data.get("notes", []): agent_notes.append(n)

    # -- B. 技術面因子 --
    is_extreme_deviation = False
    if bias_ratio_240ma is not None and bias_ratio_240ma <= -20:
        is_extreme_deviation = True
        groups["Technical"].append(100)
        agent_notes.append(f"⚡ 【雷劈加權】年線乖離率達 {bias_ratio_240ma}%！極端錯殺，強制給予技術面滿分。")

    rsi_res = RSI.get_40_days_rsi(ticker)
    if rsi_res is not None and not rsi_res.empty:
        curr_rsi = rsi_res['RSI'].iloc[-1]
        days_under_30 = (rsi_res['RSI'].tail(10) < 30).sum()
        
        if is_extreme_deviation:
            agent_notes.append(f"🎯 技術面: 已觸發極端乖離，無視 RSI 鈍化。")
        elif days_under_30 >= 4:
            groups["Technical"].append(0) 
            agent_notes.append(f"⚠️ 技術面: 強勢空頭【鈍化區】，沒收 RSI 加分")
        else:
            rsi_score = calculate_dynamic_score(curr_rsi, 15, 40, 100, inverse=True)
            groups["Technical"].append(rsi_score)
            agent_notes.append(f"🎯 技術面: 動態 RSI 得分 ({rsi_score}/100)")

    # -- C. 【核心升級】全球與本地情緒分離 & ROC 判定 --
    us_vix_score = calculate_vix_score(us_vix_val)
    roc_score = calculate_vix_roc_score(vix_roc)
    groups["Sentiment"].append(us_vix_score)
    groups["Sentiment"].append(roc_score)
    agent_notes.append(f"🌎 全球情緒: 美股 VIX={us_vix_val:.2f} (分段得分:{us_vix_score}), 5日ROC={vix_roc:+.1f}% (動能得分:{roc_score})")

    if is_tw_stock:
        # 台股 VIX 獨立加權
        tw_vix_score = calculate_vix_score(manual_vix)
        groups["Sentiment"].append(tw_vix_score)
        agent_notes.append(f"🇹🇼 本地情緒: 台股 VIX={manual_vix:.2f} (分段得分:{tw_vix_score})")
        
        try:
            retail_data = retail_sentiment.get_retail_sentiment_fixed()
            if retail_data.get("ratio", 0) < 0:
                r_score = calculate_dynamic_score(abs(retail_data["ratio"]), 0, 30, 100)
                groups["Sentiment"].append(r_score)
                agent_notes.append(f"📊 散戶情緒: 看空比例 {-retail_data['ratio']:.1f}% (得分:{r_score})")
        except: pass

        position_ratio = max(0.0, min(1.0, (manual_futures - futures_max) / (futures_min - futures_max)))
        groups["Flow"].append(100 - int(position_ratio * 100)) 
        try:
            stock_df = foreign_flow_stock.get_institutional_flow(ticker)
            if stock_df is not None and not stock_df.empty:
                net_buy_lots = int((pd.to_numeric(stock_df['buy'], errors='coerce').sum() - pd.to_numeric(stock_df['sell'], errors='coerce').sum()) / 1000)
                if net_buy_lots > 0: groups["Flow"].append(calculate_dynamic_score(net_buy_lots, 0, 5000, 100))
        except: pass

    # ==========================================
    # 4. 策略動態加權 (Strategy Routing)
    # ==========================================
    avg_scores = {k: (np.mean(v) if v else 0) for k, v in groups.items()}
    
    print("\n🧩 【因子群組獨立分析 (百分制)】")
    print(f"  ▶ 恐慌情緒 (Sentiment): {avg_scores['Sentiment']:.1f}/100")
    print(f"  ▶ 資金籌碼 (Flow)     : {avg_scores['Flow']:.1f}/100")
    print(f"  ▶ 價值護城河 (Fund)   : {avg_scores['Fundamental']:.1f}/100")
    print(f"  ▶ 技術錯殺 (Tech)     : {avg_scores['Technical']:.1f}/100")

    if current_regime == "PANIC_CRISIS":
        final_score = (avg_scores['Sentiment'] * 0.4) + (avg_scores['Technical'] * 0.3) + (avg_scores['Fundamental'] * 0.3)
        strategy_desc = "左側雷劈承接策略 (Left-Side Panic Buy)"
    elif current_regime == "BULL_TREND":
        final_score = (avg_scores['Flow'] * 0.4) + (avg_scores['Technical'] * 0.4) + (avg_scores['Fundamental'] * 0.2)
        strategy_desc = "右側順勢動能策略 (Right-Side Momentum)"
    else:
        final_score = (avg_scores['Fundamental'] * 0.3) + (avg_scores['Flow'] * 0.3) + (avg_scores['Technical'] * 0.2) + (avg_scores['Sentiment'] * 0.2)
        strategy_desc = "區間均衡策略 (Mean-Reversion)"

    recommended_position = calculate_position_size(current_regime, final_score, is_crisis_mode)

    print("\n" + "⚖️ 【AI Quant 綜合決策引擎】 ⚖️")
    print("-" * 70)
    for n in agent_notes:
        print(f"  {n}")
    print("-" * 70)
    print(f"🎯 採用策略: {strategy_desc}")
    print(f"📊 最終加權決策指數: {final_score:.1f} / 100")
    print(f"💰 【風控與倉位建議】: {recommended_position}")
    print("="*70 + "\n")