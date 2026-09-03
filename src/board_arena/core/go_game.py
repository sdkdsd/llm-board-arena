"""围棋(严格国际规则)。

规则要点:黑先行;禁自杀;全局同形禁止(positional superko,天然涵盖打劫);
双方连续虚着终局;数子法区域计分(活子+单属空点,白贴目);终局死子须双方
确认一致后才移除。
"""
from __future__ import annotations

import datetime
import json
import re

from .base import BoardGame, IllegalMove, MoveInfo, ParsedMove

COL_LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"   # 记谱列字母,跳过 I


def coord_str(x: int, y: int, size: int) -> str:
    return f"{COL_LETTERS[x]}{size - y}"


def parse_coord(text: str, size: int) -> tuple[int, int]:
    s = str(text).strip().upper()
    if len(s) < 2 or s[0] not in COL_LETTERS:
        raise ValueError(f"无法解析坐标: {text!r}")
    x = COL_LETTERS.index(s[0])
    y = size - int(s[1:])
    if not (0 <= x < size and 0 <= y < size):
        raise ValueError(f"坐标越界: {text!r}")
    return x, y


class GoBoard:
    """规则引擎:与界面无关,可独立使用。"""

    def __init__(self, size: int = 19, komi: float = 6.5):
        self.size = size
        self.komi = komi
        self.cells: list[list[str | None]] = [[None] * size for _ in range(size)]
        self.captures = {"B": 0, "W": 0}
        self.history = {self._hash()}   # 全局同形禁止

    # ---------- 基础 ----------

    def _hash(self):
        return tuple(tuple(row) for row in self.cells)

    def _clone(self) -> "GoBoard":
        b = GoBoard.__new__(GoBoard)
        b.size, b.komi = self.size, self.komi
        b.cells = [row[:] for row in self.cells]
        b.captures = dict(self.captures)
        b.history = set(self.history)
        return b

    def neighbors(self, x: int, y: int):
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < self.size and 0 <= ny < self.size:
                yield nx, ny

    def _group(self, x: int, y: int):
        color = self.cells[y][x]
        stack, stones, libs = [(x, y)], {(x, y)}, set()
        while stack:
            cx, cy = stack.pop()
            for nx, ny in self.neighbors(cx, cy):
                v = self.cells[ny][nx]
                if v is None:
                    libs.add((nx, ny))
                elif v == color and (nx, ny) not in stones:
                    stones.add((nx, ny))
                    stack.append((nx, ny))
        return stones, libs

    # ---------- 规则 ----------

    def is_legal(self, color: str, x: int, y: int) -> tuple[bool, str]:
        if not (0 <= x < self.size and 0 <= y < self.size):
            return False, "坐标越界"
        if self.cells[y][x] is not None:
            return False, "该点已有棋子"
        b = self._clone()
        try:
            b._try(color, x, y)
        except IllegalMove as e:
            return False, str(e)
        return True, ""

    def _try(self, color: str, x: int, y: int):
        opp = "W" if color == "B" else "B"
        self.cells[y][x] = color
        captured = set()
        for nx, ny in self.neighbors(x, y):
            if self.cells[ny][nx] == opp:
                stones, libs = self._group(nx, ny)
                if not libs:
                    captured |= stones
        for gx, gy in captured:
            self.cells[gy][gx] = None
        _, own_libs = self._group(x, y)
        if not own_libs:
            raise IllegalMove("自杀(禁着点)")
        if self._hash() in self.history:
            raise IllegalMove("全局同形再现(禁全同,含打劫)")
        return captured

    def play(self, color: str, x: int, y: int) -> set:
        ok, msg = self.is_legal(color, x, y)
        if not ok:
            raise IllegalMove(msg)
        b = self._clone()
        captured = b._try(color, x, y)
        self.cells = b.cells
        self.captures[color] += len(captured)
        self.history = b.history
        self.history.add(self._hash())
        return captured

    def remove_stones(self, points) -> None:
        for x, y in points:
            self.cells[y][x] = None

    # ---------- 终局计分(数子法) ----------

    def score(self, komi: float | None = None) -> tuple[float, float]:
        komi = self.komi if komi is None else komi
        black = white = 0
        for y in range(self.size):
            for x in range(self.size):
                if self.cells[y][x] == "B":
                    black += 1
                elif self.cells[y][x] == "W":
                    white += 1
        visited: set = set()
        for y in range(self.size):
            for x in range(self.size):
                if self.cells[y][x] is not None or (x, y) in visited:
                    continue
                region, borders = set(), set()
                stack = [(x, y)]
                region.add((x, y))
                while stack:
                    cx, cy = stack.pop()
                    for nx, ny in self.neighbors(cx, cy):
                        v = self.cells[ny][nx]
                        if v is None:
                            if (nx, ny) not in region:
                                region.add((nx, ny))
                                stack.append((nx, ny))
                        else:
                            borders.add(v)
                visited |= region
                if borders == {"B"}:
                    black += len(region)
                elif borders == {"W"}:
                    white += len(region)
        return black, white + komi

    def ascii(self) -> str:
        lines = ["   " + " ".join(COL_LETTERS[: self.size])]
        sym = {"B": "X", "W": "O", None: "."}
        for y in range(self.size):
            row = " ".join(sym[self.cells[y][x]] for x in range(self.size))
            lines.append(f"{self.size - y:2d} {row}")
        return "\n".join(lines)


