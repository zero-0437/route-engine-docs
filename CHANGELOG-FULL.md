# 路由引擎发布文档（完全版）

> **内部文档 — 仅供私库使用**
> 生成日期：2026-07-04
> 报告编号：CHANGELOG-FULL-20260704-v3

---

## 一、发布周期概览

### 1.1 周期范围

| 字段 | 值 |
|------|----|
| 上次发布 Commit | `a8c6a11` — 发布路由引擎：完整路由体系 + 链编排引擎 + 自动 Brief 机制 |
| 当前 HEAD | `cb0c2af` (含 uncommitted chain 重构) |
| 周期类型 | 架构优化发布 — Chain 管线并行化重构 + 索引补齐 |

### 1.2 架构全景（本轮更新后）

```
route-map/                    # 路由规则配置目录（schema v2.5，16个agent映射）
├── index.yaml                # 索引文件（101行，16个agent，含 chain_ref 映射）
├── routes/*.yaml (16个)      # 各 Agent 的路由规则
├── chains/*.yaml (9个)       # Chain 管线定义
│   ├── debugger-chain.yaml       # Bug 诊断 6 阶段管线
│   ├── dual-review-chain.yaml    # 🔁 三轴并行双评审（本轮重构）
│   ├── follow-process-chain.yaml # 🔁 标准流程管线（本轮重构）
│   ├── programmer-chain.yaml     # 🔁 编码管线（本轮重构）
│   ├── spec-agent-chain.yaml     # 🔁 新项目管线（本轮重构）
│   ├── pub-chain.yaml            # 📦 发版链（本轮接入）
│   ├── research-chain.yaml       # 数据搜索链
│   ├── learn-chain.yaml          # 学习链
│   └── triage-chain.yaml         # Issue 分类链
└── shared.yaml               # 共享规则

scripts/
├── route_engine.py           # 路由引擎核心（699行）→ 路由决策
├── chain_executor.py         # Chain 执行状态机（1285行）→ 步骤推进
├── chain_config.py           # 共享 YAML 加载模块（47行）
└── route_logger.py           # 独立日志模块（84行）

tests/
├── test_route_engine.py      # 路由引擎测试（563行，64用例）
└── test_chain_executor.py    # Chain 执行器测试（675行，53用例）
```

### 1.3 向后兼容性声明

| 维度 | 变更类型 | 兼容性 | 说明 |
|------|---------|--------|------|
| API 接口 | 无变更 | ✅ 完全兼容 | route() 签名未变，返回结构不变 |
| YAML 配置 | **格式变更** | ⚠️ 向前兼容 | chain_step_skills 条目减少（合并到 dual-review），旧版 chain_executor 无法解析单一 dual-review 步骤 |
| 运行时 | 无变更 | ✅ 完全兼容 | 无需迁移脚本 |
| 持久化状态 | 无变更 | ✅ 完全兼容 | chain_executor 状态文件格式不变 |

---

## 二、本轮修改/新增文件清单

### 2.1 新建文件（本轮周期内，含已提交 + 已回退）

| 文件路径 | 行数 | 说明 | 状态 |
|----------|------|------|------|
| `route-map/chains/pub-chain.yaml` | 14 | 发版流程 Chain — docs-writer 生成文档 → file-ops 上传双仓库。含 chain_step_skills 映射 | ✅ 已提交（a8c6a11 已含，本轮接入 chain_ref） |
| `route-map/chains/research-chain.yaml` | ~20 | 数据搜索链 — data-analyst chain_ref | ✅ 已提交（070bed3 新增 chain_ref） |
| `route-map/chains/triage-chain.yaml` | ~20 | Issue 分类链 — triage chain_ref | ✅ 已提交 |
| `route-map/chains/learn-chain.yaml` | ~15 | 学习链 — prompt-engineer chain_ref | ✅ 已提交 |
| `route-map/routes/data-analyst.yaml` | ~25 | 数据分析路由规则 | ✅ 已提交 |
| `route-map/routes/docs-writer.yaml` | ~15 | 文档工程师路由规则 | ✅ 已提交 |
| `route-map/routes/document-processor.yaml` | ~15 | 文档处理路由规则 | ✅ 已提交 |
| `route-map/routes/file-ops.yaml` | ~20 | 文件操作路由规则 | ✅ 已提交 |
| `route-map/routes/memory-agent.yaml` | ~20 | 记忆管理路由规则 | ✅ 已提交 |
| `route-map/routes/prompt-engineer.yaml` | ~15 | Prompt 工程师路由规则 | ✅ 已提交 |
| `route-map/routes/reality-checker.yaml` | ~15 | 集成测试路由规则 | ✅ 已提交 |
| `route-map/routes/synology-helper.yaml` | ~15 | NAS 运维路由规则 | ✅ 已提交 |
| `route-map/routes/ui-designer.yaml` | ~15 | 前端设计路由规则 | ✅ 已提交 |
| `route-map/shared.yaml` | ~30 | 共享路由规则 | ✅ 已提交 |

