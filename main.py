import agent, os, re
import sys, time, threading, itertools

class LoadingSpinner:
    """背景執行緒 Loading 動畫，並攔截 stdout 避免與 print 衝突"""
    def __init__(self, text="⏳ 系統正在矩陣搜尋並運算中..."):
        self.text = text
        self.busy = False
        self.spinner = itertools.cycle(['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'])
        self.thread = None
        self._original_stdout = sys.stdout

    class StdoutWrapper:
        def __init__(self, original, spinner_obj):
            self.original = original
            self.spinner_obj = spinner_obj

        def write(self, text):
            if self.spinner_obj.busy and text.strip():
                self.original.write('\r\033[K') # 成功輸出字元前清除 Loading 行
            self.original.write(text)

        def flush(self):
            self.original.flush()

    def spin(self):
        while self.busy:
            self._original_stdout.write(f'\r{next(self.spinner)} {self.text}')
            self._original_stdout.flush()
            time.sleep(0.1)

    def start(self):
        self.busy = True
        sys.stdout = self.StdoutWrapper(self._original_stdout, self)
        self.thread = threading.Thread(target=self.spin, daemon=True)
        self.thread.start()

    def stop(self):
        self.busy = False
        if self.thread:
            self.thread.join()
        sys.stdout = self._original_stdout
        sys.stdout.write('\r\033[K')
        sys.stdout.flush()

def main():
    # --- 狀態記憶區 (全域於迴圈外) ---
    last_vix_tw = 20.0 # 記憶台股 VIX
    last_futures_tw = 0 # 記憶外資期指淨額

    while True:
        print("\n" + "🤖" + "="*54 + "🤖")
        print(" 交易探員 - 記憶加強版 (Stateful Macro Context)")
        print("="*58)
        
        u_input = input("\n👉 請輸入標的代號 (如 2330, AAPL 或 exit): ").strip().upper()
        if u_input == 'EXIT': break
        
        is_tw_stock = False
        if not u_input:
            ticker = "2330.TW"
            is_tw_stock = True
        elif '.' in u_input:
            ticker = u_input
            is_tw_stock = ('.TW' in u_input or '.TWO' in u_input)
        else:
            if re.match(r'^\d{4,5}[A-Z]?$', u_input):
                ticker = f"{u_input}.TW"
                is_tw_stock = True
                print(f"💡 自動判斷：偵測為【台股】，已校正為 '{ticker}'")
            else:
                ticker = u_input
                print(f"💡 自動判斷：偵測為【美股】，代號 '{ticker}'")

        print("-" * 58)

        # --- 根據市場進行記憶讀取與更新 ---
        manual_vix = 20.0
        manual_futures = 0

        if is_tw_stock:
            # 1. 台股 VIX 記憶邏輯
            v_prompt = f"👉 (戰略層) 請輸入【台股 VIX】 (目前記憶: {last_vix_tw:.2f})\n按 Enter 沿用，或輸入新值: "
            v_input = input(v_prompt).strip()
            if v_input:
                try: 
                    last_vix_tw = float(v_input)
                except ValueError:
                    print("⚠️ 格式錯誤：台股 VIX 必須為數字，沿用舊值。")
            manual_vix = last_vix_tw

            # 2. 外資期指記憶邏輯
            f_prompt = f"👉 (戰略層) 請輸入【外資期指淨額】 (目前記憶: {last_futures_tw:+,})\n按 Enter 沿用，或輸入新值: "
            f_input = input(f_prompt).strip()
            if f_input:
                try: 
                    last_futures_tw = int(f_input)
                except ValueError:
                    print("⚠️ 格式錯誤：外資期指淨額必須為整數，沿用舊值。")
            manual_futures = last_futures_tw
        else:
            print("🌎 美股模式：VIX 與大盤量價將自動從美股市場同步。無需手動輸入。")

        print("-" * 58)
        
        # 啟動 Loading 動畫
        spinner = LoadingSpinner()
        try:
            spinner.start()
            # 將 manual_vix 統一傳入，agent 內部會判斷是否為台股並使用
            agent.run_diagnosis(ticker, manual_futures, is_tw_stock, manual_vix)
        except Exception as e:
            print(f"🚨 系統異常: {e}")
        finally:
            spinner.stop()

        input("\n診斷完成。按 Enter 繼續下一檔搜尋...")
        os.system('cls' if os.name == 'nt' else 'clear')

if __name__ == "__main__":
    main()