# ---------- 模型输出的着法解析 ----------

_COORD_RE = re.compile(r"\b([A-HJ-T])(\d{1,2})\b", re.I)
_JSON_RE = re.compile(r"\{[^{}]*\}", re.S)


def parse_go_move(text: str, size: int) -> ParsedMove:
    move_field, reason = "", ""
    m = _JSON_RE.search(text)
    if m:
        try:
            data = json.loads(m.group(0))
            move_field = str(data.get("move", "")).strip()
            reason = str(data.get("reason", "")).strip()
        except Exception:
            pass
    if not move_field:
        move_field = text

    low = move_field.lower()
    if "resign" in low or "认输" in move_field:
        return ParsedMove("resign", None, reason)
    if "pass" in low or "虚着" in move_field or "停一手" in move_field or "停着" in move_field:
        return ParsedMove("pass", None, reason)
    m2 = _COORD_RE.search(move_field)
    if m2:
        try:
            x, y = parse_coord(m2.group(0), size)
            return ParsedMove("move", coord_str(x, y, size), reason)
        except ValueError:
            pass
    return ParsedMove("unparsed", None, reason or text[:100])


# ---------- SGF 记谱 ----------

def _sgf_escape(s) -> str:
    return str(s).replace("\\", "\\\\").replace("]", "\\]")


def build_sgf(size, komi, pb, pw, record, result, comment=None) -> str:
    """record 元素: {side, action:"move"/"pass", coord:(x,y)|None, reason, note}"""
    dt = datetime.date.today().isoformat()
    head = (
        "(;GM[1]FF[4]CA[UTF-8]SZ[{size}]KM[{komi}]DT[{dt}]"
        "PB[{pb}]PW[{pw}]RE[{result}]"
        "RU[Area scoring, suicide forbidden, positional superko]"
    ).format(size=size, komi=komi, dt=dt, pb=_sgf_escape(pb),
             pw=_sgf_escape(pw), result=_sgf_escape(result))
    if comment:
        head += f"C[{_sgf_escape(comment)}]"

    def sgf_xy(x, y):
        return chr(ord("a") + x) + chr(ord("a") + y)

    body = []
    for r in record:
        c = "B" if r["side"] == "B" else "W"
        if r["action"] == "pass":
            node = f";{c}[]"
        else:
            node = f";{c}[{sgf_xy(*r['coord'])}]"
        parts = [p for p in (r.get("reason"), r.get("note")) if p]
        if parts:
            node += f"C[{_sgf_escape(' / '.join(parts))}]"
        body.append(node)
    return head + "".join(body) + ")"


# ---------- 竞技场接口 ----------

