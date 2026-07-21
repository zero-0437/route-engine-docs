# Spec 合规评审报告 — error-analyst 视角

**项目**: hermes-zero-token-router
**日期**: 2026-07-21
**角色**: error-analyst (spec 合规)

---

## 一、评审范围

检查项目缺失的规范文件、配置声明和 ADR（架构决策记录），评估项目是否符合软件工程规范文档实践。

---

## 二、缺失规范文件（🔴 阻塞项）

### 🔴 M1: 无 ADR（架构决策记录）目录或文件

项目完全没有 `adr/` 目录或任何 ADR 文件。以下重大架构决策缺乏记录：

| 决策 | 应该记录为什么 |
|------|---------------|
| 为什么选择 src/ + scripts/ 双目录 | src/ 是公开版，scripts/ 是内部版？选择理由不明 |
| Plugin 架构 vs MCP Server vs Python 模块 | 三种集成方式并存的原因和取舍 |
| 使用 YAML 规则定义而非代码配置 | 技术选型理由 |
| chain 编排状态机设计 | 状态转移图、错误恢复策略 |
| 为什么 15 个 Agent 但仅 10 个可用 | 虚拟 Agent 设计决策 |

**建议**: 创建 `adr/` 目录，至少为上述 5 个决策编写 ADR-001 到 ADR-005。

### 🔴 M2: route-map 中 5 个 Agent 无对应 Hermes profile

route-map/index.yaml 定义了 15 个 Agent，但根据 skill 文档，Hermes 实际委派白名单只有 10 个：

| Agent | 状态 | 有 chain_ref? |
|-------|------|--------------|
| dual-review | ❌ 无 profile | ✅ 有 chain_ref |
| triage | ❌ 无 profile | ✅ 有 chain_ref |
| spec-agent | ❌ 无 profile | ❌ 已清理 |
| reality-checker | ❌ 无 profile | ❌ 无 chain_ref |
| docs-writer | ❌ 无 profile | ❌ 无 chain_ref |

`reality-checker` 和 `docs-writer` 既无 Hermes profile 也不在 route-map/chains/ 中有 chain_ref，属于**死路由**。路由规则命中后无人执行。

**建议**: 
- `reality-checker` 规则合并到 `pm-agent`（同属协调/验证类）
- `docs-writer` 规则合并到 `document-processor`
- 运行 `validate-route-map.py` 后更新 index.yaml

### 🔴 M3: skill-map.yaml 跨项目引用但未声明版本一致性

`skill-map.yaml` 引用大量 `engineering-*` 技能，但这些技能定义在 Hermes Agent 的 skills/ 目录下，而非本项目内。项目未声明：
- Hermes Agent 最低版本要求
- skill-map.yaml 与 route-map rules 中 skills 字段的交叉验证机制
- skill-cache.json 的 schema 版本

### 🟡 M4: 缺少 CONTRIBUTING.md

项目无贡献指南。无 PR 流程、测试要求、编码规范的文档。对于正在活跃迭代的项目来说不可接受。

### 🟡 M5: .gitignore 不完整

当前 `.gitignore` 遗漏：
- `logs/` 目录（route-engine.jsonl 日志应忽略，但硬编码了 `*.log`）
- `reviews/` 目录（旧审查文件可以忽略或归档）
- `.skill-cache.json` 已在 gitignore 中 ✅

**建议**: 添加 `logs/` 到 gitignore。日志文件不应提交到版本控制。

### 🟡 M6: requirements.txt 仅声明 pyyaml

`requirements.txt` 只有 `pyyaml>=6.0`。项目实际依赖包括：
- `Python >= 3.8`（type hints 语法）
- `json`（内置 ✅）
- `re`（内置 ✅）
- `os`（内置 ✅）
- 测试框架（pytest？unittest？）

**建议**: 补充测试框架依赖声明。

---

## 三、配置声明检查

### ✅ 通过项

| 检查项 | 结果 |
|--------|------|
| route-map/index.yaml 存在 | ✅ |
| route-map/routes/ 目录存在 | ✅ |
| route-map/chains/ 目录存在 | ✅ |
| tests/ 目录存在 | ✅ |
| README.md 存在 | ✅ |
| .gitignore 存在（部分完善） | ✅ |
| plugin.yaml 存在 | ✅ |

### ❌ 缺失项

| 缺失项 | 严重度 |
|--------|--------|
| ADR 目录 | 🔴 |
| pyproject.toml / setup.py | 🟡 |
| CONTRIBUTING.md | 🟡 |
| LICENSE 文件 | 🟡 |
| Makefile / Taskfile | 💭 |
| .editorconfig | 💭 |

---

## 四、文档重复问题（问题② 深入分析）

### 根目录 vs docs/ 的重复映射

| 根目录文件 | docs/ 对应文件 | 关系 | 建议 |
|-----------|---------------|------|------|
| CHANGELOG-FULL.md (266行) | docs/CHANGELOG.md (341行) | 不同版本 | 合并为 docs/CHANGELOG.md |
| ROUTE-ENGINE-CHANGELOG.md (318行) | docs/ROUTE-ENGINE-CHANGELOG.md (125行) | 脱敏版 vs 公开版 | 统一命名规则或合并 |
| — | docs/DELEGATION_PROTOCOL.md | 仅 docs/ 有 | ✅ 正常 |
| — | docs/PLUGIN_INTEGRATION.md | 仅 docs/ 有 | ✅ 正常 |

**建议结构**:
```
docs/
├── CHANGELOG.md              # 单一 changelog
├── DELEGATION_PROTOCOL.md    # 保留
├── PLUGIN_INTEGRATION.md     # 保留
├── why-route-engine.md       # 保留
├── task-slice.md             # 保留
├── agent-rule-review-checklist.md  # 保留
├── fuzzy-phase-B-status.md   # 保留
```

根目录仅保留：
```
README.md                # 精简版
ARCHITECTURE.md          # 或移入 docs/
ROUTE_MAP_SPEC.md        # 或移入 docs/
```

---

## 五、整改优先级

| 优先级 | 项 | 预估工时 |
|--------|----|---------|
| P0 | 清理死路由（reality-checker, docs-writer） | 30min |
| P1 | 创建 ADR 目录 + 初始 5 个 ADR | 1h |
| P2 | 合并根目录与 docs/ 的重叠 changelog | 30min |
| P3 | 补充 requirements.txt 和 CONTRIBUTING.md | 30min |
| P4 | 完善 .gitignore | 10min |
| P5 | 添加 LICENSE 和 .editorconfig | 10min |

---

## 六、合规评分

| 维度 | 评分 (0-10) | 说明 |
|------|-------------|------|
| 文档完整性 | 5/10 | 有基本 README 但缺 ADR/CONTRIBUTING/LICENCE |
| 配置声明 | 6/10 | route-map 完整但缺 pyproject.toml |
| Agent 路由一致性 | 4/10 | 5/15 Agent 无对应 profile |
| 文档结构清晰度 | 3/10 | 根目录和 docs/ 严重重叠 |
| 版本控制规范 | 5/10 | gitignore 不完整，日志未忽略 |
| **综合** | **4.6/10** | 需要中等程度规范补全 |
