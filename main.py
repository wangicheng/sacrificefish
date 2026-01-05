import datetime
import os

from core.seed_generator import SeedGenerator
from core.trap_hunter import TrapHunter

# ==========================================
# 配置區
# ==========================================
STOCKFISH_PATH = r"engines\stockfish_17_1.exe"  # <-- 請修改為你的路徑
OUTPUT_DIR = "generated_scripts"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# ==========================================
# 主程式：流水線運行
# ==========================================
def main():
    print("--- 觀賞性棋譜自動生成器啟動 ---")
    
    # 初始化
    try:
        gen = SeedGenerator(STOCKFISH_PATH)
        hunter = TrapHunter(STOCKFISH_PATH)
    except Exception as e:
        print(f"錯誤：無法啟動 Stockfish。請檢查路徑。{e}")
        return

    count = 0
    target = 1000
    
    while count < target:
        print(f"\n[步驟 1] 正在生成平衡種子局面...")
        seed_fen = gen.get_next_seed()
        if seed_fen is None:
            continue
        
        print(f"[步驟 2] 正在種子中挖掘陷阱 (FEN: {seed_fen})")
        trap_result = hunter.find_trap(seed_fen)
        
        if trap_result:
            count += 1
            pgn_content = hunter.export_pgn(trap_result)
            
            timestamp = datetime.datetime.now().strftime("%H%M%S")
            filename = os.path.join(OUTPUT_DIR, f"spectacular_trap_{timestamp}.pgn")
            
            with open(filename, "w") as f:
                f.write(pgn_content)
            
            print(f"✅ 成功獲取劇本 {count}！")
            print(f"   失誤動作: {trap_result['blunder']}")
            print(f"   掉分幅度: {trap_result['drop']}")
            print(f"   檔案已儲存: {filename}")
        else:
            print("❌ 此局面無精彩陷阱，換下一個...")

if __name__ == "__main__":
    main()