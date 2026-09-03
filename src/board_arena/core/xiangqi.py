"""中国象棋。

坐标:9 列(x: 0-8) × 10 行(y: 0-9),红方在下(y=9),黑方在上(y=0);
着法为四位数字 x1y1x2y2,如 "1242" = 从 (1,2) 平移到 (4,2)。
规则:合法着生成含蹩马腿/塞象眼/炮翻山/九宫/过河限制,禁自杀与将帅照面;
三次重复局面判和;无子可动(非被将)判和。
"""
from __future__ import annotations

import random
import re
from typing import Optional

from .base import BoardGame, IllegalMove, MoveInfo, ParsedMove

RED, BLACK = "red", "black"
SIDE_LABEL = {RED: "红方", BLACK: "黑方"}
PIECE_NAMES = {
    "K": "帅", "A": "仕", "E": "相", "H": "马", "R": "车", "C": "炮", "P": "兵",
    "k": "将", "a": "士", "e": "象", "h": "马", "r": "车", "c": "炮", "p": "卒",
}
MAX_MOVES = 200
REPETITION_LIMIT = 3


def other(side: str) -> str:
    return BLACK if side == RED else RED


def on_board(x: int, y: int) -> bool:
    return 0 <= x <= 8 and 0 <= y <= 9


def side_of(piece: str) -> str:
    return RED if piece.isupper() else BLACK


