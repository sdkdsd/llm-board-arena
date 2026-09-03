from .base import BoardGame, IllegalMove, MoveInfo, ParsedMove, PlayerSpec
from .go_game import GoBoard, GoGame, build_sgf, parse_go_move
from .xiangqi import XiangqiGame, parse_xiangqi_move

GAMES = {"go": GoGame, "xiangqi": XiangqiGame}


def create_game(game_id: str, **kwargs) -> BoardGame:
    cls = GAMES.get(game_id)
    if cls is None:
        raise ValueError(f"未知游戏: {game_id}(可选: {', '.join(GAMES)})")
    return cls(**kwargs)


__all__ = [
    "BoardGame", "IllegalMove", "MoveInfo", "ParsedMove", "PlayerSpec",
    "GoBoard", "GoGame", "XiangqiGame", "build_sgf", "parse_go_move",
    "parse_xiangqi_move", "GAMES", "create_game",
]
