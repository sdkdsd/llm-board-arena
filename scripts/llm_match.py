"""跑一场真实 LLM 对局的命令行示例(成本可控)。

用法:
    python scripts/llm_match.py --env path/to/.env \
        --game xiangqi --red glm --black deepseek --max-moves 60

围棋请用 --game go --max-moves 60 --komi 6.5(9 路加 --size 9 更省钱)。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src"))

from board_arena import (GoGame, RandomPlayer, Referee, XiangqiGame,
                         load_env, make_player, save_record)


def main():
    ap = argparse.ArgumentParser(description="LLM 对局示例")
    ap.add_argument("--env", default=".env", help="API key 所在的 env 文件")
    ap.add_argument("--game", choices=["go", "xiangqi"], default="xiangqi")
    ap.add_argument("--red", default="glm", help="象棋红方/围棋黑方引擎")
    ap.add_argument("--black", default="deepseek", help="象棋黑方引擎")
    ap.add_argument("--white", default=None, help="围棋白方引擎(默认同 --black)")
    ap.add_argument("--size", type=int, default=9, help="围棋路数")
    ap.add_argument("--komi", type=float, default=6.5)
    ap.add_argument("--max-moves", type=int, default=60, help="手数上限(控制成本)")
    ap.add_argument("--data-dir",
                    default=os.path.join(os.path.expanduser("~"), ".board-arena"))
    args = ap.parse_args()

    load_env(args.env)
    if args.game == "go":
        game = GoGame(size=args.size, komi=args.komi, max_moves=args.max_moves)
        players = {"B": make_player(args.red, "B"),
                   "W": make_player(args.black, "W")}
    else:
        game = XiangqiGame(max_moves=args.max_moves)
        players = {"red": make_player(args.red, "red"),
                   "black": make_player(args.black, "black")}

    print(f"对局开始:{game.display_name}  "
          f"{' vs '.join(p.spec.label() for p in players.values())}"
          f"(上限 {args.max_moves} 手)\n")

    shown = {"n": 0}

    def on_event(ev):
        if ev["type"] == "move" and shown["n"] < 10:
            shown["n"] += 1
            print(f"  第{ev['no']}手 {ev['player']}({ev['side_display']}) "
                  f"{ev['move_display']}"
                  + (f" — {ev['reason'][:60]}" if ev.get("reason") else ""))
        elif ev["type"] == "move":
            shown["n"] += 1
            if shown["n"] % 10 == 0:
                print(f"  …已进行 {ev['no']} 手")
        elif ev["type"] == "illegal":
            print(f"  [非法] {ev.get('move') or '(无法解析)'}:{ev['why']}")
        elif ev["type"] == "log":
            print(f"  [裁判] {ev['text']}")
        elif ev["type"] == "end":
            print(f"\n终局:{ev['result']}"
                  + (f" — {ev['end_comment']}" if ev.get("end_comment") else ""))

    record = Referee(game, players).run(on_event)
    record = save_record(record, args.data_dir)
    moves = record["moves"]
    illegal_notes = sum(1 for m in moves if "代抽" in (m.get("note") or ""))
    print(f"总手数:{record['move_count']}  裁判代抽:{illegal_notes} 手")
    print(f"胜者:{record['winner'] or '和棋/无'}")
    print(f"档案:{args.data_dir}/games/{record['game']}/{record['id']}.json")
    if record["game"] == "go":
        print(f"SGF:{args.data_dir}/games/go/{record['id']}.sgf")


if __name__ == "__main__":
    main()
