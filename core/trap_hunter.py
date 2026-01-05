import chess
import chess.pgn
from stockfish import Stockfish

class TrapHunter:
    """從 FEN 中尋找誘人的失誤並生成連續妙手將殺"""
    def __init__(self, sf_path, deep_depth=20, swing_threshold=300):
        # 增加執行緒與 Hash 以提升挖掘速度
        self.sf = Stockfish(path=sf_path, parameters={"Threads": 6, "Hash": 1024})
        self.deep_depth = deep_depth
        self.swing_threshold = swing_threshold
        # 淺層掃描深度：從極淺到稍微有判斷力
        self.shallow_depth_range = [4, 5, 6, 7, 8, 9, 10]

    def _get_score_from_info(self, move_info):
        """
        修正錯誤：從 get_top_moves 的回傳字典中提取正確評分。
        處理 Centipawn 為 None (即 Mate 局面) 的情況。
        """
        if move_info['Mate'] is not None:
            mate_val = move_info['Mate']
            # Mate in X: 贏棋為正，輸棋為負
            # 讓靠近將殺的分數絕對值更高
            return (10000 - abs(mate_val) * 100) * (1 if mate_val > 0 else -1)
        return move_info['Centipawn'] if move_info['Centipawn'] is not None else 0

    def _get_score_from_eval(self, eval_data):
        """處理 get_evaluation() 回傳的字典"""
        if eval_data['type'] == 'cp':
            return eval_data['value']
        val = eval_data['value']
        return (10000 - abs(val) * 100) * (1 if val > 0 else -1)

    def find_trap(self, fen):
        board = chess.Board(fen)
        
        # --- 皇后存續檢查 (確保中局有觀賞性) ---
        has_white_queen = bool(board.pieces(chess.QUEEN, chess.WHITE))
        has_black_queen = bool(board.pieces(chess.QUEEN, chess.BLACK))
        if not (has_white_queen and has_black_queen):
            return None

        best_trap = None
        deep_eval_cache = {} 

        print(f"  開始多維度掃描 (FEN: {fen[:20]}...)")
        
        for s_depth in self.shallow_depth_range:
            self.sf.set_depth(s_depth)
            self.sf.set_fen_position(fen)
            shallow_moves = self.sf.get_top_moves(5) 

            for move_info in shallow_moves:
                move_uci = move_info['Move']
                # 使用修正後的評分提取函數
                shallow_eval = self._get_score_from_info(move_info)
                
                # --- 修正邏輯：排除不具誘惑力的動作 ---
                # 1. 如果淺層就已經知道被將殺 (例如 Mate -3)，這不是誘人的失誤，是單純的低級失誤
                # 2. 如果淺層分數太低 (例如 -100 以下)，代表這步棋看起來就很糟，沒人會踩陷阱
                if shallow_eval < -50:
                    continue

                # 取得真相 (Deep Evaluation)
                if move_uci in deep_eval_cache:
                    deep_eval = deep_eval_cache[move_uci]
                else:
                    temp_board = board.copy()
                    temp_board.push_uci(move_uci)
                    self.sf.set_fen_position(temp_board.fen())
                    self.sf.set_depth(self.deep_depth)
                    
                    deep_eval_data = self.sf.get_evaluation()
                    # 轉回走棋方視角：如果對手回報 Mate 5，代表走棋方被 Mate in 5
                    deep_eval = -self._get_score_from_eval(deep_eval_data) 
                    deep_eval_cache[move_uci] = deep_eval 

                score_drop = shallow_eval - deep_eval

                # 判斷是否有巨大的「認知落差」
                # 且深層評估必須是「大敗」或「被將殺」狀態
                if score_drop > self.swing_threshold and deep_eval < -300:
                    temp_board = board.copy()
                    temp_board.push_uci(move_uci)
                    sequence, is_mate = self._get_mate_sequence(temp_board.fen())
                    
                    if is_mate:
                        # 如果在更深的 shallow_depth 依然被誤判為好棋，代表陷阱品質更高
                        if best_trap is None or s_depth >= best_trap["detected_at_depth"]:
                            best_trap = {
                                "start_fen": fen,
                                "blunder": move_uci,
                                "sequence": sequence,
                                "drop": score_drop,
                                "shallow": shallow_eval,
                                "deep": deep_eval,
                                "detected_at_depth": s_depth 
                            }
                            print(f"    [發現陷阱] 深度 {s_depth} 誤判為 {shallow_eval}, 真相為 {deep_eval} ({move_uci})")

        return best_trap

    def _get_mate_sequence(self, fen, max_len=12):
        """尋找從陷阱開始的連環妙手路徑"""
        board = chess.Board(fen)
        self.sf.set_fen_position(fen)
        sequence = []
        for _ in range(max_len):
            best_move = self.sf.get_best_move()
            if not best_move: break
            sequence.append(best_move)
            board.push_uci(best_move)
            self.sf.make_moves_from_current_position([best_move])
            if board.is_checkmate():
                return sequence, True
        return sequence, False

    def export_pgn(self, trap_data):
        """將數據轉換為 PGN 格式"""
        board = chess.Board(trap_data['start_fen'])
        game = chess.pgn.Game()
        game.setup(board)
        
        game.headers["Event"] = "Spectacular Trap"
        game.headers["Annotator"] = f"Drop {trap_data['drop']} (D{trap_data['detected_at_depth']})"
        
        node = game.add_main_variation(chess.Move.from_uci(trap_data['blunder']))
        node.comment = f"Tempting Blunder (Eval: {trap_data['shallow']} at Depth {trap_data['detected_at_depth']})"
        
        for m in trap_data['sequence']:
            node = node.add_main_variation(chess.Move.from_uci(m))
            
        return str(game)