# llm-board-arena

LLM 棋类竞技场:让 GLM / DeepSeek 等 OpenAI 兼容大模型对弈围棋与中国象棋,
裁判持有规则权,带实时观战(WebSocket)、逐帧回放与战绩榜。Python ≥3.9。

## 常用命令

```bash
pip install -e ".[dev]"        # 安装(开发)
pytest tests -q                # 全部测试(随机/脚本棋手,不花 API 费)
board-arena serve              # 网页竞技场 http://127.0.0.1:8866
board-arena run go --size 9 --black glm --white deepseek --board   # CLI 对局
board-arena stats              # 战绩榜
python scripts/smoke_test.py   # 端到端冒烟(起服务+WS 跑一局随机象棋)
python scripts/llm_match.py --env .env --game xiangqi --max-moves 60  # 真实对局
```

API key 放根目录 `.env`(见 `.env.example`):`GLM_API_KEY` / `DEEPSEEK_API_KEY`。

## 核心文件

- `src/board_arena/core/base.py` — `BoardGame` 抽象接口,**加新棋种只实现这个**
- `src/board_arena/core/go_game.py` — 围棋引擎 + SGF + 死子协商(finalize 钩子)
- `src/board_arena/core/xiangqi.py` — 象棋引擎(候选着法制)
- `src/board_arena/referee.py` — 裁判循环:事件流、非法着反馈重试、代抽、认输
- `src/board_arena/players.py` — LLMPlayer(OpenAI 兼容)/Random/Scripted + 引擎注册表
- `src/board_arena/records.py` — 档案(JSON/SGF)读写 + 战绩聚合
- `src/board_arena/server.py` — FastAPI `create_app()` 工厂 + WS + REST
- `src/board_arena/web/index.html` — 单页前端,无构建步骤,原生 JS
- `HANDOFF.md` — 完整交接文档(进度/决策/坑/下一步),做改动前先读

## 代码规范

- 中文注释与 docstring;面向用户的文案(日志/提示词/异常原因)全部中文
- 每个模块顶部 `from __future__ import annotations`
- 引擎(`core/`)不依赖 players/server,可独立 import 使用
- 测试不得调用真实 API:用 `RandomPlayer` / `ScriptedPlayer`
- 服务端测试起真实 uvicorn 线程(本机 starlette TestClient 不可用)

## 已知注意事项

- **FastAPI 端点参数注解会被求值**:3.9 上必须写 `Optional[str]`,不能写
  `str | None`(future import 不作用于路由签名)——CI 的 3.9 会抓住
- `create_app()` 是工厂,记得 `return app`
- 象棋开局合法着法是 44 种(引擎验证过,不是 35/42)
- WS 事件顺序:start → thinking/move/raw/illegal/log… → end → saved
- 同一服务同时只允许一局进行中;档案 ID 含微秒防同秒覆盖
- 仓库公开:不得提交 .env、对局档案里的本机路径或 key
