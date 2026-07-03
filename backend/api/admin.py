"""
API 管理路由 — CRUD + 健康检查

存储: backend/api_configs.json
"""

import json
import os
import uuid
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
CONFIG_FILE = Path(__file__).resolve().parent.parent / "api_configs.json"
_lock = threading.Lock()


# ── 数据模型 ──
class ApiCreate(BaseModel):
    name: str
    url: str
    api_key: str = ""
    description: str = ""


# ── 持久化 ──
def _load() -> List[dict]:
    """线程安全加载配置"""
    with _lock:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, Exception):
                return []
        return _load_defaults()


def _save(configs: List[dict]):
    """线程安全保存配置"""
    with _lock:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(configs, ensure_ascii=False, indent=2), encoding="utf-8")


def _mask_key(key: str) -> str:
    """脱敏显示 API Key (仅显示最后4位)"""
    if not key:
        return ""
    return "****" + key[-4:] if len(key) >= 4 else "****"


def _load_defaults() -> List[dict]:
    """首次加载时返回预置 API 列表"""
    return [
        {
            "id": "football-data",
            "name": "Football-Data.org",
            "url": "https://api.football-data.org/v4/",
            "api_key": "2e0828890687497591a69119c6aed07d",
            "category": "football",
            "description": "官方足球数据 API，提供世界杯/联赛球队、积分榜、赛程",
            "status": "unknown",
            "last_checked": None,
        },
        {
            "id": "fifa-ranking",
            "name": "FIFA 官方排名",
            "url": "https://inside.fifa.com/fifa-world-ranking",
            "api_key": "",
            "category": "football",
            "description": "FIFA 官网男足国家队排名页面（网页抓取）",
            "status": "unknown",
            "last_checked": None,
        },
    ]


# ── 公共函数 (供其他模块调用) ──
def get_api_configs() -> List[dict]:
    return _load()


# ═══════════════════════════════════════
# API 路由
# ═══════════════════════════════════════

@router.get("/apis")
def list_apis():
    """获取已配置的 API 列表 (keys 脱敏)"""
    configs = _load()
    result = []
    for c in configs:
        result.append({
            **c,
            "api_key": _mask_key(c.get("api_key", "")),
        })
    return {"apis": result, "count": len(result)}


@router.post("/apis")
def create_api(api: ApiCreate):
    """添加新 API 配置"""
    configs = _load()

    # 去重检查
    for c in configs:
        if c.get("url", "").strip("/") == api.url.strip("/"):
            raise HTTPException(status_code=409, detail="该 API URL 已存在")

    new_id = api.name.lower().replace(" ", "-")[:30] + "-" + uuid.uuid4().hex[:6]
    new_api = {
        "id": new_id,
        "name": api.name,
        "url": api.url,
        "api_key": api.api_key,
        "category": "football",
        "description": api.description,
        "status": "unknown",
        "last_checked": None,
    }
    configs.append(new_api)
    _save(configs)
    return {**new_api, "api_key": _mask_key(api.api_key)}


@router.delete("/apis/{api_id}")
def delete_api(api_id: str):
    """删除 API 配置"""
    configs = _load()
    new_configs = [c for c in configs if c.get("id") != api_id]
    if len(new_configs) == len(configs):
        raise HTTPException(status_code=404, detail="API 不存在")
    _save(new_configs)
    return {"deleted": api_id}


@router.post("/apis/test/{api_id}")
def test_api(api_id: str):
    """测试 API 连接状态"""
    configs = _load()
    target = None
    for c in configs:
        if c.get("id") == api_id:
            target = c
            break

    if not target:
        raise HTTPException(status_code=404, detail="API 不存在")

    url = target["url"]
    api_key = target.get("api_key", "")
    headers = {}
    if api_key:
        headers["X-Auth-Token"] = api_key

    now = datetime.now().isoformat()
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        target["status"] = "online" if resp.status_code == 200 else "offline"
        target["last_checked"] = now
        result = {
            "status_code": resp.status_code,
            "api_id": api_id,
            "status": target["status"],
            "last_checked": now,
        }
    except requests.exceptions.Timeout:
        target["status"] = "offline"
        target["last_checked"] = now
        result = {"status_code": 0, "api_id": api_id, "status": "offline",
                  "last_checked": now, "error": "请求超时"}
    except Exception as e:
        target["status"] = "offline"
        target["last_checked"] = now
        result = {"status_code": 0, "api_id": api_id, "status": "offline",
                  "last_checked": now, "error": str(e)}

    _save(configs)
    return result
