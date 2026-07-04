# 代码质量评审报告 — 路由引擎插件

**评审日期**: 2026-07-04  
**评审范围**: `route_engine.py` (662行) + `chain_executor.py` (960行) + `route-map/*.yaml`  
**评审人员**: Hermes Agent 自动化代码质量分析  

---

## 总体评分: 61 / 100

| 维度 | 得分 | 说明 |
|------|------|------|
| 代码可读性 | 65 | 命名清晰但函数过长，缺少 docstring |
| 异常处理完整性 | 70 | 覆盖良好但有裸 except 和 shell=True 风险 |
| 性能 | 60 | 冷加载昂贵，重复遍历 cache，重复写 state |
| 测试覆盖 | 55 | 6 个单元测试失败，chain_executor 无正式单元测试 |
| 重复代码 | 45 | advance() 内 3 个"链结束"块完全相同，branch/batch 处理近乎重复 |
| 类型提示 | 75 | route_engine.py 覆盖好，chain_executor.py 多处遗漏 |
| 代码异味 | 55 | 超级函数 advance() 360 行，多处魔法数字，YAML 隐患 |

---

## 质量问题清单

### 🔴 CRITICAL (4 项)

#### CRITICAL-1: 5 个 chain 的 `chain_step_skills` 键格式与 `_validate_skills` 预期不匹配

**文件**: `/opt/data/route-map/chains/debugger-chain.yaml` (L49-54)  
**行号**: L49-54  
**代码引用**:
```yaml
chain_step_skills:
  error-analyst@0: [diagnosing-bugs]
  programmer@0: []   # ← 格式为 {step_agent}@{idx}，实际应为 {chain_owner}@{idx}
```
**说明**: 当前 8 个 chain 文件中，**5 个**的 `chain_step_skills` key 使用 `{step_agent}@{idx}` 格式（即步骤中的 agent 名），但 `_validate_skills()`（见 `chain_executor.py` L227-240）和 `_build_step_result()`（L338-339）要求 `{chain_owner}@{idx}` 格式。  
受影响 chain:
| Chain 文件 | chain_owner | 实际键格式 | 正确格式 |
|-----------|-------------|-----------|---------|
| `debugger-chain.yaml` (L49-54) | `error-analyst` | `error-analyst@0`, `programmer@0`... | `error-analyst@0`..`error-analyst@5` |
| `dual-review-chain.yaml` (L28-31) | `dual-review` | `data-analyst@0` | `dual-review@2` |
| `learn-chain.yaml` (L16-19) | `prompt-engineer` | `programmer@1`, `reality-checker@2` | `prompt-engineer@1`, `prompt-engineer@2` |
| `research-chain.yaml` (L25-28) | `data-analyst` | `pm-agent@0`, `pm-agent@2` | `data-analyst@0`, `data-analyst@2` |
| `programmer-chain.yaml` (无 chain_step_skills) | `programmer` | 缺失全部 | `programmer@0`..`programmer@4` |

**影响**: 通过 `chain_ref` 启动这些 chain 时，`_validate_skills()` 将返回 `ERROR`，链无法启动。  
**严重度**: CRITICAL — 运行时阻断  
**修复建议**: 将所有 chain 文件的 `chain_step_skills` key 改为 `{chain_owner}@{idx}` 格式。

---

#### CRITICAL-2: `decide()` 对低分/空分返回 `unrouted` 而非 `llm_fallback`，导致测试失败

**文件**: `/opt/data/scripts/route_engine.py` (L381-411)  
**行号**: L381-411  
**说明**: `decide()` 中空评分（L382-394）和分数低于阈值（L398-411）均返回 `method: "unrouted"`，但默认配置 `fallback_agent: pm-agent` 和测试代码期望 `method: "llm_fallback"`。这导致 **3 个单元测试失败**：
- `test_below_threshold_fallback` — 期望 `llm_fallback`, 得 `unrouted`
- `test_empty_scores_fallback` — 期望 `llm_fallback`, 得 `unrouted`  
- `test_low_confidence_input_fallsback` — 期望 `llm_fallback`, 得 `unrouted`

