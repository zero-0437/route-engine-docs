#!/usr/bin/env python3
"""
chain_config.py — 共享 YAML 配置加载模块

封装 route-map/ 目录的路径常量和 YAML 文件加载逻辑，
消除 route_engine.py 和 chain_executor.py 之间的重复代码。

使用方式：
    from chain_config import ROUTE_MAP_DIR, load_yaml_safe, load_chain
"""

import os

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


# ── 路径常量 ────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROUTE_MAP_DIR = os.path.join(SCRIPT_DIR, "..", "route-map")
INDEX_YAML_PATH = os.path.join(ROUTE_MAP_DIR, "index.yaml")
SKILL_CACHE_FILE = os.path.join(SCRIPT_DIR, "..", ".skill-cache.json")


# ── YAML 安全加载 ────────────────────────────────

def load_yaml_safe(path: str) -> dict | None:
    """安全加载 YAML 文件，文件不存在返回 None。"""
    if yaml is None:
        raise ImportError("缺少 PyYAML 库，请先安装 (pip install pyyaml)")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_index() -> dict | None:
    """加载 route-map/index.yaml。"""
    return load_yaml_safe(INDEX_YAML_PATH)


def load_chain(chain_ref: str) -> dict | None:
    """从 route-map/chains/ 目录加载指定 chain 文件。"""
    chain_path = os.path.join(ROUTE_MAP_DIR, "chains", f"{chain_ref}.yaml")
    return load_yaml_safe(chain_path)
