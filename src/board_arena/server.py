"""FastAPI 服务:实时观战(WebSocket)+ 对局档案/战绩榜(REST)+ 单页前端。

同时只允许一局进行中的对弈;再开局会返回错误。
"""
from __future__ import annotations

import os
import threading
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .core import create_game
from .players import available_engines, load_env, make_player
from .records import compute_stats, load_record, load_records, save_record
from .referee import Referee

WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
DEFAULT_DATA_DIR = os.path.join(os.path.expanduser("~"), ".board-arena")


def create_app(data_dir: str = DEFAULT_DATA_DIR,
               env_file: str | None = None) -> FastAPI:
    if env_file:
        load_env(env_file)
    app = FastAPI(title="LLM 棋类竞技场")
    state = {"thread": None}

    # ---------- REST ----------

    @app.get("/")
    async def index():
        return FileResponse(os.path.join(WEB_DIR, "index.html"))

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/api/engines")
    async def engines():
        return available_engines()

    @app.get("/api/games")
    async def games(game: str | None = None, limit: int = 50):
        rs = load_records(data_dir, game)[:limit]
        for r in rs:
            r.pop("sgf", None)
        return rs

    @app.get("/api/games/{record_id}")
    async def game_detail(record_id: str):
        r = load_record(data_dir, record_id)
        if r is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        return r

    @app.get("/api/games/{record_id}/frames")
    async def game_frames(record_id: str):
        """逐帧重建整局快照,供网页回放(提子等规则由服务端引擎完成)。"""
        r = load_record(data_dir, record_id)
        if r is None:
            return JSONResponse({"error": "not found"}, status_code=404)
        frames: list[dict] = []
        if r["game"] == "go":
            from .core.go_game import GoBoard, parse_coord
            size = r.get("extra", {}).get("size", 19)
            komi = r.get("extra", {}).get("komi", 6.5)
            b = GoBoard(size, komi)
            sym = {"B": "X", "W": "O", None: "."}

            def snap():
                return {"game": "go", "size": size,
                        "grid": ["".join(sym[b.cells[y][x]] for x in range(size))
                                 for y in range(size)],
                        "captures": dict(b.captures), "komi": komi}
            frames.append(snap())
            for m in r["moves"]:
                if m["move"] not in ("pass", "resign"):
                    x, y = parse_coord(m["move"], size)
                    b.play(m["side"], x, y)
                frames.append(snap())
        else:
            from .core.xiangqi import initial_board
            board = initial_board()

            def snap():
                return {"game": "xiangqi", "board": [row[:] for row in board]}
            frames.append(snap())
            for m in r["moves"]:
                if len(m["move"]) == 4 and m["move"].isdigit():
                    x1, y1, x2, y2 = (int(c) for c in m["move"])
                    board[y2][x2] = board[y1][x1]
                    board[y1][x1] = ""
                frames.append(snap())
        return {"id": record_id, "game": r["game"], "frames": frames,
                "moves": r["moves"], "result": r["result"],
                "end_comment": r.get("end_comment", "")}

    @app.get("/api/stats")
    async def stats():
        return compute_stats(load_records(data_dir))

    # ---------- WebSocket 实时观战 ----------

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        await ws.accept()
        import asyncio
        loop = asyncio.get_running_loop()

        async def send(payload: dict):
            try:
                await ws.send_json(payload)
            except Exception:
                pass

        def run_game(cfg: dict):
            """在对局线程里跑裁判,把事件经事件循环转发给 WS 客户端。"""
            def submit(ev: dict):
                loop.call_soon_threadsafe(asyncio.create_task, send(ev))

            try:
                game = create_game(cfg["game"], **cfg.get("options", {}))
                players = {}
                for side, engine_key in cfg["players"].items():
                    if engine_key == "random":
                        from .players import RandomPlayer
                        players[side] = RandomPlayer()
                    else:
                        players[side] = make_player(engine_key, side)
                ref = Referee(game, players)
                record = ref.run(submit)
                record = save_record(record, data_dir)
                rec = dict(record)
                rec.pop("sgf", None)
                submit({"type": "saved", "record": rec})
            except Exception as e:  # noqa: BLE001
                submit({"type": "error", "text": str(e)})
            finally:
                state["thread"] = None

        try:
            while True:
                msg = await ws.receive_json()
                mtype = msg.get("type")
                if mtype == "start":
                    if state["thread"] is not None:
                        await send({"type": "error", "text": "已有一局在进行中,请等待结束或刷新页面。"})
                        continue
                    cfg = {
                        "game": msg.get("game", "go"),
                        "players": msg.get("players", {"B": "glm", "W": "deepseek"}),
                        "options": msg.get("options", {}),
                    }
                    await send({"type": "log", "text": f"对局准备中:{cfg['game']}"})
                    t = threading.Thread(target=run_game, args=(cfg,), daemon=True)
                    state["thread"] = t
                    t.start()
                elif mtype == "ping":
                    await send({"type": "pong"})
        except WebSocketDisconnect:
            pass
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    load_env()
    uvicorn.run(app, host="127.0.0.1", port=8866)
