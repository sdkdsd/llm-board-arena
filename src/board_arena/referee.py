"""裁判程序:驱动一局对弈,产出事件流与对局档案。

对局过程对模型完全透明可审计:每手棋的原始输出、非法着法反馈重试、
裁判代抽等都会进入事件流与档案。
"""
from __future__ import annotations

import datetime
import time
from typing import Callable

from .core.base import BoardGame, MoveInfo, PlayerSpec
from .core.go_game import GoGame

Event = dict


class Referee:
    """跑一局对弈。``on_event`` 收到事件 dict 流(网页/CLI 各取所需)。"""

    def __init__(self, game: BoardGame,
                 players: dict,                      # side -> 有 chat/spec 的棋手
                 max_illegal_attempts: int = 4,
                 log_raw: bool = True):
        self.game = game
        self.players = players
        self.max_illegal_attempts = max_illegal_attempts
        self.log_raw = log_raw
        self.events: list[Event] = []

    # ---------- 事件 ----------

    def _emit(self, ev: Event, on_event: Callable[[Event], None]) -> None:
        self.events.append(ev)
        on_event(ev)

    def _spec(self, side: str) -> PlayerSpec:
        return self.players[side].spec

    # ---------- 主循环 ----------

    def run(self, on_event: Callable[[Event], None] = lambda e: None) -> dict:
        game = self.game
        started = datetime.datetime.now().isoformat(timespec="seconds")
        assignments = {side: self._spec(side).__dict__ | {"side": side}
                       for side in game.sides}
        self._emit({"type": "start",
                    "game": game.game_id,
                    "display_name": game.display_name,
                    "snapshot": game.snapshot(),
                    "players": assignments}, on_event)

        # RandomPlayer 之类需要知道局面/执方
        for side, p in self.players.items():
            if hasattr(p, "bind"):
                p.bind(game, side)

        recent: list[str] = []
        t0 = time.time()
        while not game.over:
            side = game.to_move
            player = self.players[side]
            self._emit({"type": "thinking", "side": side,
                        "player": self._spec(side).name}, on_event)

            move, reason, note = self._ask_move(side, player, recent, on_event)

            if move == "resign":
                # game.resign 已在 _ask_move 内调用
                info = MoveInfo(game.move_count, side, "resign", reason=reason)
                self._emit({"type": "move", **info.to_json(),
                            "player": self._spec(side).name,
                            "side_display": game.side_display(side),
                            "move_display": game.move_display("resign"),
                            "snapshot": game.snapshot()}, on_event)
                if not game.over:      # 引擎未实现认输状态时防死循环
                    break
                continue

            info = game.apply(side, move)
            info.reason = reason
            info.note = note
            recent.append(f"{game.side_display(side)}{game.move_display(info.move)}")
            ev = {"type": "move", **info.to_json(),
                  "player": self._spec(side).name,
                  "side_display": game.side_display(side),
                  "move_display": game.move_display(info.move),
                  "snapshot": game.snapshot()}
            self._emit(ev, on_event)

        # 终局收尾(围棋死子协商等),结果在收尾后才最终确定
        end_comment = game.finalize(self.players, lambda e: self._emit(e, on_event))
        game.end_comment = end_comment or game.end_comment
        result = game.result or "和棋"
        duration = round(time.time() - t0, 1)

        record = {
            "id": "",
            "game": game.game_id,
            "display_name": game.display_name,
            "started": started,
            "duration_sec": duration,
            "players": assignments,
            "moves": [],
            "move_count": 0,
            "result": result,
            "end_comment": game.end_comment,
            "reason": getattr(game, "reason", ""),
        }
        moves = []
        for ev in self.events:
            if ev["type"] == "move":
                m = {k: ev[k] for k in ("no", "side", "move", "captured",
                                        "reason", "note")}
                m["player"] = ev["player"]
                m["move_display"] = ev["move_display"]
                moves.append(m)
        record["moves"] = moves
        record["move_count"] = len(moves)
        winner_side = self._winner_side(result)
        record["winner_side"] = winner_side
        record["winner"] = self._spec(winner_side).name if winner_side else None
        snap = game.snapshot()
        if game.game_id == "go":
            record["extra"] = {"size": snap.get("size", 19),
                               "komi": snap.get("komi", 6.5)}
        self._emit({"type": "end", "result": result,
                    "end_comment": game.end_comment,
                    "reason": getattr(game, "reason", ""),
                    "snapshot": game.snapshot(),
                    "duration_sec": duration}, on_event)
        return record

    # ---------- 单回合 ----------

    def _ask_move(self, side: str, player, recent: list[str],
                  on_event) -> tuple[str, str, str]:
        """询问一方着法。返回 (move_str, reason, note)。非法/无法解析给反馈重试,
        连续失败则由裁判代抽合法着。"""
        game = self.game
        feedback: str | None = None
        for attempt in range(1, self.max_illegal_attempts + 1):
            prompt = game.turn_prompt(side, recent, feedback)
            try:
                raw = player.chat(game.system_prompt(side), prompt)
            except Exception as e:  # 接口异常也计入重试次数
                feedback = f"第{attempt}/{self.max_illegal_attempts}次调用接口失败({e}),请重新作答。"
                self._emit({"type": "log", "text": f"接口异常({self._spec(side).name}): {e}"},
                           on_event)
                continue
            if self.log_raw:
                self._emit({"type": "raw", "side": side,
                            "text": raw.strip()[:300]}, on_event)
            parsed = game.parse_move(raw)
            if parsed.kind == "resign":
                game.resign(side)
                self._emit({"type": "log",
                            "text": f"{self._spec(side).name}({game.side_display(side)})认输。"
                                    f"理由:{parsed.reason or '未说明'}"}, on_event)
                return "resign", parsed.reason, ""
            if parsed.kind == "pass":
                return "pass", parsed.reason, ""
            if parsed.kind == "move":
                ok, msg = game.is_legal(side, parsed.move)
                if ok:
                    return parsed.move, parsed.reason, ""
                feedback = f"你上一步的 {parsed.move} 不合法:{msg}。请换一手。"
                self._emit({"type": "illegal", "side": side, "attempt": attempt,
                            "move": parsed.move, "why": msg}, on_event)
            else:
                feedback = ("无法从你的回答中解析出着法,请严格只输出JSON:"
                            '{"move":"...","reason":"..."}。')
                self._emit({"type": "illegal", "side": side, "attempt": attempt,
                            "move": None, "why": "输出无法解析"}, on_event)

        forced = game.random_legal_move(side) or "pass"
        if forced == "pass":
            note = f"连续{self.max_illegal_attempts}次失败且无合法着点,裁判判为虚着"
        else:
            note = f"连续{self.max_illegal_attempts}次给出非法/无法解析的着法,裁判代抽一手合法着"
        self._emit({"type": "log",
                    "text": f"{self._spec(side).name} 连续{self.max_illegal_attempts}次失败,"
                            f"裁判代抽:{game.move_display(forced)}"}, on_event)
        return forced, "(强制落子)", note

    # ---------- 结果辅助 ----------

    def _winner_side(self, result: str) -> str | None:
        game = self.game
        sides = game.sides
        if isinstance(game, GoGame):
            if result.startswith("B+"):
                return "B"
            if result.startswith("W+"):
                return "W"
            return None
        if result == "红方胜":
            return "red"
        if result == "黑方胜":
            return "black"
        return None
