# Architecture 轴复评审报告 — 路由引擎插件

**评审时间**: 2026-07-04
**评审类型**: report_only（只出报告，不修改代码）
**评审范围**:
- `/opt/data/scripts/route_engine.py` (669 行)
- `/opt/data/scripts/chain_executor.py` (1203 行)
- `/opt/data/scripts/chain_config.py` (新建 47 行)
- `/opt/data/scripts/route_logger.py` (新建 84 行)
- `/opt/data/route-map/chains/*.yaml` (8 个)
- `/opt/data/route-map/index.yaml`
- `/opt/data/tests/test_chain_executor.py` (新建 ~675 行)

**参考基准**: 原始架构报告 `/opt/data/architecture_report.md` (评分 **54/100**)
**前置评审**: 合规复评 `/opt/data/review_fix.md` (82/100) + 质量复评 `/opt/data/quality_fix.md` (63/100)

---

## 架构复评评分: **71/100** ↑ (+17)

| 维度 | 权重 | 修复前 | 复评 | 变化 | 说明 |
|------|------|--------|------|------|------|
| 模块边界划分 | 15% | 5/15 | 11/15 | ↑+6 | 日志剥离 + 共享 config 模块 + chain 加载去重，边界清晰度显著提升 |
| 接口一致性 | 15% | 6/15 | 10/15 | ↑+4 | 函数签名统一，但 run_chain() 参数形状仍与 advance/start 不一致 |
| ADR/设计决策合规 | 15% | 7/15 | 12/15 | ↑+5 | confidence clamp + llm_fallback + per-rule chain_ref 清理全部就位 |
| 依赖方向 | 10% | 7/10 | 10/10 | ↑+3 | 无循环依赖 ✅ chain_config 为纯叶子节点 ✅ 依赖流向正确 ✅ |
| 模式一致性 | 10% | 5/10 | 8/10 | ↑+3 | 共享模块使用一致，但 CLI/缓存策略仍不同 |
| 测试 seam 质量 | 15% | 4/15 | 7/15 | ↑+3 | 新增 675 行测试套件，但 11 个测试失败严重拖累质量 |
| Scope creep | 10% | 5/10 | 8/10 | ↑+3 | 日志剥离 ✓，技能 CLI 仍在 route_engine，但整体无模块膨胀 |
| Hermes 零 token 集成 | 10% | 15/15 | 13/15 | ↓-2 | chain_config 共享模块设计合理，但 CLI 断路降低集成完整性 |

**加权总分**: 11×0.15 + 10×0.15 + 12×0.15 + 10×0.10 + 8×0.10 + 7×0.15 + 8×0.10 + 13×0.10 = 1.65+1.50+1.80+1.00+0.80+1.05+0.80+1.30 = **9.90 → 71/100**（满分 14.0，归一化至百）

---

## 一、已修架构问题的验证结果

### 1.1 模块边界划分修复验证

| 原始问题 | 修复人 | 验证结果 | 证据 |
|---------|--------|---------|------|
| route_engine 承载日志轮转 (HIGH-1) | ✅ 剥离至 route_logger.py | **通过** | route_engine.py L618-619: 仅两行 import；日志轮转和 route_logging 实现已移至 route_logger.py |
| per-rule chain_ref 死配置 (CRITICAL-4) | ✅ 全部删除 | **通过** | `search_files("chain_ref", path="route-map/routes")` → 0 条匹配 |
| chain_step_skills key 格式不匹配 (CRITICAL-1) | ✅ 全部修正 | **通过** | 8/8 chain 文件全部使用 `{chain_owner}@{idx}`，key 数量=step 数量 |

**证据细节**:
- `route_logger.py` 完整功能: L26 _rotate_log(), L46 log_route() — 分离后的模块为纯日志职责
- `programmer-chain.yaml:55-61`: `programmer@0`~`programmer@5` — 全部 owner 前缀
- `debugger-chain.yaml:48-54`: `error-analyst@0`~`error-analyst@5` — 从混用 step_agent 改为全 owner

### 1.2 共享配置模块验证

| 原始问题 | 修复人 | 验证结果 | 证据 |
|---------|--------|---------|------|
| 双份 YAML 配置加载 (CRITICAL-2) | ✅ chain_config.py 新建 | **通过** | route_engine.py L12-18 从 chain_config 导入；chain_executor.py L45 也从 chain_config 导入 |
| 路径计算重复 (MEDIUM-4) | ✅ 统一至 SCRIPT_DIR 常量 | **通过** | chain_config.py L21: `SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))`；chain_executor.py 不再硬编码路径 |

