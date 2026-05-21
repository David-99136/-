#   每次重新開啟Terminal時皆須重新輸入下面的api金鑰
#   $env:GEMINI_API_KEY="你的金鑰"
#   AIzaSyDOsca3tyHBXS6W7GcWIubTs-A4jty_PHc
import os
import json
from google import genai
from pydantic import BaseModel, Field
from typing import List

# ==========================================
# 1. 初始化 Gemini 客戶端
# 請確保已在終端機設定環境變數： $env:GEMINI_API_KEY="你的金鑰"
# ==========================================
client = genai.Client()

# ==========================================
# 2. 定義結構化輸出格式 (支援多檔案處理)
# ==========================================
class SingleFileResponse(BaseModel):
    file_path: str = Field(description="檔案路徑（例如 main.py）")
    updated_code: str = Field(description="完整且修改過後的 Python 程式碼，絕對不包含 Markdown 標記，不可使用省略號")

class MultiCodeModifierResponse(BaseModel):
    explanation: str = Field(description="這次對這批檔案進行整體修改的深度架構說明")
    files: List[SingleFileResponse] = Field(description="所有被修改的檔案列表")

# ==========================================
# 3. 核心修改函式 (Pro 版)
# ==========================================
def modify_multiple_codes_pro(file_paths: List[str], user_instruction: str):
    """
    同時讀取多個指定的程式碼檔案，結合 Gemini Pro 的強大推理能力，進行跨檔案聯合審閱與重構。
    """
    all_files_content = {}
    
    print("📂 [Pro Mode] 正在讀取目標檔案...")
    for path in file_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                all_files_content[path] = f.read()
            print(f"  -> 已成功讀取：{path}")
        else:
            print(f"  ❌ 找不到檔案：{path}，將跳過此檔案。")

    if not all_files_content:
        print("❌ 沒有讀取到任何有效檔案，終止執行。")
        return

    print(f"\n🧠 正在呼叫 Gemini 2.5 Pro 進行跨檔案聯合推理與修改 ({len(all_files_content)} 個檔案)...")
    print("⏳ Pro 模型思考較為深入，請耐心等候幾秒鐘...")

    # 讀取專案說明書
    context_content = ""
    if os.path.exists("gemini_context.md"):
         with open("gemini_context.md", "r", encoding="utf-8") as f:
            context_content = f.read()

    # ✨ Pro 版專屬的系統提示詞 (深度客製化交易思維)
    system_instruction = (
        "你是『何景澤 AI 交易探員』系統的首席架構師與資深 Python 開發者，擁有頂尖的電子與電腦工程背景。"
        "本系統專注於左側交易，結合奧地利學派經濟週期理論，並透過 MACD、RSI、VIX 以及恐懼與貪婪指數 (Fear & Greed Index) 來進行台股/美股 ETF 與大盤的市場情緒分析與進場點預測。"
        "使用者會同時提供你多個互相有關聯的程式碼檔案。"
        "請根據指示進行跨檔案的高階邏輯修改。保持程式碼結構嚴謹、模組化且高效，並確保檔案之間的調用（Import）語法完全精確。"
        "請務必在 `updated_code` 中回傳該檔案【完整】的程式碼，絕對不要使用 `...` 或省略原本的任何邏輯。"
    )

    # 把多個檔案的內容打包進 Prompt
    files_str_for_prompt = ""
    for path, code in all_files_content.items():
        files_str_for_prompt += f"\n### 檔案路徑: {path}\n```python\n{code}\n```\n-----------------\n"

    prompt = f"""
    以下是專案的背景與核心策略補充：
    {context_content}

    --------------------------------------------------
    目前專案中互相關聯的程式碼檔案內容如下：
    {files_str_for_prompt}

    --------------------------------------------------
    使用者修改指示（請通盤考量上述所有檔案的關聯性，進行全面重構）：
    {user_instruction}
    """

    try:
        # 💡 模型切換為 Pro 版本，應對複雜的程式碼生成任務
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'system_instruction': system_instruction,
                'response_mime_type': 'application/json',
                'response_schema': MultiCodeModifierResponse,
            }
        )

        # 完美消滅紅線的 JSON 解析寫法
        json_data = json.loads(response.text)
        result = MultiCodeModifierResponse(**json_data)

        print("\n✅ Pro 架構師審閱完成！開始覆寫檔案...")
        print(f"📝 深度修改說明：\n{result.explanation}\n")

        for file_item in result.files:
            target_path = file_item.file_path
            
            # 安全防呆：拒絕未經請求的檔案建立
            if target_path in all_files_content:
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(file_item.updated_code)
                print(f"💾 已成功覆寫檔案：{target_path}")
            else:
                print(f"⚠️ 警告：AI 嘗試修改未授權的檔案路徑 {target_path}，已攔截。")
        
        print("\n✨ 所有檔案 Pro 級重構完成！")

    except Exception as e:
        print(f"❌ 發生錯誤：{e}")

# ==========================================
# 4. 實際呼叫區塊
# ==========================================
if __name__ == "__main__":
    # 填入你想讓 Pro 模型檢查的所有檔案
    target_files = ["main.py", "agent.py"]
    
    # 填寫高階修改指示
    my_instruction = (
        "請幫我檢查這兩個檔案。"
        "並且將兩個檔案的邏輯進行整合、優化。請幫我把異常處理 (Try-Except) 也做得更完善。"
    )
    
    modify_multiple_codes_pro(file_paths=target_files, user_instruction=my_instruction)