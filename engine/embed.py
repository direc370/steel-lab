# -*- coding: utf-8 -*-
"""embedding 后端：把文本转成稠密向量。

三种后端，按可用性自动选择：

1. **fastembed**（推荐，本地跑）：ONNX 推理，不需要 GPU，模型约 100 MB，
   首次使用会自动下载到本地缓存。中文用 BGE-small-zh-v1.5，512 维。
2. **api**：OpenAI 兼容的 `/embeddings` 接口。注意并非所有对话模型服务都提供
   embedding 端点，配置前先用 `tools/check_embed.py` 探一下。
3. **lsa**：纯标准库兜底（见 engine/vec.py），不需要任何模型，但只是词项空间的
   潜在语义近似，跨措辞召回能力有限。

统一接口：`encode(list[str]) -> list[list[float]]`、`.dim`、`.name`。
"""

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "data", "config.json")

DEFAULT_LOCAL_MODEL = "BAAI/bge-small-zh-v1.5"
LOCAL_FALLBACKS = [
    "BAAI/bge-small-zh-v1.5",
    "BAAI/bge-base-zh-v1.5",
    "intfloat/multilingual-e5-small",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
]


class EmbedError(RuntimeError):
    pass


class FastEmbedBackend:
    kind = "fastembed"

    def __init__(self, model_name=None, cache_dir=None):
        try:
            from fastembed import TextEmbedding
        except Exception as exc:  # 没装就是没装，交给上层降级
            raise EmbedError(f"fastembed 未安装：{exc}")
        self._model = None
        self._TextEmbedding = TextEmbedding
        names = []
        try:
            names = [m["model"] for m in TextEmbedding.list_supported_models()]
        except Exception:
            names = []
        cands = [model_name] if model_name else []
        cands += [m for m in LOCAL_FALLBACKS if m not in cands]
        last = None
        for name in cands:
            if not name:
                continue
            if names and name not in names:
                continue
            try:
                kwargs = {"model_name": name}
                if cache_dir:
                    kwargs["cache_dir"] = cache_dir
                self._model = TextEmbedding(**kwargs)
                self.name = name
                break
            except Exception as exc:
                last = exc
        if self._model is None:
            raise EmbedError(f"没有可用的本地 embedding 模型（{last or '模型列表为空'}）")
        self.kind = "fastembed"
        self._dim = None

    @property
    def dim(self):
        if self._dim is None:
            self._dim = len(self.encode(["测试"])[0])
        return self._dim

    def encode(self, texts):
        texts = [t if t else " " for t in texts]
        return [list(map(float, v)) for v in self._model.embed(texts)]


class ApiEmbeddingBackend:
    kind = "api"

    def __init__(self, base_url, api_key, model, timeout=30):
        if not base_url or not api_key or not model:
            raise EmbedError("api 后端需要 base_url / api_key / model")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.name = model
        self.timeout = timeout
        self._dim = None

    @property
    def dim(self):
        if self._dim is None:
            self._dim = len(self.encode(["测试"])[0])
        return self._dim

    def encode(self, texts):
        import urllib.error
        import urllib.request
        payload = json.dumps({"model": self.name,
                              "input": [t if t else " " for t in texts]}).encode()
        req = urllib.request.Request(
            self.base_url + "/embeddings", data=payload,
            headers={"Content-Type": "application/json",
                     "Authorization": "Bearer " + self.api_key})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", "replace")[:200]
            raise EmbedError(f"embedding 接口返回 {exc.code}：{body}")
        except Exception as exc:
            raise EmbedError(f"embedding 接口不可用：{exc}")
        items = data.get("data") or []
        if not items:
            raise EmbedError("embedding 接口返回空结果")
        items.sort(key=lambda d: d.get("index", 0))
        return [list(map(float, d["embedding"])) for d in items]


def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def get_backend(prefer=None, config=None):
    """按 prefer → 配置文件 → auto 的顺序挑一个能用的后端，全不可用返回 None。"""
    cfg = config if config is not None else load_config()
    order = [prefer] if prefer else []
    configured = (cfg.get("embed_backend") or "").strip()
    if configured and configured not in order:
        order.append(configured)
    order += ["fastembed", "api"]

    for kind in order:
        if not kind:
            continue
        if kind == "fastembed":
            try:
                return FastEmbedBackend(cfg.get("embed_model"),
                                        cache_dir=cfg.get("embed_cache_dir"))
            except EmbedError:
                continue
        if kind == "api":
            base = os.environ.get("STEEL_LAB_EMBED_BASE_URL") or cfg.get("embed_base_url")
            key = os.environ.get("STEEL_LAB_EMBED_API_KEY") or cfg.get("embed_api_key")
            model = os.environ.get("STEEL_LAB_EMBED_MODEL") or cfg.get("embed_model_api")
            if base and key and model:
                try:
                    return ApiEmbeddingBackend(base, key, model)
                except EmbedError:
                    continue
    return None


def status():
    """给前端/排查用：当前能拿到哪些后端。"""
    out = {"local": False, "local_models": [], "api_configured": False}
    try:
        from fastembed import TextEmbedding
        out["local"] = True
        try:
            names = [m["model"] for m in TextEmbedding.list_supported_models()]
            out["local_models"] = [n for n in names
                                   if "zh" in n.lower() or "multilingual" in n.lower()][:8]
        except Exception:
            pass
    except Exception:
        pass
    cfg = load_config()
    out["api_configured"] = bool(cfg.get("embed_base_url") and cfg.get("embed_api_key"))
    return out
