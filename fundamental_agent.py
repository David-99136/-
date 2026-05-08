import yfinance as yf
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import pandas as pd
from datetime import datetime

def get_fundamentals(ticker, is_crisis_mode=False):
    """
    獲取個股基本面與全網情緒數據
    加入 is_crisis_mode 參數，用於動態退守斐波那契安全防線
    """
    print(f"📡 啟動【矩陣式深度基本面探勘】：全網大數據與價值位階 (2026) - {ticker}")
    
    result = {
        "eps": 0.0,
        "current_price": 0.0,
        "pe_ratio": 0.0,
        "pe_score": 0,
        "fibo_score": 0,
        "sd_score": 0,
        "notes": []
    }

    raw_high = raw_low = 0.0
    unique_titles = set()
    target_news_count = 50

    # 1. 建立個股矩陣對照表
    stock_map = {
        "2454.TW": {
            "name_cn": "聯發科", "name_en": "MediaTek",
            "products": ["天璣", "Dimensity", "手機晶片", "WiFi 7"],
            "sc": ["台積電", "高通", "Qualcomm", "庫存去化", "智慧型手機"]
        },
        "2330.TW": {
            "name_cn": "台積電", "name_en": "TSMC",
            "products": ["2奈米", "CoWoS", "晶圓代工"],
            "sc": ["輝達", "NVIDIA", "蘋果", "Apple", "艾司摩爾", "ASML"]
        },
        "2317.TW": {
            "name_cn": "鴻海", "name_en": "Foxconn",
            "products": ["AI伺服器", "電動車", "MIH", "iPhone代工"],
            "sc": ["蘋果", "Apple", "輝達", "NVIDIA", "GB200", "組裝"]
        }
    }
    
    mapping = stock_map.get(ticker, {
        "name_cn": ticker.replace('.TW', ''), 
        "name_en": "", 
        "products": [], 
        "sc": []
    })

    # ==========================================
    # 2. EPS 備援抓取機制與價格獲取
    # ==========================================
    try:
        stk = yf.Ticker(ticker)
        info = stk.info
        
        hist = stk.history(period="1y")
        if hist.empty:
            raise ValueError("無法從 yfinance 獲取歷史股價數據")
            
        current_price = hist['Close'].iloc[-1]
        result["current_price"] = current_price
        
        raw_high = hist['High'].max()
        raw_low = hist['Low'].min()
        
        eps = info.get('trailingEPS')
        if not eps: eps = info.get('epsTrailingTwelveMonths')
        if not eps:
            income = stk.quarterly_income_stmt
            if not income.empty and 'Basic EPS' in income.index:
                eps = income.loc['Basic EPS'].head(4).sum()
        
        result["eps"] = eps if eps else 0.0
        if result["eps"] > 0:
            result["pe_ratio"] = current_price / result["eps"]

    except Exception as e:
        result["notes"].append(f"⚠️ EPS/股價抓取異常: {e}")

    # ==========================================
    # 3. 矩陣式新聞探勘 (財經媒體 + 論壇 + 國際視野)
    # ==========================================
    print("  🔍 正在啟動全網爬蟲，目標：突破 50 篇獨立新聞...")
    
    queries_zh = [
        f"{mapping['name_cn']} {mapping['name_en']}", 
        f"{mapping['name_cn']} {' OR '.join(mapping['products'][:2]) if mapping['products'] else ''}", 
        f"{' OR '.join(mapping['sc'][:2]) if mapping['sc'] else ''} 需求 OR 庫存", 
        f"{mapping['name_cn']} site:businesstoday.com.tw OR site:cw.com.tw", 
        f"{mapping['name_cn']} site:cnyes.com OR site:moneydj.com", 
        f"{mapping['name_cn']} site:ctee.com.tw OR site:money.udn.com", 
        f"{mapping['name_cn']} site:yahoo.com.tw", 
        f"{mapping['name_cn']} site:ptt.cc/bbs/Stock", 
        f"{mapping['name_cn']} site:mobile01.com", 
        f"{mapping['name_cn']} site:dcard.tw/f/money", 
    ]
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    for q in queries_zh:
        if len(unique_titles) >= target_news_count:
            break
        try:
            encoded_q = urllib.parse.quote(q)
            rss_url = f"https://news.google.com/rss/search?q={encoded_q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            resp = requests.get(rss_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                root = ET.fromstring(resp.content)
                for item in root.findall('.//item')[:20]:
                    unique_titles.add(item.find('title').text)
        except Exception: 
            continue

    if mapping['name_en'] and len(unique_titles) < target_news_count + 10:
        try:
            en_q = urllib.parse.quote(f"{mapping['name_en']} stock OR demand OR inventory")
            en_rss = f"https://news.google.com/rss/search?q={en_q}&hl=en-US&gl=US&ceid=US:en"
            en_resp = requests.get(en_rss, headers=headers, timeout=10)
            if en_resp.status_code == 200:
                en_root = ET.fromstring(en_resp.content)
                for item in en_root.findall('.//item')[:15]:
                    unique_titles.add(item.find('title').text)
        except Exception: 
            pass

    all_titles = list(unique_titles)

    # 奧地利學派關鍵字分析
    pos_keywords = [
        '看好', '看多', '看高', '看長', '樂觀', '買進', '加碼', '推薦', '首選', '青睞', 
        '唱多', '按讚', '升評', '調升', '上調', '上修', '買盤', '進場', '做多', '目標價調升', 
        '上看', '強勢', '漲停', '創高', '成長', '增加', '暴增', '大增', '雙位數成長', '躍升', 
        '攀升', '創紀錄', '飆升', '翻倍', '創新高', '突破', '超乎預期', '擊敗預期', '賺贏', '獲利亮眼', 
        '轉虧為盈', '滿載', '急單', '追加', '去化', '供不應求', '拉貨', '回溫', '爆單', '訂單湧入', 
        '產能吃緊', '缺貨', '漲價', '訂單滿手', '排程滿載', '產能利用率滿載', '擴產', '擴廠',
        '熱銷', '大賣', '暢銷', '獨家', '搶下', '奪單', '受惠', '迎來商機', '爆發', 
        '復甦', '觸底反彈', '谷底回升', 'Beat', 'Strong', 'Demand', 'Surge', 'Outperform', 
        'Buy', 'Upgrade', 'Bullish', 'High', 'Growth'
    ]
    neg_keywords = [
        '看壞', '看空', '看低', '看短', '悲觀', '賣出', '減碼', '降評', '調降', '下調', 
        '下修', '唱衰', '棄息', '倒貨', '提款', '逃命', '停損', '做空', '目標價下調', 
        '下看', '弱勢', '跌停', '衰退', '下滑', '減少', '大減', '暴跌', '縮水', '跌破', 
        '創低', '探底', '不如預期', '獲利衰退', '虧損', '轉盈為虧', '旺季不旺', '營收雙減',
        '砍單', '庫存', '延遲', '產能利用率下滑', '調整', '庫存積壓', '去化緩慢', '供過於求', 
        '塞港', '滯銷', '掉單', '抽單', '違約', '產能閒置', '減產', '暫停擴產',
        '疲弱', '慘淡', '萎縮', '逆風', '衝擊', '拖累', '踩雷', '認列損失', '削價競爭', 
        '價格戰', '跌價', '崩盤', '泡沫', '寒冬', '戰爭', '空襲', '制裁', '天災', '地震', 
        '斷鏈', '疫情', '封鎖', '降息預期落空', '通膨反撲', 'CPI超預期', '倒閉', '破產', 
        '違約', 'War', 'Conflict', 'Sanctions', 'Disaster', 'Bankruptcy', 'Crisis',
        'Miss', 'Weak', 'Inventory', 'Slump', 'Downgrade', 'Sell', 'Underperform', 
        'Bearish', 'Low', 'Decline'
    ]
    
    pos_hits = sum(1 for t in all_titles for k in pos_keywords if k in t)
    neg_hits = sum(1 for t in all_titles for k in neg_keywords if k in t)

    # 內部數據核實面板
    print("\n" + "⚙️ " + "-"*54)
    print("【模組內部數據監測 (Telemetry Monitor - Matrix V3)】")
    print(f"  ▶ 標的代號: {ticker} ({mapping['name_cn']})")
    print(f"  ▶ 抓取現價: {result['current_price']:.2f}")
    print(f"  ▶ 最終 EPS : {result['eps']:.2f}")
    if result["eps"] > 0:
        print(f"  ▶ 運算 P/E : {result['pe_ratio']:.2f} 倍")
    print(f"  ▶ 52週高低: H:{raw_high:.2f} / L:{raw_low:.2f}")
    print(f"  ▶ 矩陣新聞: 成功過濾並抓取 {len(all_titles)} 篇不重複新聞")
    print(f"  ▶ 詞彙命中: 正向 {pos_hits} 次 / 負向 {neg_hits} 次")
    print("-" * 58 + "\n")

    # ==========================================
    # 4. 邏輯判定與給分區塊
    # ==========================================
    
    # --- (A) 斐波那契動態柔性給分 (滿分 15) ---
    if raw_high > raw_low:
        diff = raw_high - raw_low
        
        # 1. 動態防線偏移 (Dynamic Shift)
        # 一般模式從 0.5 (半山腰) 開始給分，危機模式嚴格退守至 0.618
        safe_start_ratio = 0.618 if is_crisis_mode else 0.500
        safe_start_price = raw_high - (diff * safe_start_ratio)
        
        # 定義極致恐慌深水區 (定義跌幅達 85% 為極限滿分區)
        deep_water_price = raw_high - (diff * 0.850) 
        
        result["notes"].append(f"📐 【斐波那契】52週高低: {raw_high:.1f} - {raw_low:.1f} (動態起算防線: {safe_start_ratio})")
        
        if current_price >= safe_start_price:
            # 淺水區 (包含 0.382) 直接濾除雜訊，不給予左側買進訊號
            result["fibo_score"] = 0
            mode_str = "危機模式" if is_crisis_mode else "一般模式"
            result["notes"].append(f"⚠️ 【技術支撐】現價 ({current_price:.1f}) 未達 {mode_str} 安全邊際 ({safe_start_price:.1f})，視為雜訊 (+0)")
        else:
            # 2. 柔性映射 (Continuous Mapping)
            # 將股價在安全區間內的深度，轉換為 0~1 的比例
            ratio = (safe_start_price - current_price) / (safe_start_price - deep_water_price)
            ratio = max(0.0, min(1.0, ratio)) # 箝制在 0~1 之間
            
            # 3. 非線性增益 (Non-linear Gain)
            # 引入指數 1.5，讓價格越深，加分斜率越陡 (強力獎勵深水區接刀)
            max_fibo_score = 15
            fibo_score = int((ratio ** 1.5) * max_fibo_score)
            
            result["fibo_score"] = fibo_score
            result["notes"].append(f"🎯 【動態支撐】現價 ({current_price:.1f}) 突破防線，非線性深水補償啟動 (+{fibo_score})")

    # --- (B) 本益比河流圖給分 (滿分 15) ---
    if result["eps"] > 0:
        pe = result["pe_ratio"]
        result["notes"].append(f"🌊 【P/E 河流圖】當前本益比: {pe:.1f}倍 (近四季 EPS: {result['eps']:.2f})")
        
        if pe <= 10:
            result["pe_score"] = 15
            result["notes"].append(f"💎 【價值低估】落入 10x 以下極度便宜區間，資本安全墊極厚 (+15)")
        elif pe <= 16:
            result["pe_score"] = 10
            result["notes"].append(f"✅ 【價值便宜】落入 10x-16x 便宜區間，具備長線投資價值 (+10)")
        elif pe <= 21:
            result["pe_score"] = 5
            result["notes"].append(f"⚖️ 【價值合理】落入 16x-21x 合理區間，無明顯超跌溢價 (+5)")
        else:
            result["notes"].append(f"🔥 【價值高估】本益比超過 21x 偏高區間，左側買盤應觀望 (+0)")
    else:
        result["notes"].append(f"🚨 【資本錯置】當前無實質獲利 (EPS <= 0)，防禦力極低")

    # --- (C) 奧地利學派供需新聞給分 (滿分 10) ---
    net_sentiment = pos_hits - neg_hits
    if net_sentiment >= 5:
        result["sd_score"] = 10
        result["notes"].append(f"🏭 【真實需求】大數據顯示市場情緒極度樂觀，供需結構強勁偏多 (+{pos_hits}/-{neg_hits}) (+10)")
    elif net_sentiment <= -8:
        result["sd_score"] = 0
        result["notes"].append(f"📉 【庫存/悲觀積壓】多方信源預警風險，市場情緒偏空 (+{pos_hits}/-{neg_hits}) (+0)")
    else:
        result["sd_score"] = 5
        result["notes"].append(f"⚖️ 【多空交戰】全網 {len(all_titles)} 篇新聞顯示多空力道拉扯或處於中性狀態 (+{pos_hits}/-{neg_hits}) (+5)")

    return result