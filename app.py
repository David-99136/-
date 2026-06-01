"""Streamlit 單頁版交易輔助儀表板。

啟動方式：
    streamlit run app.py
    #亦可直接執行此命令獲得網址
    # & 'C:\Users\User\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m streamlit run app.py
畫面只負責蒐集輸入與呈現結果，所有分析邏輯仍由 agent.py 統一處理。
"""

import io
import re
import sys

import pandas as pd
import streamlit as st

import agent


st.set_page_config(
    page_title="Macro Signal Lab | 趨勢輔助判斷工具",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def inject_finance_theme():
    """套用深色財經儀表板樣式，不需要額外下載圖片素材。"""
    st.markdown(
        """
        <style>
        :root {
            --bg: #06111f;
            --panel: rgba(10, 28, 46, 0.88);
            --panel-soft: rgba(14, 39, 61, 0.70);
            --line: rgba(86, 160, 181, 0.22);
            --text: #eaf6f7;
            --muted: #9cb8c1;
            --green: #56d59b;
            --gold: #e8bd67;
            --red: #ff7a84;
        }

        .stApp {
            color: var(--text);
            background:
                linear-gradient(rgba(6, 17, 31, 0.94), rgba(6, 17, 31, 0.97)),
                repeating-linear-gradient(0deg, transparent 0 39px, rgba(86,160,181,.08) 40px),
                repeating-linear-gradient(90deg, transparent 0 59px, rgba(86,160,181,.08) 60px);
        }

        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            opacity: .34;
            background:
                linear-gradient(145deg, transparent 0 54%, rgba(86,213,155,.16) 55% 56%, transparent 57%),
                linear-gradient(25deg, transparent 0 65%, rgba(232,189,103,.11) 66% 67%, transparent 68%);
        }

        .block-container {
            max-width: 1500px;
            padding-top: 1.6rem;
            padding-bottom: 3rem;
        }

        .hero {
            padding: 1.2rem 1.45rem;
            border: 1px solid var(--line);
            border-radius: 18px;
            background: linear-gradient(135deg, rgba(16,48,67,.96), rgba(8,24,41,.88));
            box-shadow: 0 18px 40px rgba(0,0,0,.20);
            margin-bottom: 1rem;
        }

        .eyebrow {
            margin: 0 0 .35rem 0;
            color: var(--green);
            font-size: .74rem;
            font-weight: 700;
            letter-spacing: .16em;
        }

        .hero h1 {
            margin: 0;
            font-size: clamp(1.8rem, 4vw, 3rem);
            letter-spacing: -.04em;
        }

        .hero p {
            max-width: 830px;
            margin: .5rem 0 0 0;
            color: var(--muted);
        }

        div[data-testid="stForm"],
        div[data-testid="stMetric"],
        div[data-testid="stExpander"] {
            border: 1px solid var(--line);
            border-radius: 15px;
            background: var(--panel);
        }

        div[data-testid="stMetric"] {
            padding: 1rem;
            min-height: 118px;
        }

        div[data-testid="stMetricLabel"] {
            color: var(--muted);
        }

        div[data-testid="stMetricValue"] {
            color: var(--text);
        }

        h2, h3 {
            letter-spacing: -.02em;
        }

        .section-kicker {
            color: var(--green);
            font-size: .74rem;
            font-weight: 700;
            letter-spacing: .13em;
            margin-bottom: -.45rem;
        }

        .decision-card {
            border-left: 4px solid var(--green);
            border-radius: 13px;
            padding: 1rem 1.1rem;
            background: var(--panel-soft);
            margin: .25rem 0 1rem 0;
        }

        .decision-card strong {
            color: var(--gold);
        }

        .disclaimer {
            color: var(--muted);
            font-size: .8rem;
            padding-top: .4rem;
        }

        .stButton button, .stFormSubmitButton button {
            border: 1px solid rgba(86,213,155,.45);
            background: linear-gradient(135deg, #19825d, #176a74);
            color: white;
            font-weight: 700;
        }

        .stButton button:hover, .stFormSubmitButton button:hover {
            border-color: var(--gold);
            color: white;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def normalize_ticker(ticker_input):
    """把常見台股代號補上 .TW，美股代號則維持原樣。"""
    ticker = ticker_input.strip().upper()
    if re.fullmatch(r"\d{4,5}[A-Z]?", ticker):
        return f"{ticker}.TW", True
    return ticker, ".TW" in ticker or ".TWO" in ticker


def get_advice(score):
    """將百分制決策分數轉成容易閱讀的行動提示。"""
    if score >= 70:
        return "偏積極：可依策略分批布局"
    if score >= 50:
        return "中性偏多：保留彈性並分段執行"
    if score >= 30:
        return "觀察：等待更明確的價格或籌碼訊號"
    return "偏保守：控制風險並保留現金"


def render_price_chart(result):
    """顯示近一年收盤價與 20 日、60 日移動平均線。"""
    price_df = result["price_history"].copy()
    price_df["MA20"] = price_df["Close"].rolling(20).mean()
    price_df["MA60"] = price_df["Close"].rolling(60).mean()
    chart_width, chart_height = 900, 310
    padding_left, padding_top, padding_bottom = 68, 22, 42
    plot_width = chart_width - padding_left - 20
    plot_height = chart_height - padding_top - padding_bottom

    # SVG 使用共同的最高價與最低價，讓三條線可在同一張圖上比較。
    valid_values = price_df[["Close", "MA20", "MA60"]].stack().dropna()
    min_price, max_price = float(valid_values.min()), float(valid_values.max())
    price_range = max(max_price - min_price, 1.0)
    point_count = max(len(price_df) - 1, 1)

    def build_points(column):
        points = []
        for position, value in enumerate(price_df[column]):
            if pd.notna(value):
                x_pos = padding_left + (position / point_count) * plot_width
                y_pos = padding_top + ((max_price - float(value)) / price_range) * plot_height
                points.append(f"{x_pos:.1f},{y_pos:.1f}")
        return " ".join(points)

    grid_lines = []
    for index in range(5):
        y_pos = padding_top + index * plot_height / 4
        label = max_price - index * price_range / 4
        grid_lines.append(
            f'<line x1="{padding_left}" y1="{y_pos:.1f}" x2="{chart_width - 20}" y2="{y_pos:.1f}" '
            f'stroke="rgba(156,184,193,.18)" stroke-width="1" />'
            f'<text x="{padding_left - 10}" y="{y_pos + 4:.1f}" text-anchor="end" '
            f'fill="#9cb8c1" font-size="11">{label:,.1f}</text>'
        )

    start_date = price_df.index[0].strftime("%Y-%m-%d")
    end_date = price_df.index[-1].strftime("%Y-%m-%d")
    st.markdown(
        f"""
        <svg viewBox="0 0 {chart_width} {chart_height}" width="100%" role="img" aria-label="價格趨勢圖">
            {''.join(grid_lines)}
            <polyline points="{build_points('Close')}" fill="none" stroke="#e8bd67" stroke-width="3" />
            <polyline points="{build_points('MA20')}" fill="none" stroke="#56d59b" stroke-width="2" />
            <polyline points="{build_points('MA60')}" fill="none" stroke="#69a7d7" stroke-width="2" />
            <text x="{padding_left}" y="{chart_height - 15}" fill="#9cb8c1" font-size="11">{start_date}</text>
            <text x="{chart_width - 20}" y="{chart_height - 15}" text-anchor="end" fill="#9cb8c1" font-size="11">{end_date}</text>
        </svg>
        <div style="color:#9cb8c1;font-size:.78rem;margin-top:-.35rem;">
            <span style="color:#e8bd67;">●</span> 收盤價　
            <span style="color:#56d59b;">●</span> 20 日均線　
            <span style="color:#69a7d7;">●</span> 60 日均線
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_factor_chart(group_scores):
    """用橫向長條圖比較四個分析構面。"""
    labels = {
        "Sentiment": "恐慌情緒",
        "Flow": "資金籌碼",
        "Fundamental": "價值護城河",
        "Technical": "技術錯殺",
    }
    bar_rows = []
    for index, (key, label) in enumerate(labels.items()):
        score = max(0.0, min(100.0, float(group_scores[key])))
        y_pos = 20 + index * 58
        bar_rows.append(
            f'<text x="0" y="{y_pos + 15}" fill="#eaf6f7" font-size="14">{label}</text>'
            f'<rect x="112" y="{y_pos}" width="300" height="20" rx="10" fill="rgba(156,184,193,.16)" />'
            f'<rect x="112" y="{y_pos}" width="{score * 3:.1f}" height="20" rx="10" fill="#56d59b" />'
            f'<text x="425" y="{y_pos + 15}" fill="#e8bd67" font-size="14">{score:.1f}</text>'
        )
    st.markdown(
        f"""
        <svg viewBox="0 0 480 255" width="100%" role="img" aria-label="四構面分數比較圖">
            {''.join(bar_rows)}
        </svg>
        """,
        unsafe_allow_html=True,
    )


def render_dashboard(result, raw_log):
    """把 agent.py 的結構化回傳值整理成單頁圖像儀表板。"""
    score = result["final_score"]
    metrics = result["metrics"]

    st.markdown('<p class="section-kicker">MARKET SNAPSHOT</p>', unsafe_allow_html=True)
    st.subheader(f"{result['ticker']} 市場快照")

    metric_cols = st.columns(4)
    metric_cols[0].metric("最新收盤價", f"{result['current_price']:,.2f}")
    metric_cols[1].metric("決策指數", f"{score:.1f} / 100")
    metric_cols[2].metric("美股 VIX", f"{metrics['us_vix']:.2f}", f"{metrics['vix_roc_percent']:+.1f}%")
    bias_text = "資料不足" if metrics["bias_ratio_240ma"] is None else f"{metrics['bias_ratio_240ma']:+.2f}%"
    metric_cols[3].metric("240 日年線乖離", bias_text)

    st.progress(max(0, min(100, int(round(score)))))
    st.markdown(
        f"""
        <div class="decision-card">
            <strong>{get_advice(score)}</strong><br>
            市場狀態：{result["regime_desc"]}<br>
            採用策略：{result["strategy"]}<br>
            攻擊型預算內的倉位建議：{result["recommended_position"]}<br>
            <small>注意：此比例僅適用於 15% - 20% 的攻擊型預算，不可動用核心防禦資金。</small>
        </div>
        """,
        unsafe_allow_html=True,
    )

    chart_cols = st.columns([1.65, 1])
    with chart_cols[0]:
        st.markdown('<p class="section-kicker">PRICE TREND</p>', unsafe_allow_html=True)
        st.subheader("價格走勢與移動平均線")
        render_price_chart(result)
    with chart_cols[1]:
        st.markdown('<p class="section-kicker">FACTOR MODEL</p>', unsafe_allow_html=True)
        st.subheader("四構面分數比較")
        render_factor_chart(result["group_scores"])

    detail_cols = st.columns([1, 1])
    with detail_cols[0]:
        st.markdown('<p class="section-kicker">INPUTS</p>', unsafe_allow_html=True)
        st.subheader("分析參數")
        input_metrics = [
            ("市場", result["market"]),
            ("黃金月變動", f"{metrics['gold_month_change_percent']:+.2f}%"),
        ]
        if metrics["tw_vix"] is not None:
            input_metrics.append(("台股 VIX", f"{metrics['tw_vix']:.2f}"))
        if metrics["foreign_futures"] is not None:
            input_metrics.append(("外資期指淨額", f"{metrics['foreign_futures']:+,} 口"))
        st.dataframe(pd.DataFrame(input_metrics, columns=["項目", "數值"]), hide_index=True, width="stretch")

    with detail_cols[1]:
        st.markdown('<p class="section-kicker">FACTOR NOTES</p>', unsafe_allow_html=True)
        st.subheader("重要判讀摘要")
        for note in result["notes"][-7:]:
            st.write(note)

    with st.expander("查看完整診斷日誌"):
        st.code(raw_log, language="text")
    st.caption("資料透明度：目前 NAAIM 因子仍沿用 agent.py 內的模擬值，尚未接上經驗證的即時資料來源。")


inject_finance_theme()

st.markdown(
    """
    <div class="hero">
        <p class="eyebrow">MACRO SIGNAL LAB</p>
        <h1>趨勢輔助判斷工具</h1>
        <p>整合宏觀資金流、市場情緒、基本面與技術指標。輸入標的後，即可在同一頁查看決策分數、價格圖表、因子比較與風控建議。</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.form("diagnosis_form"):
    input_cols = st.columns([1.7, 1, 1])
    with input_cols[0]:
        ticker_input = st.text_input("股票或 ETF 代號", value="2330", help="台股可輸入 2330，美股可輸入 AAPL。")

    ticker, is_tw_stock = normalize_ticker(ticker_input)
    with input_cols[1]:
        st.text_input("偵測市場", value="台股" if is_tw_stock else "美股", disabled=True)
    with input_cols[2]:
        st.text_input("執行代號", value=ticker or "尚未輸入", disabled=True)

    manual_vix = 20.0
    manual_futures = 0
    if is_tw_stock:
        with st.expander("台股進階資料（手動輸入）", expanded=True):
            st.caption("目前沒有已驗證可靠的自動來源，因此保留手動輸入。請使用最近交易日的資料。")
            advanced_cols = st.columns(2)
            manual_vix = advanced_cols[0].number_input("台股 VIX", min_value=0.0, value=20.0, step=0.5)
            manual_futures = advanced_cols[1].number_input("外資期指淨額（口）", value=0, step=1000)
    else:
        st.caption("美股模式會自動同步 VIX 與大盤量價資料。")

    run_btn = st.form_submit_button("開始分析", width="stretch", type="primary")

if run_btn:
    if not ticker:
        st.error("請先輸入股票或 ETF 代號。")
    else:
        with st.spinner("正在同步市場資料並計算因子分數..."):
            old_stdout = sys.stdout
            sys.stdout = captured_output = io.StringIO()
            try:
                result = agent.run_diagnosis(ticker, manual_futures, is_tw_stock, manual_vix)
            except Exception as exc:
                result = {"ok": False, "error": f"系統執行異常：{exc}"}
            finally:
                sys.stdout = old_stdout

        st.session_state["diagnosis_result"] = result
        st.session_state["diagnosis_log"] = captured_output.getvalue()

if "diagnosis_result" in st.session_state:
    saved_result = st.session_state["diagnosis_result"]
    if saved_result.get("ok"):
        render_dashboard(saved_result, st.session_state.get("diagnosis_log", ""))
    else:
        st.error(saved_result.get("error", "分析失敗，請確認標的代號與網路連線。"))
        with st.expander("查看錯誤日誌"):
            st.code(st.session_state.get("diagnosis_log", ""), language="text")
else:
    st.info("輸入標的後按下「開始分析」，結果會直接顯示在本頁下方。")

st.markdown(
    '<p class="disclaimer">本工具僅提供市場資料整理與策略研究參考，不構成投資建議。實際交易前仍應自行確認資料日期與風險承受能力。</p>',
    unsafe_allow_html=True,
)