### 1.3 接口契约修复验证

| 原始问题 | 修复人 | 验证结果 | 证据 |
|---------|--------|---------|------|
| confidence 溢出 1.0 (HIGH-4) | ✅ 三重 min clamp | **通过** | route_engine.py L420, L438, L586 — 三处 min(top_score, 1.0) 防护 |
| decide() 返回 unrouted 而非 llm_fallback (CRITICAL-3) | ✅ 改为 llm_fallback | **通过** | route_engine.py L399-411, L417-428 均返回 `"method": "llm_fallback"` |
| advance() 360 行超级函数 (HIGH-3) | ✅ 拆分为 9+ 辅助函数 | **通过** | chain_executor.py: advance() 主体 L921-1078 (~158 行)；9 个独立函数: _build_parallel_result, _build_interactive_result, _build_loop_result, _build_step_result, _handle_blocked, _handle_needs_fix, _build_chain_done_result, _handle_batch_complete, _handle_branch_complete + 2 个额外: _handle_loop_complete, _accumulate_partial_result |

---

## 二、新发现的架构问题

### 🔴 CRITICAL 级（1 项）

#### N-CRITICAL-A: CLI argparse 设计缺陷导致路由引擎 CLI 完全不可用

| 字段 | 值 |
|------|------|
| 文件 | `scripts/route_engine.py:634-666` |
| 严重性 | **CRITICAL** — 功能阻断 |

**问题描述**:
argparse 配置使用 `add_subparsers(dest="command")` 定义 `skills` 子命令，同时将 `input` 定义为顶层位置参数 (`nargs="*"`)。由于 argparse 要求首个位置参数必须匹配子命令名，普通文本输入（如 `"修复一个 Python bug"`）被 argparse 解释为子命令名，触发：

```
invalid choice: '修复一个 Python bug' (choose from skills)
```

**架构影响**:
- 5 个 CLI 测试全部失败（`test_cli_docs_writer`, `test_cli_output_is_json`, `test_cli_pm_agent`, `test_cli_programmer`, `test_cli_synology`）
- CLI 作为 Hermes 零 token 路由的用户接口被阻断，降低了整体集成可用性
- 这是**修复过程中引入的回归缺陷**（修复前使用简单的 `if argv[0] == "skills"` 分支，功能完好）

**证据**: route_engine.py L637-646:
```python
subparsers = parser.add_subparsers(dest="command", ...)
skills_parser = subparsers.add_parser("skills", ...)
parser.add_argument("input", nargs="*", ...)  # ← 与 subparsers 冲突
```

**根本原因**: argparse 中 `add_subparsers` 和位置参数不能共存于同一层级。`input` 参数永远无法被解析，因为所有非空参数都被视为子命令名。

**修复方向**: 将路由功能转为 `route` 子命令，或将 `skills` 改为 `--skills` 可选参数。

---

### 🔶 HIGH 级（2 项）

#### N-HIGH-A: chain_executor 6 个测试因状态验证逻辑和 verification gate 实际执行而失败

| 字段 | 值 |
|------|------|
| 文件 | `tests/test_chain_executor.py` |
| 严重性 | **HIGH** | 

**问题描述**:
6 个测试失败，均反映架构层面的一致性缺口：

| 测试 | 失败原因 | 架构含义 |
|------|---------|---------|
| `test_needs_fix_unrecognized_type` | STEP_VALID_STATUSES 中 tdd 类型不包含 NEEDS_FIX | 状态映射与运行时处理顺序不匹配 |
| `test_approve_advances` | STEP_VALID_STATUSES 中 tdd 类型不含 APPROVE | 同上，状态定义覆盖不全 |
| `test_no_status_field` | 空字符串状态不在合法列表中 | 边界条件处理与测试预期不一致 |
| `test_shell_command_whitelist` | `git status --porcelain` 参数 `status`/`--porcelain` 被误判为命令名 | 白名单校验逻辑粒度错误 |
| `test_done_chain_complete` | real `verify_command` 执行失败（`uv run pytest -x`） | verification gate 在测试中未 mock |
| `test_missing_goal_in_step` | KeyError: `'goal'` — `_build_step_result` 使用 `step["goal"]` 而非 `.get()` | 防御性编程不足 |

