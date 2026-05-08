import GAFI, vix_monitor, retail_sentiment, MACD, RSI, foreign_flow, foreign_flow_stock
import fundamental_agent
import us_macro
import global_macro
import yfinance as yf
import pandas as pd

def calculate_dynamic_score(current_val, min_val, max_val, max_score, inverse=False):
    """
    動態歸一化引擎 (Dynamic Normalizer)
    將當前數值平滑映射到 0 ~ max_score 區間，消除硬編碼帶來的分數斷層。
    """
    if max_val == min_val: return 0
    ratio = max(0, min(1, (current_val - min_val) / (max_val - min_val)))
    if inverse:
        ratio = 1 - ratio
    return int(ratio * max_score)

def run_diagnosis(ticker, manual_futures, is_tw_stock, manual_vix, futures_history_5d=None, bias_ratio_240ma=None, futures_min=-50000, futures_max=10000):
    market_str = "台股" if is_tw_stock else "美股"
    print(f"\n[何景澤 AI 交易探員 - 2026 穩定版] 啟動左側交易診斷程序 - 標的：{ticker} ({market_str})")
    print("="*70)
    
    total_score = 0
    agent_notes = []
    
    # 系統狀態變數
    is_crisis_mode = False
    buy_threshold = 70
    accumulate_threshold = 45

    # ==========================================
    # Tier 1: 戰略狀態切換 (Macro & Black Swan)
    # ==========================================
    print("🛡️ Tier 1: 宏觀環境與流動性掃描...")
    try:
        macro_data = global_macro.get_capital_flow_status()
        total_score += macro_data.get("macro_score", 0)
        
        # 黑天鵝觸發「危機模式」提高建倉門檻
        if macro_data.get("is_black_swan"):
            is_crisis_mode = True
            buy_threshold = 85          
            accumulate_threshold = 60   
            agent_notes.append("🚨 【危機模式啟動】：偵測到黑天鵝級別避險，系統自動調高安全邊際，嚴格審核基本面！")
        else:
            for n in macro_data.get("notes", []):
                agent_notes.append(n)
    except Exception as e:
        agent_notes.append(f"⚠️ 資金流向掃描異常: {e}")

    # ==========================================
    # Tier 2: 價值基底與基本面護城河 (Fundamentals)
    # ==========================================
    print("🏗️ Tier 2: 價值基底與護城河驗證...")
    
    # 傳遞 is_crisis_mode 進行動態防線連動
    fund_data = fundamental_agent.get_fundamentals(ticker, is_crisis_mode=is_crisis_mode)
    
    fund_score = fund_data.get("pe_score", 0) + fund_data.get("fibo_score", 0) + fund_data.get("sd_score", 0)
    
    # 危機模式下的動態權重調整：基本面分數權重放大 1.2 倍
    if is_crisis_mode:
        fund_score = int(fund_score * 1.2)
        agent_notes.append(f"⚓ 黑天鵝防禦: 基本面權重已放大，當前價值基底得分 (+{fund_score})")
    
    total_score += fund_score
    for n in fund_data.get("notes", []):
        agent_notes.append(n)

    # 乖離率錯殺補償
    if bias_ratio_240ma is not None and bias_ratio_240ma < -25:
        panic_bonus = calculate_dynamic_score(abs(bias_ratio_240ma), 25, 40, 15)
        total_score += panic_bonus
        agent_notes.append(f"📉 極端錯殺補償: 年線乖離率過大 ({bias_ratio_240ma}%)，給予恐慌溢價加分 (+{panic_bonus})")

    # ==========================================
    # Tier 3: 戰術觸發 - 動態籌碼與情緒精算
    # ==========================================
    print("⚡ Tier 3: 技術面與籌碼動態響應 (自適應百分位版)...")
    
    rsi_res = RSI.get_40_days_rsi(ticker)
    curr_rsi = rsi_res['RSI'].iloc[-1] if rsi_res is not None and not rsi_res.empty else 50.0

    # 1. 具備「鈍化防禦」的 RSI 動態給分
    if rsi_res is not None and not rsi_res.empty:
        # 計算近 10 日內 RSI < 30 的天數
        days_under_30 = (rsi_res['RSI'].tail(10) < 30).sum()
        
        if days_under_30 >= 4:
            agent_notes.append(f"⚠️ 技術面陷阱: 近 10 日有 {days_under_30} 天 RSI < 30，處於強勢空頭【鈍化區】，沒收接刀加分 (+0)")
        elif curr_rsi <= 40:
            rsi_score = calculate_dynamic_score(curr_rsi, 15, 40, 15, inverse=True)
            total_score += rsi_score
            agent_notes.append(f"🎯 技術面 (動態 RSI): 超賣水位 ({curr_rsi:.1f})，未見鈍化跡象 (+{rsi_score})")

    if is_tw_stock:
        # 2. 台股 VIX 動態給分
        vix_score = calculate_dynamic_score(manual_vix, 15, 35, 15)
        total_score += vix_score
        agent_notes.append(f"📈 恐慌指數 (VIX): 波動率溢價 ({manual_vix:.2f}) (+{vix_score})")

        # 3. 期指外資空單 (百分位數 Percentile 正規化)
        if futures_max != futures_min:
            position_ratio = (manual_futures - futures_max) / (futures_min - futures_max)
            position_ratio = max(0.0, min(1.0, position_ratio)) 
            penalty = int(position_ratio * 25)
            
            if penalty > 10:
                total_score -= penalty
                agent_notes.append(f"🚨 宏觀籌碼壓力: 外資部位 ({manual_futures:+,} 口) 處於低檔 {position_ratio*100:.1f}% 分位，風險折減 (-{penalty})")
            else:
                total_score += 10
                agent_notes.append(f"🟢 宏觀籌碼健康: 外資部位 ({manual_futures:+,} 口) 未達極端壓力區 (+10)")
        
        # 期指 ROC (變化率) 檢測
        if futures_history_5d is not None:
            short_increase = abs(manual_futures) - abs(futures_history_5d)
            if short_increase > 10000:
                total_score -= 10
                agent_notes.append(f"🛑 趨勢警告 (期指 ROC): 空單 5 日內異常激增 ({short_increase:+,} 口) (-10)")

        # 4. 【微觀權重提升】個股法人逆勢吃貨 (滿分 20 分)
        try:
            stock_df = foreign_flow_stock.get_institutional_flow(ticker)
            if stock_df is not None and not stock_df.empty:
                net_buy = pd.to_numeric(stock_df['buy'], errors='coerce').sum() - pd.to_numeric(stock_df['sell'], errors='coerce').sum()
                net_buy_lots = int(net_buy / 1000) 
                
                if net_buy_lots > 0:
                    micro_score = calculate_dynamic_score(net_buy_lots, 0, 5000, 20)
                    total_score += micro_score
                    agent_notes.append(f"🛡️ 【微觀籌碼護城河】: 法人逆勢買超 {net_buy_lots:+,} 張，抵銷大盤弱勢 (+{micro_score})")
                elif net_buy_lots < -3000:
                    total_score -= 10
                    agent_notes.append(f"⚠️ 個股提款機: 法人同步拋售該股 ({net_buy_lots:+,} 張)，微觀籌碼潰散 (-10)")
        except Exception as e: 
            agent_notes.append(f"⚠️ 個股法人籌碼讀取失敗: {e}")

        # 5. 散戶籌碼動態聯動
        try: 
            retail_data = retail_sentiment.get_retail_sentiment_fixed()
            r_ratio = retail_data.get("ratio", 0)
            if r_ratio < 0:
                r_score = calculate_dynamic_score(abs(r_ratio), 0, 30, 15)
                total_score += r_score
                agent_notes.append(f"📊 散戶反指標: 散戶看空 ({r_ratio:.1f}%)，具反向動能 (+{r_score})")
            elif r_ratio > 10:
                r_penalty = calculate_dynamic_score(r_ratio, 10, 30, 10)
                total_score -= r_penalty
                agent_notes.append(f"⚠️ 散戶擁擠: 散戶追多 ({r_ratio:.1f}%)，籌碼凌亂 (-{r_penalty})")
        except: pass

    else:
        # 美股專用 VIX 與宏觀邏輯
        try:
            vix_monitor.get_us_vix_monitor() 
            vix_df = yf.Ticker("^VIX").history(period="1d")
            vix_val = float(vix_df['Close'].iloc[-1])
            us_vix_score = calculate_dynamic_score(vix_val, 15, 40, 20)
            total_score += us_vix_score
            agent_notes.append(f"📈 恐慌指數 (美股 VIX): 波動率溢價 ({vix_val:.2f}) (+{us_vix_score})")
        except Exception: pass
        
        us500_data = us_macro.get_us500_trend()
        total_score += us500_data.get("score", 0)
        for n in us500_data.get("notes", []):
            agent_notes.append(n)

    # ==========================================
    # 最終診斷與行動建議
    # ==========================================
    print("\n" + "⚖️ 【AI Agent 左側交易綜合診斷結果】 ⚖️")
    print("-" * 70)
    print(f"🎯 左側交易決策指數: {total_score} / 100")
    print(f"📌 當前系統狀態: {'🔴 危機模式 (高門檻)' if is_crisis_mode else '🟢 一般模式 (標準門檻)'}")
    print("-" * 70)
    for n in agent_notes:
        print(f"  {n}")
    
    print("\n💡 探員行動總結：")
    if total_score >= buy_threshold:
        print(f"  【強烈買進 (Strong Buy)】- 分數達標 ({total_score} >= {buy_threshold})！市場情緒極度悲觀且基底穩固，正是貪婪時刻。")
    elif total_score >= accumulate_threshold:
        print(f"  【分批建倉 (Accumulate)】- 分數中等 ({total_score} >= {accumulate_threshold})。建議以資金的 10%-15% 試單，往下金字塔承接。")
    elif total_score > 20:
        print(f"  【觀望等待 (Hold/Wait)】- 尚缺乏足夠的安全邊際與恐慌溢價，耐心等待更好的打擊區。")
    else:
        print("  【嚴格避險 (Danger)】- 系統偵測到嚴重破壞，籌碼與資金雙輸，切勿接刀！")
    print("="*70 + "\n")