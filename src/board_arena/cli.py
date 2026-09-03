"""命令行入口。

    board-arena run go --size 9 --black glm --white deepseek
    board-arena run xiangqi --red deepseek --black glm
    board-arena serve --port 8866
"""
from __future__ import annotations

import argparse
import sys

from .core import GAMES, create_game
from .players import RandomPlayer, available_engines, load_env, make_player
from .records import compute_stats, load_records, save_record
from .referee import Referee


def _print_event(ev: dict) -> None:
    t = ev["type"]
    if t == "move":
        cap = f",吃{ev['captured']}子" if ev.get("captured") else ""
        note = f"  [{ev['note']}]" if ev.get("note") else ""
        reason = f"  理由:{ev['reason']}" if ev.get("reason") else ""
        print(f"第{ev['no']}手 {ev['player']}({ev['side_display']}) "
              f"{ev['move_display']}{cap}{reason}{note}")
    elif t == "log":
        print(ev["text"])
    elif t == "illegal":
        mv = ev.get("move") or "(无法解析)"
        print(f"    非法着法 {mv}:{ev['why']} (第{ev['attempt']}次)")
    elif t == "end":
        print(f"\n终局:{ev['result']}"
              + (f" — {ev['end_comment']}" if ev.get("end_comment") else ""))
        if ev.get("reason"):
            print(ev["reason"])


def cmd_run(args: argparse.Namespace) -> int:
    load_env()
    game = create_game(args.game, size=args.size, komi=args.komi) \
        if args.game == "go" else create_game(args.game)

    players = {}
    for side_key, engine_key in (("B", args.black), ("W", args.white)) \
            if args.game == "go" else (("red", args.red), ("black", args.black)):
        if engine_key == "random":
            players[side_key] = RandomPlayer()
        else:
            players[side_key] = make_player(engine_key, side_key,
                                            temperature=args.temperature)
    names = " vs ".join(f"{p.spec.name}" for p in players.values())
    print(f"对局开始:{game.display_name} {names}\n")
    if args.board:
        print(game.ascii())

    ref = Referee(game, players, log_raw=False)
    record = ref.run(_print_event)
    record = save_record(record, args.data_dir)
    if record["game"] == "go" and args.board:
        print("\n终局盘面:\n" + game.ascii())
    print(f"对局档案:{args.data_dir}/games/{record['game']}/{record['id']}.json")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .server import create_app
    load_env()
    app = create_app(data_dir=args.data_dir)
    avail = [k for k, v in available_engines().items() if v["available"]]
    print(f"LLM 棋类竞技场:http://127.0.0.1:{args.port}"
          f"(已配置引擎:{', '.join(avail) or '无——请先填 .env'})")
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    stats = compute_stats(load_records(args.data_dir))
    print(f"共 {stats['total_games']} 局\n")
    header = f"{'棋手':<14}{'局':>4}{'胜':>4}{'负':>4}{'和':>4}{'积分':>6}{'胜率':>8}"
    print(header)
    for e in stats["players"]:
        rate = f"{e['win_rate']:.0%}" if e["win_rate"] is not None else "-"
        print(f"{e['player']:<14}{e['games']:>4}{e['wins']:>4}{e['losses']:>4}"
              f"{e['draws']:>4}{e['points']:>6}{rate:>8}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="board-arena",
                                 description="LLM 棋类竞技场:大模型对弈围棋/中国象棋")
    ap.add_argument("--data-dir", default=None, help="对局档案目录(默认 ~/.board-arena)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="跑一局对弈(终端直播)")
    run.add_argument("game", choices=list(GAMES), help="棋种")
    run.add_argument("--black", default="glm", help="围棋黑方/象棋黑方引擎")
    run.add_argument("--white", default="deepseek", help="围棋白方引擎")
    run.add_argument("--red", default="deepseek", help="象棋红方引擎")
    run.add_argument("--size", type=int, default=19, help="围棋路数(调试可用9)")
    run.add_argument("--komi", type=float, default=6.5, help="围棋贴目")
    run.add_argument("--temperature", type=float, default=0.7)
    run.add_argument("--board", action="store_true", help="打印棋盘")
    run.set_defaults(func=cmd_run)

    serve = sub.add_parser("serve", help="启动网页竞技场")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8866)
    serve.set_defaults(func=cmd_serve)

    st = sub.add_parser("stats", help="查看战绩榜")
    st.set_defaults(func=cmd_stats)

    args = ap.parse_args(argv)
    if args.data_dir is None:
        import os
        args.data_dir = os.path.join(os.path.expanduser("~"), ".board-arena")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
