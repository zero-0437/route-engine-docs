#!/usr/bin/env python3
"""route_logger.py — 路由日志记录模块

提供日志轮转和 JSON Lines 格式的日志写入功能，
从 route_engine.py 剥离以降低主模块复杂度。
"""

import datetime
import json
import os
import sys as _sys

_SCRIPTS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "scripts"))
if _SCRIPTS_DIR not in _sys.path:
    _sys.path.insert(0, _SCRIPTS_DIR)
del _SCRIPTS_DIR, _sys
from chain_config import SCRIPT_DIR

# ── 日志常量 ──
LOG_FILE = os.path.join(SCRIPT_DIR, "..", "logs", "route-engine.jsonl")
LOG_MAX_BYTES = 10 * 1024 * 1024   # 10 MB
LOG_BACKUP_COUNT = 5
LOW_CONFIDENCE_THRESHOLD = 0.6     # flagged 阈值


def _rotate_log() -> None:
    """按文件大小轮转日志，保留 LOG_BACKUP_COUNT 份备份。"""
    try:
        size = os.path.getsize(LOG_FILE)
    except OSError:
        return  # 文件不存在，无需轮转
    if size < LOG_MAX_BYTES:
        return
    # 移除最旧的备份（如 .5 → 删除），然后依次重命名
    last = f"{LOG_FILE}.{LOG_BACKUP_COUNT}"
    if os.path.exists(last):
        os.remove(last)
    for i in range(LOG_BACKUP_COUNT - 1, 0, -1):
        src = f"{LOG_FILE}.{i}"
        dst = f"{LOG_FILE}.{i + 1}"
        if os.path.exists(src):
            os.rename(src, dst)
    os.rename(LOG_FILE, f"{LOG_FILE}.1")


def log_route(route_result: dict, user_input: str) -> None:
    """记录路由日志，JSON Lines 格式，追加写入（自动轮转）

    Args:
        route_result: route() 返回的完整路由结果字典
        user_input: 原始用户输入文本
    """
    confidence = route_result.get("confidence", 0)
    method = route_result.get("method", "unknown")

    flagged = False
    flag_reason = None
    if method == "llm_fallback":
        flagged = True
        flag_reason = "low_confidence"
    elif method == "auto_tiebreak":
        flagged = True
        flag_reason = "tiebreak"
    elif method == "auto" and confidence < LOW_CONFIDENCE_THRESHOLD:
        flagged = True
        flag_reason = "borderline"

    entry = {
        "ts": datetime.datetime.now(
            datetime.timezone(datetime.timedelta(hours=8))
        ).isoformat(),
        "input": user_input[:200],
        "agent": route_result.get("agent", ""),
        "confidence": confidence,
        "method": method,
        "matched": route_result.get("details", {}).get("matched_rules", []),
        "flagged": flagged,
        "flag_reason": flag_reason,
    }

    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    _rotate_log()
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