**严重度**: CRITICAL — 测试一致性破坏，且下游可能依赖 `llm_fallback` method 做 LLM 回退  
**修复建议**: 方案 A：将 `unrouted` 改为 `llm_fallback` 并填充 `fallback_agent`；方案 B：与测试约定统一命名。

---

#### CRITICAL-3: `run_verification()` 使用 `shell=True` 执行未充分校验的命令

**文件**: `/opt/data/scripts/chain_executor.py` (L448-454)  
**行号**: L448-454  
**代码引用**:
```python
cp = subprocess.run(
    cmd,
    shell=True,
    capture_output=True,
    timeout=30,
    text=True,
)
```
**说明**: `verify_command` 来自 YAML 配置文件，使用 `shell=True` 执行。虽然 YAML 受版本控制，但存在两层风险：(a) 若攻击者能写入 YAML 则可执行任意 shell 命令；(b) 部分 verify_command 含 `! grep -q 'DEBUG-' src/ -r`（debugger-chain.yaml L47）依赖 shell 特性，但 `shlex.quote` 未使用。  
**严重度**: CRITICAL — 安全风险  
**修复建议**: 对简单命令去掉 `shell=True`，改用 `shlex.split()`；对必须 shell 的命令至少添加命令白名单校验。

---

#### CRITICAL-4: `decide()` 返回的 `confidence` 可能超过 1.0

**文件**: `/opt/data/scripts/route_engine.py` (L432-444)  
**行号**: L432-444  
**代码引用**:
```python
# 正常自动路由
return {
    "agent": top_name,
    "confidence": top_score,  # ← top_score 未经截断
    ...
}
```
**说明**: `evaluate()` 累加所有匹配规则的 weight，若某 Agent 匹配多个规则且 weight 总和 > 1.0，则 `confidence` 会超过 1.0。测试 `test_confidence_range` 因此失败（得到 1.5）。`decide()` 和 `route()` 均未对 confidence 做 `min(score, 1.0)` 截断。  
**严重度**: CRITICAL — 违反 API 契约（置信度应 ∈ [0, 1]）  
**修复建议**: 在 `decide()` 返回前或 `route()` 中调用 `confidence = min(confidence, 1.0)`。

---

### 🟠 HIGH (7 项)

#### HIGH-1: `advance()` 函数过长（360 行）

**文件**: `/opt/data/scripts/chain_executor.py` (L489-848)  
**行号**: L489-L848  
**说明**: `advance()` 函数包含完整的链状态机逻辑：首次调用、batch_complete、branches_complete、loop_complete、branch_index、batch_index、状态校验、BLOCKED、NEEDS_CONTEXT、DONE_WITH_CONCERNS、NEEDS_FIX、DONE/APPROVE 等 12+ 个分支路径。单个函数超过 350 行，无法理解和测试。  
**严重度**: HIGH — 可维护性差，测试困难  
**修复建议**: 将每个 `last_result` 状态分支（batch_complete, branches_complete, loop_complete, branch_index, batch_index, BLOCKED, NEEDS_CONTEXT, DONE_WITH_CONCERNS, NEEDS_FIX, DONE/APPROVE）提取为独立函数。

---

#### HIGH-2: 3 个"链结束"代码块完全相同（DRY 违规）

**文件**: `/opt/data/scripts/chain_executor.py` (L564-577, L601-617, L626-641)  
**行号**: L564-577, L601-617, L626-641  
**代码引用**: 三处片段结构完全一致：
```python
_save_state(task_id, state)
return {
    "status": "REPORT_ONLY" if state.get("report_only") else "DONE",
    "final_output_path": state["context"].get("last_output", ""),
    "concerns": state["concerns"],
    "summary": {
        "total_steps": len(chain_def),
        "spec_retry_count": state["spec_retry"],
        "quality_retry_count": state["quality_retry"],
        "concerns_count": len(state["concerns"]),
    },
}
```
出现在 `batch_complete`、`branches_complete`、`loop_complete` 三个分支结束时。  
**严重度**: HIGH — 修改时极易漏改一处导致 bug  
**修复建议**: 提取为 `_build_chain_done_result(state, chain_def)` 工具函数。

---

#### HIGH-3: `branch_index` 和 `batch_index` 处理代码高度重复