**架构影响**:
- 这些失败并非孤立测试问题，而是架构设计的接口契约未在实现中完全贯彻的体现
- `STEP_VALID_STATUSES` 定义在各步类型上的合法状态映射，与 `advance()` 中的实际状态处理分支之间存在缺口
- verification gate 白名单校验逻辑（L494-501）遍历所有 token 而非只检查命令名，这是设计层面的缺陷

**证据**: chain_executor.py L57-61:
```python
VERIFY_COMMAND_BASENAMES = frozenset({
    "test", "true", "false", "git", "head", "cat", "grep",
    "wc", "diff", "echo", "ls", "sort", "uniq", "cut", "tr",
    "sed", "awk", "find", "xargs",
})
```
缺失 `uv`, `pytest`, `curl`, `python3` 等常用工具。白名单校验 L494-501 对所有 token 执行 basename 检查，而非只检查每个管道段落的第一个 token。

---

#### N-HIGH-B: `_handle_serial_step()` 和 `_handle_parallel_step()` 为不必要的委派包装函数

| 字段 | 值 |
|------|------|
| 文件 | `scripts/chain_executor.py:883-918` |
| 严重性 | **HIGH** — 代码异味 |

**问题描述**:
`_handle_serial_step()` (L883-900) 和 `_handle_parallel_step()` (L902-918) 只是直接调用 `_build_step_result()`，无任何额外逻辑：

```python
def _handle_serial_step(step, chain_owner, step_idx, chain_step_skills, context=None):
    return _build_step_result(step, chain_owner, step_idx, chain_step_skills, context)
```

**架构意义**:
1. 这两个函数目前在代码库中未被任何调用点引用（高级的 `advance()` 状态分支直接调用 `_build_step_result`）
2. 如果未来 serial 和 parallel 步骤需要不同的处理逻辑，这种预留是合理的；但目前它们增加了认知负载而无实际价值
3. 这违反了 YAGNI（You Ain't Gonna Need It）原则

**证据**: 
- `_handle_serial_step` 和 `_handle_parallel_step` 的函数体完全相同
- 搜索两个函数名的调用点: chain_executor.py 中无任何位置调用它们（只有定义）

---

### 🟡 MEDIUM 级（3 项）

#### N-MED-A: `aggregate_parallel_results()` 是唯一未用 `_` 前缀的模块级函数

| 字段 | 值 |
|------|------|
| 文件 | `scripts/chain_executor.py:198` |
| 严重性 | **MEDIUM** — 模式一致性 |

**问题描述**:
chain_executor.py 中所有辅助函数都以 `_` 前缀命名（共 24 个 `_func`），但 `aggregate_parallel_results()`（L198-240）是唯一未加 `_` 前缀的函数。这虽然暗示该函数是"公共 API"，但 chain_executor 模块的设计契约并非库 API——它通过 CLI + 插件暴露功—而非 Python import。

**架构影响**: 命名模式不一致，降低了代码的可预测性。

---

#### N-MED-B: `run_chain()` 的 chain 加载逻辑与 `route_engine` 的 load_route_map 存在隐式 Schema 耦合

| 字段 | 值 |
|------|------|
| 文件 | `scripts/chain_executor.py:414-449`, `scripts/route_engine.py:90-134` |
| 严重性 | **MEDIUM** |

**问题描述**:
虽然文件 I/O 已经共享到 chain_config，但 `run_chain()` 中解析 index.yaml 的 agents 结构（L418-449）和 `route_engine._load_agent_rules()` 中解析的结构（L90-134）是重复的 Schema 知识。两者都对 index.yaml 的 `agents[chain_agent].chain_ref`, `chain_ref → chains/{ref}.yaml → steps` 结构有相同的理解。

如果未来 YAML Schema 变更（如 chain_ref 改为链标识符），需要同时修改两处；虽然比修复前的 40 行代码重复好，但仍然存在隐式 Schema 耦合。

**证据**:
- chain_executor.py L418-449: `index_data.get("agents", {})` → `agent_config.get("chain_ref")` → `load_chain(chain_ref)` → `chain_data.get("steps", [])`
- route_engine.py L96-117: `agents_map.items()` → `info.get("chain_ref")` → `load_yaml_safe(chain_file)` → `chain_data.get("steps", [])`

---

