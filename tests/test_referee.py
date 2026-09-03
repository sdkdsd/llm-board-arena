"""裁判 + 档案 + 战绩榜全链路(脚本/随机棋手,不联网)。"""
import json

from board_arena import (GoGame, RandomPlayer, Referee, ScriptedPlayer,
                         XiangqiGame, compute_stats, load_records, save_record)


def test_go_scripted_resign(tmp_path):
    g = GoGame(size=9)
    black = ScriptedPlayer("黑方脚本", "script",
                           ['{"move": "E5", "reason": "占角"}',
                            '{"move": "pass", "reason": "等待时机"}'])
    white = ScriptedPlayer("白方脚本", "script",
                           ['{"move": "D4", "reason": "挂角"}',
                            '{"move": "resign", "reason": "打不过"}'])
    events = []
    record = Referee(g, {"B": black, "W": white}).run(events.append)

    assert record["result"] == "B+R"
    assert record["winner"] == "黑方脚本"
    kinds = [e["type"] for e in events]
    assert kinds[0] == "start" and kinds[-1] == "end"
    assert "move" in kinds and "end" in kinds
    # 档案保存 + SGF
    saved = save_record(record, str(tmp_path))
    assert (tmp_path / "games" / "go" / f"{record['id']}.json").exists()
    assert (tmp_path / "games" / "go" / f"{record['id']}.sgf").exists()
    sgf = (tmp_path / "games" / "go" / f"{record['id']}.sgf").read_text(encoding="utf-8")
    assert "RE[B+R]" in sgf and ";B[ee]" in sgf   # E5 -> ee
    # B E5 / W D4 / B pass / W resign = 4 手
    assert json.load(open(tmp_path / "games" / "go" / f"{record['id']}.json",
                          encoding="utf-8"))["move_count"] == 4


def test_referee_illegal_feedback_and_forced(tmp_path):
    g = GoGame(size=9, max_moves=6)
    # 黑方:先给非法着(占已占点),再给合法着;之后循环 pass
    black = ScriptedPlayer("黑B", "script",
                           ['{"move": "E5"}',          # 第1手合法
                            '{"move": "E5"}',          # 重复占点 -> 非法反馈
                            '{"move": "E5"}', '{"move": "E5"}',
                            '{"move": "E5"}',          # 4次失败后代抽
                            '{"move": "pass"}'])
    white = ScriptedPlayer("白W", "script", ['{"move": "pass"}'])
    events = []
    record = Referee(g, {"B": black, "W": white}).run(events.append)
    illegal = [e for e in events if e["type"] == "illegal"]
    assert illegal, "应出现非法着法反馈事件"
    forced = [m for m in record["moves"] if "代抽" in (m.get("note") or "")]
    assert forced, "4次失败后裁判应代抽"
    assert record["move_count"] >= 4


def test_random_xiangqi_full_pipeline(tmp_path):
    g = XiangqiGame(max_moves=30)
    events = []
    record = Referee(g, {"red": RandomPlayer(), "black": RandomPlayer()}
                     ).run(events.append)
    assert record["game"] == "xiangqi"
    assert record["move_count"] <= 30
    assert record["result"] in ("红方胜", "黑方胜", "和棋")
    # 事件里的快照可直接渲染
    snaps = [e["snapshot"] for e in events if e["type"] == "move"]
    assert snaps and len(snaps[-1]["board"]) == 10
    save_record(record, str(tmp_path))
    assert load_records(str(tmp_path), "xiangqi")[0]["id"] == record["id"]


def test_stats_aggregation(tmp_path):
    g = XiangqiGame(max_moves=10)
    r1 = Referee(g, {"red": RandomPlayer(), "black": RandomPlayer()}).run()
    save_record(r1, str(tmp_path))
    g2 = GoGame(size=9, max_moves=10)
    r2 = Referee(g2, {"B": RandomPlayer(), "W": RandomPlayer()}).run()
    save_record(r2, str(tmp_path))

    stats = compute_stats(load_records(str(tmp_path)))
    assert stats["total_games"] == 2
    names = {e["player"] for e in stats["players"]}
    assert "随机棋手" in names
    top = stats["players"][0]
    # 随机棋手同时执两边的所有四手
    assert top["games"] == 4 and top["points"] >= 2
    assert set(top["by_game"]) == {"xiangqi", "go"}