**文件**: `/opt/data/scripts/chain_executor.py` (L643-665, L667-689)  
**行号**: L643-689  
**说明**: `branch_index` 和 `batch_index` 两个分支的处理逻辑几乎相同——都扩展结果数组、填充索引位置、保存 state、返回 `_PROGRESS` 状态。  
**严重度**: HIGH — 双重维护负担  
**修复建议**: 提取公共逻辑为 `_accumulate_partial_result(state, key, index, result)`。

---

#### HIGH-4: `load_route_map()` 职责过重（130 行）

**文件**: `/opt/data/scripts/route_engine.py` (L42-172)  
**行号**: L42-L172  
**说明**: 单个函数负责：加载 index.yaml → 加载 shared.yaml → 遍历 agents 加载每个 agent 文件 → 处理 chain_ref 并加载 chain 文件 → 构建 chain_kw_index → 扫描 chains/ 目录。  
**严重度**: HIGH — 违反单一职责原则，难以测试  
**修复建议**: 拆分为 `_load_index()`, `_load_shared_rules()`, `_load_agent_rules()`, `_build_chain_index()`。

---

#### HIGH-5: `route()` 函数过长（117 行），包含 4 个不同逻辑阶段

**文件**: `/opt/data/scripts/route_engine.py` (L447-564)  
**行号**: L447-L564  
**说明**: `route()` 在单一函数中完成了：(1) override 匹配 + 返回；(2) chain_keyword 匹配 + 返回；(3) evaluate + decide + 技能反向匹配；(4) 结果后处理。4 条独立路径有 3 个不同的返回点。  
**严重度**: HIGH — 逻辑耦合，修改一处可能影响另一条路径  
**修复建议**: 拆分为 `_try_override()`, `_try_chain_keyword()`, `_evaluate_and_decide()`。

---

#### HIGH-6: "修复 PROXY 连接的 bug" 误路由到 triage 而非 programmer

**文件**: `/opt/data/route-map/routes/triage.yaml` (L11-12)  
**行号**: L11-12  
**代码引用**:
```yaml
- type: phrase
  pattern: bug
  weight: 1.5
```
**说明**: `triage` 规则的 `bug` 权重 1.5 过于激进，导致 "修复 PROXY 连接的 bug"（明显的编程任务）被 triage 截获。programmer 同时匹配 `bug`(0.7) + `fix`(0.7) = 1.4，仍低于 triage 的 1.5。  
**严重度**: HIGH — 功能路由错误  
**修复建议**: 降低 triage 的 `bug` 权重至 1.0，或给 programmer 添加"修复"组合规则权重。

---

#### HIGH-7: 缺少 chain_executor 专用单元测试文件

**文件**: `/opt/data/scripts/chain_executor.py` (960 行)  
**说明**: 960 行的复杂状态机引擎只有 `/opt/data/scripts/test_chain_link.py`（133 行手动 assert 脚本，非 unittest），没有正式的单元测试文件。核心函数如 `_validate_skills`、`run_verification`、`advance` 的各个状态分支均无自动化测试覆盖。  
**严重度**: HIGH — 无回归保护  
**修复建议**: 创建 `tests/test_chain_executor.py`，用 unittest 覆盖：`start_chain`、`advance` 各状态分支、`run_verification`、`_validate_skills`、`aggregate_parallel_results`。

---

### 🟡 MEDIUM (9 项)

#### MEDIUM-1: `_score_skill_matches()` 中魔法数字 0.2

**文件**: `/opt/data/scripts/route_engine.py` (L245)  
**行号**: L245  
**代码引用**:
```python
scores[agent] = scores.get(agent, 0.0) + 0.2
```
**说明**: 每次技能匹配的权重加分为硬编码 `0.2`，无命名常量，也无文档说明为什么是这个值。  
**修复建议**: 提取为模块级常量 `SKILL_BONUS = 0.2`。

---

#### MEDIUM-2: `log_route()` 中魔法数字 0.6

**文件**: `/opt/data/scripts/route_engine.py` (L610)  
**行号**: L610  
**代码引用**:
```python
elif method == "auto" and confidence < 0.6:
```
**说明**: 日志标记"边界路由"的置信度阈值 0.6 为硬编码，与 `min_confidence: 0.5` 不统一，也无说明区分意图。  
**修复建议**: 提取为 `_BORDERLINE_THRESHOLD = 0.6` 并加注释。