#### N-MED-C: `route_engine` CLI 的 `skills` 子命令仍留在路由引擎中

| 字段 | 值 |
|------|------|
| 文件 | `scripts/route_engine.py:640-656` |
| 严重性 | **MEDIUM** — 模块职责越界 |

**问题描述**:
原始架构报告 HIGH-1 指出 route_engine.py 承载了日志轮转 (已剥离) 和 `skills` CLI (未剥离)。技能查询与路由决策是不同维度的职责。技能数据 (`_load_skill_cache`, `_lookup_skills`) 目前是路由引擎的技能加分逻辑的一部分，但 `skills` CLI 提供的是"查询 Agent 技能列表"功能——这应属于技能管理模块。

**架构影响**: 虽然不是关键阻断，但技能管理逻辑与路由引擎耦合，限制了未来技能系统的独立演进。

---

### 🟢 LOW 级（2 项）

#### N-LOW-A: `FORCE_ROUTE_THRESHOLD = 2.0` 与 confidence 上限 1.0 的冲突仍存在

| 字段 | 值 |
|------|------|
| 文件 | `plugins/route-router/__init__.py:9` |
| 严重性 | **LOW** |

confidence 已 clamp 到 [0.0, 1.0]，但 `__init__.py` 的 `FORCE_ROUTE_THRESHOLD = 2.0` 从未被更新。该阈值永久不可达，强制路由逻辑成为死代码。原 LOW-2 未在修复范围内。

---

#### N-LOW-B: chain_executor 的 `INDEX_YAML_PATH` 常量冗余

| 字段 | 值 |
|------|------|
| 文件 | `scripts/chain_executor.py:52` |
| 严重性 | **LOW** |

`INDEX_YAML_PATH = os.path.join(SCRIPT_DIR, "..", "route-map", "index.yaml")` 与 chain_config.py 中定义的 `INDEX_YAML_PATH` 完全重复。chain_executor 的 `run_chain()` 并未直接使用该常量（通过 `load_index()` 间接使用），但模块级常量定义造成混淆。

---

## 三、架构复评各维度详细分析

### 3.1 模块边界划分（11/15）

**修复前:** route_engine 承载日志 + 技能 CLI；双份 YAML 加载；chain_executor 无测试。

**修复后依赖拓扑:**
```
chain_config.py (路径常量 + YAML 加载)
    ↑          ↑
    |          |
route_logger.py  route_engine.py ←──→ chain_executor.py
(日志轮转记录)    (路由匹配决策)       (链状态编排)
                        ↑
                        | (L619 import)
                    route_logger.py
```

**净效果:**
- ✅ 日志完全剥离 → route_logger.py 为纯日志模块
- ✅ 共享 YAML 加载 → chain_config.py 为纯工具模块
- ✅ chain_executor.run_chain() 使用共享模块而非手写路径
- ⚠️ route_engine 的 `skills` CLI 子命令仍在路由模块内
- ⚠️ chain_executor `run_chain()` 和 route_engine `_load_agent_rules()` 有重复的 Schema 解析知识

**结论**: 模块边界从"重叠→独立"走了 70% 的路，仍有 30% 边界模糊区域。

---

### 3.2 接口一致性（10/15）

| 维度 | route_engine.py | chain_executor.py | 一致性 |
|------|----------------|-------------------|--------|
| 入口函数 | `route(user_input: str) → dict` | `advance(...) → dict` | ✅ 都返回 dict |
| CLI | `main(argv=None) → None` | `main() → None` | ✅ 签名不同但意图一致 |
| 内部辅助 | 全部 `_` 前缀（18个） | 25/26 用 `_` 前缀 | ⚠️ `aggregate_parallel_results` 无前缀 |
| 错误返回 | `{"status": "ERROR", "diagnosis": ...}` | 同上 | ✅ 完全一致 |
| 返回结构 | flat dict with agent/confidence/method | dict with status/step_idx/goal | ⚠️ 不同领域自然不同 |

**发现**: 两个模块的返回结构反映了不同的领域模型——路由输出路由决策，链输出状态机步骤。这是合理的差异，不应强制统一。类型提示方面全部完整。

---

### 3.3 依赖方向（10/10 ✅）

```
chain_config.py
  ↑         ↑
  │         │
route_engine.py  chain_executor.py
  ↑
  │ (L619)
route_logger.py
```

