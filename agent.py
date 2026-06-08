import GAFI, vix_monitor, retail_sentiment, MACD, RSI, foreign_flow, foreign_flow_stock
import fundamental_agent
import us_macro
import global_macro
import naaim_monitor
import yfinance as yf
import pandas as pd
import numpy as np

def _fetch_ticker_data(ticker, period="1y"): # Default to 1 year for 240MA, RSI, MACD
    """
    統一從 yfinance 獲取指定股票/ETF 的歷史數據。
    包含健壯的錯誤處理。
    """
    try:
        df = yf.Ticker(ticker).history(period=period)
        if df.empty:
            print(f"⚠️ {ticker} 數據為空，請檢查代號或時間範圍。")
            return None
        return df
    except Exception as e:
        print(f"🚨 無法從 yfinance 獲取 {ticker} 數據: {e}")
        return None

def calculate_dynamic_score(current_val, min_val, max_val, max_score, inverse=False, clamp=True):
    """動態歸一化引擎 (Dynamic Normalizer)，可選是否鉗制在 0-1 區間"""
    if max_val == min_val: return 0
    
    if clamp:
        ratio = max(0, min(1, (current_val - min_val) / (max_val - min_val)))
    else:
        ratio = (current_val - min_val) / (max_val - min_val)

    if inverse:
        ratio = 1 - ratio
    return int(ratio * max_score)

def calculate_vix_score(vix_val):
    """
    【升級】分段式 VIX 評分引擎：
    - VIX <= 15: 0 分 (極度樂觀)
    - 15 ~ 35 (常態恐慌區間): 0 分 -> 60 分 (VIX 越高分越高)
    - 35 ~ 80 (極端黑天鵝區): 60 分 -> 100 分 (VIX 越高分越高)
    """
    if vix_val <= 15: return 0
    elif vix_val <= 35:
        return calculate_dynamic_score(vix_val, 15, 35, 60)
    elif vix_val <= 80:
        return 60 + calculate_dynamic_score(vix_val, 35, 80, 40) # 在 60 分基礎上再加 40 分
    else: # VIX > 80, 極端情況，直接滿分
        return 100

def calculate_vix_roc_score(roc_percent):
    """
    【升級】VIX 變化率 (ROC) 評分：
    只有 VIX 短期急速飆升 (ROC > 10%) 才會給予情緒加分。最高分 100 分。
    若 VIX 正在下降 (ROC <= 0)，表示恐慌降溫，給 0 分以拖低群組平均。
    """
    if roc_percent <= 0: return 0 # VIX下降或不變不加分
    return calculate_dynamic_score(roc_percent, 10, 60, 100) # 飆升 60% 給滿分

def calculate_fear_greed_score(fg_index):
    """
    CNN 恐懼貪婪指數評分：
    <= 25 (極度恐慌) 獲得滿分 100 分 (反向分數)
    >= 75 (極度貪婪) 獲得 0 分
    """
    if fg_index <= 25: return 100
    if fg_index >= 75: return 0
    # 25-75 之間反向歸一化, 25->100分, 75->0分
    return calculate_dynamic_score(fg_index, 25, 75, 100, inverse=True)

