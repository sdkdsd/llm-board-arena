"""REST API 测试:起真实 uvicorn(线程内),用 requests 打接口。"""
import socket
import threading
import time

import pytest
import requests

from board_arena import RandomPlayer, Referee, XiangqiGame, save_record


@pytest.fixture(scope="module")
def base_url(tmp_path_factory):
    import uvicorn

    from board_arena.server import create_app
    tmp_path = tmp_path_factory.mktemp("arena-data")
    for i in range(2):
        g = XiangqiGame(max_moves=8 + i)
        r = Referee(g, {"red": RandomPlayer(), "black": RandomPlayer()}).run()
        save_record(r, str(tmp_path))
    app = create_app(data_dir=str(tmp_path))

    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    deadline = time.time() + 15
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"


def test_index_page(base_url):
    r = requests.get(base_url + "/", timeout=10)
    assert r.status_code == 200
    assert "LLM 棋类竞技场" in r.text


def test_engines_api(base_url):
    engines = requests.get(base_url + "/api/engines", timeout=10).json()
    assert "glm" in engines and "deepseek" in engines
    assert set(engines["glm"]) >= {"label", "model", "available"}


def test_games_list_and_detail_and_frames(base_url):
    games = requests.get(base_url + "/api/games", timeout=10).json()
    assert len(games) == 2
    gid = games[0]["id"]
    detail = requests.get(f"{base_url}/api/games/{gid}", timeout=10).json()
    assert detail["game"] == "xiangqi"
    frames = requests.get(f"{base_url}/api/games/{gid}/frames", timeout=10).json()
    assert frames["game"] == "xiangqi"
    # 帧数 = 手数 + 1(含开局空盘)
    assert len(frames["frames"]) == len(detail["moves"]) + 1
    assert requests.get(f"{base_url}/api/games/nonexistent",
                        timeout=10).status_code == 404
    assert requests.get(f"{base_url}/api/games/none/frames",
                        timeout=10).status_code == 404


def test_stats_api(base_url):
    s = requests.get(base_url + "/api/stats", timeout=10).json()
    assert s["total_games"] == 2
    assert s["players"]