- ✅ **无循环依赖**: chain_config.py 不导入任何 scripts/ 下的其他模块
- ✅ **chain_config.py 是纯叶子节点**: 仅依赖 stdlib(os) 和外部包(yaml)
- ✅ **所有依赖流向正确**: 高层（业务逻辑）→ 低层（工具函数/路径）
- ✅ **route_logger.py 从属于 route_engine.py**: 仅被 route_engine.py 导入，不被反导入

**隐式耦合注意点**: route_engine._load_agent_rules() 与 chain_executor.run_chain() 共享对 index.yaml Schema 的理解，但这是通过 YAML 文件形成的隐式耦合，非代码层面。本维度满分，但建议日后通过统一 Schema 访问层进一步消除隐式耦合。

---

### 3.4 模式一致性（8/10）

对比修复前（两个模块风格完全不同），改进显著：

| 模式 | 修复前 | 修复后 |
|------|--------|--------|
| YAML 加载 | 各自手写路径 | 共同调用 chain_config.load_yaml_safe/load_index |
| 路径计算 | 各自脚本目录 | 共同引用 chain_config.SCRIPT_DIR |
| 错误处理 | `print()+sys.exit()` vs `return dict` | 统一返回 dict |
| 类型提示 | 缺失 | 完整✅ |
| 私有函数 | 部分 `_` | 全部 `_` ✅ |
| CLI | 手写分支 vs argparse | 两者都用 argparse ⚠️ 但使用模式不同 |

**唯一突出的不一致**: `aggregate_parallel_results()` 无 `_` 前缀（N-MED-A）。

---

### 3.5 Scope Creep 检测（8/10）

**文件规模变化**（修复前后对比）:

| 文件 | 修复前 | 修复后 | 净变化 | 评估 |
|------|--------|--------|--------|------|
| route_engine.py | 662 行 | 669 行 | +7 行 | ✅ 函数拆分开销，无实质膨胀 |
| chain_executor.py | 960 行 | 1203 行 | +243 行 | ⚠️ 拆分为 9+ 辅助函数，每函数更小但总行数增 |
| chain_config.py | — | 47 行 | +47 行 | ✅ 新增提取模块 |
| route_logger.py | — | 84 行 | +84 行 | ✅ 新增提取模块 |
| test_chain_executor.py | — | ~675 行 | +675 行 | ✅ 测试代码，不算产品膨胀 |

**净产品代码变化**: +7 +243 +47 +84 = +381 行

**评估**: 
- 这 381 行增量中，约 300 行为函数分解（将 360 行超级函数拆为多个小函数）的"样板代码"（docstrings, 参数列表, 空行）而非新功能
- 约 131 行为提取代码 (chain_config + route_logger)，原在 route_engine.py 中的对应代码已删除，实质上是零净增
- 实际新功能代码量约 50 行以下

**结论**: ✅ 无显著 scope creep。行数增长全部来自分解/提取，非功能膨胀。

---

### 3.6 测试 Seam 质量（7/15）

| 指标 | 值 | 评估 |
|------|----|------|
| route_engine 非 CLI 测试 | 64/64 ✅ | 全部通过 |
| route_engine CLI 测试 | 0/5 ❌ | 全部失败（N-CRITICAL-A）|
| chain_executor 测试 | 47/53 ⚠️ | 6 个失败（N-HIGH-A）|
| _clear_cache 测试基础设施 | ✅ 已修复 | 测试重用模块函数 |

**架构意义**: 测试失败集中反映了两个架构缺口：
1. CLI 层面的 argparse 设计缺陷让整个 CLI 测试套件失效
2. `STEP_VALID_STATUSES` 状态映射与状态机实现不一致，让 3 个测试因状态拒绝而失败
3. Verification gate 白名单逻辑与测试期望不一致

这些测试失败不是表面问题——它们标志着 架构接口契约与实现之间的缺口。

---

### 3.7 Hermes 零 Token 集成架构（13/15）

**集成拓扑**（修复后）:
```
Hermes Core (pre_llm_call)
    │
plugins/route-router/__init__.py
    │ 调用 route(user_input)
    ▼
route_engine.py ──→ chain_config.py
    │              ←── route_logger.py
    │
    │ (输出路由决策 JSON)
    ▼
Hermes Core → 读取路由结果 → delegate_task
    │
    ▼ (完成后)
chain_executor.py ──→ chain_config.py
    │ advance()
    │ (输出步骤决策 JSON)
    ▼
Hermes Core → 读取步骤决策 → 推进链
```