def calculate_futures_tolerance(ticker_df, base_futures_min, base_futures_max):
    """
    依照標的價格趨勢調整外資空單容忍度。
    股價越強，空單下限放寬；股價越弱，空單下限收窄。
    """
    neutral_result = {
        "price_trend_status": "NEUTRAL",
        "price_trend_reason": "資料不足，沿用原始外資空單容忍區間",
        "price_change_20d_percent": 0.0,
        "futures_tolerance_factor": 1.0,
        "adjusted_futures_min": int(base_futures_min),
        "adjusted_futures_max": int(base_futures_max),
    }

    if ticker_df is None or len(ticker_df) < 60:
        return neutral_result

    close_series = ticker_df["Close"].dropna()
    if len(close_series) < 60:
        return neutral_result

    current_price = float(close_series.iloc[-1])
    previous_20d_price = float(close_series.iloc[-21])
    ma20 = float(close_series.rolling(window=20).mean().iloc[-1])
    ma60 = float(close_series.rolling(window=60).mean().iloc[-1])

    if previous_20d_price == 0:
        return neutral_result

    price_change_20d_percent = ((current_price - previous_20d_price) / previous_20d_price) * 100

    is_strong_uptrend = price_change_20d_percent >= 8 and current_price > ma20 > ma60
    is_uptrend = price_change_20d_percent >= 3 or current_price > ma20
    is_strong_downtrend = price_change_20d_percent <= -8 and current_price < ma20 < ma60
    is_downtrend = price_change_20d_percent <= -3 or current_price < ma20

    if is_strong_uptrend:
        price_trend_status = "STRONG_UPTREND"
        futures_tolerance_factor = 1.35
        price_trend_reason = "20日漲幅明顯且價格站上20MA/60MA，外資空單容忍度大幅提高"
    elif is_uptrend:
        price_trend_status = "UPTREND"
        futures_tolerance_factor = 1.20
        price_trend_reason = "價格偏多，外資空單容忍度提高"
    elif is_strong_downtrend:
        price_trend_status = "STRONG_DOWNTREND"
        futures_tolerance_factor = 0.65
        price_trend_reason = "20日跌幅明顯且價格跌破20MA/60MA，外資空單容忍度大幅下降"
    elif is_downtrend:
        price_trend_status = "DOWNTREND"
        futures_tolerance_factor = 0.80
        price_trend_reason = "價格偏弱，外資空單容忍度下降"
    else:
        price_trend_status = "NEUTRAL"
        futures_tolerance_factor = 1.00
        price_trend_reason = "價格處於中性區間，沿用原始外資空單容忍度"

    adjusted_futures_min = int(base_futures_min * futures_tolerance_factor)

    return {
        "price_trend_status": price_trend_status,
        "price_trend_reason": price_trend_reason,
        "price_change_20d_percent": float(price_change_20d_percent),
        "futures_tolerance_factor": float(futures_tolerance_factor),
        "adjusted_futures_min": adjusted_futures_min,
        "adjusted_futures_max": int(base_futures_max),
    }

# ==========================================
# 模組 1：市場狀態機 (Regime Detector)
# ==========================================
def detect_market_regime(macro_data, primary_vix, is_tw_stock, gold_mom_percent=0.0):
    is_black_swan = macro_data.get("is_black_swan", False) # 由 global_macro 提供
    macro_score = macro_data.get("macro_score", 0)
    
    # 黃金月變動 > 8.0% 作為黑天鵝觸發條件之一 (從 macro_data 獲取)
    if gold_mom_percent > 8.0 or primary_vix >= 35 or is_black_swan:
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
def calculate_position_size(regime, final_score):
    """根據市場狀態和最終得分計算建議的動態倉位。"""
    # 倉位比例僅限於攻擊型預算 (15-20%) 內進行分配
    if regime == "PANIC_CRISIS":
        if final_score >= 80: return "20% - 25% (火力全開，雷劈核心區)"
        elif final_score >= 50: return "10% - 15% (左側分批受雷)"
        else: return "5% (基礎守候位，確保在場)" 
    elif regime == "BULL_TREND":
        if final_score >= 70: return "20% - 30% (順勢加碼，右側突破)"
        elif final_score >= 50: return "10% - 15% (持倉續抱)"
        else: return "5% (動能減弱，準備減碼)"
    elif regime == "BEAR_TREND": # 空頭趨勢下，得分高代表錯殺機會，應保守試單
        if final_score >= 60: return "5% - 10% (保守試單，等待落底)"
        else: return "0% (保留現金)"
    else: # NEUTRAL_CHOPPY 震盪整理
        if final_score >= 75: return "5% - 10% (區間錯殺低接)"
        else: return "0% - 5% (保留現金實力)"