class GoGame(BoardGame):
    game_id = "go"
    display_name = "围棋"

    def __init__(self, size: int = 19, komi: float = 6.5, max_moves: int = 500):
        self.board = GoBoard(size, komi)
        self.komi = komi
        self.max_moves = max_moves
        self.consecutive_pass = 0
        self.move_count = 0
        self._to_move = "B"
        self._resigned: str | None = None
        self.end_comment = ""

    # ---------- 对局结构 ----------

    @property
    def sides(self) -> list[str]:
        return ["B", "W"]

    def side_display(self, side: str) -> str:
        return "黑棋" if side == "B" else "白棋"

    def next_side(self, side: str) -> str:
        return "W" if side == "B" else "B"

    @property
    def to_move(self) -> str:
        return self._to_move

    @property
    def over(self) -> bool:
        return (self._resigned is not None or self.consecutive_pass >= 2
                or self.move_count >= self.max_moves)

    @property
    def result(self) -> str | None:
        if not self.over:
            return None
        if self._resigned is not None:
            return "W+R" if self._resigned == "B" else "B+R"
        b, w = self.board.score(self.komi)
        diff = b - w
        return ("B+%.1f" % diff) if diff > 0 else ("W+%.1f" % -diff)

    # ---------- 着法 ----------

    def parse_move(self, text: str) -> ParsedMove:
        return parse_go_move(text, self.board.size)

    def is_legal(self, side: str, move: str) -> tuple[bool, str]:
        if move == "pass":
            return True, ""
        try:
            x, y = parse_coord(move, self.board.size)
        except ValueError as e:
            return False, str(e)
        return self.board.is_legal(side, x, y)

    def apply(self, side: str, move: str) -> MoveInfo:
        if move == "pass":
            self.consecutive_pass += 1
            self.move_count += 1
            self._to_move = self.next_side(side)
            return MoveInfo(self.move_count, side, "pass")
        x, y = parse_coord(move, self.board.size)
        cap_before = self.board.captures[side]
        self.board.play(side, x, y)
        gained = self.board.captures[side] - cap_before
        self.consecutive_pass = 0
        self.move_count += 1
        self._to_move = self.next_side(side)
        return MoveInfo(self.move_count, side, move, captured=gained)

    def resign(self, side: str) -> None:
        self._resigned = side
        self.move_count += 1

    def random_legal_move(self, side: str) -> str | None:
        pts = [coord_str(x, y, self.board.size)
               for y in range(self.board.size)
               for x in range(self.board.size)
               if self.board.is_legal(side, x, y)[0]]
        import random
        return random.choice(pts) if pts else None

    def candidates(self, side: str) -> list[str] | None:
        return None

    # ---------- 提示词 ----------

    def system_prompt(self, side: str) -> str:
        color_name = "黑棋(X)" if side == "B" else "白棋(O)"
        example = '{"move":"坐标(如E5)或pass(虚着)或resign(认输)","reason":"简短理由,50字以内"}'
        return (
            f"你是一位围棋棋手,执{color_name},参加一场严格按国际围棋规则进行的对局"
            f"(数子法区域计分、白贴{self.komi}目、禁自杀、全局同形禁止)。"
            "你每回合只做一件事:根据给出的局面选择一手棋。"
            f"必须只输出一个JSON对象,格式:{example},禁止输出JSON以外的任何文字。"
        )

    def turn_prompt(self, side: str, recent: list[str], feedback: str | None) -> str:
        b = self.board
        lines = [
            f"棋盘({b.size}路;列从左到右为A-T跳过I,行号自下而上;X=黑,O=白,.=空):",
            b.ascii(),
            f"当前提子:黑提{b.captures['B']}子,白提{b.captures['W']}子;贴目:白+{self.komi}目。",
        ]
        if recent:
            lines.append("最近着手:" + " ".join(recent[-12:]))
        lines.append(f"轮到你执{'黑(X)' if side == 'B' else '白(O)'}落子。")
        if feedback:
            lines.append("注意:" + feedback)
        lines.append(
            "落点必须是空点;不能下成自杀;不能形成全局同形再现(含打劫)。"
            "对方已死或濒死的棋群应寻找手段提掉,确信盘上已无价值点时才可pass。只输出JSON。"
        )
        return "\n".join(lines)

    # ---------- 展示 / 序列化 ----------

    def ascii(self) -> str:
        return self.board.ascii()

    def move_display(self, move: str) -> str:
        return move

    def snapshot(self) -> dict:
        b = self.board
        sym = {"B": "X", "W": "O", None: "."}
        return {
            "game": self.game_id,
            "size": b.size,
            "grid": ["".join(sym[b.cells[y][x]] for x in range(b.size))
                     for y in range(b.size)],
            "captures": b.captures,
            "komi": self.komi,
            "to_move": self._to_move,
            "over": self.over,
            "result": self.result,
            "end_comment": self.end_comment,
        }

    # ---------- 终局钩子:死子协商 ----------

    def finalize(self, players, on_event) -> str:
        if self._resigned is not None:
            self.end_comment = "中盘胜"
            return self.end_comment
        if self.move_count >= self.max_moves and self.consecutive_pass < 2:
            self.end_comment = "达到手数上限,裁判按盘面数目判定。"
            on_event({"type": "log", "text": self.end_comment})

        def ask_dead_stones(seer: str, opp_color: str) -> set:
            opp_name = "黑(X)" if opp_color == "B" else "白(O)"
            prompt = (
                f"对局已结束。请判断:对方{opp_name}的棋子中,哪些是终局时的死棋?\n"
                f"{self.board.ascii()}\n"
                '只输出一个JSON数组,元素为坐标字符串,例如 ["E5","F5"];没有死子则输出 []。'
            )
            try:
                text = players[seer].chat(
                    "你是围棋规则助手,只输出JSON,禁止其他文字。", prompt)
                m = re.search(r"\[[^\[\]]*\]", text, re.S)
                arr = json.loads(m.group(0)) if m else []
            except Exception:
                return set()
            pts = set()
            for c in arr:
                try:
                    x, y = parse_coord(c, self.board.size)
                    if self.board.cells[y][x] == opp_color:
                        pts.add((x, y))
                except (ValueError, IndexError):
                    continue
            return pts

        claimed_b = ask_dead_stones("B", "W")   # 黑方指认白死子
        claimed_w = ask_dead_stones("W", "B")   # 白方指认黑死子
        if claimed_b and claimed_b == claimed_w:
            self.board.remove_stones(claimed_b)
            coords = "、".join(coord_str(x, y, self.board.size)
                               for x, y in sorted(claimed_b))
            self.end_comment += f"终局死子双方确认一致并移除:{coords}。"
            on_event({"type": "log", "text": f"死子协商:双方一致确认死子:{coords},已移除后数子。"})
        else:
            self.end_comment += "终局死子双方判断不一致或未指认,按盘面原样数子。"
            on_event({"type": "log", "text": "死子协商:双方未达成一致,按盘面原样数子。"})
        return self.end_comment