---

#### MEDIUM-3: `decide()` 中魔法数字 99 作为默认 priority

**文件**: `/opt/data/scripts/route_engine.py` (L121, L418, L503)  
**行号**: L121, L418, L503  
**代码引用**:
```python
agents.get(x[0], {}).get("priority", 99)
```
**说明**: 99 作为默认 priority 出现在 load_route_map 和 decide 中。  
**修复建议**: 提取为 `DEFAULT_PRIORITY = 99`。

---

#### MEDIUM-4: 类型提示遗漏 — `chain_executor.py` 多处函数无返回类型

**文件**: `/opt/data/scripts/chain_executor.py`  
**行号**: 多处  
**说明**: 以下函数缺少返回类型注解：
- `_state_path(task_id: str) -> str`（L250）
- `_save_state(task_id: str, state: dict) -> None`（L275）
- `start_chain(...)`（L354）
- `run_chain(...)`（L363）
- `main()`（L851）
- `aggregate_parallel_results` 参数 `branch_results: ...` 类型不够精确

**修复建议**: 补充全部返回类型注解。

---

#### MEDIUM-5: `_load_skill_cache()` 中冗余的 `Exception` 捕获

**文件**: `/opt/data/scripts/route_engine.py` (L187)  
**行号**: L187  
**代码引用**:
```python
except (json.JSONDecodeError, Exception):
```
**说明**: `Exception` 已经包含 `json.JSONDecodeError`，后者冗余。  
**修复建议**: 简化为 `except Exception:`。

---

#### MEDIUM-6: index.yaml 中 priority 类型不一致（int vs float）

**文件**: `/opt/data/route-map/index.yaml` (L44, L80)  
**行号**: L44, L80-81  
**代码引用**:
```yaml
pm-agent:
  priority: 3    # int
...
triage:
  priority: 1.5  # float
```
**说明**: 大部分 agent 的 priority 为整数，但 `triage` 使用 `1.5`（浮点数）。代码中 priority 比较有 `1e-9` 容差，但混合类型存在解析风险。  
**修复建议**: 统一为整数，或将 triage 的 1.5 改为 2（程序员 2）让 triage 低于 programmer。

---

#### MEDIUM-7: 测试中 `_clear_cache()` 重复定义

**文件**: `/opt/data/scripts/route_engine.py` (L17-21) vs `/opt/data/tests/test_route_engine.py` (L39-42)  
**行号**: route_engine.py L17, test_route_engine.py L39  
**说明**: 测试文件重新实现了一个 `_clear_cache()` 辅助函数，直接调用 `import route_engine as _re; _re._route_map_cache = None`，而非调用已有的模块级函数。  
**修复建议**: 测试中直接 `from route_engine import _clear_cache` 复用生产代码。

---

#### MEDIUM-8: `_rotate_log()` 中魔法数字 10MB 和 5 份备份

**文件**: `/opt/data/scripts/route_engine.py` (L569-571)  
**行号**: L569-571  
**说明**: `_LOG_MAX_BYTES = 10 * 1024 * 1024` 和 `_LOG_BACKUP_COUNT = 5` 虽然已经是命名常量，但缺少文档说明为什么是 10MB 和 5 份。  
**严重度**: LOW-ish, 但命名常量已够好，仅建议加注释。

Actually this is MEDIUM considering it's already named. Let me reconsider.

---

#### MEDIUM-8 (revised): 测试 12 Agent 全量端到端用例硬编码，覆盖范围有限

**文件**: `/opt/data/tests/test_route_engine.py` (L357-458)  
**行号**: L357-458  
**说明**: `TestRouteIntegration` 中的 12 个端到端测试使用固定的中文输入字符串，每个只测试一个断言。没有参数化测试、没有英文输入测试、没有边界值测试（超长输入、特殊字符）。  
**修复建议**: 使用 `@parameterized.expand` 或子测试（`subTest`）批量测试多语言、多格式输入。

---

#### MEDIUM-9: `run_verification()` 中 stdout/stderr 截断 2000 字符为魔法数字

