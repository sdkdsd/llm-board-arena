"""棋手客户端。

所有棋手实现统一接口 ``chat(system, user) -> str`` 与 ``spec``(PlayerSpec)。
- LLMPlayer: OpenAI 兼容接口(智谱 GLM / DeepSeek / 任意兼容端点)。
- RandomPlayer: 每回合随机挑一个合法候选(调试用,调用 game.candidates)。
- ScriptedPlayer: 按预设队列吐出原始回复文本(测试用)。
"""
from __future__ import annotations

import os
import random
import time

import requests

from .core.base import PlayerSpec


class APIError(Exception):
    pass


class LLMPlayer:
    """OpenAI 兼容 chat 接口客户端(同步 requests,带重试)。"""

    def __init__(self, name: str, engine: str, base_url: str, api_key: str,
                 model: str, temperature: float = 0.7, max_tokens: int = 200):
        self.name = name
        self.engine = engine
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.url = self.base_url + "/chat/completions"
        self.spec = PlayerSpec(name, engine, model)

    def chat(self, system: str, user: str, max_retries: int = 3,
             timeout: int = 180) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        last_err: Exception = APIError("未知错误")
        for i in range(max_retries):
            try:
                r = requests.post(self.url, headers=headers, json=payload,
                                  timeout=timeout)
                if r.status_code == 200:
                    msg = r.json()["choices"][0]["message"]
                    # deepseek-reasoner 的正文可能在 reasoning_content 里
                    content = msg.get("content") or msg.get("reasoning_content") or ""
                    if content.strip():
                        return content
                    last_err = APIError("模型返回空内容")
                else:
                    last_err = APIError(f"HTTP {r.status_code}: {r.text[:300]}")
            except requests.RequestException as e:
                last_err = e
            time.sleep(2 * (i + 1))
        raise last_err


class RandomPlayer:
    """随机棋手:从候选走法中随机挑一个(调试/基准用)。"""

    def __init__(self, name: str = "随机棋手", engine: str = "random"):
        self.name = name
        self.engine = engine
        self.spec = PlayerSpec(name, engine)
        self._game = None
        self._side = None

    def bind(self, game, side: str) -> None:
        """RandomPlayer 需要 game 才能知道候选集;由裁判在开局时注入。"""
        self._game = game
        self._side = side

    def chat(self, system: str, user: str) -> str:
        cands = self._game.candidates(self._side) if self._game else None
        if cands:
            move = random.choice(cands)
        else:
            move = self._game.random_legal_move(self._side) or "pass"
        return '{"move": "%s", "reason": "随机走子"}' % move


class ScriptedPlayer:
    """按队列吐出预设回复文本,吐完循环最后一个(测试用,不联网)。"""

    def __init__(self, name: str, engine: str, replies: list[str]):
        self.name = name
        self.engine = engine
        self.spec = PlayerSpec(name, engine)
        self.replies = list(replies)
        self.calls: list[tuple[str, str]] = []

    def chat(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if not self.replies:
            return '{"move": "pass", "reason": "无预设"}'
        idx = 0 if len(self.replies) == 1 else min(len(self.calls) - 1, len(self.replies) - 1)
        return self.replies[idx]


# ---------- 引擎注册表 ----------

DEFAULT_ENGINES = {
    "glm": {
        "label": "GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key_env": "GLM_API_KEY",
        "model_env": "GLM_MODEL",
        "default_model": "glm-4-flash",
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "model_env": "DEEPSEEK_MODEL",
        "default_model": "deepseek-chat",
    },
}


def load_env(path: str = ".env") -> None:
    """把键值对写入 os.environ(不覆盖已有值)。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def available_engines(env: dict | None = None) -> dict:
    """返回已配置 API Key 的引擎(env 未填 key 的引擎标记 available=False)。"""
    env = os.environ if env is None else env
    out = {}
    for key, cfg in DEFAULT_ENGINES.items():
        api_key = env.get(cfg["api_key_env"], "")
        out[key] = {
            "key": key,
            "label": cfg["label"],
            "model": env.get(cfg["model_env"], cfg["default_model"]),
            "base_url": cfg["base_url"],
            "available": bool(api_key),
        }
    return out


def make_player(engine_key: str, side: str, env: dict | None = None,
                temperature: float = 0.7) -> LLMPlayer:
    env = os.environ if env is None else env
    cfg = DEFAULT_ENGINES.get(engine_key)
    if cfg is None:
        raise ValueError(f"未知引擎: {engine_key}")
    api_key = env.get(cfg["api_key_env"], "")
    if not api_key:
        raise ValueError(f"引擎 {cfg['label']} 未配置 API Key(环境变量 {cfg['api_key_env']})")
    model = env.get(cfg["model_env"], cfg["default_model"])
    return LLMPlayer(cfg["label"], engine_key, cfg["base_url"], api_key,
                     model, temperature)
