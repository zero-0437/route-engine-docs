# Hermes 零 Token 路由引擎

> 纯 Python + YAML 驱动，替代 LLM 路由决策，**1ms / 0 token** 匹配。

## 概述

零 Token 路由引擎是 [Hermes Agent](https://hermes-agent.nousresearch.com) 的子 Agent 路由层。传统 Agent 系统依赖 LLM 本身来判断"把当前请求交给谁"——每次路由决策消耗数百到数千 token，且决策质量受模型温度和 prompt 影响大。本引擎将路由逻辑从 LLM 中剥离，用纯 YAML 规则 + Python 评分引擎替代。

**核心理念**：路由是确定性工程问题，不是 LLM 推理问题。

## 核心特性

| 特性 | 说明 |
|------|------|
| **零 Token 开销** | 路由决策不消耗任何 LLM token |
| **纯 YAML 配置** | route-map/ 目录即路由配置，所见即所得 |
| **多层评分** | keyword / phrase / regex / fuzzy 四种匹配类型 |
| **Chain 编排** | serial / parallel / interactive / loop 四种步骤 |
| **强绑定** | unrouted 模式直接返回，无 LLM 兜底 |
| **1ms 响应** | 冷启动 < 5ms，热缓存 < 1ms |
| **技能绑定** | 规则可绑定特定技能，路由时自动加载 |
| **事务保护** | 规则变更自动验证，失败自动回滚 |

## 快速开始

### 1. 安装依赖

```bash
pip install pyyaml>=6.0
```

### 2. 编写路由规则

创建 `route-map/index.yaml`：

```yaml
agents:
  programmer:
    condition: Coding 任务
    file: routes/programmer.yaml
    priority: 2
```

创建 `route-map/routes/programmer.yaml`：

```yaml
agent: programmer
priority: 2
rules:
  - type: phrase
    pattern: 写代码
    weight: 1.0
  - type: regex
    pattern: 实现.*功能
    weight: 0.8
```

### 3. 运行引擎

```python
from route_engine import decide

result = decide("帮我写一个 Python 脚本")
print(result["agent"])       # → programmer
print(result["confidence"])  # → 1.0
```

## 项目目录结构

```
.
├── README.md                 # 本文件
├── ARCHITECTURE.md           # 系统架构说明
├── ROUTE_MAP_SPEC.md         # route-map 目录规范
├── CHAIN_EXECUTOR.md         # chain 编排引擎文档
├── requirements.txt          # Python 依赖
├── scripts/
│   ├── route_engine.py       # 核心路由引擎
│   ├── chain_executor.py     # chain 状态机引擎
│   ├── validate-route-map.py # route-map 结构验证器（12 维审计）
│   ├── hermes-route-add      # 规则追加 CLI
│   ├── analyze-route-log.py  # 路由日志分析维护
│   └── agent-mgmt/           # Agent 管理工具集
│       ├── _yaml_ops.py
│       ├── _validation.py
│       ├── _transaction.py
│       ├── _binding_table.py
│       ├── _templates.py
│       ├── _skills_patch.py
│       └── templates/
│           ├── agent-route.yaml.j2
│           ├── agent-config.yaml.j2
│           ├── binding-row.md.j2
│           └── skill-entry.yaml.j2
└── examples/
    └── route-map/            # 示例路由规则
        ├── index.yaml
        ├── shared.yaml
        └── routes/
            ├── programmer.yaml
            └── pm-agent.yaml
```

## 与 Hermes Agent 的集成

1. **替代 LLM 路由**：在 `config.yaml` 中设置 `route_mode: zero-token`
2. **规则热加载**：修改 route-map/ 文件后，引擎自动检测变更并重新加载
3. **Chain 集成**：路由结果可触发 chain 执行链，自动编排多 Agent
4. **日志审计**：所有路由决策写入 `logs/route-engine.jsonl`，支持 `analyze-route-log.py` 分析

## 许可证

MIT
