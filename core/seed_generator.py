import chess
from stockfish import Stockfish
import random

class SeedGenerator:
    """負責生成平衡且複雜的中局局面 (FEN)，具備狀態保持功能"""
    def __init__(self, sf_path):
        # 較低深度用於快速走子
        self.sf = Stockfish(path=sf_path, depth=8, parameters={"Threads": 6, "Hash": 1024})
        
        # --- 狀態維護 ---
        self.board = chess.Board()
        
        # --- 配置控制參數 ---
        self.AVOID_QUEEN_CAPTURE_PROB = 1 
        self.AVOID_ROOK_CAPTURE_PROB = 0.5   
        self.EVAL_THRESHOLD = 200            # 超過 2.0 則視為不平衡
        self.MIN_PIECES = 17
        self.MAX_PIECES = 26

    def _should_skip_capture(self, board, move_uci):
        """判定是否應該為了保留大子而避開此動作"""
        move = chess.Move.from_uci(move_uci)
        captured_piece = board.piece_at(move.to_square)
        if captured_piece:
            if captured_piece.piece_type == chess.QUEEN:
                return random.random() < self.AVOID_QUEEN_CAPTURE_PROB
            if captured_piece.piece_type == chess.ROOK:
                return random.random() < self.AVOID_ROOK_CAPTURE_PROB
        return False

    def reset(self):
        """重置棋盤到開局狀態"""
        self.board = chess.Board()

    def get_next_seed(self):
        """
        核心邏輯：從上次的局面繼續往下走，直到找到下一個合格的 FEN。
        修改：輸出的局面必須讓『當前走棋方』處於平手或小優勢。
        """
        attempts = 0
        while attempts < 100:  # 防止無限死迴圈
            # 1. 檢查當前棋盤是否還「可用」
            if not self._is_board_usable():
                self.reset()
            
            # 2. 讓 Stockfish 挑選後續動作
            self.sf.set_fen_position(self.board.fen())
            top_moves = self.sf.get_top_moves(15)
            
            if not top_moves:
                self.reset()
                continue

            # 3. 篩選平衡動作
            balanced_candidates = [
                m['Move'] for m in top_moves 
                if m['Centipawn'] is not None and abs(m['Centipawn']) <= self.EVAL_THRESHOLD + 50
            ]
            
            if not balanced_candidates:
                # 若無平衡動作，直接取最優動作以維持棋局，但這可能導致局面崩潰
                chosen_move = top_moves[0]['Move']
            else:
                # 4. 大子保護邏輯
                filtered_candidates = [
                    m for m in balanced_candidates 
                    if not self._should_skip_capture(self.board, m)
                ]
                chosen_move = random.choice(filtered_candidates) if filtered_candidates else random.choice(balanced_candidates)

            # 5. 執行走棋
            self.board.push_uci(chosen_move)
            attempts += 1

            # --- 判定輸出的種子是否合格 ---
            piece_count = len(self.board.piece_map())
            if self.MIN_PIECES <= piece_count <= self.MAX_PIECES:
                self.sf.set_fen_position(self.board.fen())
                eval_data = self.sf.get_evaluation()
                
                if eval_data['type'] == 'cp':
                    eval_val = eval_data['value']
                    
                    # 計算『當前走棋方』的視角分數 (Relative Score)
                    side_to_move_eval = eval_val if self.board.turn == chess.WHITE else -eval_val
                    
                    # 1. side_to_move_eval >= -10: 確保當前走棋方平手或有優勢 (給予 10 cp 的寬容值)
                    # 2. side_to_move_eval <= EVAL_THRESHOLD: 確保優勢不要太大，否則對手隨便下都輸，沒戲劇性
                    if -10 <= side_to_move_eval <= self.EVAL_THRESHOLD:
                        return self.board.fen()
            
        return None

    def _is_board_usable(self):
        """判斷當前棋盤是否還具備挖掘價值"""
        # 條件：遊戲沒結束、子力夠多
        if self.board.is_game_over():
            return False
        if len(self.board.piece_map()) < self.MIN_PIECES:
            return False
        
        # 檢查當前評分是否已經大崩盤
        self.sf.set_fen_position(self.board.fen())
        eval_data = self.sf.get_evaluation()
        if eval_data['type'] == 'mate' or abs(eval_data['value']) > self.EVAL_THRESHOLD + 100:
            return False
            
        return True