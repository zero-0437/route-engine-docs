# 代码质量评审报告 — programmer 视角

**项目**: hermes-zero-token-router
**日期**: 2026-07-21
**角色**: programmer (代码质量)

---

## 一、核心发现：src/ 与 scripts/ 代码重复（问题① 深入分析）

### 1.1 重复概览

| 文件 | src/ 行数 | scripts/ 行数 | 重复度 | 差异分析 |
|------|-----------|--------------|--------|---------|
| route_engine.py | 665 | 687 | ~99% | 4 处差异 |
| chain_config.py | 47 | 47 | **100% 完全一致** | 0 处差异 |
| chain_executor.py | 1325 | 1639 | ~70% | 有结构差异 |

### 1.2 route_engine.py 差异对比

通过 `diff src/route_engine.py scripts/route_engine.py` 发现 **4 处差异**：

| # | 位置 | src/ 版本 | scripts/ 版本 | 影响 |
|---|------|-----------|---------------|------|
| 1 | line 86a87 | 无 | 多了一行 `"mode": chain_data.get("mode", "stepwise")` | scripts/ 多了一个字段 |
| 2 | line 534a536 | 无 | 同上，另一次引用 | scripts/ 两处传 mode |
| 3 | line 577-580 | `cache_manual_skills` 参与合并 | 只用 `matched_skills` | ⚠️ **BUG**: scripts/ 缺少手动技能缓存合并 |
| 4 | line 603-625 | 无 | 多了问号/感叹号/连续句号跳过逻辑 | src/ 缺少这个特性 |

**关键结论**: 两个版本已分叉。src/ 有 manual_skills 修复但缺 punctuation-skip 逻辑；scripts/ 有 punctuation-skip 但缺 manual_skills 修复。

> 🔴 **阻塞项**: `scripts/route_engine.py` 存在已知 bug（缺少 cache_manual_skills 合并），同时 `src/route_engine.py` 缺少 punctuation-skip 特性。双方向分叉导致两套代码都不能完全信任。

### 1.3 chain_config.py 完全一致

`chain_config.py` 在两个目录下**内容完全相同**（47 行，零差异）。这意味着有两份完全一样的配置文件加载模块。

> 🟡 **建议项**: 删除 `scripts/chain_config.py`，让 scripts/ 通过相对路径导入 `src/` 版本。

### 1.4 chain_executor.py 结构差异

**行数**: src/ = 1325, scripts/ = 1639（scripts/ 多 314 行）
`scripts/chain_executor.py` 增加了：
- `MAX_TOTAL_ITERATIONS = 100` 和 `CHAIN_TIMEOUT = 3600` 全局常量
- 额外的安全网逻辑

**建议**: 统一到 src/ 作为主版本，scripts/ 删除或改为薄 wrapper。

### 1.5 根因分析

根据 `CHANGELOG-FULL.md` 的说明，src/ 是"脱敏版源码目录（公开库）"，scripts/ 是"内部路由引擎核心"。但实践中：
- 两个目录的文件不仅同名，**路由、配置、执行器三套文件高度重复**
- 架构使用了 `sys.path.insert(0, 'src')` 还是 `scripts/` 的自引用？当前 `chain_config.py` 使用 `SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))` → 导入时取决于哪个目录的 `chain_config.py` 先被找到
- 维护者需要同时修改 6 个文件才能完成一次更新

> 🔴 **阻塞项**: 双目录分叉策略带来了实质性 bug（manual_skills 合并缺失），且每次修改需要同步两份代码。

---

## 二、模块边界分析

### 2.1 依赖方向

```
route_engine.py ──→ chain_config.py
       │
       ├─→ chain_executor.py（间接通过 route-map chains/ 配置）
       │
       └─→ route_logger.py
```

**依赖方向正确**：core 模块依赖配置模块和日志模块，没有循环依赖。

### 🟡 2.2 route_logger.py 未被 src/ 中的 route_engine.py 导入

`route_logger.py` 存在于 `src/` 目录（84 行），但 `src/route_engine.py` 并未导入它。日志直接通过 `print(json.dumps(...))` 写入 stdout。

