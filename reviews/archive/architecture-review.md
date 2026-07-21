# Architecture 轴评审报告 — 路由引擎插件

**评审时间**: 2026-07-04
**评审范围**: 
- `/opt/data/scripts/route_engine.py` (662 行)
- `/opt/data/scripts/chain_executor.py` (960 行)
- `/opt/data/route-map/index.yaml` + `routes/*.yaml` (15 个) + `chains/*.yaml` (8 个)
- `/opt/data/tests/test_route_engine.py` (563 行, 69 个测试)
- `/opt/data/tests/bench_route_engine.py` (96 行)
- `/opt/data/plugins/route-router/` (plugin.yaml, router.py, __init__.py)
- `/opt/data/skills/multi-agent-arch/zero-token-routing/` (设计决策文档)

**评审维度**: 模块边界 / 接口一致性 / ADR合规 / 依赖方向 / 模式一致性 / 测试 seam / Scope creep / Hermes 集成

---

## 架构评分: **54/100**

| 维度 | 权重 | 得分 | 摘要 |
|------|------|------|------|
| 模块边界划分 | 15% | 5/15 | 职责交叉严重，chain 配置加载重复，route_engine 越界管理 chain 元数据 |
| 接口一致性 | 15% | 6/15 | method 命名、返回结构、参数列表风格不一致，decide() 缺少 matched_rules |
| ADR/设计决策合规 | 15% | 7/15 | strong-binding ADR 半实现，dead config 残留，confidence 溢出 1.0 |
| 依赖方向 | 10% | 7/10 | 无循环依赖 ✓，但通过 YAML 文件形成隐式耦合 |
| 模式一致性 | 10% | 5/10 | 状态管理、错误处理、CLI 入口风格完全不同 |
| 测试 seam 质量 | 15% | 4/15 | chain_executor 零测试，6 个 route_engine 测试因架构变更而失败 |
| Scope creep | 10% | 5/10 | 两个模块都承载了不应属于自己的功能 |
| Hermes 零 token 集成 | 10% | 15/15 | 插件架构合理，懒加载 + 预热模式恰当 |

---

## 发现的问题清单

### 🔴 CRITICAL（5 项）

---

#### CRITICAL-1: chain_step_skills key 格式在 YAML 和代码间不匹配

**文件**: `/opt/data/route-map/chains/debugger-chain.yaml`, `programmer-chain.yaml`, `dual-review-chain.yaml`, `spec-agent-chain.yaml`, `follow-process-chain.yaml`
**行号**: 各 chain 文件的 `chain_step_skills` 区块
**严重性**: **CRITICAL** — 功能阻断

**说明**:
`_validate_skills()` (chain_executor.py L227-240) 和 `_build_step_result()` (L338-339) 使用 `{chain_owner}@{step_idx}` 格式构建 skills key。但 YAML chain 文件中的 `chain_step_skills` 使用 `{step_agent}@{idx}` 格式（即步骤中出现的 agent 名），而非 `{chain_owner}@{idx}`。

**证据**:
- `dual-review-chain.yaml` L29-30: `dual-review@0: [code-review, codebase-inspection]` — 这里 `dual-review` 既是 chain_owner 也是 owner 字段，格式正确
- `debugger-chain.yaml` (上一步评审报告指出): key 用 `programmer@0`, `programmer@1`... 但 chain_owner = `error-analyst`
- chain_executor.py L237: `key = f"{chain_owner}@{i}"` — 预期格式确定
- `dual-review-chain.yaml` L30-31: `dual-review@1: [receiving-code-review]` 但 L31 定义的是 `data-analyst@0: [architecture-review, codebase-inspection]` — key 前缀不统一（`dual-review@1` vs `data-analyst@0`）

**修复建议**: 
统一 key 格式标准——要么全部使用 `{chain_owner}@{step_idx}`，要么全部使用 `{step_agent}@{step_idx}`。建议使用 `{chain_owner}@{step_idx}` 并修正所有 chain YAML 文件。

---

#### CRITICAL-2: route_engine.py 和 chain_executor.py 独立重复加载 YAML 配置

**文件**: `/opt/data/scripts/route_engine.py` L42-172 和 `/opt/data/scripts/chain_executor.py` L363-409
**严重性**: **CRITICAL** — 双份配置解析，同份 YAML 变更需改两处代码

