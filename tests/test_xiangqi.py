import pytest

from board_arena.core import xiangqi as xq
from board_arena.core.xiangqi import IllegalMove, XiangqiGame


def test_initial_legal_moves():
    g = XiangqiGame()
    assert g.to_move == xq.RED
    cands = g.candidates(xq.RED)
    assert len(cands) == 44           # 象棋开局红方 44 种合法着法(车马炮兵各展其能)
    assert "0605" in cands            # 兵(0,6)进(0,5)
    assert "1927" in cands            # 马(1,9)跳(2,7)
    assert all(len(c) == 4 for c in cands)


def test_horse_leg_blocked():
    b = xq.initial_board()
    # 马 (1,9) 蹩腿:上方 (1,8) 为空?开局 (1,8) 为空,马可跳 (2,7)/(0,7)
    assert (2, 7) in xq.pseudo_moves(b, 1, 9)
    # 挡住马腿
    b[8][1] = "P"
    assert (2, 7) not in xq.pseudo_moves(b, 1, 9)


def test_cannon_screen_capture():
    b = xq.initial_board()
    # 红炮 (1,7) 打黑卒 (1,3):中间 (1,6)(1,5)(1,4) 全空,是合法吃子
    assert (1, 3) in xq.pseudo_moves(b, 1, 7)
    # 中间垫一子后不能直接吃
    b[6][1] = "A"
    assert (1, 3) not in xq.pseudo_moves(b, 1, 7)


def test_apply_and_turn():
    g2 = XiangqiGame()
    g2.apply(xq.RED, "0605")             # 兵(0,6)进(0,5)
    assert g2.to_move == xq.BLACK
    assert g2.history[-1] == ("0605", xq.RED)


def test_illegal_move_rejected():
    g = XiangqiGame()
    with pytest.raises(IllegalMove):
        g.apply(xq.RED, "9999")          # 格式合法但起点无子/不合法
    with pytest.raises(IllegalMove):
        g.apply(xq.RED, "0010")          # 黑车不属于红方


def test_in_check_and_facing():
    # 红车(4,5)沿中路直指黑将(4,0),中间无子 -> 黑被将军
    b = xq.initial_board()
    for y in range(10):
        for x in range(9):
            b[y][x] = ""
    b[0][4] = "k"
    b[5][4] = "R"
    b[9][3] = "K"
    assert xq.is_in_check(b, xq.BLACK)
    assert not xq.is_in_check(b, xq.RED)
    # 垫一个子后不再被将军
    b[3][4] = "a"
    assert not xq.is_in_check(b, xq.BLACK)
    # 将帅照面
    b2 = xq.initial_board()
    for y in range(10):
        for x in range(9):
            b2[y][x] = ""
    b2[0][4] = "k"
    b2[9][4] = "K"
    assert xq.kings_facing(b2)


def test_checkmate_detection():
    # 黑将(4,0)被三只红车封死全部去路:R(0,0) 封 (3,0),R(8,0) 封 (5,0),
    # R(4,9) 沿中路封 (4,1) 并将军;红帅放 (3,9) 避免照面
    g = XiangqiGame()
    g.board = [
        ["R", "", "", "", "k", "", "", "", "R"],
        ["", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", ""],
        ["", "", "", "", "", "", "", "", ""],
        ["", "", "", "K", "R", "", "", "", ""],
    ]
    g.history = [("9999", "red")]       # 让黑方行棋
    g.check_status()
    assert g.status == "checkmate"
    assert g.winner == xq.RED
    assert g.result == "红方胜"


def test_repetition_draw():
    g = XiangqiGame()
    g.board = [
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
    # 人工注入重复局面
    g.history_map = {g.fingerprint(): 3}
    g.check_status()
    assert g.status == "draw" and "重复" in g.reason


def test_max_moves_draw():
    g = XiangqiGame(max_moves=0)
    g.check_status()
    assert g.status == "draw"


def test_snapshot():
    g = XiangqiGame()
    snap = g.snapshot()
    assert snap["game"] == "xiangqi"
    assert snap["to_move"] == "red"
    assert len(snap["board"]) == 10 and len(snap["board"][0]) == 9
