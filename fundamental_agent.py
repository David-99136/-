import yfinance as yf
import requests
import xml.etree.ElementTree as ET
import urllib.parse
import pandas as pd
from datetime import datetime

def get_fundamentals(ticker, is_crisis_mode=False):
    """
    獲取個股基本面與全網情緒數據
    【升級】加入 is_crisis_mode 參數，用於動態退守斐波那契安全防線
    【升級】新增 ETF 專屬模型與高韌性 yfinance 缺漏字串攔截
    """
    print(f"📡 啟動【矩陣式深度基本面探勘】：全網大數據與價值位階 (2026) - {ticker}")
    
    result = {
        "eps": 0.0,
        "current_price": 0.0,
        "pe_ratio": 0.0,
        "pb_ratio": 0.0,
        "pe_score": 0,
        "fibo_score": 0,
        "sd_score": 0,
        "notes": []
    }

    raw_high = raw_low = 0.0
    unique_titles = set()
    target_news_count = 50

    # 1. 個股新聞關鍵字對照表
    stock_map = {
        "2454.TW": {"name_cn": "聯發科", "name_en": "MediaTek", "products": ["天璣", "Dimensity", "手機晶片", "WiFi 7"], "sc": ["台積電", "高通", "Qualcomm", "庫存去化"]},
        "2330.TW": {"name_cn": "台積電", "name_en": "TSMC", "products": ["2奈米", "CoWoS", "晶圓代工"], "sc": ["輝達", "NVIDIA", "蘋果", "Apple", "ASML"]},
        "2881.TW": {"name_cn": "富邦金", "name_en": "Fubon", "products": ["壽險", "銀行", "金控"], "sc": ["降息", "美聯儲", "避險成本"]},
        "2002.TW": {"name_cn": "中鋼", "name_en": "CSC", "products": ["鋼鐵", "熱軋", "冷軋"], "sc": ["鐵礦砂", "報價", "庫存去化"]}
    }
    
    mapping = stock_map.get(ticker, {
        "name_cn": ticker.replace('.TW', ''), 
        "name_en": "", 
        "products": [], 
        "sc": []
    })

    # ==========================================
    # 2. 自動搜索產業分類、抓取財報與股價
    # ==========================================
    industry_type = "Tech"
    detected_sector = "未知"

    try:
        stk = yf.Ticker(ticker)
        info = stk.info
        
        sector = info.get('sector', '').lower()
        industry = info.get('industry', '').lower()
        quote_type = info.get('quoteType', '').lower()
        
        detected_sector = info.get('sector', info.get('industry', '未分類'))
        
        # --- 自動產業搜索功能 (升級 ETF 辨識) ---
        if quote_type == 'etf' or 'etf' in detected_sector.lower() or 'etf' in ticker.lower() or ticker.startswith(('005', '006', '007', '008', '009')):
            industry_type = "ETF"
            detected_sector = "ETF 指數股票型基金"
        elif 'financial' in sector or 'bank' in industry or 'insurance' in industry or 'credit' in industry:
            industry_type = "Financial"
        elif 'material' in sector or 'energy' in sector or 'industrial' in sector or 'steel' in industry or 'shipping' in industry or 'chemical' in industry:
            industry_type = "Cyclical"
        elif 'technology' in sector or 'semiconductor' in industry or 'electronic' in industry or 'communication' in sector:
            industry_type = "Tech"
        else:
            industry_type = "Tech"

        # 抓取股價
        hist = stk.history(period="1y")
        if hist.empty:
            raise ValueError("無法從 yfinance 獲取歷史股價數據")
            
        current_price = hist['Close'].iloc[-1]
        result["current_price"] = current_price
        raw_high = hist['High'].max()
        raw_low = hist['Low'].min()
        
        # 獲取 P/B Ratio (強化備援)
        pb = info.get('priceToBook')
        if not pb and info.get('bookValue'):
            pb = current_price / info.get('bookValue')
        result["pb_ratio"] = pb if pb else 0.0
        
        # 獲取 EPS (強化備援)
        eps = info.get('trailingEPS')
        if not eps: eps = info.get('epsTrailingTwelveMonths')
        if not eps and info.get('trailingPE'):
            eps = current_price / info.get('trailingPE')
            
        if not eps:
            try:
                income = stk.quarterly_income_stmt
                if not income.empty and 'Basic EPS' in income.index:
                    eps = income.loc['Basic EPS'].head(4).sum()
            except Exception:
                pass
        
        result["eps"] = eps if eps else 0.0
        if result["eps"] > 0:
            result["pe_ratio"] = current_price / result["eps"]
        elif info.get('trailingPE'):
            result["pe_ratio"] = info.get('trailingPE')

    except Exception as e:
        result["notes"].append(f"⚠️ 財報/股價/產業抓取異常: {e}")

    # ==========================================
    # 3. 矩陣式新聞探勘
    # ==========================================
    print("  🔍 正在啟動全網爬蟲，目標：突破 50 篇獨立新聞...")
    
    queries_zh = [
        f"{mapping['name_cn']} {mapping['name_en']}", 
        f"{mapping['name_cn']} {' OR '.join(mapping['products'][:2]) if mapping['products'] else ''}", 
        f"{' OR '.join(mapping['sc'][:2]) if mapping['sc'] else ''} 需求 OR 庫存", 
        f"{mapping['name_cn']} site:businesstoday.com.tw OR site:cw.com.tw", 
        f"{mapping['name_cn']} site:yahoo.com.tw", 
        f"{mapping['name_cn']} site:ptt.cc/bbs/Stock"
    ]
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    for q in queries_zh:
        if len(unique_titles) >= target_news_count: break
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

    all_titles = list(unique_titles)

    pos_keywords = ['看好', '看多', '買進', '加碼', '推薦', '升評', '大增', '飆升', '創新高', '滿載', '急單', '供不應求', '復甦']
    neg_keywords = ['看壞', '看空', '賣出', '減碼', '降評', '下修', '暴跌', '不如預期', '虧損', '砍單', '庫存', '供過於求', '衰退']
    
    pos_hits = sum(1 for t in all_titles for k in pos_keywords if k in t)
    neg_hits = sum(1 for t in all_titles for k in neg_keywords if k in t)

    # ==========================================
    # 4. 邏輯判定與給分區塊
    # ==========================================
    
    # --- (A) 斐波那契動態柔性給分 ---
    if raw_high > raw_low:
        diff = raw_high - raw_low
        safe_start_ratio = 0.618 if is_crisis_mode else 0.500
        safe_start_price = raw_high - (diff * safe_start_ratio)
        deep_water_price = raw_high - (diff * 0.850) 
        
        result["notes"].append(f"📐 【斐波那契】52週高低: {raw_high:.1f} - {raw_low:.1f} (動態起算防線: {safe_start_ratio})")
        
        if current_price >= safe_start_price:
            result["fibo_score"] = 0
            mode_str = "危機模式" if is_crisis_mode else "一般模式"
            result["notes"].append(f"🛡️ 【嚴格左側紀律】現價 ({current_price:.1f}) 尚未跌至 {mode_str} 安全邊際 ({safe_start_price:.1f})，系統拒絕接刀 (+0)")
        else:
            ratio = (safe_start_price - current_price) / (safe_start_price - deep_water_price)
            ratio = max(0.0, min(1.0, ratio))
            fibo_score = int((ratio ** 1.5) * 15)
            result["fibo_score"] = fibo_score
            result["notes"].append(f"🎯 【動態支撐】現價突破防線，非線性深水補償啟動 (+{fibo_score})")

    # --- (B) 產業自動歸類專屬估值模型 (滿分 15) ---
    pe = result["pe_ratio"]
    pb = result["pb_ratio"]
    
    if industry_type == "ETF":
        result["notes"].append(f"📦 【ETF 估值】指數/主題型基金無法直接套用單一個股本益比。")
        yield_pct = info.get('dividendYield')
        if yield_pct is None: yield_pct = info.get('yield', 0)
        if yield_pct is None: yield_pct = 0
        
        if yield_pct > 0.05:
            result["pe_score"] = 15
            result["notes"].append(f"💎 【高殖利率保護】ETF 殖利率達 {yield_pct*100:.1f}%，具備強大左側保護力 (+15)")
        elif yield_pct > 0.03:
            result["pe_score"] = 10
            result["notes"].append(f"✅ 【穩定配息】ETF 殖利率達 {yield_pct*100:.1f}%，具備基本安全邊際 (+10)")
        else:
            result["pe_score"] = 7
            result["notes"].append(f"⚖️ 【大盤/主題型 ETF】回歸技術與籌碼面判斷，給予中性基礎分 (+7)")

    elif industry_type == "Tech":
        result["notes"].append(f"🌊 【科技/成長股估值】當前本益比: {pe:.1f}倍 (買的是未來的爆發力與技術護城河)")
        if result["eps"] > 0 or pe > 0:
            if pe <= 15 and pe > 0:
                result["pe_score"] = 15
                result["notes"].append("💎 【極度便宜】P/E 15 倍以下，對於科技股屬極低區間 (+15)")
            elif pe <= 22 and pe > 0:
                result["pe_score"] = 10
                result["notes"].append("✅ 【價值便宜】P/E 落入 15x - 22x，具備長線保護力 (+10)")
            elif pe <= 30 and pe > 0:
                result["pe_score"] = 5
                result["notes"].append("⚖️ 【價值合理】P/E 落入 22x - 30x，對高成長股屬常態區間 (+5)")
            else:
                result["notes"].append("🔥 【過高警戒】本益比超過 30 倍，已反映高度成長預期，防範修正 (+0)")
        else:
            if info.get('marketCap') is None and info.get('previousClose') is None:
                result["pe_score"] = 5
                result["notes"].append("⚠️ 【數據缺失】yfinance 無法獲取該股獲利數據，給予中性預設分 (+5)")
            else:
                result["notes"].append("🚨 【資本錯置】當前無實質獲利 (EPS <= 0) (+0)")
            
    elif industry_type == "Financial":
        result["notes"].append(f"🏦 【金融股估值】切換至 P/B 股價淨值比評估。當前 P/B: {pb:.2f}倍")
        if pb > 0:
            if pb < 1.0:
                result["pe_score"] = 15
                result["notes"].append("💎 【跌破淨值】P/B < 1.0，金融股絕佳左側買點 (+15)")
            elif pb <= 1.2:
                result["pe_score"] = 10
                result["notes"].append("✅ 【估值便宜】P/B 落入 1.0 - 1.2，具備安全邊際 (+10)")
            elif pb <= 1.5:
                result["pe_score"] = 5
                result["notes"].append("⚖️ 【估值合理】P/B 落入 1.2 - 1.5，屬常態區間 (+5)")
            else:
                result["notes"].append("🔥 【估值高估】P/B 超過 1.5，獲利預期已滿，不宜追高 (+0)")
        else:
            result["pe_score"] = 5
            result["notes"].append("⚠️ 【數據缺失】無法取得淨值資料，給予中性預設分 (+5)")
            
    elif industry_type == "Cyclical":
        result["notes"].append(f"🏭 【景氣循環股估值】啟動反向操作策略 (買高 P/E，賣低 P/E)。當前本益比: {pe:.1f}倍")
        if result["eps"] <= 0 or pe >= 50:
            result["pe_score"] = 15
            result["notes"].append("💎 【盈餘谷底(買點)】P/E 飆升到 50 倍以上或虧損，景氣爛到谷底，正是佈局轉折點 (+15)")
        elif pe >= 20:
            result["pe_score"] = 10
            result["notes"].append("✅ 【景氣復甦】P/E 落入 20x - 50x 區間，景氣處於復甦早期 (+10)")
        elif pe >= 10:
            result["pe_score"] = 5
            result["notes"].append("⚖️ 【景氣平穩】P/E 落入 10x - 20x 區間 (+5)")
        elif pe > 0 and pe < 10:
            result["pe_score"] = 0
            result["notes"].append("🔥 【景氣過熱(賣點)】低本益比 (<10)，看似便宜實則 EPS 爆發，往往是景氣見頂訊號！ (+0)")
        else:
            result["pe_score"] = 5
            result["notes"].append("⚠️ 【數據缺失】無效本益比數據，給予中性預設分 (+5)")

    # --- (C) 奧地利學派供需新聞給分 ---
    net_sentiment = pos_hits - neg_hits
    if net_sentiment >= 5:
        result["sd_score"] = 10
        result["notes"].append(f"🏭 【真實需求】大數據顯示供需結構強勁偏多 (+{pos_hits}/-{neg_hits}) (+10)")
    elif net_sentiment <= -8:
        result["sd_score"] = 0
        result["notes"].append(f"📉 【悲觀積壓】多方信源預警風險，市場情緒偏空 (+{pos_hits}/-{neg_hits}) (+0)")
    else:
        result["sd_score"] = 5
        result["notes"].append(f"⚖️ 【多空交戰】全網新聞顯示多空力道拉扯 (+{pos_hits}/-{neg_hits}) (+5)")

    return result