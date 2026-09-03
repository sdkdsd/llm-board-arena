# LLM 棋类竞技场 (llm-board-arena)

[![CI](https://github.com/sdkdsd/llm-board-arena/actions/workflows/ci.yml/badge.svg)](https://github.com/sdkdsd/llm-board-arena/actions/workflows/ci.yml)

让大模型对弈**围棋**和**中国象棋**,带实时观战网页、逐帧复盘回放和跨局战绩榜。
支持智谱 GLM、DeepSeek 以及任何 OpenAI 兼容接口的模型。

本项目合并并重构自两个独立原型:`ai-go-battle`(GLM vs DeepSeek 围棋对弈)与
`chess_arena`(中国象棋 LLM 对战演示),统一成一个可扩展的竞技场框架。

## 特性

- **严格规则引擎**——围棋实现国际通行规则(禁自杀、全局同形禁止/打劫、数子法
  区域计分、终局死子双方确认),象棋完整实现蹩马腿/塞象眼/炮翻山/九宫/将帅
  照面/三次重复判和等。
- **公平的裁判机制**——每手棋的模型原始输出全部留档;非法着法带原因反馈重试,
  连续失败由裁判代抽合法着并标记;LLM 只负责"选点",规则判定权在裁判。
- **实时观战**——FastAPI + WebSocket 直播每一手,Canvas 渲染双棋盘,
  模型思考时实时显示。
- **复盘回放**——每局存 JSON 档案(围棋另存 SGF,可用 Sabaki 等打开),
  服务端逐帧重建局面,网页上滑动回放。
- **战绩榜**——按棋手聚合胜/负/和与积分(胜 2 分和 1 分),跨棋种统计。
- **测试友好**——随机棋手与脚本棋手不花一分钱 API 费用,26 个测试覆盖
  引擎、裁判、档案与服务端全链路。

## 快速开始

```bash
pip install -e .
copy .env.example .env      # 填入 GLM_API_KEY / DEEPSEEK_API_KEY
board-arena serve           # 打开 http://127.0.0.1:8866
```

网页里选棋种(围棋 19/9 路、象棋)、为双方挑引擎,点击开始即可观战;
对局结束后切到「复盘」回放、「战绩榜」看积分。

命令行党:

```bash
board-arena run go --size 9 --black glm --white deepseek --board
board-arena run xiangqi --red deepseek --black glm
board-arena stats
```

不想花 API 费用可以 `--black random --white random` 跑随机对局调试。

## 架构

```
src/board_arena/
├── core/            # 棋类抽象 + 规则引擎
│   ├── base.py      #   BoardGame 统一接口(解析/校验/落子/提示词/快照)
│   ├── go_game.py   #   围棋引擎 + SGF + 死子协商
│   └── xiangqi.py   #   象棋引擎 + 合法着生成
├── players.py       # LLMPlayer(OpenAI 兼容)/ RandomPlayer / ScriptedPlayer
├── referee.py       # 裁判循环:事件流 + 非法着反馈重试 + 代抽
├── records.py       # 对局档案(JSON/SGF)+ 战绩榜聚合
├── server.py        # FastAPI:WS 观战 + REST(档案/回放帧/战绩榜)
└── cli.py           # board-arena run / serve / stats
web/index.html       # 单页前端(观战/回放/战绩榜)
```

新增棋种只需实现 `BoardGame` 的十来个方法(解析 LLM 输出、合法性校验、落子、
提示词、快照),裁判/档案/网页自动获得回放与观战能力。

## 设计说明

- **单轮提示词,零对话历史**:每回合只把棋盘 ASCII + 最近着手 + 非法反馈发给
  模型,要求只输出 `{"move": ..., "reason": ...}`。从根上避免对话拼接导致的
  幻觉与死循环。
- **两种着法风格**:围棋为开放式(坐标/pass/认输,模型自由发挥);象棋为候选制
  (裁判把全部合法着法列给模型,只允许从中选择)。两种风格由同一个接口抽象。
- **对局档案可审计**:每手棋记录原始理由、吃子数、裁判备注(代抽/非法反馈),
  战绩榜完全由档案实时聚合,无独立状态。

English summary: an arena framework where LLMs play Go and Xiangqi (Chinese
chess) under strict rule engines, with live WebSocket spectating, frame-by-frame
replay and a cross-game leaderboard. Works with GLM, DeepSeek and any
OpenAI-compatible endpoint. See the quick start above.

## License

MIT。
