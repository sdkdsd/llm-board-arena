"""端到端冒烟:起真实服务,用 WS 客户端跑一局随机对弈(不调 LLM API)。"""
import asyncio
import json
import shutil
import socket
import threading
import time

import requests
import uvicorn

from board_arena.server import create_app

DATA = r"C:\Users\18796\AppData\Local\Temp\board-arena-smoke"
shutil.rmtree(DATA, ignore_errors=True)


def main():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    app = create_app(data_dir=DATA)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                           log_level="error"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    base = f"http://127.0.0.1:{port}"
    print("index:", requests.get(base + "/", timeout=5).status_code)

    async def game():
        import websockets
        uri = f"ws://127.0.0.1:{port}/ws"
        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"type": "start", "game": "xiangqi",
                                      "options": {"max_moves": 12},
                                      "players": {"red": "random",
                                                  "black": "random"}}))
            result = None
            saved = None
            while saved is None:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=60))
                t = m.get("type")
                if t == "move":
                    print(f"  第{m['no']}手 {m['player']}({m['side_display']}) "
                          f"{m['move_display']}")
                elif t in ("log", "error"):
                    print(f"  [{t}] {m['text']}")
                    if t == "error":
                        raise SystemExit("server error")
                elif t == "end":
                    result = m["result"]
                    print("  终局:", result, "-", m.get("end_comment", ""))
                elif t == "saved":
                    saved = m["record"]["id"]
                    assert result is not None
            return saved

    rid = asyncio.run(game())
    games = requests.get(base + "/api/games", timeout=5).json()
    frames = requests.get(f"{base}/api/games/{rid}/frames", timeout=5).json()
    stats = requests.get(base + "/api/stats", timeout=5).json()
    print("档案数:", len(games), "| 帧数:", len(frames["frames"]),
          "| 战绩榜人数:", len(stats["players"]))
    assert len(games) == 1 and len(frames["frames"]) == 13
    print("SMOKE OK  (档案:", rid + ")")
    server.should_exit = True


if __name__ == "__main__":
    main()
