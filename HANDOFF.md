# HANDOFF — LLM 棋类竞技场交接文档

> 更新时间:2026-09-03 ｜ 状态:v0.1.0 已发布(https://github.com/sdkdsd/llm-board-arena,CI 全绿)

## 1. 项目目标与当前进度

**目标**:让大模型(GLM / DeepSeek / 任意 OpenAI 兼容端点)对弈围棋和中国象棋。
裁判程序持有全部规则权,LLM 只负责"选点";对局全程留档,支持实时观战、
逐帧回放与跨局战绩榜。合并并重构自两个原型:`ai-go-battle`(围棋)与
`chess_arena`(象棋)。

### 进度
- ✅ 统一 `BoardGame` 接口 + 围棋引擎(禁自杀/全局同形/数子法/死子双方确认)
- ✅ 象棋引擎(蹩马腿/塞象眼/炮翻山/九宫/照面/三重复判和/将死困毙)
- ✅ 玩家层:LLMPlayer(OpenAI 兼容,含 deepseek-reasoner reasoning_content 回退)、
  RandomPlayer、ScriptedPlayer(测试用,零 API 费)
- ✅ 裁判:非法着带原因反馈重试 4 次 → 代抽合法着并标记;原始输出留档
- ✅ 对局档案 JSON(围棋另存 SGF,Sabaki 可开);战绩榜实时聚合(胜2和1)
- ✅ FastAPI 服务:WS 实时观战 + REST(档案/逐帧回放/战绩榜)+ 单页前端
- ✅ CLI:`board-arena run | serve | stats`
- ✅ 26 个测试 + 真实 uvicorn 冒烟,CI 覆盖 Python 3.9/3.12/3.13 全绿
- ✅ **首战已打**:GLM(glm-4-flash) vs DeepSeek(deepseek-chat) 象棋 60 手,
  和棋,代抽 0 手,2 次非法着反馈后自行修正
- ⏳ 未开始:网页人类对战(原型 chess_arena 有、合并时未移植)、多房间并发对局、
  Elo 评级、五子棋/国际象棋等新棋种、PyPI 发布

## 2. 架构设计与关键技术决策

- **两种着法风格,一个接口**:围棋是开放式(坐标/pass/resign,模型自由发挥);
  象棋是候选制(裁判把全部合法着法列出来,模型只许从中选)。
  `BoardGame.candidates()` 返回 None 即开放式——提示词生成和网页渲染都靠
  这一个抽象,新棋种实现十来个方法即可接入全部基础设施。
- **单轮提示词,零对话历史**:每回合只发"棋盘 ASCII + 最近 12 手 + 非法反馈",
  要求只输出 `{"move":...,"reason":...}`。从根上避免对话拼接幻觉和死循环
  (chess_arena 原型验证过的方案)。
- **规则权归裁判**:模型给的理由原样留档(哪怕胡说八道,如"兵推进将军"),
  但落子合法性由引擎判定;非法着带中文原因反馈重试,4 次失败代抽并标记
  `note`,档案可审计。
- **服务端逐帧回放**:`/api/games/{id}/frames` 用引擎重放整局生成快照序列,
  前端不用实现提子等规则,只管画。
- **档案即数据库**:战绩榜每次从 `games/*/ *.json` 实时聚合,无独立状态、
  无迁移问题。档案 ID 含微秒(同一秒保存两局曾互相覆盖)。
- **并发模型**:WS 一局一线程,事件经 `loop.call_soon_threadsafe` 回传
  asyncio;同服务同时只允许一局(`state["thread"]` 单槽)。

## 3. 核心文件清单

```
src/board_arena/
├── core/base.py      # BoardGame 抽象接口(解析/校验/落子/提示词/快照)
├── core/go_game.py   # 围棋引擎 + SGF + 死子协商(finalize 钩子)
├── core/xiangqi.py   # 象棋引擎(合法着生成/将军判定/状态机)
├── players.py        # LLMPlayer/RandomPlayer/ScriptedPlayer + 引擎注册表
├── referee.py        # 裁判循环:事件流/重试/代抽/认输处理
├── records.py        # 档案读写 + compute_stats 战绩聚合
├── server.py         # FastAPI:create_app() 工厂 + WS + REST + frames
├── cli.py            # board-arena run/serve/stats
└── web/index.html    # 单页前端(观战/回放/战绩榜,canvas 双棋盘)
tests/                # 26 测试;test_server 用真实 uvicorn(线程内)
scripts/smoke_test.py # 端到端冒烟(随机对局,不花钱)
scripts/llm_match.py  # 真实 LLM 对局示例(限手数控成本)
```

## 4. 未完成 TODO 与已知的坑

### TODO
- [ ] 网页人类对战(WS 下行 move 队列,原型有实现可抄)
- [ ] 多房间并发(现在全局单局)
- [ ] Elo 或贝叶斯评级替代简单积分
- [ ] 新棋种:五子棋最简单(改 candidates 即可);国际象棋工作量大
- [ ] README 英文化分离、PyPI 发布、演示部署

### 坑(都已修过,别再踩)
- **FastAPI 端点参数注解会被真正求值**:3.9 上 `str | None` 直接炸
  (`from __future__ import annotations` 救不了路由),端点签名必须用
  `Optional[str]`。新增端点时注意。
- 本机 starlette 的 TestClient 坏的(要 httpx2,ASGI2 报 NoneType)——
  API 测试起真实 uvicorn 线程。
- 象棋开局合法着法是 **44** 种(引擎验证过,别"改对"成别的数)。
- 围棋数子:双方共同边界的空点(公气)不计分。
- `create_app()` 工厂忘 `return app` → 请求时才报 "NoneType is not callable"。
- WS 客户端要等 `saved` 事件(在 `end` 之后)再拉档案列表。
- 认输在 `_ask_move` 里调 `game.resign()`,裁判主循环对 move=="resign"
  单独发事件、不调 apply。

## 5. 下一步建议

1. 网页加人类对战(从原 chess_arena 的 human_move_q 方案移植,量不大)
2. 跑一批正式对局攒战绩榜数据(围棋 9 路 + 象棋各若干场,glm-4-flash 免费)
3. 五子棋作为第三个棋种验证 BoardGame 接口的扩展性
4. 有传播诉求时:加 Elo + 对局分享链接 + GitHub Pages 前端演示
