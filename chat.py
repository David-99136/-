import os
import sys
import time
from google import genai

def load_all_workspace_files():
    """
    【自動化專案掃描器】
    遍歷整個 VS Code 工作區，讀取所有 .py 與 .md 檔案，並打包成結構化文本
    """
    workspace_content = "\n==================================================\n"
    workspace_content += "【⚠️ 核心通知：以下是目前 VS Code 專案工作區內的所有檔案與最新程式碼】\n"
    workspace_content += "==================================================\n"
    
    file_count = 0
    
    for root, dirs, files in os.walk("."):
        # 自動過濾不需要讀取的編譯檔與隱藏資料夾
        if "__pycache__" in root or ".git" in root or ".vscode" in root or "venv" in root:
            continue
            
        for file in files:
            if file.endswith(".py") or file.endswith(".md"):
                if file == "chat.py":
                    continue
                    
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        code_data = f.read()
                    
                    workspace_content += f"\n📂 檔案路徑: {file_path}\n"
                    workspace_content += f"```python\n{code_data}\n```\n"
                    workspace_content += "--------------------------------------------------\n"
                    file_count += 1
                except Exception:
                    continue
                    
    return workspace_content, file_count

def start_terminal_chat():
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("❌ 錯誤：未偵測到環境變數 GEMINI_API_KEY")
        print("💡 請在 Terminal 執行：$env:GEMINI_API_KEY=\"你的金鑰\" 後再重新啟動。")
        return

    print("📡 系統啟動：正在啟動工作區雷達，矩陣掃描所有檔案...")
    
    all_code_context, total_files = load_all_workspace_files()
    print(f"✅ 掃描完成！已成功將專案內 {total_files} 個檔案全部載入記憶體核心。")
    print("📡 正在連接至 何景澤 AI 交易探員核心量化大腦 (防帶偏 + 全專案感知版)...")
    
    client = genai.Client(api_key=api_key)
    
    # 【完美融合版】系統提示詞：量化大腦 + 全專案感知 + 防帶偏鎖
    system_instruction = (
        "你是『何景澤 AI 交易探員』系統的首席量化分析師與決策架構師，具備電子工程與計量經濟學雙重背景。\n\n"
        "【你的核心特權：全專案代碼感知】\n"
        "使用者已經將他目前在 VS Code 內編寫的所有 Python 程式碼、說明文件（Context / README）全部載入到你的大腦中了。\n"
        "不論使用者詢問專案內的哪一個檔案、哪一段邏輯、或是如何優化架構，你都必須基於下方提供的真實程式碼內容進行精密回答。\n\n"
        "【核心對話原則：嚴防單一指標以偏概全（Anti-Bias Rules）】\n"
        "1. 交叉驗證機制：當使用者提及單一指標（例如：RSI 發生低檔交叉）時，你絕對不可直接給出單邊的多空結論。你必須立刻啟動『矩陣思維』，提醒使用者檢查此時的『全球宏觀狀態機（Regime）』、VIX 恐慌動能、以及小台指散戶多空比的擁擠度，進行多維度加權評估。\n"
        "2. 左側交易紀律鎖：我們堅守奧地利學派與景氣循環的左側思維。當市場極度看好、大盤創新高時，你要保持清醒，主動尋找 NAAIM 聰明錢是否背離、經理人是否逢高減碼；當市場暴跌恐慌、單一技術指標鈍化時，你要理智尋找年線乖離過大或 MACD 爆量宣洩的錯殺機會。\n"
        "3. 動態風控約束：任何進場倉位建議，必須嚴格限制在 15-20% 的攻擊型預算內，絕對不可動搖核心防禦資金（66% 高股息資產）。\n"
        "4. 對話風格：沉穩、務實、批判性思考。不畫大餅，不被短期單一市場雜訊所帶偏，凡事以多因子量化分數與安全邊際（Margin of Safety）為依據。\n"
        "5. 程式碼協作：給予程式碼範例時，請確保語法能完美與專案內其他檔案對接（Import 關係精確），且程式碼必須嚴謹、模組化。\n"
    )
    
    # 將所有檔案的程式碼注入為系統底層 Context
    system_instruction += all_code_context

    # 建立對話 Session
    chat = client.chats.create(
        model="gemini-2.5-flash",
        config={
            "system_instruction": system_instruction,
            "temperature": 0.3  # 保持低隨機性，確保邏輯推演穩定
        }
    )

    print(f"🤖 Gemini 探員已成功通讀全專案！輸入 'exit' 或 'quit' 可退出對話。")
    print("=" * 60)

    # 對話與 503 錯誤防禦迴圈
    while True:
        try:
            user_input = input("\n🧑 專案主官: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ['exit', 'quit']:
                print("\n👋 矩陣大腦關閉，祝長線複利順利！")
                print("=" * 60)
                break
                
            print("⏳ 矩陣代碼與因子分析中...", end="", flush=True)
            
            response = None
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = chat.send_message(user_input)
                    break
                except Exception:
                    if attempt == max_retries - 1:
                        raise
                    print(f"\n⚠️ 伺服器繁忙 (嘗試 {attempt + 1}/{max_retries})，2秒後自動重新連線...", end="", flush=True)
                    time.sleep(2)
            
            sys.stdout.write("\r" + " " * 40 + "\r")
            if response:
                print(f"🤖 AI 探員: \n{response.text}")
            
        except KeyboardInterrupt:
            print("\n\n👋 偵測到強行中斷，安全切斷數據鏈路。")
            break
        except Exception as e:
            sys.stdout.write("\r" + " " * 40 + "\r")
            print(f"\n❌ 連線異常：{str(e)}")
            print("💡 提示：若持續 503，請稍等一分鐘讓 Google 伺服器消化流量。")

if __name__ == "__main__":
    start_terminal_chat()