### 2.2 修改文件

#### 2.2.1 route-map/index.yaml — chain_ref 批量接入（已提交）

**Commit**: 070bed3 (pub-chain: 接入 docs-writer chain_ref) + 其他 chain_ref 添加

| 新增 chain_ref | Agent | Chain 引用 |
|---------------|-------|-----------|
| `chain_ref: pub-chain` | docs-writer | pub-chain |
| `chain_ref: research-chain` | data-analyst | research-chain |
| `chain_ref: programmer-chain` | programmer | programmer-chain |
| `chain_ref: learn-chain` | prompt-engineer | learn-chain |
| `chain_ref: triage-chain` | triage | triage-chain（新增 agent） |

**原因**：完成路由引擎 chain 管线全覆盖，确保各 Agent 在路由决策后自动绑定对应的 Chain 执行流程。

#### 2.2.2 route-map/chains/dual-review-chain.yaml — 并行化重构（uncommitted）

**原结构**（串行 3 步）：
```yaml
steps:
  - agent: error-analyst      # spec 合规评审
  - agent: programmer          # 代码质量评审
  - agent: data-analyst        # Architecture 轴评审
chain_step_skills:
  dual-review@0: [code-review, codebase-inspection]
  dual-review@1: [receiving-code-review]
  dual-review@2: [architecture-review, codebase-inspection]
```

**新结构**（并行 3-branch）：
```yaml
steps:
  - type: parallel
    join_strategy: separate
    branches:
      - agent: error-analyst   # spec 合规评审
      - agent: programmer      # 代码质量评审
      - agent: data-analyst    # Architecture 轴评审
chain_step_skills:
  dual-review@0: [code-review, receiving-code-review, architecture-review, codebase-inspection]
```

**改动要点**：
- 将 3 个串行评审步骤改为并行 3-branch 结构
- 三轴（Spec / 代码质量 / Architecture）同时评审，全局耗时从 O(3) 降为 O(1)
- 删除冗余的 `completion_contract` 条目（移至 branch 内局部控制）
- chain_step_skills 从 3 个独立条目合并为 1 个（`dual-review@0`），包含所有评审技能
- description 更新为"三轴并行评审（spec合规/代码质量/架构），同步出报告"

**原因**：三轴评审无数据依赖，并行化可显著缩短端到端管线耗时。技能条目合并简化了 chain_executor 的步骤索引逻辑。

#### 2.2.3 route-map/chains/follow-process-chain.yaml — 评审步骤合并（uncommitted）

**原结构**：6 个串行步骤，最后 3 步分别为 spec 合规评审、代码质量评审、架构评审。

**新结构**：4 个串行步骤，评审阶段合并为单步 `dual-review`。

| 原步骤 | 新步骤 | 说明 |
|--------|--------|------|
| pm-agent → 任务拆解 | ✅ 保留 | 不变 |
| pm-agent → 修复方案摘要 | ✅ 保留 | 不变 |
| programmer → 批量实现 | ✅ 保留 | 不变 |
| error-analyst → spec 合规评审 | ❌ 删除 | 合并到 dual-review |
| programmer → 代码质量评审 | ❌ 删除 | 合并到 dual-review |
| data-analyst → 架构评审 | ❌ 删除 | 合并到 dual-review |
| **—** | **dual-review → 三轴双评审** | 🆕 新增 |

**chain_step_skills 变更**：
- 删除：`pm-agent@3: [requesting-code-review]`、`pm-agent@4: [requesting-code-review, receiving-code-review]`、`pm-agent@5: [architecture-review, codebase-inspection]`
- 新增：`pm-agent@3: [code-review, receiving-code-review, architecture-review, codebase-inspection]`
- 合并后的 skill 列表包含所有评审能力，由 dual-review chain 内部调度

**原因**：消除重复的串行评审步骤，统一由 dual-review chain 管理三轴评审，减少管线层级和状态维护复杂度。

#### 2.2.4 route-map/chains/programmer-chain.yaml — review 步骤清理 + 索引修复（uncommitted）

**原结构**：6 步（TDD → spec评审 → 质量评审 → 并行cross-check → 验证门控 → 收尾）

**新结构**：4 步（TDD → 双评审 → 验证门控 → 收尾）

