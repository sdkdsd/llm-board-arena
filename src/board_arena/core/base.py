"""统一棋类接口。

裁判程序只依赖这里的抽象:一个棋类游戏负责
  1. 把 LLM 的原始输出解析成着法(``parse_move``),
  2. 校验着法合法性并给出失败原因(``is_legal``),
  3. 落子并返回着法信息(``apply``),
  4. 生成给模型的系统/回合提示词,
  5. 输出网页快照(``snapshot``)与 ASCII 棋盘。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ParsedMove:
    """从模型输出解析出的着法。"""

    kind: str            # "move" / "pass" / "resign" / "unparsed"
    move: str | None = None
    reason: str = ""


@dataclass
class MoveInfo:
    """一步已落子的着法(写入对局档案、推送给网页)。"""

    no: int                       # 手数(从 1 起)
    side: str                     # 该方的内部标识
    move: str                     # 着法文本(如 "E5" / "1242" / "pass")
    captured: int = 0             # 提子/吃子数
    reason: str = ""              # 模型给出的理由
    note: str = ""                # 裁判备注(如"代抽合法着")
    raw: str = ""                 # 模型原始输出(截断)

    def to_json(self) -> dict:
        return {
            "no": self.no, "side": self.side, "move": self.move,
            "captured": self.captured, "reason": self.reason,
            "note": self.note,
        }


class IllegalMove(Exception):
    pass


@dataclass
class PlayerSpec:
    """一名棋手的身份描述。"""

    name: str                     # 展示名,如 "GLM"
    engine: str                   # 引擎标识,如 "glm" / "deepseek" / "random"
    model: str = ""               # 模型名(LLM 玩家才有)
    extra: dict[str, Any] = field(default_factory=dict)

    def label(self) -> str:
        return f"{self.name}({self.model})" if self.model else self.name


class BoardGame(ABC):
    """棋类游戏抽象。side 用内部标识(围棋 "B"/"W",象棋 "red"/"black")。"""

    game_id: str = ""
    display_name: str = ""

    # ---------- 对局结构 ----------

    @property
    @abstractmethod
    def sides(self) -> list[str]:
        """所有执方,第一个为先手。"""

    @abstractmethod
    def side_display(self, side: str) -> str:
        """执方的展示名,如 "黑棋" / "红方"。"""

    @abstractmethod
    def next_side(self, side: str) -> str:
        """轮到谁。"""

    @property
    @abstractmethod
    def to_move(self) -> str:
        """当前该谁走。"""

    @property
    @abstractmethod
    def over(self) -> bool:
        """对局是否已经结束。"""

    @property
    @abstractmethod
    def result(self) -> str | None:
        """终局结果字符串,如 "B+2.5" / "W+R" / "红方胜" / "和棋"。未结束为 None。"""

    end_comment: str = ""

    # ---------- 着法 ----------

    @abstractmethod
    def parse_move(self, text: str) -> ParsedMove:
        """从模型原始输出解析着法(永不抛异常,解析不出返回 kind="unparsed")。"""

    @abstractmethod
    def is_legal(self, side: str, move: str) -> tuple[bool, str]:
        """着法是否合法,失败时给出中文原因。"""

    @abstractmethod
    def apply(self, side: str, move: str) -> MoveInfo:
        """落子,返回着法信息。非法着抛 IllegalMove。pass 由实现自行处理。"""

    def resign(self, side: str) -> None:
        """认输。默认由子类自行实现状态转移。"""

    @abstractmethod
    def random_legal_move(self, side: str) -> str | None:
        """随机一个合法着法(裁判代抽用);无合法着返回 None。"""

    def candidates(self, side: str) -> list[str] | None:
        """候选走法列表;开放式着法(围棋)返回 None,提示词里不列候选。"""

    # ---------- 提示词 ----------

    @abstractmethod
    def system_prompt(self, side: str) -> str:
        """系统提示词。"""

    @abstractmethod
    def turn_prompt(self, side: str, recent: list[str], feedback: str | None) -> str:
        """回合提示词。recent 为最近着手描述,feedback 为裁判对上一手非法着法的反馈。"""

    # ---------- 展示 / 序列化 ----------

    @abstractmethod
    def ascii(self) -> str:
        """ASCII 棋盘(喂给模型和终端日志)。"""

    @abstractmethod
    def snapshot(self) -> dict:
        """网页渲染所需的完整局面快照(可 JSON 序列化)。"""

    @abstractmethod
    def move_display(self, move: str) -> str:
        """着法的展示文本(网页/棋谱用)。"""

    # ---------- 终局钩子 ----------

    def finalize(self, players: dict[str, Any], on_event) -> str:
        """终局收尾钩子(如围棋死子协商)。返回补充说明;已用 players[side].chat。
        players: side -> 具备 chat(system, user) 的玩家;on_event(dict) 推送事件。
        """
        return ""