# ==========================================
# 主程式：多模組聚合與策略路由
# ==========================================
def run_diagnosis(ticker, manual_futures, is_tw_stock, manual_vix, futures_min=-50000, futures_max=10000):
    market_str = "台股" if is_tw_stock else "美股"
    print(f"\n[交易輔助工具 - 邏輯升級版] 標的：{ticker} ({market_str})")
    print("="*70)
    
    agent_notes = []
    
    # 1. 獲取標的歷史數據 (一次性獲取)
    ticker_df = _fetch_ticker_data(ticker, period="1y") # 至少需要 240 交易日數據
    if ticker_df is None: 
        agent_notes.append(f"🚨 無法獲取 {ticker} 數據，跳過詳細分析。")
        print("\n" + "⚠️ 診斷無法完成，請檢查標的代號。" + "\n" + "="*70 + "\n")
        return {
            "ok": False,
            "ticker": ticker,
            "market": market_str,
            "error": f"無法獲取 {ticker} 數據，請檢查標的代號。",
            "notes": agent_notes
        }

    # 2. 獲取宏觀數據
    macro_data = {}
    gold_mom_percent = 0.0
    try:
        macro_data = global_macro.get_capital_flow_status() # 假設會返回 macro_score 和 is_black_swan, gold_mom_percent
        gold_mom_percent = macro_data.get("gold_month_change_percent", 0.0) # 從 global_macro 獲取黃金月變動
        for n in macro_data.get("notes", []): agent_notes.append(n)
    except Exception as e:
        agent_notes.append(f"⚠️ 獲取全球宏觀資金流數據失敗: {e}")
        macro_data = {"macro_score": 0, "is_black_swan": False, "notes": ["宏觀數據不可用。"]}
        
    # 3. 自動抓取美股 VIX 與計算 5 日 ROC
    us_vix_val = 20.0 
    vix_roc_percent = 0.0
    try:
        vix_df = _fetch_ticker_data("^VIX", period="6d") 
        if vix_df is not None and len(vix_df) >= 2:
            us_vix_val = float(vix_df['Close'].iloc[-1])
            prev_us_vix = float(vix_df['Close'].iloc[0]) # 約 5 個交易日前的 VIX
            vix_roc_percent = ((us_vix_val - prev_us_vix) / prev_us_vix) * 100
    except Exception as e:
        agent_notes.append(f"⚠️ 無法獲取或計算美股 VIX 數據: {e}")

    # 狀態機判定：取 台股/美股 較高的 VIX 作為風險警報依據
    primary_vix = max(manual_vix, us_vix_val) if is_tw_stock else us_vix_val
    regime_info = detect_market_regime(macro_data, primary_vix, is_tw_stock, gold_mom_percent)
    current_regime = regime_info["regime"]
    
    print(f"🌍 【市場狀態機 (Regime)】: {regime_info['desc']}")
    
    # ==========================================
    # 4. 因子群組化 (Factor Groups)
    #    所有因子分數在此標準化為 0-100。
    # ==========================================
    groups = {
        "Sentiment": [], "Flow": [], "Fundamental": [], "Technical": []
    }
    futures_tolerance_data = None

    # --- A. 情緒因子 (Sentiment) ---
    # 美股 VIX
    us_vix_score = calculate_vix_score(us_vix_val)
    groups["Sentiment"].append(us_vix_score)
    agent_notes.append(f"🌎 全球情緒: 美股 VIX={us_vix_val:.2f} (分段得分:{us_vix_score}/100)")

    # VIX 變化率
    roc_score = calculate_vix_roc_score(vix_roc_percent)
    groups["Sentiment"].append(roc_score)
    agent_notes.append(f"🌎 全球情緒: VIX 5日ROC={vix_roc_percent:+.1f}% (動能得分:{roc_score}/100)")

    # CNN Fear & Greed Index (恐懼貪婪指數)
    try:
        fg_index = GAFI.get_fear_greed_index() # 假設此模組提供 0-100 的指數
        fg_score = calculate_fear_greed_score(fg_index)
        groups["Sentiment"].append(fg_score)
        agent_notes.append(f"📈 CNN 恐懼貪婪指數: {fg_index:.1f} (得分:{fg_score}/100)")
    except Exception as e:
        agent_notes.append(f"⚠️ 無法獲取 CNN 恐懼貪婪指數: {e}")

    # --- B. 資金與籌碼因子 (Flow) ---
    # NAAIM 聰明錢籌碼與 S&P 500 背離判定
    # 這裡先預設傳入模擬值，實際應用應從 naaim_monitor 取得最新數據
    naaim_sim_val = 78 # 模擬值，例如當前 NAAIM 指數
    naaim_sim_trend = 'DOWN' # 模擬值，例如當前 NAAIM 趨勢
    try:
        # 假設 naaim_monitor 內部會自行獲取 S&P 500 數據
        naaim_res = naaim_monitor.evaluate_naaim_sp500_logic(naaim_current=naaim_sim_val, naaim_trend=naaim_sim_trend)
        # 將 NAAIM 的判斷分數 (-15 到 +15) 映射至 0-100 的百分制因子中
        naaim_normalized_score = max(0, min(100, 50 + (naaim_res.get('score', 0) * 3.33))) # 0分對應-15, 50分對應0, 100分對應+15
        groups["Flow"].append(naaim_normalized_score)
        agent_notes.append(f"🧠 聰明錢追蹤 (NAAIM): {naaim_res.get('log', 'N/A')} (得分:{naaim_normalized_score}/100)")
    except Exception as e:
        agent_notes.append(f"⚠️ NAAIM 追蹤異常: {e}")

    # --- C. 基本面與價值護城河因子 (Fundamental) ---
    fund_data = {}
    try:
        fund_data = fundamental_agent.get_fundamentals(ticker, is_crisis_mode=current_regime=="PANIC_CRISIS")
        # 假設 fundamental_agent 的分數為原始點數 (例如 P/E +15分)，需要歸一化至 0-100
        if fund_data.get("pe_score") is not None: 
            groups["Fundamental"].append(calculate_dynamic_score(fund_data["pe_score"], 0, 15, 100)) # P/E 最高 15 分
            agent_notes.append(f"🏦 基本面: 產業估值 (P/E或P/B) 得分({groups['Fundamental'][-1]}/100)")
        if fund_data.get("fibo_score") is not None: 
            groups["Fundamental"].append(calculate_dynamic_score(fund_data["fibo_score"], 0, 15, 100)) # Fibo 最高 15 分
            agent_notes.append(f"🏦 基本面: 動態防線 (斐波那契) 得分({groups['Fundamental'][-1]}/100)")
        if fund_data.get("sd_score") is not None: 
            groups["Fundamental"].append(calculate_dynamic_score(fund_data["sd_score"], 0, 10, 100)) # SD 最高 10 分
            agent_notes.append(f"🏦 基本面: 產業微觀數據 (庫存/產能) 得分({groups['Fundamental'][-1]}/100)")

        for n in fund_data.get("notes", []): agent_notes.append(n)
    except Exception as e:
        agent_notes.append(f"⚠️ 獲取基本面數據失敗: {e}")

    # --- D. 技術面錯殺因子 (Technical) ---
    # 1. 年線乖離率 (240MA) 極端錯殺優先判斷
    is_extreme_deviation = False
    bias_ratio_240ma = None
    try:
        if len(ticker_df) >= 240:
            # 計算 240 日移動平均線 (年線)
            ma240 = ticker_df['Close'].rolling(window=240).mean().iloc[-1]
            current_price = ticker_df['Close'].iloc[-1]
            if ma240 and ma240 != 0:
                bias_ratio_240ma = ((current_price - ma240) / ma240) * 100
                agent_notes.append(f"📊 技術面: 年線乖離率 {bias_ratio_240ma:.2f}%")
                if bias_ratio_240ma <= -20:
                    is_extreme_deviation = True
                    groups["Technical"].append(100) # 給予技術面滿分 100
                    agent_notes.append(f"⚡ 【雷劈加權】年線乖離率達 {bias_ratio_240ma:.2f}%！極端錯殺，強制給予技術面滿分。")
        else:
            agent_notes.append(f"⚠️ 數據不足 {len(ticker_df)} 天，無法計算 240MA 乖離率。")
    except Exception as e:
        agent_notes.append(f"⚠️ 計算 240MA 乖離率失敗: {e}")

    # 只有在未觸發極端乖離時才計算其他技術指標
    if not is_extreme_deviation:
        macd_signals = None
        
        # RSI Calculation