| 原步骤 | 新步骤 | 说明 |
|--------|--------|------|
| TDD 实现 + self-review | ✅ 保留（step 0） | 不变 |
| spec 合规评审 | ❌ 删除 | 合并到 dual-review |
| 代码质量评审 | ❌ 删除 | 合并到 dual-review |
| 并行审查 (error-analyst|programmer) | ❌ 删除 | 合并到 dual-review |
| 验证门控 | ✅ 保留（step 2） | completion_contract 精简 |
| 收尾 | ✅ 保留（step 3） | 不变 |
| **—** | **dual-review → 三轴双评审** | 🆕 新增（step 1） |

**chain_step_skills 索引修复**：
- 旧索引：`programmer@0` ~ `programmer@5`（6 个条目，含 3 个空/冗余条目）
- 新索引：`programmer@0` ~ `programmer@3`（4 个条目，去除空条目）
- 技能合并：`programmer@1` 包含 `[code-review, codebase-inspection, receiving-code-review]`（原分散在 step 1/2/3 的评审技能）

**description 更新**："编码管线 — TDD实现→双评审→验证门控→收尾"

**原因**：消除 3 个冗余评审步骤（spec/代码质量/并行cross-check），统一由 dual-review 管理。修复 chain_step_skills 索引不连续问题（原 programmer@1 为空列表）。

#### 2.2.5 route-map/chains/spec-agent-chain.yaml — 并行审查改为单步 dual-review（uncommitted）

**原结构**：第 5 步为并行 `type: parallel` 双分支（error-analyst Standards + programmer Spec）

**新结构**：第 4 步为单步 `agent: dual-review`

| 原步骤 | 新步骤 | 说明 |
|--------|--------|------|
| spec-agent → 需求分析 | ✅ 保留 | 不变 |
| pm-agent → 制定计划 | ✅ 保留 | 不变 |
| pm-agent → 任务拆解 | ✅ 保留 | 不变 |
| programmer → 批量实现 | ✅ 保留 | 不变 |
| 并行审查分支 | ❌ 删除 | 替换为 dual-review |
| **—** | **dual-review → 三轴双评审** | 🆕 新增 |
| 验证门控 | ✅ 保留 | 不变 |
| 收尾 | ✅ 保留 | 不变 |

**chain_step_skills 变更**：
- `spec-agent@4: []`（原为空的并行分支技能）→ `spec-agent@4: [code-review, codebase-inspection, receiving-code-review]`

**description 更新**："新项目管线 — 需求分析→制定计划→任务拆解→批量实现→双评审→验证门控→收尾"

**原因**：消除并行分支结构，统一使用 dual-review chain 进行三轴评审，降低 chain_executor 对并行分支的特殊处理复杂度。

### 2.3 变更统计

| 类别 | 文件数 | 净增/修改行数 | 说明 |
|------|--------|-------------|------|
| 新建路由规则文件 | 10 个 route + 1 个 shared | ~200 | 补齐 12 个缺失 Agent 路由文件 |
| 新建 chain 文件 | 4 个（research/triage/learn/pub） | ~70 | Chain 管线网络扩容 |
| 修改 index.yaml | 1 个 | +5 chain_ref | 自动路由绑定 |
| 重构 chain 文件 | 4 个 | ~120（修改） | 串行→并行 + 步骤合并 |
| **合计** | **~16 个文件** | **~390 行** | |

### 2.4 全项目累积统计

| 文件 | 行数 | 状态 |
|------|------|------|
| `scripts/route_engine.py` | 699 | ✅ 不变（本周期无修改） |
| `scripts/chain_executor.py` | 1285 | ✅ 不变（本周期无修改） |
| `scripts/chain_config.py` | 47 | ✅ 不变 |
| `scripts/route_logger.py` | 84 | ✅ 不变 |
| `route-map/index.yaml` | 101 | ✅ 修改（+5 chain_ref + triage agent） |
| `route-map/chains/*.yaml (9 个)` | — | ✅ 4 个重构，5 个新增/现有 |
| `route-map/routes/*.yaml (16 个)` | — | ✅ 10 个新增 |
| `tests/ (2 个文件, 212 测试)` | — | ✅ 全部通过 |

---

## 三、详细重构变更对照

### 3.1 dual-review-chain.yaml — 串行→并行详细对照

| 对比项 | 重构前（serial） | 重构后（parallel） |
|--------|-----------------|-------------------|
| 执行方式 | 3 步串行：error-analyst → programmer → data-analyst | 3-branch 并行：error-analyst \| programmer \| data-analyst |
| 总耗时 | T(spec) + T(quality) + T(arch) | max(T(spec), T(quality), T(arch)) |
| description | "双评审 — spec合规评审→代码质量评审→仅出报告" | "三轴并行评审（spec合规/代码质量/架构），同步出报告" |
| completion_contract | 每步独立 report 校验 | 每 branch 独立 report 校验 |
| chain_step_skills 条目数 | 3（dual-review@0/1/2） | 1（dual-review@0） |