**文件**: `/opt/data/scripts/chain_executor.py` (L461-462)  
**行号**: L461-462  
**代码引用**:
```python
"stdout": cp.stdout[:2000] if cp.stdout else "",
"stderr": cp.stderr[:2000] if cp.stderr else "",
```
**说明**: 输出截断长度 2000 字符为硬编码，无常量。  
**修复建议**: 提取为 `MAX_OUTPUT_LENGTH = 2000`。

---

### 🟢 LOW (7 项)

#### LOW-1: `chain_executor.py` 中 `yaml` 可选导入可能造成静默失败

**文件**: `/opt/data/scripts/chain_executor.py` (L35-38)  
**行号**: L35-38  
**说明**: `import yaml` 放在 try/except 中，缺失时 `yaml = None`。`run_chain()` 等函数在调用时才会检查并返回 ERROR，但 `_load_state` 中 json 与 yaml 分支已在多处使用。  
**修复建议**: 去掉 try/except 让缺失时直接 ImportError 崩溃（fail fast）。

---

#### LOW-2: `_save_state()` 使用 `f.flush()` + `os.fsync()` 但未处理 `fsync` 异常

**文件**: `/opt/data/scripts/chain_executor.py` (L276-283)  
**行号**: L276-283  
**说明**: 原子写入模式中，`os.fsync()` 在部分系统（如某些容器）可能失败，但当前未处理。  
**修复建议**: 将 `fsync` 包裹在 try/except 中 fallback 到无 fsync。

---

#### LOW-3: `run_verification()` 中 timeout=30 为硬编码

**文件**: `/opt/data/scripts/chain_executor.py` (L452)  
**行号**: L452  
**说明**: `timeout=30` 硬编码，来自 `chain_def` 的命令可能耗时差异巨大。  
**修复建议**: 从 step 的 `completion_contract` 中读取 `timeout` 字段或设为默认值 + step 配置覆盖。

---

#### LOW-4: `spec-agent-chain.yaml` 中 `chain_step_skills` 第 3-4 步技能为空数组

**文件**: `/opt/data/route-map/chains/spec-agent-chain.yaml` (L63-64)  
**行号**: L63-64  
**代码引用**:
```yaml
chain_step_skills:
  spec-agent@3: []
  spec-agent@4: []
```
**说明**: 第 3 步（batch implement）和第 4 步（parallel review）的 skills 为空数组。虽然对于 parallel 步骤 `_validate_skills` 会跳过，但 batch 步骤（step 3）是 serial 类型，明确赋空数组可能掩盖问题。  
**修复建议**: 考虑移除空数组项，或添加注释说明 batch/parallel 步骤无需 skills。

---

#### LOW-5: `triage.yaml` 中 `agent` 字段值是 `spec-agent` 而非 `triage`

**文件**: `/opt/data/route-map/routes/triage.yaml` (L3)  
**行号**: L3  
**代码引用**:
```yaml
agent: spec-agent
```
**说明**: 文件名是 `triage.yaml`，但 `agent` 字段却是 `spec-agent`。虽然 index.yaml 中 `triage` 的 `file: routes/triage.yaml` 正确映射，但 YAML 内部 `agent` 与文件名不一致会造成混淆。  
**修复建议**: 将 `agent: spec-agent` 改为 `agent: triage` 或删除该字段（由 index.yaml 映射）。

---

#### LOW-6: `dual-review-chain.yaml` 中 step 3 的 `data-analyst@0` skill 键无法匹配 `chain_owner` 格式

**文件**: `/opt/data/route-map/chains/dual-review-chain.yaml` (L31)  
**行号**: L31  
**说明**: 见 CRITICAL-1，此处单独列出为 LOW 是因为这是 CRITICAL-1 的一个子案例，但单独来看若 `_validate_skills` 有容错机制（如允许 step agent 名格式），则仅当 skill 查找失败时影响步骤 3 的技能分配。  
**修复建议**: 改为 `dual-review@2: [architecture-review, codebase-inspection]`。

---

#### LOW-7: `test_chain_link.py` 使用全局变量（passed/failed）而非测试框架