**建议**: 统一日志路径，要么删除未使用的 `route_logger.py`，要么让 route_engine.py 实际使用它。

### 💭 2.3 mcp-router-server.py 在根目录

`mcp-router-server.py`（文件权限 600）位于根目录，作为 MCP Server 入口点。建议移入 `scripts/` 目录。

---

## 三、文件命名一致性

### 🟡 3.1 命名风格不一致

| 文件 | 风格 | 问题 |
|------|------|------|
| src/route_engine.py | snake_case | ✅ |
| scripts/route_engine.py | snake_case | ✅ |
| scripts/analyze-route-log.py | kebab-case | ❌ 与其他 snake_case 不一致 |
| scripts/route-log-suggest.py | kebab-case | ❌ 同上 |
| scripts/hermes-route-add | 无扩展名 | ❌ 无 .py 后缀 |
| plugins/route-router/ | route-router vs project name | ❌ 命名不统一 |

### 🟡 3.2 scripts/ 工具命名建议

```python
# 当前
scripts/analyze-route-log.py      # kebab-case
scripts/route-log-suggest.py      # kebab-case

# 建议
scripts/analyze_route_log.py      # 统一 snake_case
scripts/suggest_route_log.py      # 统一 snake_case
```

### 💭 3.3 plugins/ 目录命名不一致

项目名称为 `zero-token-router`，但插件目录命名为 `route-router`。建议统一为 `zero-token-router`。

---

## 四、代码度量

### 4.1 模块大小

| 文件 | 行数 | 评估 |
|------|------|------|
| src/chain_executor.py | 1325 | 🟡 较大，建议拆分（状态机 + 步骤类型 + CLI） |
| scripts/chain_executor.py | 1639 | 🔴 过大，应该拆分 |
| src/route_engine.py | 665 | 🟡 适中，但可考虑拆分 rule_loader + matcher + decider |
| scripts/route_engine.py | 687 | 🟡 同上 |
| scripts/validate-route-map.py | 468 | ✅ 合理 |

### 4.2 测试覆盖率

| 文件 | 测试文件 | 行数 | 评估 |
|------|---------|------|------|
| route_engine.py | test_route_engine.py | 存在 | 需确认覆盖率 |
| chain_executor.py | test_chain_executor.py | 存在 | 需确认覆盖率 |
| chain_config.py | ❌ 无独立测试 | — | 🟡 缺少 |
| route_logger.py | ❌ 无独立测试 | — | 💭 可加 |

---

## 五、整改建议优先级

| 优先级 | 项 | 预估工时 |
|--------|----|---------|
| 🔴 P0 | 消除 src/ 与 scripts/ 双目录重复：确定主版本（建议 src/），scripts/ 统一为薄工具包装 | 2h |
| 🔴 P0 | 修复 scripts/route_engine.py 的 manual_skills bug | 10min |
| 🔴 P0 | 将 punctuation-skip 特性合并到 src/route_engine.py | 10min |
| 🟡 P1 | 统一文件命名风格为 snake_case | 30min |
| 🟡 P1 | 删除 scripts/chain_config.py（与 src/chain_config.py 完全一致） | 5min |
| 🟡 P2 | 评估 chain_executor.py 拆分（1325/1639 行） | 1h |
| 🟡 P2 | 确认 route_logger.py 是否实际被使用 | 10min |
| 💭 P3 | 统一 plugins/ 目录名 | 5min |
| 💭 P3 | 移动 mcp-router-server.py 到 scripts/ | 5min |

---

## 六、代码质量评分

| 维度 | 评分 (0-10) | 说明 |
|------|-------------|------|
| 代码重复度 | 3/10 | src/ vs scripts/ 严重重复 |
| 模块边界 | 6/10 | 依赖方向正确，但 route_logger 未使用 |
| 命名一致性 | 5/10 | kebab-case + snake_case 混用 |
| 文件大小合理性 | 5/10 | chain_executor.py 过大 |
| 测试覆盖 | 6/10 | 有测试但部分模块无独立测试 |
| **综合** | **5.0/10** | 核心问题是双目录分叉 |