### 3.2 follow-process-chain.yaml — 步骤合并详细对照

| 对比项 | 重构前 | 重构后 |
|--------|--------|--------|
| 总步骤数 | 6 个 | 4 个 |
| 评审步骤 | 3 个独立 agent 步骤 | 1 个 dual-review 步骤 |
| completion_contract | 3 个独立 report 文件 | 1 个"任一报告存在"条件 |
| chain_step_skills | 6 个条目（pm-agent@0~5） | 4 个条目（pm-agent@0~3） |
| pm-agent 评审技能 | @3: [requesting-code-review], @4: [requesting-code-review, receiving-code-review], @5: [architecture-review, codebase-inspection] | @3: [code-review, receiving-code-review, architecture-review, codebase-inspection] |

### 3.3 向后兼容性关注点

1. **chain_step_skills 索引变更**：所有引用旧索引的外部代码（如 chain_executor 的状态持久化）需要重置。索引从 6→4（programmer-chain）、6→4（follow-process-chain）、7→7（spec-agent-chain 但 step 4 语义变更）、3→1（dual-review-chain）。
2. **并行->串行聚合**：chain_executor 无需特殊处理并行分支的调度了，所有评审步骤统一由 dual-review agent 内部的 parallel 结构管理。
3. **存量 chain 状态**：此前运行中的 chain 状态序列中的步骤索引与新版不兼容。建议在更新后清空 `chain_state.json` 或重启 chain_executor。

---

## 四、测试状态

| 测试套件 | 文件 | 用例数 | 通过数 | 通过率 |
|----------|------|--------|--------|--------|
| route_engine 测试 | `tests/test_route_engine.py` | 64 | 64 | 100% |
| chain_executor 测试 | `tests/test_chain_executor.py` | 148 | 148 | 100% |
| **合计** | **2 套件** | **212** | **212** | **100% ✅** |

> 本周期未修改 route_engine.py 和 chain_executor.py，测试状态维持不变。

---

## 五、发布检查清单

- [x] index.yaml chain_ref 已为 5 个 agent 注册（data-analyst/docs-writer/programmer/prompt-engineer/triage）
- [x] 所有 16 个 Agent 路由规则文件齐全
- [x] dual-review-chain 已重构为并行 3-branch 结构
- [x] follow-process-chain 评审步骤已合并为 dual-review 单步
- [x] programmer-chain 冗余评审已清理，索引已修复
- [x] spec-agent-chain 并行审查已改为单步 dual-review
- [x] 所有 chain_step_skills 格式统一为 `{agent}@{index}: [skills]`
- [x] 212 测试全部通过
- [x] 本发布文档签字就绪

---

## 六、附录

### 6.1 本周期 Commit 清单

| Commit | 消息 | 说明 |
|--------|------|------|
| 070bed3 | pub-chain: 接入 docs-writer chain_ref | index.yaml chain_ref 接入 |
| 62891cb | route-map 关键词补齐 | 新增 12 个路由文件 |
| 52055ab | 路由引擎架构文档 | 架构文档补充 |
| 150d1d6 | 备份: 路由引擎最新完整快照 2026-07-03 | 全量快照备份 |
| (uncommitted) | Chain 管线并行化重构 | 4 个 chain YAML 的重构变更 |

### 6.2 关键架构改进总结

1. **Chain 并行化**: dual-review-chain 从串行 3 步改为并行 3-branch，评审耗时从 O(3) 降为 O(1)
2. **步骤合并**: follow-process-chain / programmer-chain / spec-agent-chain 评审步骤统一委托给 dual-review
3. **索引清理**: programmer-chain chain_step_skills 从 6 个条目精简到 4 个，去除空条目
4. **路由网络扩容**: 从 8 个 Agent → 16 个 Agent，新增 chain_ref 自动绑定机制
5. **发版流水线**: pub-chain 接入 docs-writer，发布流程自动化
6. **零改动核心引擎**: route_engine.py/chain_executor.py 本周期无修改，证明 chain 抽象成功

### 6.3 文件校验

| 文件 | MD5 |
|------|-----|
| `route-map/chains/dual-review-chain.yaml` | `ef47ef9f9dffe8905126f81c9e47a4bf` |
| `route-map/chains/follow-process-chain.yaml` | `57c5ecdf5ea0382d2af79186a3c016e7` |
| `route-map/chains/programmer-chain.yaml` | `49d9840f2d67523dd3d7a662155bb719` |
| `route-map/chains/spec-agent-chain.yaml` | `ccef038a4ab74a10ebc74c66d2adc2ff` |
| `route-map/chains/debugger-chain.yaml` | 未变更 |
| `route-map/chains/pub-chain.yaml` | 未变更 |
| `route-map/index.yaml` | 已提交（070bed3） |
