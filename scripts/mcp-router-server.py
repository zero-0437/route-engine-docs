#!/usr/bin/env python3
"""
Hermes Zero-Token Router — MCP Server
将路由引擎注册为 MCP Server，作为 Hermes 的前置路由层。
调用方式：route(text) → 返回路由结果 JSON
"""

import json
import sys
import os

# 将路由引擎加入路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from route_engine import route as engine_route, _clear_cache

# ── MCP Server: stdio 模式 ──────────────────────────────────────────

def handle_request(request: dict) -> dict:
    """处理 MCP 请求"""
    method = request.get("method", "")
    req_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "0.1.0",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "hermes-zero-token-router",
                    "version": "2.6.0"
                }
            }
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [
                    {
                        "name": "route",
                        "description": "将用户输入路由到目标 Agent。明确单意图任务自动路由，模糊/复合任务由主 Agent 兜底。",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "用户输入文本"
                                }
                            },
                            "required": ["text"]
                        }
                    },
                    {
                        "name": "route_with_details",
                        "description": "路由决策（带详细评分），用于调试和分析",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "description": "用户输入文本"
                                }
                            },
                            "required": ["text"]
                        }
                    },
                    {
                        "name": "clear_cache",
                        "description": "清空路由规则缓存（热重载），规则文件修改后调用",
                        "inputSchema": {
                            "type": "object",
                            "properties": {}
                        }
                    }
                ]
            }
        }

    elif method == "tools/call":
        tool_name = request.get("params", {}).get("name", "")
        arguments = request.get("params", {}).get("arguments", {})

        if tool_name == "route":
            text = arguments.get("text", "")
            result = engine_route(text)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({
                                "agent": result.get("agent"),
                                "confidence": result.get("confidence", 0),
                                "mode": result.get("mode", "auto"),
                                "method": result.get("method", ""),
                            }, ensure_ascii=False)
                        }
                    ]
                }
            }

        elif tool_name == "route_with_details":
            text = arguments.get("text", "")
            result = engine_route(text)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            }

        elif tool_name == "clear_cache":
            _clear_cache()
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({"status": "ok", "message": "路由规则缓存已清空"})
                        }
                    ]
                }
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
            }

    elif method == "notifications/initialized":
        return None  # 无响应

    else:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Unknown method: {method}"}
        }


def main():
    """MCP Server 主循环 — stdio 模式"""
    # 初始化时加载一次规则
    _clear_cache()

    # 标准输入/输出 JSON-RPC 循环
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError as e:
            error_resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {e}"}
            }
            sys.stdout.write(json.dumps(error_resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            error_resp = {
                "jsonrpc": "2.0",
                "id": request.get("id") if 'request' in dir() else None,
                "error": {"code": -32603, "message": f"Internal error: {e}"}
            }
            sys.stdout.write(json.dumps(error_resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
