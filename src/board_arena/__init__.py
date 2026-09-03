"""llm-board-arena: LLM 棋类竞技场。"""

from .core import (GAMES, GoBoard, GoGame, XiangqiGame, BoardGame,
                   create_game)
from .players import (LLMPlayer, RandomPlayer, ScriptedPlayer,
                      available_engines, load_env, make_player)
from .referee import Referee
from .records import compute_stats, load_record, load_records, save_record

__version__ = "0.1.0"

__all__ = [
    "BoardGame", "GoBoard", "GoGame", "XiangqiGame", "GAMES", "create_game",
    "LLMPlayer", "RandomPlayer", "ScriptedPlayer",
    "available_engines", "load_env", "make_player",
    "Referee", "compute_stats", "load_record", "load_records", "save_record",
    "__version__",
]
