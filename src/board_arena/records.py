"""对局档案与战绩榜。

每局结束写一个 JSON 档案到 ``<data_dir>/games/<game_id>/``;围棋另存 SGF。
战绩榜从档案实时聚合,无需单独维护数据库。
"""
from __future__ import annotations

import datetime
import json
import os

from .core.go_game import build_sgf, parse_coord


def games_dir(data_dir: str) -> str:
    return os.path.join(data_dir, "games")


def save_record(record: dict, data_dir: str) -> dict:
    """保存对局档案,补全 id/timestamp 并写盘(围棋另存 SGF)。返回补充后的 record。"""
    gid = record["game"]
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    slug = (record.get("winner") or "draw").replace(" ", "_")
    record["id"] = f"{stamp}_{slug}"
    record["saved_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    outdir = os.path.join(games_dir(data_dir), gid)
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, record["id"] + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=1)

    if gid == "go":
        black = record["players"].get("B", {})
        white = record["players"].get("W", {})
        size = _go_size(record)
        komi = _go_komi(record)
        sgf_entries = []
        for m in record["moves"]:
            action = "pass" if m["move"] in ("pass", "resign") else "move"
            coord = None
            if action == "move":
                coord = parse_coord(m["move"], size)
            sgf_entries.append({"side": m["side"], "action": action,
                                "coord": coord, "reason": m.get("reason", ""),
                                "note": m.get("note", "")})
        sgf = build_sgf(size, komi,
                        f"{black.get('name', '?')}({black.get('model', '')})",
                        f"{white.get('name', '?')}({white.get('model', '')})",
                        sgf_entries, record["result"], record.get("end_comment"))
        with open(os.path.join(outdir, record["id"] + ".sgf"), "w",
                  encoding="utf-8") as f:
            f.write(sgf)
        record["sgf"] = sgf
    return record


def _go_size(record: dict) -> int:
    return record.get("extra", {}).get("size", 19)


def _go_komi(record: dict) -> float:
    return record.get("extra", {}).get("komi", 6.5)


def load_records(data_dir: str, game_id: str | None = None) -> list[dict]:
    out = []
    root = games_dir(data_dir)
    if not os.path.isdir(root):
        return out
    for gid in sorted(os.listdir(root)):
        if game_id and gid != game_id:
            continue
        gdir = os.path.join(root, gid)
        for fn in sorted(os.listdir(gdir)):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(gdir, fn), encoding="utf-8") as f:
                    out.append(json.load(f))
            except (json.JSONDecodeError, OSError):
                continue
    out.sort(key=lambda r: r.get("saved_at", ""), reverse=True)
    return out


def load_record(data_dir: str, record_id: str) -> dict | None:
    for r in load_records(data_dir):
        if r["id"] == record_id:
            return r
    return None


def compute_stats(records: list[dict]) -> dict:
    """按引擎聚合战绩:胜/负/和、对局数、胜率,按积分排序。"""
    table: dict[str, dict] = {}

    def entry(name: str) -> dict:
        if name not in table:
            table[name] = {"player": name, "games": 0, "wins": 0,
                           "losses": 0, "draws": 0,
                           "by_game": {}}
        return table[name]

    for r in records:
        g = r["game"]
        for side_key, p in r.get("players", {}).items():
            name = p.get("name") or p.get("engine") or side_key
            e = entry(name)
            e["games"] += 1
            e["by_game"].setdefault(g, {"games": 0, "wins": 0, "losses": 0, "draws": 0})
            e["by_game"][g]["games"] += 1
            winner = r.get("winner_side")
            if winner is None:
                e["draws"] += 1
                e["by_game"][g]["draws"] += 1
            elif winner == side_key:
                e["wins"] += 1
                e["by_game"][g]["wins"] += 1
            else:
                e["losses"] += 1
                e["by_game"][g]["losses"] += 1
    rows = []
    for e in table.values():
        decided = e["wins"] + e["losses"]
        e["win_rate"] = round(e["wins"] / decided, 3) if decided else None
        e["points"] = e["wins"] * 2 + e["draws"]  # 胜2分和1分
        rows.append(e)
    rows.sort(key=lambda e: (-e["points"], -e["wins"], e["player"]))
    return {"updated": datetime.datetime.now().isoformat(timespec="seconds"),
            "total_games": len(records), "players": rows}