**文件**: `/opt/data/scripts/test_chain_link.py` (L10-20, L132-133)  
**行号**: L10-20, L132-133  
**说明**: 使用自定义 `check()` 函数和全局 counter 而非 unittest/pytest。  
**修复建议**: 迁移到 `unittest.TestCase` 以便 CI 集成和断言一致性。

---

## 测试当前状态

运行 `uv run python -m unittest tests.test_route_engine -v`:

```
Ran 69 tests in 27.802s
FAILED (failures=6)
```

### 失败的 6 个测试

| 测试 | 问题 | 对应问题编号 |
|------|------|-------------|
| `test_below_threshold_fallback` | 期望 `llm_fallback`, 得 `unrouted` | CRITICAL-2 |
| `test_empty_scores_fallback` | 期望 `llm_fallback`, 得 `unrouted` | CRITICAL-2 |
| `test_programmer_bug` | 期望 `programmer`, 得 `triage` | HIGH-6 |
| `test_confidence_range` | confidence=1.5 > 1.0 | CRITICAL-4 |
| `test_low_confidence_input_fallsback` | `unrouted` not in `('llm_fallback',)` | CRITICAL-2 |
| `test_programmer` (integration) | 期望 `programmer`, 得 `triage` | HIGH-6 |

### 测试覆盖缺口

| 需要覆盖的模块 | 覆盖状态 |
|---------------|---------|
| `route_engine.py` 路由逻辑 | ✅ 69 个测试（含 6 个失败） |
| `route_engine.py` 性能基准 | ✅ bench_route_engine.py |
| `chain_executor.py` 单元测试 | ❌ 无正式测试文件 |
| `chain_executor.py` 链路测试 | ⚠️ test_chain_link.py（133 行手动脚本） |
| YAML schema 校验 | ❌ 无 |
| 链文件 chain_step_skills 格式校验 | ❌ 无 |

---

## 按文件统计问题数

| 文件 | CRITICAL | HIGH | MEDIUM | LOW |
|------|----------|------|--------|-----|
| `route_engine.py` | 2 | 2 | 4 | 0 |
| `chain_executor.py` | 1 | 4 | 2 | 3 |
| `route-map/chains/*.yaml` | 1 | 0 | 1 | 3 |
| `route-map/routes/*.yaml` | 0 | 1 | 1 | 1 |
| `tests/` | 0 | 1 | 1 | 1 |
| **合计** | **4** | **8** | **9** | **8** |

---

## 评分细则

| 评分项 | 满分 | 扣分 | 得分 | 说明 |
|--------|------|------|------|------|
| 代码可读性 | 20 | -7 | 13 | 命名清晰(+5)，超级函数 advance() 360 行(-4)，load_route_map() 130 行(-2)，YAML agent 字段不一致(-1) |
| 异常处理 | 15 | -5 | 10 | try/except 覆盖较好(+3)，shell=True 无防护(-2)，裸 except(-1)，yaml 静默失败(-1)，无 fsync 异常处理(-1) |
| 性能 | 15 | -6 | 9 | 模块级缓存有效(+3)，_score_skill_matches 重复遍历(-2)，冷加载 O(N_files)(-1)，_save_state 每次 step 写磁盘(-2)，重复加载 skill cache(-1) |
| 测试覆盖 | 20 | -9 | 11 | 69 个测试(+5)，6 个失败(-3)，chain_executor 无正式测试(-4)，无 YAML schema 校验(-1)，手动脚本非框架(-1) |
| 重复代码 | 10 | -6 | 4 | 3 个链结束块相同(-2.5)，branch/batch 处理重复(-2)，测试/生产 _clear_cache 重复(-0.5)，advance 内状态机分支不提取(-1) |
| 类型提示 | 10 | -3 | 7 | route_engine.py 几乎完整(+5)，chain_executor.py 多处遗漏(-2)，start_chain/run_chain/main 无返回类型(-1) |
| 代码异味 | 10 | -4 | 6 | 魔法数字多处(-2)，YAML chain_step_skills 格式错误(-1)，confidence>1.0(-1)，_clear_cache 私有函数直接访问缓存(-0.5)，test_chain_link globals(-0.5) |
| **总分** | **100** | **-39** | **61** | |

---

*本报告为只读分析，未修改任何代码。报告文件已写入 `/opt/data/quality_report.md`。*