# RSI Calculation
        try:
            rsi_res_df = RSI.get_40_days_rsi(ticker_df) 
            if rsi_res_df is not None and not rsi_res_df.empty:
                curr_rsi = rsi_res_df['RSI'].iloc[-1]
                days_under_30 = (rsi_res_df['RSI'].tail(10) < 30).sum()
                
                # --- 新增：呼叫 RSI 動能反轉訊號 ---
                rsi_signals = RSI.calculate_rsi_signals(ticker_df)
                is_rsi_bullish = rsi_signals.get('bullish_reversal') if rsi_signals else False
                is_rsi_bearish = rsi_signals.get('bearish_reversal') if rsi_signals else False

                # 💡 邏輯優化：如果出現了 RSI 底部黃金交叉，就打破「鈍化過濾」的限制
                if days_under_30 >= 4 and not is_rsi_bullish:
                    # 強勢空頭【鈍化區】，沒收 RSI 加分，改看 MACD 動能
                    macd_signals = MACD.calculate_macd_signals(ticker_df) 
                    macd_momentum_score = 0
                    if macd_signals and macd_signals.get('golden_cross') and macd_signals.get('histogram_positive_flip'):
                        macd_momentum_score = 50 
                        agent_notes.append(f"🎯 技術面: 強勢空頭【鈍化區】，RSI 沒收加分，改看 MACD 動能 ({macd_momentum_score}/100)。")
                    else:
                        agent_notes.append(f"⚠️ 技術面: 強勢空頭【鈍化區】，RSI 與 MACD 皆無明顯反轉動能。")
                    groups["Technical"].append(macd_momentum_score)
                else:
                    # 正常動態給分
                    rsi_score = calculate_dynamic_score(curr_rsi, 15, 40, 100, inverse=True) 
                    
                    # --- ⚡ 動能衰竭策略加權 ---
                    if is_rsi_bullish:
                        rsi_score = min(100, rsi_score + 30) # 底部交叉，強力加分
                        agent_notes.append(f"🔥 技術面: 偵測到 RSI 底部黃金交叉 (<=32區間)！動能反轉看漲，強力加分 (+30)。")
                    elif is_rsi_bearish:
                        rsi_score = max(0, rsi_score - 30) # 頂部交叉，防禦扣分
                        agent_notes.append(f"🚨 技術面: 偵測到 RSI 高檔死亡交叉 (>=70區間)！動能衰竭預備回調，防禦扣分 (-30)。")
                    else:
                        agent_notes.append(f"🎯 技術面: 動態 RSI 得分 ({rsi_score}/100)。")

                    groups["Technical"].append(rsi_score)
            else:
                agent_notes.append("⚠️ 無法計算 RSI，跳過 RSI 因子。")
        except Exception as e:
            agent_notes.append(f"⚠️ 計算 RSI 因子異常: {e}")

        # MACD 爆量背離 (+20分) - US 500 volume check
        sp500_volume_trigger = False
        try:
            sp500_df = _fetch_ticker_data("^GSPC", period="40d") # Fetch enough data for 30-day average
            if sp500_df is not None and len(sp500_df) >= 30:
                sp500_last_close = sp500_df['Close'].iloc[-1]
                sp500_prev_close = sp500_df['Close'].iloc[-2]
                sp500_current_volume = sp500_df['Volume'].iloc[-1]
                sp500_30d_avg_volume = sp500_df['Volume'].iloc[-31:-1].mean()
                
                if sp500_last_close < sp500_prev_close and sp500_current_volume > (sp500_30d_avg_volume * 1.5):
                    sp500_volume_trigger = True
                    agent_notes.append("📊 US 500 檢測: 大量收黑，符合恐慌拋售極致條件。")
            else:
                agent_notes.append("⚠️ 無法取得足夠的 US 500 數據以判斷爆量背離。")
        except Exception as e:
            agent_notes.append(f"⚠️ 無法取得或計算 US 500 成交量資料: {e}")

        # 結合 US 500 交易量與標的 MACD 訊號
        if sp500_volume_trigger:
            if macd_signals is None: # 如果 MACD 訊號還沒被計算過 (例如 RSI 沒有鈍化)
                try:
                    macd_signals = MACD.calculate_macd_signals(ticker_df) # 假設 MACD 模組接收 DataFrame
                except Exception as e:
                    agent_notes.append(f"⚠️ 計算 MACD 訊號失敗: {e}")

            if macd_signals and macd_signals.get('golden_cross') and macd_signals.get('histogram_positive_flip'):
                groups["Technical"].append(20) # 觸發加分 20 點 (直接加到 Technical 群組)
                agent_notes.append(f"⚡ 技術面: MACD 爆量背離 (+20分) 觸發。")
            else:
                agent_notes.append("💡 技術面: US 500 爆量但標的 MACD 未觸發正向背離。")

    # --- 僅台股模式下啟用的因子 (Sentiment & Flow) ---
    if is_tw_stock:
        futures_tolerance_data = calculate_futures_tolerance(ticker_df, futures_min, futures_max)

        # 台股 VIX 獨立加權
        tw_vix_score = calculate_vix_score(manual_vix)
        groups["Sentiment"].append(tw_vix_score)
        agent_notes.append(f"🇹🇼 本地情緒: 台股 VIX={manual_vix:.2f} (分段得分:{tw_vix_score}/100)")
        
        # 散戶多空比
        try:
            retail_data = retail_sentiment.get_retail_sentiment_fixed() # 假設此模組會自行獲取數據
            if retail_data and retail_data.get("ratio") is not None:
                # 散戶淨留倉比例 <= -10% 為極度看空，給予高分
                if retail_data["ratio"] <= -10: 
                    r_score = calculate_dynamic_score(abs(retail_data["ratio"]), 10, 30, 100, clamp=True) # 10->0, 30->100
                    groups["Sentiment"].append(r_score)
                    agent_notes.append(f"📊 散戶情緒 (小台/微台): 淨空單比例 {-retail_data['ratio']:.1f}% (得分:{r_score}/100)")
                elif retail_data["ratio"] >= 10:
                    r_score = calculate_dynamic_score(retail_data["ratio"], 10, 30, 100, inverse=True, clamp=True) # 10->100, 30->0 (反向)
                    groups["Sentiment"].append(r_score)
                    agent_notes.append(f"📊 散戶情緒 (小台/微台): 淨多單比例 {retail_data['ratio']:.1f}% (擁擠風險，得分:{r_score}/100)")
                else:
                    groups["Sentiment"].append(50) # 中立區給予中等分數
                    agent_notes.append(f"📊 散戶情緒 (小台/微台): 淨留倉比例 {retail_data['ratio']:.1f}% (中性區，得分:50/100)")
            else:
                agent_notes.append("⚠️ 無法獲取散戶多空比數據。")
        except Exception as e:
            agent_notes.append(f"⚠️ 獲取散戶多空比失敗: {e}")

        # 外資期指淨額 (手動輸入)
        if manual_futures != 0: # 僅在有手動輸入時才加入考量
            adjusted_futures_min = futures_tolerance_data["adjusted_futures_min"]
            adjusted_futures_max = futures_tolerance_data["adjusted_futures_max"]

            # 將期指淨額從調整後區間映射到 0-100
            # 淨空單越多 (趨近 min) 得分越高，淨多單越多 (趨近 max) 得分越低
            futures_score = calculate_dynamic_score(
                manual_futures,
                adjusted_futures_min,
                adjusted_futures_max,
                100,
                inverse=True,
            )
            groups["Flow"].append(futures_score)
            agent_notes.append(
                f"📊 資金籌碼: 外資期指淨額 {manual_futures:+,} "
                f"(趨勢:{futures_tolerance_data['price_trend_status']}, "
                f"20日:{futures_tolerance_data['price_change_20d_percent']:+.1f}%, "
                f"容忍係數:{futures_tolerance_data['futures_tolerance_factor']:.2f}, "
                f"調整區間:{adjusted_futures_min:+,}~{adjusted_futures_max:+,}, "
                f"得分:{futures_score}/100)"
            )
            agent_notes.append(f"🧭 空單容忍度: {futures_tolerance_data['price_trend_reason']}")

        # 外資現貨買賣超 (個股)
        try:
            stock_institutional_flow_df = foreign_flow_stock.get_institutional_flow(ticker) # 假設此模組接收 ticker
            if stock_institutional_flow_df is not None and not stock_institutional_flow_df.empty:
                net_buy_lots = int((pd.to_numeric(stock_institutional_flow_df['buy'], errors='coerce').sum() - pd.to_numeric(stock_institutional_flow_df['sell'], errors='coerce').sum()) / 1000)
                # 淨買超越多得分越高，上限設為 5000 張代表非常積極
                flow_score = calculate_dynamic_score(net_buy_lots, -5000, 5000, 100) 
                groups["Flow"].append(flow_score)
                agent_notes.append(f"📊 資金籌碼: 外資現貨淨買賣超 {net_buy_lots:+,} 張 (得分:{flow_score}/100)")
            else:
                agent_notes.append("⚠️ 無法獲取個股外資現貨買賣超數據。")
        except Exception as e:
            agent_notes.append(f"⚠️ 獲取個股外資現貨買賣超失敗: {e}")

    # ==========================================
    # 5. 策略動態加權 (Strategy Routing)
    # ==========================================
    avg_scores = {k: (np.mean(v) if v else 50) for k, v in groups.items()} # 若無數據，預設中性 50 分
    
    print("\n🧩 【因子群組獨立分析 (百分制)】")
    print(f"  ▶ 恐慌情緒 (Sentiment): {avg_scores['Sentiment']:.1f}/100")
    print(f"  ▶ 資金籌碼 (Flow)     : {avg_scores['Flow']:.1f}/100")
    print(f"  ▶ 價值護城河 (Fund)   : {avg_scores['Fundamental']:.1f}/100")
    print(f"  ▶ 技術錯殺 (Tech)     : {avg_scores['Technical']:.1f}/100")

    final_score = 0
    strategy_desc = ""

    if current_regime == "PANIC_CRISIS":
        final_score = (avg_scores['Sentiment'] * 0.4) + (avg_scores['Technical'] * 0.3) + (avg_scores['Fundamental'] * 0.3)
        strategy_desc = "左側雷劈承接策略 (Left-Side Panic Buy)"
    elif current_regime == "BEAR_TREND": 
        final_score = (avg_scores['Fundamental'] * 0.3) + (avg_scores['Flow'] * 0.3) + (avg_scores['Technical'] * 0.2) + (avg_scores['Sentiment'] * 0.2)
        strategy_desc = "空頭趨勢防禦策略 (Bearish Trend Defense)"
    elif current_regime == "BULL_TREND":
        final_score = (avg_scores['Flow'] * 0.4) + (avg_scores['Technical'] * 0.4) + (avg_scores['Fundamental'] * 0.2)
        strategy_desc = "右側順勢動能策略 (Right-Side Momentum)"
    else: # NEUTRAL_CHOPPY
        final_score = (avg_scores['Fundamental'] * 0.3) + (avg_scores['Flow'] * 0.3) + (avg_scores['Technical'] * 0.2) + (avg_scores['Sentiment'] * 0.2)
        strategy_desc = "區間均衡策略 (Mean-Reversion)"

    recommended_position = calculate_position_size(current_regime, final_score)

    print("\n" + "⚖️ 【AI Quant 綜合決策引擎】 ⚖️")
    print("-" * 70)
    for n in agent_notes:
        print(f"  {n}")
    print("-" * 70)
    print(f"🎯 採用策略: {strategy_desc}")
    print(f"📊 最終加權決策指數: {final_score:.1f} / 100")
    print(f"💰 【風控與倉位建議】: {recommended_position}")
    print("="*70 + "\n")

    # 額外回傳結構化資料給網頁使用。終端機版仍保留原本的文字輸出，
    # 因此 main.py 與既有分析流程不需要改動。
    return {
        "ok": True,
        "ticker": ticker,
        "market": market_str,
        "price_history": ticker_df[["Close"]].copy(),
        "current_price": float(ticker_df["Close"].iloc[-1]),
        "regime": current_regime,
        "regime_desc": regime_info["desc"],
        "strategy": strategy_desc,
        "recommended_position": recommended_position,
        "final_score": float(final_score),
        "group_scores": {name: float(score) for name, score in avg_scores.items()},
        "group_factors": groups,
        "notes": agent_notes,
        "metrics": {
            "us_vix": float(us_vix_val),
            "vix_roc_percent": float(vix_roc_percent),
            "tw_vix": float(manual_vix) if is_tw_stock else None,
            "foreign_futures": int(manual_futures) if is_tw_stock else None,
            "price_trend_status": futures_tolerance_data["price_trend_status"] if futures_tolerance_data else None,
            "price_change_20d_percent": float(futures_tolerance_data["price_change_20d_percent"]) if futures_tolerance_data else None,
            "futures_tolerance_factor": float(futures_tolerance_data["futures_tolerance_factor"]) if futures_tolerance_data else None,
            "adjusted_futures_min": int(futures_tolerance_data["adjusted_futures_min"]) if futures_tolerance_data else None,
            "adjusted_futures_max": int(futures_tolerance_data["adjusted_futures_max"]) if futures_tolerance_data else None,
            "gold_month_change_percent": float(gold_mom_percent),
            "bias_ratio_240ma": float(bias_ratio_240ma) if bias_ratio_240ma is not None else None
        }
    }
