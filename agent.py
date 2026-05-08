import GAFI, vix_monitor, retail_sentiment, MACD, RSI, foreign_flow, foreign_flow_stock
import fundamental_agent
import us_macro
import global_macro
import yfinance as yf

def run_diagnosis(ticker, manual_futures, is_tw_stock, manual_vix):
    market_str = "台股" if is_tw_stock else "美股"
    print(f"\n[AI Agent] 啟動左側交易診斷程序 - 標的：{ticker} ({market_str})")
    print("="*64)
    
    total_score = 0
    agent_notes = []

    # ==========================================
    # 0. 提前抓取技術面 
    # ==========================================
    print("🔍 啟動技術面探測 (確保不盲目接刀)...")
    macd_res = MACD.get_40_days_macd(ticker)
    rsi_res = RSI.get_40_days_rsi(ticker)
    curr_rsi = rsi_res['RSI'].iloc[-1] if rsi_res is not None and not rsi_res.empty else 50.0

    # ==========================================
    # 1. 戰略層：全球資金流向與避險掃描 (宏觀防禦)
    # ==========================================
    print("🔍 執行大趨勢與宏觀資金輪動掃描...")
    
    try:
        macro_data = global_macro.get_capital_flow_status()
        total_score += macro_data.get("macro_score", 0)
        for n in macro_data.get("notes", []):
            agent_notes.append(n)
            
        if macro_data.get("is_black_swan"):
            total_score -= 30 
            agent_notes.append("🛑 【系統強制覆寫】：偵測到黑天鵝級避險資金流動，總分重罰，嚴禁接刀！ (-30)")
    except Exception as e:
        agent_notes.append(f"⚠️ 資金流向掃描異常: {e}")

    # ==========================================
    # 2. 戰略層：外資籌碼與市場情緒 
    # ==========================================
    try: GAFI.get_gafi_v2026()
    except: pass

    if is_tw_stock:
        print(f"\n📊 【台股 VIX】 接收手動輸入數值: {manual_vix:.2f}")
        if manual_vix >= 30:
            total_score += 15
            agent_notes.append(f"📈 大趨勢 (台股VIX): 極度恐慌 ({manual_vix:.2f})，符合左側買進條件 (+15)")
        elif manual_vix >= 20:
            total_score += 10
            agent_notes.append(f"📈 大趨勢 (台股VIX): 市場波動加劇 ({manual_vix:.2f}) (+10)")

        # 🛑 【籌碼核爆區】：台指期貨外資空單 (核心權重)
        if manual_futures < -45000:
            total_score -= 25
            agent_notes.append(f"🚨 警告 (籌碼核災)：外資期指空單高達 {manual_futures:+,} 口！大盤處於系統性風險邊緣，嚴禁加碼 (-25)")
        elif manual_futures < -30000:
            if curr_rsi >= 50:
                total_score -= 10
                agent_notes.append(f"🛑 警訊 (壓盤嚴重)：外資空單重兵部署 ({manual_futures:+,} 口) 且位階未觸底，提防大跌 (-15)")
            else:
                total_score -= 5
                agent_notes.append(f"⚠️ 警訊 (外資承壓)：空單沉重 ({manual_futures:+,} 口)，雖有超賣跡象仍需謹慎 (-5)")
        elif manual_futures < -15000:
            agent_notes.append(f"⚖️ 大趨勢 (期指): 外資空單水位偏高 ({manual_futures:+,} 口) (+0)")
        else:
            total_score += 10
            agent_notes.append(f"🟢 大趨勢 (期指): 外資部位相對安全 ({manual_futures:+,} 口) (+10)")

        # 散戶多空比聯動
        try: 
            retail_data = retail_sentiment.get_retail_sentiment_fixed()
            r_ratio = retail_data.get("ratio", 0)
            if r_ratio <= -15:
                total_score += 20
                agent_notes.append(f"📊 散戶籌碼: 散戶極度看空 ({r_ratio:.1f}%)，具備強大反向買進動能 (+20)")
            elif r_ratio >= 15:
                total_score -= 10
                agent_notes.append(f"⚠️ 散戶籌碼: 散戶過度追多 ({r_ratio:.1f}%)，籌碼混亂不宜接刀 (-10)")
            else:
                total_score += 5
                agent_notes.append(f"⚖️ 散戶籌碼: 心理偏差中性 ({r_ratio:.1f}%) (+5)")
        except: pass

        try: foreign_flow.get_market_institutional_flow()
        except: pass

    else:
        # 美股邏輯
        vix_val = 20.0
        try:
            vix_monitor.get_us_vix_monitor() 
            vix_df = yf.Ticker("^VIX").history(period="1d")
            vix_val = float(vix_df['Close'].iloc[-1])
        except Exception: pass
        
        if vix_val >= 30:
            total_score += 25
            agent_notes.append(f"📈 大趨勢 (美股VIX): 全球極度恐慌 ({vix_val:.2f})，大膽執行左側建倉 (+25)")
        elif vix_val >= 20:
            total_score += 15
            agent_notes.append(f"📈 大趨勢 (美股VIX): 波動率上升 ({vix_val:.2f})，逐步往下承接 (+15)")
            
        us500_data = us_macro.get_us500_trend()
        total_score += us500_data.get("score", 0)
        for n in us500_data.get("notes", []):
            agent_notes.append(n)

    # ==========================================
    # 3. 戰術層：基本面、估值與回測位階 
    # ==========================================
    print("🔍 執行價值河流圖、斐波那契與大數據新聞掃描...")
    fund_data = fundamental_agent.get_fundamentals(ticker)
    
    total_score += fund_data.get("pe_score", 0)
    total_score += fund_data.get("fibo_score", 0)
    total_score += fund_data.get("sd_score", 0)
    
    for n in fund_data["notes"]:
        agent_notes.append(n)

    # ==========================================
    # 4. 執行層：技術面給分 
    # ==========================================
    rsi_max_score = 10 if is_tw_stock else 15
    if curr_rsi < 30:
        total_score += rsi_max_score
        agent_notes.append(f"🎯 技術面 (RSI): 處於極度超賣區 ({curr_rsi:.1f})，絕佳左側買點 (+{rsi_max_score})")
    elif curr_rsi < 45:
        total_score += (rsi_max_score // 2)
        agent_notes.append(f"🔎 技術面 (RSI): 相對低檔 ({curr_rsi:.1f}) (+{rsi_max_score // 2})")
    else:
        agent_notes.append(f"🔥 技術面 (RSI): 偏高或過熱 ({curr_rsi:.1f})，不符左側建倉原則 (+0)")

    if is_tw_stock:
        net_stk_lots = 0
        try:
            stock_df = foreign_flow_stock.get_institutional_flow(ticker)
            if stock_df is not None and not stock_df.empty:
                net_stk_shares = stock_df['buy'].sum() - stock_df['sell'].sum()
                net_stk_lots = int(net_stk_shares / 1000)
                if net_stk_lots > 2000:
                    total_score += 5
                    agent_notes.append(f"🤝 個股籌碼: 法人逆勢吃貨 ({net_stk_lots:+,} 張) (+5)")
                elif net_stk_lots > 0:
                    total_score += 2
                    agent_notes.append(f"🤝 個股籌碼: 法人微幅買超 ({net_stk_lots:+,} 張) (+2)")
        except: pass

    # ==========================================
    # 最終診斷輸出
    # ==========================================
    print("\n" + "⚖️ 【AI Agent 左側交易綜合診斷】 ⚖️")
    print("-" * 64)
    print(f"🎯 左側交易決策指數: {total_score} / 100 (越接近100越適合左側建倉)")
    print("-" * 64)
    for n in agent_notes:
        print(f"  {n}")
    
    print("\n💡 系統總結：")
    if total_score >= 70:
        print("  【強烈買進 (Strong Buy)】- 宏觀資金健康且市場充滿恐慌，正是別人恐懼我貪婪的時刻！")
    elif total_score >= 45:
        print("  【分批建倉 (Accumulate)】- 結構中性偏低，可利用閒置資金採取金字塔式向下建倉。")
    elif total_score > 20:
        print("  【觀望或減碼 (Hold/Reduce)】- 缺乏恐慌溢價或面臨外資壓盤風險，耐心等待價格回落。")
    else:
        print("  【高度警戒 (Danger)】- 系統偵測到嚴重籌碼壓力或宏觀資金流出，切勿接刀！")
    print("="*64 + "\n")