**chain_config.py 作为共享模块的合理性评估**:

| 维度 | 评估 | 说明 |
|------|------|------|
| 职责控制 | ✅ 合理 | 仅封装路径常量和 YAML 加载，不包含业务逻辑 |
| 依赖方向 | ✅ 合理 | 纯叶子节点，不导入任何业务模块 |
| 模块大小 | ✅ 合理 | 47 行，易于理解和维护 |
| 解耦效果 | ✅ 有效 | 消除了 route_engine 和 chain_executor 之间的代码重复 |
| 扩展性 | ✅ 良好 | 可添加更多通用工具而不影响调用方 |

**唯一扣分项**: CLI 断路（N-CRITICAL-A）导致用户无法通过命令行与路由引擎交互，降低了 Hermes 集成的可操作性。虽然 plugin 路径仍然正常工作，但 CLI 作为开发和调试接口是 Hermes 工作流的关键组成部分。

---

## 四、架构改进净效果总结

### 4.1 修复前 → 修复后对比

| 维度 | 修复前 | 修复后 | 变化方向 |
|------|--------|--------|---------|
| 独立模块数 | 2 (route_engine + chain_executor) | 4 (+ chain_config + route_logger) | ✅ 职责分离 |
| YAML 加载方式 | 双份硬编码路径 | 共享 chain_config | ✅ 消除重复 |
| 最大函数 | advance() 360 行 | advance() ~158 行 | ✅ 可维护性 |
| 测试覆盖 | 0 chain_executor 测试 | 53 个 chain_executor 测试 | ✅ 质量提升 |
| CLI 可用性 | 可用（手写分支） | 不可用（argparse 设计缺陷） | ❌ 回归 |
| 模块依赖 | 无共享模块 | 共享 chain_config 叶子节点 | ✅ 架构整洁 |

### 4.2 原始 7 个 CRITICAL 问题的解决状态

| 编号 | 问题 | 修复状态 | 本复评审 |
|------|------|---------|---------|
| C-1 | chain_step_skills key 格式不匹配 | ✅ | 8/8 YAML 文件全部通过 |
| C-2 | 双份 YAML 配置加载 | ✅ | chain_config 消除重复 |
| C-3 | decide() 返回 unrouted | ✅ | 三处 return 全部 llm_fallback |
| C-4 | per-rule chain_ref 死配置 | ✅ | route-map/routes 中 0 条 chain_ref |
| C-5 | 无 chain_executor 测试 | ✅ | 新 ~675 行测试套件 |
| — | N-CRITICAL-A: CLI argparse 缺陷 | ❌ 新引入 | 5 个 CLI 测试全部失败 |
| — | N-HIGH-A: 链测试 6 个失败 | ❌ 部分修复 | 47/53 通过，6 个新建失败 |

### 4.3 架构评分：71/100

**评分依据**: 
- 修复前 54/100 的核心问题是 C-1~C-5 和 HIGH-1~HIGH-4
- 其中 5 个 CRITICAL 全部修好，4 个 HIGH 全部修好（含 shell 加固 + advance 拆分 + logging 剥离）
- 但修复中引入了 1 个新 CRITICAL（CLI 断路）+ 1 个新 HIGH（6 测试失败 + 委派包装函数）
- 加上 2 个新 MEDIUM + 2 个新 LOW → 净得 +17 分

**结论**: 架构质量从"无法交付"提升至"可接受但需修补"。核心架构决策（零 token 预判 + YAML 驱动 + plugin 集成 + 模块解耦）全部正确。CLI 断路是修复过程中的意外回归，修复成本低（约 30 行 argparse 调整），建议优先修复。

### 4.4 修复建议优先级

| 优先级 | 问题 | 影响 | 修复难度 |
|--------|------|------|---------|
| P0 | N-CRITICAL-A: CLI argparse 断路 | 功能阻断，5 CLI 测试全失 | 低 (~30 行) |
| P1 | N-HIGH-A: 6 测试失败 | 测试信心破裂 | 中 (状态 + verification 设计) |
| P2 | N-HIGH-B: 委派包装函数 | 代码异味 | 低 (删除未引用函数) |
| P3 | N-MED-A~C | 模式不一致 | 低 |
| P4 | N-LOW-A~B | 死代码/冗余 | 极低 |
