import pytest

from board_arena.core.go_game import (GoBoard, GoGame, build_sgf,
                                      parse_go_move)


def test_capture():
    b = GoBoard(9)
    b.play("W", 2, 0); b.play("B", 1, 0); b.play("B", 2, 1); b.play("B", 3, 0)
    assert b.cells[0][2] is None          # 白子被提
    assert b.captures["B"] == 1


def test_suicide_forbidden():
    b = GoBoard(9)
    b.play("B", 1, 0); b.play("B", 0, 1)     # 黑棋包住角点 (0,0) 两面
    ok, msg = b.is_legal("W", 0, 0)
    assert not ok and "自杀" in msg


def test_superko():
    # 全局同形禁止:人为还原到历史局面后再落同一点,应被拒绝
    b = GoBoard(9)
    b.play("B", 0, 0)
    b.play("W", 5, 5)
    b.cells[0][0] = None
    b.cells[5][5] = None            # 盘面回到初始空盘,但历史里已有 B(0,0) 局面
    ok, msg = b.is_legal("B", 0, 0)
    assert not ok and "同形" in msg


def test_scoring_empty_board():
    b = GoBoard(9)
    black, white = b.score(komi=6.5)
    assert black == 0 and white == 6.5


def test_scoring_territory():
    b = GoBoard(9)
    # 黑第2列、白第6列各一条墙:左右各自围空,中间为双方共同边界的中立点
    for y in range(9):
        b.play("B", 2, y)
        b.play("W", 6, y)
    black, white = b.score(komi=0)
    assert black == 9 + 2 * 9     # 活子9 + 左侧 2列x9
    assert white == 9 + 2 * 9     # 活子9 + 右侧 2列x9


def test_parse_moves():
    m = parse_go_move('{"move": "E5", "reason": "占角"}', 19)
    assert m.kind == "move" and m.move == "E5" and m.reason == "占角"
    assert parse_go_move("我认输", 19).kind == "resign"
    assert parse_go_move('{"move":"pass"}', 19).kind == "pass"
    assert parse_go_move(" nonsense ", 19).kind == "unparsed"


def test_sgf_build():
    sgf = build_sgf(9, 5.5, "黑(测试)", "白(测试)",
                    [{"side": "B", "action": "move", "coord": (4, 4),
                      "reason": "天元", "note": ""},
                     {"side": "W", "action": "pass", "coord": None,
                      "reason": "", "note": ""}],
                    "B+2.5", "测试注释")
    assert sgf.startswith("(;GM[1]FF[4]")
    assert "SZ[9]" in sgf and "KM[5.5]" in sgf and "RE[B+2.5]" in sgf
    assert ";B[ee]" in sgf and ";W[]" in sgf and "天元" in sgf


def test_go_game_flow_pass_end():
    g = GoGame(size=9, komi=6.5, max_moves=100)
    assert not g.over
    g.apply("B", "pass"); g.apply("W", "pass")
    assert g.over
    assert g.result == "W+6.5"   # 空盘数子