def initial_board():
    return [
        ["r", "h", "e", "a", "k", "a", "e", "h", "r"],
        ["", "", "", "", "", "", "", "", ""],
        ["", "c", "", "", "", "", "", "c", ""],
        ["p", "", "p", "", "p", "", "p", "", "p"],
        ["", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", ""],
        ["P", "", "P", "", "P", "", "P", "", "P"],
        ["", "C", "", "", "", "", "", "C", ""],
        ["", "", "", "", "", "", "", "", ""],
        ["R", "H", "E", "A", "K", "A", "E", "H", "R"],
    ]


def palace(side: str):
    return (3, 5, 7, 9) if side == RED else (3, 5, 0, 2)


def find_king(board, side: str) -> Optional[tuple]:
    k = "K" if side == RED else "k"
    for y in range(10):
        for x in range(9):
            if board[y][x] == k:
                return (x, y)
    return None


def pseudo_moves(board, x: int, y: int):
    """该位置棋子所有可走/可吃的目标格(未过滤己方被将军)。"""
    piece = board[y][x]
    side = side_of(piece)
    moves = []

    def add(nx, ny):
        if on_board(nx, ny) and (board[ny][nx] == "" or side_of(board[ny][nx]) != side):
            moves.append((nx, ny))

    if piece in ("R", "r"):                       # 车
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            while on_board(nx, ny):
                if board[ny][nx] == "":
                    moves.append((nx, ny))
                else:
                    if side_of(board[ny][nx]) != side:
                        moves.append((nx, ny))
                    break
                nx, ny = nx + dx, ny + dy

    elif piece in ("C", "c"):                     # 炮:走直线,吃子翻一座山
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            jumped = False
            while on_board(nx, ny):
                if not jumped:
                    if board[ny][nx] == "":
                        moves.append((nx, ny))
                    else:
                        jumped = True
                else:
                    if board[ny][nx] != "":
                        if side_of(board[ny][nx]) != side:
                            moves.append((nx, ny))
                        break
                nx, ny = nx + dx, ny + dy

    elif piece in ("H", "h"):                     # 马:走日,蹩马腿
        for (dx, dy), (lx, ly) in (
            ((2, 1), (1, 0)), ((2, -1), (1, 0)),
            ((-2, 1), (-1, 0)), ((-2, -1), (-1, 0)),
            ((1, 2), (0, 1)), ((1, -2), (0, -1)),
            ((-1, 2), (0, 1)), ((-1, -2), (0, -1)),
        ):
            lpx, lpy = x + lx, y + ly
            if on_board(lpx, lpy) and board[lpy][lpx] == "":
                add(x + dx, y + dy)

    elif piece in ("E", "e"):                     # 象/相:走田,塞象眼,不过河
        for (dx, dy), (bx, by) in (
            ((2, 2), (1, 1)), ((2, -2), (1, -1)),
            ((-2, 2), (-1, 1)), ((-2, -2), (-1, -1)),
        ):
            nx, ny = x + dx, y + dy
            if on_board(nx, ny) and board[y + by][x + bx] == "":
                if side == RED and ny >= 5:
                    add(nx, ny)
                elif side == BLACK and ny <= 4:
                    add(nx, ny)

    elif piece in ("A", "a"):                     # 士/仕:九宫内斜一步
        xmin, xmax, ymin, ymax = palace(side)
        for dx, dy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            nx, ny = x + dx, y + dy
            if xmin <= nx <= xmax and ymin <= ny <= ymax:
                add(nx, ny)

    elif piece in ("K", "k"):                     # 帅/将:九宫内直一步
        xmin, xmax, ymin, ymax = palace(side)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if xmin <= nx <= xmax and ymin <= ny <= ymax:
                add(nx, ny)

    elif piece in ("P", "p"):                     # 兵/卒:过河前只进,过河后可横走
        forward = -1 if side == RED else 1
        add(x, y + forward)
        if (side == RED and y <= 4) or (side == BLACK and y >= 5):
            add(x + 1, y)
            add(x - 1, y)

    return moves


def is_attacked(board, side: str, tx: int, ty: int) -> bool:
    for y in range(10):
        for x in range(9):
            p = board[y][x]
            if p and side_of(p) == side:
                if (tx, ty) in pseudo_moves(board, x, y):
                    return True
    return False


def kings_facing(board) -> bool:
    for x in range(9):
        ry = by = None
        for y in range(10):
            if board[y][x] == "K":
                ry = y
            elif board[y][x] == "k":
                by = y
        if ry is not None and by is not None:
            lo, hi = (ry, by) if ry < by else (by, ry)
            if all(board[y][x] == "" for y in range(lo + 1, hi)):
                return True
    return False


def king_safe(board, side: str) -> bool:
    kp = find_king(board, side)
    if kp is None:
        return False
    if is_attacked(board, other(side), kp[0], kp[1]):
        return False
    if kings_facing(board):
        return False
    return True


def legal_moves(board, side: str):
    result = []
    for y in range(10):
        for x in range(9):
            p = board[y][x]
            if not p or side_of(p) != side:
                continue
            for nx, ny in pseudo_moves(board, x, y):
                captured = board[ny][nx]
                board[y][x] = ""
                board[ny][nx] = p
                if king_safe(board, side):
                    result.append((x, y, nx, ny))
                board[y][x] = p
                board[ny][nx] = captured
    return result


def is_in_check(board, side: str) -> bool:
    kp = find_king(board, side)
    return kp is not None and is_attacked(board, other(side), kp[0], kp[1])


def fmt_move(m) -> str:
    return f"{m[0]}{m[1]}{m[2]}{m[3]}"


def parse_xiangqi_move(text: str) -> ParsedMove:
    """从模型输出提取 {"move":"x1y1x2y2","reason":"..."}。"""
    if not text:
        return ParsedMove("unparsed", None, "")
    m = re.search(r'"move"\s*:\s*"([^"]+)"', text)
    r = re.search(r'"reason"\s*:\s*"([^"]*)"', text)
    move = m.group(1).strip() if m else None
    reason = r.group(1).strip() if r else ""
    if move and re.fullmatch(r"[0-9]{4}", move):
        return ParsedMove("move", move, reason)
    if move and re.fullmatch(r"[0-9]{4}", move.replace(" ", "")):
        return ParsedMove("move", move.replace(" ", ""), reason)
    return ParsedMove("unparsed", None, reason or text[:100])


def board_to_text(board) -> str:
    lines = ["     0  1  2  3  4  5  6  7  8"]
    for y in range(10):
        cells = "  ".join(PIECE_NAMES.get(p, "．") for p in board[y])
        lines.append(f" {y}   {cells}")
    return "\n".join(lines)


class XiangqiGame(BoardGame):
    game_id = "xiangqi"
    display_name = "中国象棋"

    def __init__(self, max_moves: int = MAX_MOVES):
        self.board = initial_board()
        self.max_moves = max_moves
        self.history: list[tuple[str, str]] = []
        self.history_map: dict[str, int] = {}
        self.status = "playing"      # playing / check / checkmate / stalemate / draw
        self.winner: str | None = None
        self.reason = ""
        self.end_comment = ""

    # ---------- 对局结构 ----------

    @property
    def sides(self) -> list[str]:
        return [RED, BLACK]

    def side_display(self, side: str) -> str:
        return SIDE_LABEL[side]

    def next_side(self, side: str) -> str:
        return other(side)

    @property
    def to_move(self) -> str:
        return RED if not self.history or self.history[-1][1] == BLACK else BLACK

    @property
    def over(self) -> bool:
        return self.status in ("checkmate", "stalemate", "draw")

    @property
    def result(self) -> str | None:
        if not self.over:
            return None
        if self.status == "checkmate":
            return "红方胜" if self.winner == RED else "黑方胜"
        return "和棋"

    # ---------- 着法 ----------

    def parse_move(self, text: str) -> ParsedMove:
        return parse_xiangqi_move(text)

    def is_legal(self, side: str, move: str) -> tuple[bool, str]:
        if not re.fullmatch(r"[0-9]{4}", str(move)):
            return False, "着法必须是四位数字格式 x1y1x2y2(如 1242)"
        x1, y1, x2, y2 = (int(c) for c in move)
        if not (on_board(x1, y1) and on_board(x2, y2)):
            return False, "坐标越界"
        piece = self.board[y1][x1]
        if not piece:
            return False, f"起点 ({x1},{y1}) 没有棋子"
        if side_of(piece) != side:
            return False, f"起点 ({x1},{y1}) 的棋子不属于你"
        if (x1, y1, x2, y2) not in legal_moves(self.board, side):
            return False, "该走法不在当前合法走法列表中(注意蹩马腿、塞象眼、被将军时必须应将等)"
        return True, ""

    def apply(self, side: str, move: str) -> MoveInfo:
        ok, msg = self.is_legal(side, move)
        if not ok:
            raise IllegalMove(msg)
        x1, y1, x2, y2 = (int(c) for c in move)
        captured_piece = self.board[y2][x2]
        piece = self.board[y1][x1]
        self.board[y1][x1] = ""
        self.board[y2][x2] = piece
        self.history.append((move, side))
        fp = self.fingerprint()
        self.history_map[fp] = self.history_map.get(fp, 0) + 1
        self.check_status()
        return MoveInfo(len(self.history), side, move,
                        captured=1 if captured_piece else 0)

    def random_legal_move(self, side: str) -> str | None:
        moves = legal_moves(self.board, side)
        return fmt_move(random.choice(moves)) if moves else None

    def candidates(self, side: str) -> list[str] | None:
        if self.over:
            return None
        return [fmt_move(m) for m in legal_moves(self.board, side)]

    # ---------- 状态机 ----------

    def fingerprint(self) -> str:
        return "".join("".join(row) for row in self.board) + self.to_move

    def check_status(self) -> None:
        side = self.to_move
        legal = legal_moves(self.board, side)
        in_check = is_in_check(self.board, side)
        if len(self.history) >= self.max_moves:
            self.status, self.winner, self.reason = "draw", None, f"达到步数上限 {self.max_moves},判和"
            return
        if max(self.history_map.values(), default=1) >= REPETITION_LIMIT:
            self.status, self.winner, self.reason = "draw", None, "三次重复局面,判和"
            return
        if not legal:
            if in_check:
                self.status = "checkmate"
                self.winner = other(side)
                self.reason = f"{SIDE_LABEL[side]}被将死,{SIDE_LABEL[other(side)]}胜"
            else:
                self.status, self.winner, self.reason = "stalemate", None, "无子可动,判和"
            return
        self.status = "check" if in_check else "playing"
        self.reason = ""
        self.winner = None

    # ---------- 提示词 ----------

    def system_prompt(self, side: str) -> str:
        return (
            f"你是一位中国象棋 AI 棋手,执{SIDE_LABEL[side]}。"
            "你每回合只做一件事:从给出的合法候选走法列表中选择一手棋,"
            "只输出一个JSON对象,格式:{\"move\":\"x1y1x2y2\",\"reason\":\"一句话理由\"},"
            "禁止输出任何其他文字。"
        )

    def turn_prompt(self, side: str, recent: list[str], feedback: str | None) -> str:
        moves = legal_moves(self.board, side)
        move_list = "  ".join(fmt_move(m) for m in moves)
        lines = [
            f"轮到【{SIDE_LABEL[side]}】行棋。",
            "棋盘为 9 列(x=0~8) × 10 行(y=0~9),第 0 行在上方为黑方,第 9 行在下方为红方。",
            "走法格式为 x1y1x2y2(四位数字:起点坐标+终点坐标),例如 1242 表示从 (1,2) 平移到 (4,2)。",
            "",
            "当前棋盘:",
            board_to_text(self.board),
            "",
            f"你当前所有合法的候选走法(必须从中选择其一):\n{move_list}",
        ]
        if recent:
            lines.append("最近着手:" + " ".join(recent[-12:]))
        if feedback:
            lines.append("注意:" + feedback)
        if self.status == "check":
            lines.append("警告:你正被将军,必须走出解除将军的走法!")
        lines.append(
            '请只输出一个JSON对象,格式严格如下,不要输出任何其他文字:'
            '{"move": "x1y1x2y2", "reason": "一句话理由"}'
        )
        return "\n".join(lines)

    # ---------- 展示 / 序列化 ----------

    def ascii(self) -> str:
        return board_to_text(self.board)

    def move_display(self, move: str) -> str:
        if not (isinstance(move, str) and re.fullmatch(r"[0-9]{4}", move)):
            return move
        x1, y1, x2, y2 = (int(c) for c in move)
        piece = self.board[y2][x2] or ""
        name = PIECE_NAMES.get(piece, "?")
        return f"{name} ({x1},{y1})->({x2},{y2})"

    def snapshot(self) -> dict:
        return {
            "game": self.game_id,
            "board": self.board,
            "to_move": self.to_move,
            "status": self.status,
            "winner": self.winner,
            "reason": self.reason,
            "over": self.over,
            "result": self.result,
            "end_comment": self.end_comment,
            "move_count": len(self.history),
            "last_move": self.history[-1][0] if self.history else None,
        }
