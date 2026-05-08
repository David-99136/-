# streamlit run app.py 使用該指令開啟本地部屬之 Streamlit 網頁應用程式
import streamlit as st
import sys
import io
import re
import agent # 載入您原本的系統模組

# 1. 網頁基本設定
st.set_page_config(page_title="左側交易投資決策 AI", page_icon="📈", layout="wide")

st.title("🤖 左側交易 AI 投資決策系統")
st.markdown("這是一個結合宏觀資金流、大數據情緒與基本面的左側交易診斷面板。")

# 2. 側邊欄：設定參數
with st.sidebar:
    st.header("⚙️ 參數設定")
    ticker_input = st.text_input("標的代號 (例如: 2330, AAPL)", value="2330")
    
    # 自動判斷台/美股
    ticker = ticker_input.strip().upper()
    is_tw_stock = False
    if re.match(r'^\d{4,5}[A-Z]?$', ticker):
        ticker = f"{ticker}.TW"
        is_tw_stock = True
    elif '.TW' in ticker or '.TWO' in ticker:
        is_tw_stock = True
        
    st.success(f"偵測市場: {'台股' if is_tw_stock else '美股'}\n\n執行代號: {ticker}")

    manual_vix = 20.0
    manual_futures = 0
    
    if is_tw_stock:
        manual_vix = st.number_input("輸入台股 VIX", value=20.0, step=1.0)
        manual_futures = st.number_input("輸入外資期指淨額 (口)", value=0, step=1000)
    else:
        st.info("🌎 美股模式：VIX 與大盤量價將自動從美股市場同步。")
        
    run_btn = st.button("🚀 開始啟動診斷", use_container_width=True, type="primary")

# 3. 主畫面：顯示結果
if run_btn:
    with st.spinner("系統正在矩陣搜尋並運算中，請稍候... ⏳"):
        # 攔截原本 terminal 的 print 輸出，導向至網頁顯示
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()
        
        try:
            agent.run_diagnosis(ticker, manual_futures, is_tw_stock, manual_vix)
        except Exception as e:
            print(f"\n🚨 系統異常: {e}")
        finally:
            sys.stdout = old_stdout
            
        output_text = captured_output.getvalue()
        
        # 解析並抽取總分 (讓 UI 有明顯的儀表板)
        score_match = re.search(r'奧地利學派決策指數:\s*(-?\d+)', output_text)
        if score_match:
            score = int(score_match.group(1))
            
            # 根據分數決定建議
            if score >= 70:
                advice = "🔥 強烈買進 (Strong Buy)"
            elif score >= 45:
                advice = "✅ 分批建倉 (Accumulate)"
            elif score > 20:
                advice = "⚖️ 觀望或減碼 (Hold/Reduce)"
            else:
                advice = "🚨 高度警戒 (Danger)"

            # 顯示大字體儀表板
            col1, col2 = st.columns(2)
            with col1:
                st.metric(label="🎯 奧地利學派決策指數 (滿分 100)", value=score)
            with col2:
                st.metric(label="💡 系統最終判定", value=advice)
                
        st.divider()
        st.markdown("### 📊 詳細診斷日誌")
        # 顯示完整終端機日誌
        st.code(output_text, language="log")
else:
    # 預設提示畫面
    st.info("👈 請從左側設定標的與參數，並點擊「開始啟動診斷」。")