**说明**:
`load_route_map()` 在 route_engine.py 中完整解析 index.yaml + routes/*.yaml + chains/*.yaml（含 chain_data, chain_step_skills, chain_keywords, report_only 等完整 chain 元数据）。而 chain_executor.py 的 `run_chain()` 方法（L363-409）又独立重新解析 index.yaml 和 chains/*.yaml——完全相同的文件、相同的字段、相同的错误处理。

**证据**:
- route_engine.py L84-114: 读取 `info.get("chain_ref")` → 加载 chain 文件 → 提取 `steps`, `chain_step_skills`, `report_only`
- chain_executor.py L371-409: 以 `INDEX_YAML_PATH` 为入口，遍历 `agents[chain_agent].chain_ref` → 再次加载 chain 文件
- 重复代码约 40 行，逻辑几乎一致

**修复建议**:
将 chain 配置加载逻辑抽取为共享模块（如 `scripts/chain_config.py`），route_engine.py 和 chain_executor.py 共同调用。或者让 chain_executor.py 依赖 route_engine.py 的 `load_route_map()` 返回结果。

---

#### CRITICAL-3: decide() 返回 `method: "unrouted"` 但与设计决策 ADR 冲突

**文件**: `/opt/data/scripts/route_engine.py` L371-444
**行号**: L382-410
**严重性**: **CRITICAL** — 架构决策未完全贯彻

**说明**:
strong-binding 部署文档（`references/strong-binding-deployment.md`）明确用 `unrouted` 替换了 `llm_fallback`，但：
1. 测试用例（test_route_engine.py L306, L323, L458）仍然断言 `method == "llm_fallback"`
2. 插件 `__init__.py` (L33-36) 对 `unrouted` 的处理是"不注入，但返回基本信息"，而 strong-binding ADR 要求"上报用户，请求明确意图"
3. 部分代码路径（`test_low_confidence_input_fallsback`）调用 `route()` 整体流程时也期待 `llm_fallback`，但实际得到 `unrouted`

**证据**:
- route_engine.py L399-411: 低分返回 `"method": "unrouted"` 
- test_route_engine.py L306: `self.assertEqual(result["method"], "llm_fallback")` → FAIL
- strong-binding-deployment.md L5-8: "The route engine originally had an `llm_fallback` path... This created a false sense of coverage"
- main-agent-workflow-integration.md L34: "→ method == 'unrouted' → 上报用户，请求明确意图"

**修复建议**:
统一所有代码和测试使用 `unrouted` method 名称。更新插件 `__init__.py` 在 `unrouted` 时返回适当的"请明确意图"提示，而非静默跳过。

---

#### CRITICAL-4: per-rule chain_ref 字段全部为 dead config，但散布在 2 个 YAML 文件中

**文件**: `/opt/data/route-map/routes/programmer.yaml` (15 处), `spec-agent.yaml` (11 处), `dual-review.yaml` (注释标记已迁移)
**行号**: programmer.yaml L10, L16, L22, L28, L34, L41, L48, L54, L174, L180, L186, L192, L198, L204, L210; spec-agent.yaml L13, L18, L23, L28, L33, L38, L43, L48, L54, L60, L65
**严重性**: **CRITICAL** — 误导性配置，说明配置模式存在架构错误

**说明**:
`load_route_map()` (route_engine.py L84-114) 仅从 `index.yaml` 的 agent 条目中读取 `chain_ref` 字段。per-rule 级别的 `chain_ref` 字段虽然存在于 YAML 文件（programmer.yaml 15 处, spec-agent.yaml 11 处），但从未被任何代码解析或使用。dual-review.yaml 的注释 `# chain_ref: dual-review-chain (moved to index.yaml agent entry)` 表明团队已意识到此问题但未彻底清理。

**证据**:
- route_engine.py L84-114: `chain_ref = info.get("chain_ref")` — 只读 index-level，不读 rule-level
- programmer.yaml L10: `chain_ref: programmer-chain` — 在 rule 级别，永不生效
- route_engine.py 的 `load_route_map()` 遍历 `agent_data.get("rules", [])` (L117) 但从不检查 rule 中的 `chain_ref`

**修复建议**:
删除 route YAML 文件中所有 per-rule 级别的 `chain_ref` 字段，统一由 index.yaml 的 agent 级别 `chain_ref` 控制。或者如果规则级别的 chain_ref 有设计意图，则更新 `load_route_map()` 读取它。

---

#### CRITICAL-5: 无 chain_executor.py 单元测试，关键状态机逻辑零覆盖

**文件**: 无测试文件（`/opt/data/tests/` 下无 `test_chain_executor.py`）
**严重性**: **CRITICAL** — 960 行状态机代码无保护

**说明**:
chain_executor.py 有 960 行，实现了复杂的链状态机（`advance()` 函数 360+ 行，处理 serial/parallel/interactive/loop/batch 等 8+ 种状态路径）。但完全没有任何单元测试。而 `advance()` 涉及以下高风险逻辑：
- 文件状态读写（`_load_state`/`_save_state`）
- Verification gate 执行 shell 命令（`run_verification`）
- branch/batch 结果聚合
- retry 循环 + retry count 限制

**证据**:
- `search_files` 在 `tests/` 下找不到任何 chain 相关测试文件
- chain_executor.py L489-848: `advance()` 长达 359 行
- quality_report.md 已指出此问题（"chain_executor 无正式单元测试"）

**修复建议**:
为 chain_executor.py 创建完整的单元测试套件，至少覆盖：
- `start_chain()` / `advance()` 基础流程
- 所有 step 类型（serial / parallel / interactive / loop）
- 状态持久化（`_load_state`/`_save_state`）
- Verification gate（mock subprocess.run）
- retry 逻辑
- 边界条件（空 chain_def、非法 task_id、state 损坏）

---

### 🔶 HIGH（4 项）

---

#### HIGH-1: route_engine.py 承载日志轮转和技能查询 CLI，超出路由职责

**文件**: `/opt/data/scripts/route_engine.py`
**行号**: L569-630（日志系统），L646-654（skills CLI）
**严重性**: **HIGH** — 模块耦合度高

**说明**:
`route_engine.py` 本应是纯路由引擎（加载规则 → 匹配 → 评分 → 决策），但包含了：
1. JSONL 日志系统（`_rotate_log()` + `log_route()`，L569-630），含文件轮转、日期格式化、flag 标记
2. CLI subcommand `skills <agent_name>`（L646-654）——技能查询本应属于独立的技能管理模块

**证据**:
- route_engine.py L633-658: `main()` CLI 支持 `route <text>` 和 `skills <agent_name>` 两种子命令
- `_LOG_FILE`, `_LOG_MAX_BYTES`, `_LOG_BACKUP_COUNT` 是模块级常量
- `_rotate_log()` L574-591 实现完整的日志轮转算法

**修复建议**:
将日志功能抽离为独立的 `route_logger.py` 模块，route_engine.py 仅导入调用。将 `skills` CLI 移出或标注为 `route_engine skills` 子命令在 main() 中分发。

---

#### HIGH-2: chain_executor.py 的 run_verification() 执行 shell 命令，引入安全风险

**文件**: `/opt/data/scripts/chain_executor.py`
**行号**: L443-483
**严重性**: **HIGH** — 系统安全

**说明**:
`run_verification()` 使用 `subprocess.run(cmd, shell=True, ...)` 执行来自 YAML chain 配置的 `verify_command`。虽然 chain YAML 文件受信任，但：
1. `shell=True` 在 L450 开放了命令注入通道
2. L449 注释承认"不能对整个命令做 shlex.quote，因为可能含管道/重定向"
3. command 参数来自 YAML 文件（外部数据），未做内容校验

**证据**:
- chain_executor.py L448-454: `subprocess.run(cmd, shell=True, capture_output=True, timeout=30, text=True)`
- 注释 L444-447: 承认 `shell=True` 下保护不足
- `completion_contract` 字段来自 chain YAML 文件，虽然项目内部可控，但缺乏白名单机制

**修复建议**:
1. 为 `verify_command` 建立命令白名单（允许的命令模板集）
2. 或使用 `shlex.split()` 避免 `shell=True`
3. 或实现命令验证器确保只执行预定义的安全命令

---

#### HIGH-3: advance() 360 行超级函数，状态处理逻辑大量重复

**文件**: `/opt/data/scripts/chain_executor.py`
**行号**: L489-848
**严重性**: **HIGH** — 可维护性

**说明**:
`advance()` 函数长达 360 行，处理 8 个不同的 last_result 状态分支（init / batch_complete / branches_complete / loop_complete / branch_index / batch_index / NEEDS_FIX 等）。其中"链结束返回"DONE"的代码块在 L565-577、L602-617、L627-641、L830-846 重复了 4 次，逻辑完全一致但散落在不同 if 分支中。

**证据**:
- L565-577: batch_complete → DONE 路径
- L602-617: branches_complete → DONE 路径
- L627-641: loop_complete → DONE 路径
- L830-846: DONE/APPROVE → DONE 路径
- 4 段代码几乎完全重复（return 结构一致）

**修复建议**:
将"链完成"逻辑抽取为 `_chain_complete(state, report_only)` 共享函数，4 处调用点统一归约。

---

#### HIGH-4: confidence 可能超过 1.0 上限，破坏契约语义

**文件**: `/opt/data/scripts/route_engine.py`
**行号**: L447-564 (route 函数整体)
**严重性**: **HIGH** — 接口契约被违反

**说明**:
`route()` 返回的 `confidence` 字段合约约定范围是 `[0.0, 1.0]`，但实际上：
- Override 匹配强制返回 `confidence: 1.0`（L476）
- chain_keyword 匹配返回 `confidence: 1.0`（L508）
- 但如果 override 匹配且叠加 skill 加分（`_score_skill_matches`, L526-536），score 会加到 1.2-1.5
- 测试 `test_confidence_range` (L447) 验证 `assertLessEqual(result["confidence"], 1.0)` 失败，实际得到 1.5

**证据**:
- route_engine.py L476: override 返回 `"confidence": 1.0`
- route_engine.py L526-536: skill_scores 对 override 路径不起作用（override 提前 return 在 L474）
- 但正常 evaluate+decide 路径 L538-539 中, `decide()` 从 `scored_results` 提取分数，可能 > 1.0
- test_route_engine.py L447: `self.assertLessEqual(result["confidence"], 1.0)` → FAIL (1.5)

**修复建议**:
在 `route()` 返回前将 confidence clamp 到 `[0.0, 1.0]` 范围，或更新接口契约文档为 `[0.0, ∞)`。

---

### 🟡 MEDIUM（5 项）

---

#### MEDIUM-1: two modules have different cache management strategies

**文件**: `/opt/data/scripts/route_engine.py` (module-level cache) vs `/opt/data/scripts/chain_executor.py` (file-based state)
**行号**: route_engine.py L13-21, chain_executor.py L250-283
**严重性**: MEDIUM

**说明**:
route_engine.py 使用模块级全局变量缓存（`_route_map_cache`, `_skill_cache`），内存驻留不过期。chain_executor.py 使用文件系统持久化状态（`_load_state`/`_save_state` 至 `/opt/data/.shared/<task_id>/chain-state.json`）。两种策略缺乏一致性——测试中需要额外调用 `_clear_cache()` 来 reset 路由缓存，但 chain_executor 无对应测试基础设施。

**修复建议**:
统一缓存策略文档，明确何时用内存缓存、何时用文件持化。route_engine.py 可增加 TTL 机制。

---

#### MEDIUM-2: chain_executor 的 sys.exit(1) 在 CLI 和库函数间混用

**文件**: `/opt/data/scripts/chain_executor.py`
**行号**: L875, L882, L887, L895, L903, L910, L918, L925, L932, L943, L951
**严重性**: MEDIUM

**说明**:
`main()` 中多处直接 `sys.exit(1)` 输出 JSON 错误，但这些路径也通过 `start_chain()`、`run_chain()` 等纯函数暴露。当其他模块以库方式调用这些函数时，`sys.exit()` 会导致整个进程终止，而非返回错误值。

**证据**:
- L875: `sys.exit(1)` in `main()` 错误处理
- `run_chain()` (L363-409) 本身返回 `{"status": "ERROR", ...}` 而非 exit，但调用链后 `main()` 用 sys.exit 处理
- 混合模式增加了单元测试难度（需要 mock sys.exit）

**修复建议**:
`main()` 应收集所有错误后一次 return 非零退出码，函数内部不直接 exit。

---

#### MEDIUM-3: route_engine 的 _load_skill_cache JSON 错误处理过于宽松

**文件**: `/opt/data/scripts/route_engine.py`
**行号**: L175-188
**严重性**: MEDIUM

**说明**:
`_load_skill_cache()` 使用 `except (json.JSONDecodeError, Exception)` 的宽泛捕获，静默吞掉所有异常返回 None。当 `.skill-cache.json` 损坏时，`_lookup_skills()` 返回空列表，路由决策不会报错但丢失了技能信息——静默降级。

**证据**:
- route_engine.py L183-188: `except (json.JSONDecodeError, Exception): return None`
- L191-199: `_lookup_skills()` 接收 None 返回 `([], [])` 无告警

**修复建议**:
至少记录 warning 日志。在生产环境可考虑发送警报。

---

#### MEDIUM-4: chain_executor 的 run_chain() 重新实现 route_engine 的 YAML 加载路径解析逻辑

**文件**: `/opt/data/scripts/chain_executor.py`
**行号**: L371-401
**严重性**: MEDIUM

**说明**:
`run_chain()` 中硬编码了 `_SCRIPT_DIR_CHAIN` 和 `INDEX_YAML_PATH`，又硬编码 `_route_map_dir` 的路径计算。这和 route_engine.py 中 `_ROUTE_MAP_DIR` 的计算完全一致但独立实现。任何路径结构调整都需要两处同步修改。

**证据**:
- chain_executor.py L41: `_SCRIPT_DIR_CHAIN = os.path.dirname(os.path.abspath(__file__))`
- chain_executor.py L393: `_route_map_dir = os.path.join(_SCRIPT_DIR_CHAIN, "..", "route-map")`
- route_engine.py L30-31: 相同的路径计算逻辑

**修复建议**:
抽取共享路径常量到 `scripts/paths.py` 或类似共享模块。

---

#### MEDIUM-5: 测试中 _clear_cache() 辅助函数与 route_engine 模块级函数同名

**文件**: `/opt/data/tests/test_route_engine.py`
**行号**: L39-42
**严重性**: MEDIUM

**说明**:
测试文件定义了自己的 `_clear_cache()` 函数（L39-42），与 route_engine 模块级 `_clear_cache()`（L17-21）功能相近但实现不同。
测试版本调用了 `import route_engine as _re; _re._route_map_cache = None`。
模块版本使用了 `global _route_map_cache, _skill_cache` 同时清空两者。
测试版本未清空 `_skill_cache`。

**证据**:
- test_route_engine.py L39-42: `_re._route_map_cache = None` — 只清 route_map 不清 skill_cache
- route_engine.py L17-21: `global _route_map_cache, _skill_cache` — 两者都清

**修复建议**:
测试中的 `_clear_cache()` 应重用模块函数或完全同步两者的语义（清除所有缓存）。

---

### 🟢 LOW（3 项）

---

#### LOW-1: `decide()` 的 `matched_rules` 字段在所有路径中都返回空数组

**文件**: `/opt/data/scripts/route_engine.py`
**行号**: L382-444（3 个 return 路径中的 `matched_rules: []`）
**严重性**: LOW

**说明**:
`decide()` 在三个返回路径（空评分 / 低分 unrouted / tiebreak / auto）中都设置 `matched_rules: []`。实际上，调用方 `route()` (L541-549) 在 decide() 返回后又从 `scored_results[0][2]` 提取匹配规则覆盖到 `result["details"]["matched_rules"]`。所以 `decide()` 内部的 `matched_rules` 是死代码。

**修复建议**:
删除 `decide()` 中和 matched_rules 相关的逻辑，让 route() 函数统一管理。

---

#### LOW-2: `__init__.py` 中 FORCE_ROUTE_THRESHOLD = 2.0 与 confidence 上限 1.0 冲突

**文件**: `/opt/data/plugins/route-router/__init__.py`
**行号**: L9
**严重性**: LOW

**说明**:
`FORCE_ROUTE_THRESHOLD = 2.0` 触发高置信强制路由，但 confidence 上限在正常情况下为 1.0（即使目前有 >1.0 的 bug）。该阈值永远无法达到，除非 confidence 上限被重新调整。导致强制路由功能实际不可用。

**修复建议**:
将 FORCE_ROUTE_THRESHOLD 调整为 0.9 或 1.0，并确保 confidence 被 clamp 到 `[0, 1]`。

---

#### LOW-3: 路由引擎的 `main()` CLI 缺少标准 subparser，混合 argv 处理

**文件**: `/opt/data/scripts/route_engine.py`
**行号**: L634-658
**严重性**: LOW

**说明**:
`main()` 使用简单的 `if argv[0] == "skills"` 分支而非 Python argparse 标准 subparser。当 future 添加更多子命令时，手写分支会扩散。
同时 chain_executor.py 使用完整的 argparse subparser（L851-869），风格不一致。

**修复建议**:
将 route_engine.py 的 main() 改为 argparse subparser 风格以保持一致。

---

## 详细架构分析

### 1. 模块边界划分

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│      route_engine.py         │     │      chain_executor.py        │
│                              │     │                              │
│  load_route_map()  ──────────┼──YAML──→  run_chain() 重复加载     │
│  evaluate()                  │     │  advance() 状态机            │
│  decide()                    │     │  run_verification()          │
│  route()                     │     │  aggregate_parallel_results()│
│                              │     │                              │
│  ← scope creep:              │     │  ← scope creep:              │
│    _rotate_log()             │     │    run_verification()        │
│    log_route()               │     │    (shell commands)          │
│    skills CLI                │     │                              │
└─────────────────────────────┘     └──────────────────────────────┘
```

**核心问题**: route_engine.py 负责**加载 chain 配置**（甚至扫描 chains/ 目录），但 chain_executor.py 又**独立重复加载**同样的配置。两个模块通过 YAML 文件形成隐式耦合，但代码层面无依赖关系——意味着更改 YAML schema 需要两边同步修改。

### 2. 依赖方向

```
Hermes Core / LLM
    │
    ▼
plugins/route-router/__init__.py
    │
    ▼
plugins/route-router/router.py
    │ 依赖 route_engine (正确方向)
    ▼
scripts/route_engine.py  ──→  route-map/index.yaml
                                   │
                                   ▼
scripts/chain_executor.py  ──→  route-map/index.yaml (重复依赖)
                                   │
                                   ▼
                              route-map/chains/*.yaml (双份依赖)
```

依赖方向**整体正确**（高层 → 低层，无循环依赖），但**非共享加载**导致隐式耦合。

### 3. ADR 合规对照表

| 设计决策 | 来源 | 合规状态 | 证据 |
|---------|------|---------|------|
| `unrouted` 替换 `llm_fallback` | strong-binding-deployment.md | ❌ 部分实现 — 代码改了但测试/插件未同步 | L399 返回 unrouted, 测试断言 llm_fallback |
| Route engine 在 delegate_task 之上 | hermes-native-vs-zero-token.md | ✅ 正确 | `route()` 返回 agent+chain, 由主 Agent 调用 delegate_task |
| YAML 驱动，不代码驱动 | zero-token-routing SKILL.md | ✅ 基本符合 | 规则在 YAML, 但 chain 配置有重复 |
| `unrouted` → "上报用户，请求明确意图" | main-agent-workflow-integration.md | ❌ 未实现 | 插件返回空上下文信息而非用户提示 |
| 两轴分离: routing vs execution | hermes-native-vs-zero-token.md | ⚠️ 基本符合但执行层边界模糊 | chain 加载逻辑在 routing 层 |

### 4. Hermes 零 token 集成架构

插件模式（pre_llm_call 钩子）是**正确选择**：
- `plugin.yaml` 定义生命周期钩子，与 Hermes 框架解耦
- `router.py` 懒加载 + 预热，避免启动时失败
- `__init__.py` 格式化路由结果为 `[路由引擎预判]` 上下文标记

唯一的架构问题在于 `unrouted` 的处理方式——按 ADR 要求在 unrouted 时应让主 Agent 询问用户，但目前插件返回的信息较薄弱。

### 5. 架构改进路线图（建议）

1. **第一阶段（架构巩固）**: 抽取共享 chain 配置模块，统一 chain_step_skills key 格式
2. **第二阶段（测试加固）**: 为 chain_executor.py 创建完整测试套件
3. **第三阶段（职责清理）**: 从 route_engine.py 剥离日志和 skills CLI
4. **第四阶段（架构统一）**: 统一状态管理模式、错误处理模式、CLI 入口风格

---

## 总结

该路由引擎插件在核心设计方向上正确（零 token 预判 + YAML 驱动 + plugin 钩子集成），但在**模块边界的执行层面**存在严重偏离：
- **CRITICAL 级别问题 5 个**: 2 个属于配置加载重复/散乱，2 个属于 ADR 贯彻不一致，1 个属于关键模块零测试
- **HIGH 级别问题 4 个**: 职责越界、安全风险、函数超长、契约违反
- **架构评分 54/100**: 核心架构方向可行，但执行细节和代码质量拖累整体

> **结论**: 架构可救，无需重写。重点修复 CRITICAL-1（chain_step_skills 格式统一）+ CRITICAL-5（chain_executor 测试覆盖）+ 共享配置模块抽取，即可将架构提升至可维护水平。
