# Route-Map 目录结构规范

## 目录结构

```
route-map/
├── index.yaml          # 路由索引（必选）
├── shared.yaml         # 共享规则（可选，被各 Agent 引用）
├── routes/             # Agent 规则文件（必选）
│   ├── programmer.yaml
│   ├── pm-agent.yaml
│   ├── memory-agent.yaml
│   └── ...             # 每个 Agent 对应一个规则文件
└── chains/             # Chain 定义（可选）
    ├── programmer-chain.yaml
    ├── debugger-chain.yaml
    └── ...
```

## index.yaml 格式

```yaml
# route-map/index.yaml
defaults:
  threshold: 0.5        # 全局默认阈值
  margin: 0.3           # 全局默认差距阈值
  priority: 99          # Agent 默认优先级

overrides:              # 完全匹配覆盖规则（优先级最高）
  - pattern: /debug
    agent: error-analyst
    chain_ref: debugger-chain
  - pattern: /test
    agent: programmer
    skills: [test-driven-development]

chain_keywords:         # Chain 级关键词（直接匹配 chain，跳过 Agent 评分）
  - keyword: 架构审计
    chain_ref: architecture-chain
  - keyword: 双评审
    chain_ref: dual-review-chain

agents:                 # Agent 索引
  programmer:
    condition: Coding 任务
    description: 代码编写与调试
    file: routes/programmer.yaml
    priority: 2
  pm-agent:
    condition: 纯协调类
    description: 技术架构师 + 执行调度者
    file: routes/pm-agent.yaml
    priority: 1
    chain_ref: pm-chain
```

### 字段说明

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `condition` | string | 是 | Agent 适用条件描述 |
| `description` | string | 否 | 详细描述 |
| `file` | string | 是 | 规则文件路径（相对于 route-map/） |
| `priority` | int | 是 | Agent 优先级（0=最高，数字越大优先级越低） |
| `chain` | list | 否 | 内联 chain 定义 |
| `chain_ref` | string | 否 | 引用 chains/ 下的 chain 定义文件 |
| `chain_step_skills` | dict | 否 | Chain 步骤绑定的技能 |
| `report_only` | bool | 否 | 仅报告模式（不实际执行修改） |

## 规则文件格式

```yaml
# route-map/routes/programmer.yaml
agent: programmer
priority: 2
condition: Coding 任务
rules:
  # ── 示例注释 ──
  - type: phrase
    pattern: 实现新功能
    weight: 1.0
    skills: [spike]
    fuzzy: true
    chain_ref: programmer-chain
  - type: regex
    pattern: 写.*(代码|code|脚本)
    weight: 0.8
    skills: [spike]
```

### 字段说明

#### agent（顶层）

| 字段 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `agent` | string | 是 | Agent 名称（与 index.yaml 中的 key 一致） |
| `priority` | int | 否 | 规则文件级优先级（覆盖 index.yaml 中的 priority） |
| `condition` | string | 否 | 适用条件说明 |
| `rules` | list | 是 | 规则列表 |

#### rules[].type — 规则类型

四种匹配类型：

| 类型 | 说明 | 匹配方式 | 性能 |
|------|------|----------|------|
| `keyword` | 精确关键词 | 分词后哈希表精确匹配 | O(1) |
| `phrase` | 短语子串 | 用户输入包含该短语即可 | O(n) |
| `regex` | 正则表达式 | Python re.search 匹配 | 取决于正则复杂度 |
| `fuzzy` | 模糊匹配 | CJK 分词重叠率 + 英文词边界匹配 | O(n) |

##### keyword — 精确关键词匹配

```yaml
- type: keyword
  pattern: TDD
  weight: 1.0
```

输入文本按 `CJK_CHAR_RE` 和 `EN_WORD_RE` 分词后，检查是否包含精确匹配。

##### phrase — 短语子串匹配

```yaml
- type: phrase
  pattern: 帮我写一段代码
  weight: 0.8
  skills: [spike]
```

简单子串包含匹配（`pattern in normalized_input`）。

##### regex — 正则表达式匹配

```yaml
- type: regex
  pattern: (修复|fix|修复bug).*
  weight: 0.9
  skills: [test-driven-development]
  chain_ref: bugfix-chain
```

Python `re.search` 匹配。支持捕获组，但引擎仅判断是否匹配。

##### fuzzy — 模糊匹配

```yaml
- type: phrase
  pattern: 实现新功能
  weight: 1.0
  fuzzy: true
  skills: [spike]
  chain_ref: programmer-chain
```

模糊匹配使用 CJK 分词重叠率算法：
- 输入文本中抽取 CJK 字符块和英文单词
- 规则模式也做同样分词
- 计算两集合的 Jaccard 重叠率
- 超过 `FUZZY_OVERLAP_THRESHOLD`（0.6）视为命中

#### rules[].weight — 权重机制

权重范围：**-2.0 ~ 2.0**

| 权重 | 效果 |
|------|------|
| > 0 | 正向匹配，加分 |
| = 0 | 不评分（仅用于元数据） |
| < 0 | 负向匹配，减分（排除规则） |

权重累加：同一 Agent 所有命中规则的 weight 相加，总分最高的 Agent 胜出。

```yaml
# 负权重示例 — 排除不必要的路由
- type: phrase
  pattern: 简单查询
  weight: -0.5
  agent: programmer
```

#### rules[].skills — 技能绑定

```yaml
- type: phrase
  pattern: 写单元测试
  weight: 1.0
  skills: [test-driven-development, verification-before-completion]
```

路由时自动加载绑定技能到上下文。技能名从 `.skill-cache.json` 反向解析为实际文件路径。

#### chain / chain_step_skills — Chain 绑定

```yaml
# 在规则中直接定义 chain 步骤
- type: phrase
  pattern: 全流程开发
  weight: 1.0
  chain:
    - agent: programmer
      goal: 实现功能
    - agent: error-analyst
      goal: 代码审查
  chain_step_skills:
    programmer_0: [test-driven-development]
    error-analyst_1: [verification-before-completion]
```

或通过 `chain_ref` 引用预定义 chain（推荐）：

```yaml
- type: phrase
  pattern: 全流程开发
  weight: 1.0
  chain_ref: full-dev-chain
```

## shared.yaml — 共享规则

共享规则文件，可被多个 Agent 通过 `inherits` 字段引用：

```yaml
# route-map/shared.yaml
rules:
  - type: phrase
    pattern: 你好
    weight: 0.1
    skills: [greeting]
```

## 验证工具

使用 `validate-route-map.py` 对 route-map 目录进行 12 维审计：

```bash
python3 scripts/validate-route-map.py
```

验证项包括：
1. index.yaml YAML 合法性
2. 规则文件引用完整性
3. Agent 命名一致性
4. 规则格式正确性
5. 权重范围检查
6. 技能引用有效性
7. Chain 引用完整性
8. Priority 合法性
9. 循环引用检测
10. 重复规则检测
11. 文件编码检查
12. 目录结构完整性
