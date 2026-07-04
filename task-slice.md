# 路由引擎插件 — 任务切片表

> **来源**: 双评审（Spec 合规 64/100 + 代码质量 61/100 + Architecture 54/100）
> **总问题数**: 62（三份报告交叉去重后约 45 个唯一问题）
> **生成时间**: 2026-07-04
> **拆解原则**: 每切片 = 独立交付单元（修代码→验证）；按文件/模块聚合；CRITICAL/HIGH 优先

---

## 优先级 P0 — CRITICAL（功能阻断，必须优先修复）

| 编号 | 切片名 | 涉及文件 | 级别 | 改动量 | 依赖关系 | 描述 |
|------|--------|----------|------|--------|----------|------|
| S01 | **统一 chain_step_skills key 格式** | `route-map/chains/debugger-chain.yaml`, `dual-review-chain.yaml`, `learn-chain.yaml`, `research-chain.yaml`, `programmer-chain.yaml` | CRITICAL | ⭐ 小（5文件 YAML 字段修正） | 无 | 5 个 chain 的 chain_step_skills key 使用 `{step_agent}@{idx}` 格式（如 `programmer@0`），而 `_validate_skills()` 要求 `{chain_owner}@{idx}`（如 `error-analyst@1`）。需全部修正为 `{chain_owner}@{step_idx}`，删除 orphan key，补全缺失 key。对应问题：review C-1~C-5, quality CRITICAL-1, arch CRITICAL-1 |
| S02 | **decide() 返回 "llm_fallback" 修复** | `scripts/route_engine.py` (L381-411) | CRITICAL | ⭐ 小（改2个方法+3个断言） | S01 无依赖 | `decide()` 低分/空分路径返回 `method: "unrouted"`，但测试和 ADR 期望 `method: "llm_fallback"`。方案：将 unrouted 改为 llm_fallback 并填充 fallback_agent。需同步修正强绑定 ADR 文档和插件 `__init__.py` 对 unrouted 的处理。对应问题：quality CRITICAL-2, arch CRITICAL-3 |
| S03 | **confidence 截断到 [0.0, 1.0]** | `scripts/route_engine.py` (L432-444, route() 返回处) | CRITICAL | ⭐ 小（加1行 clamp） | S02 无依赖 | `evaluate()` 累加权重可能 > 1.0，decide() 和 route() 均未做 `min(score, 1.0)`。测试 `test_confidence_range` 得到 1.5 而失败。在 decide() 返回前和 route() 返回前 clamp。对应问题：quality CRITICAL-4, arch HIGH-4 |
| S04 | **shell=True 安全加固** | `scripts/chain_executor.py` (L443-483, run_verification) | CRITICAL | ⭐⭐ 中（改写 shell 调用逻辑） | 无 | `run_verification()` 使用 `subprocess.run(cmd, shell=True)` 执行 YAML 配置命令。方案：简单命令用 `shlex.split()` + shell=False；管道命令加命令白名单校验；抽取 `VERIFICATION_TIMEOUT` 常量和 `MAX_OUTPUT_LENGTH = 2000` 常量。对应问题：quality CRITICAL-3, arch HIGH-2, review L-3 |
| S05 | **per-rule chain_ref 死配置清理** | `route-map/routes/programmer.yaml`, `spec-agent.yaml`, `dual-review.yaml` | CRITICAL | ⭐ 小（YAML 清理） | 无 | 15+11 处 per-rule `chain_ref` 字段从未被 `load_route_map()` 读取。删除全部 per-rule chain_ref，仅保留 index.yaml agent 级别 entry。清理 dual-review.yaml 注释。对应问题：arch CRITICAL-4, review L-1 |
| S06 | **创建 chain_executor 单元测试** | `tests/test_chain_executor.py`（新建）| CRITICAL | ⭐⭐⭐ 大（300-500行测试） | S01, S04 必须完成（代码先修好再测） | 960 行状态机代码零正式测试。需覆盖：start_chain()、advance() 各状态分支（init/batch_complete/branches_complete/loop_complete/BLOCKED/NEEDS_CONTEXT/DONE）、_validate_skills()、run_verification()（mock subprocess）、状态持久化（_load_state/_save_state）、retry 逻辑、边界条件。对应问题：arch CRITICAL-5, quality HIGH-7 |

---

## 优先级 P1 — HIGH（功能/可维护性）

| 编号 | 切片名 | 涉及文件 | 级别 | 改动量 | 依赖关系 | 描述 |
|------|--------|----------|------|--------|----------|------|
| S07 | **共享 chain 配置加载模块** | `scripts/chain_config.py`（新建）, `scripts/route_engine.py`, `scripts/chain_executor.py` | HIGH | ⭐⭐⭐ 大（新建模块 + 修改两处导入） | S01 建议先 | 抽取重复 YAML 加载逻辑（route_engine.py L42-172 和 chain_executor.py L363-409）为共享 `chain_config.py`。统一路径常量（`_SCRIPT_DIR` vs `_SCRIPT_DIR_CHAIN`）、共享 `load_route_map()` 结果。也同时解决 MEDIUM-4 arch（路径重复）。对应问题：arch CRITICAL-2, review M-2, arch MEDIUM-4 |
| S08 | **advance() 超级函数拆解** | `scripts/chain_executor.py` (L489-848) | HIGH | ⭐⭐⭐ 大（提取6-8个辅助函数） | S01 必须完成（先保证链能启动再重构） | 360 行超级函数含 12+ 分支路径。按状态类型提取：`_handle_serial_step()`, `_handle_parallel_step()`, `_handle_branch_complete()`, `_handle_batch_complete()`, `_handle_loop_complete()`, `_handle_blocked()`, `_handle_needs_fix()`。合并 3 个链结束代码块为 `_build_chain_done_result()`。合并 branch_index/batch_index 为 `_accumulate_partial_result()`。对应问题：quality HIGH-1/HIGH-2/HIGH-3, arch HIGH-3 |
| S09 | **load_route_map() 职责拆分** | `scripts/route_engine.py` (L42-172) | HIGH | ⭐⭐ 中（4个辅助函数） | S07 建议先（拆出的共享逻辑在 S07 中统一） | 130 行函数拆为：`_load_index()`, `_load_shared_rules()`, `_load_agent_rules()`, `_build_chain_index()`。对应问题：quality HIGH-4 |
| S10 | **route() 函数拆分** | `scripts/route_engine.py` (L447-564) | HIGH | ⭐⭐ 中（3个辅助函数） | 无 | 117 行含 4 条独立路径：拆为 `_try_override()`, `_try_chain_keyword()`, `_evaluate_and_decide()`。对应问题：quality HIGH-5 |
| S11 | **triage 误路由 "bug" 修复** | `route-map/routes/triage.yaml` (L11-12) | HIGH | ⭐ 小（改1个权重值） | 无 | triage 规则中 `bug: 1.5` 权重过高，导致编程任务被截获。将 triage `bug` 降至 1.0 或给 programmer 添加组合规则。对应问题：quality HIGH-6 |
| S12 | **日志功能剥离** | `scripts/route_logger.py`（新建）, `scripts/route_engine.py` | HIGH | ⭐⭐ 中（提取日志模块） | 无 | 从 route_engine.py 抽取 `_rotate_log()` 和 `log_route()` 到独立 `route_logger.py`。提取魔法数字（10MB / 5备份 / 0.6阈值）为命名常量。对应问题：arch HIGH-1, quality MEDIUM-2, review L-2 |
| S13 | **CLI 入口统一** | `scripts/route_engine.py` (L633-658), `scripts/chain_executor.py` (L851-869) | HIGH | ⭐ 小（argparse subparser 改造） | 无 | route_engine.py `main()` 使用手写分支而非 argparse subparser；chain_executor.py 使用完整 argparse 但 sys.exit 混用。统一风格，将 skills CLI 从 route_engine 移到独立处理或标注。对应问题：arch LOW-3, arch MEDIUM-2 |
| S14 | **chain_executor docstring 补全** | `scripts/chain_executor.py` (L250, 255, 275, 851) | HIGH | ⭐ 小（4处 docstring） | 无 | 补充 `_state_path()`、`_load_state()`、`_save_state()`、`main()` 的 docstring（参数、返回值、异常场景）。对应问题：review H-1 |

---

## 优先级 P2 — MEDIUM（非功能阻断但需修复）

| 编号 | 切片名 | 涉及文件 | 级别 | 改动量 | 依赖关系 | 描述 |
|------|--------|----------|------|--------|----------|------|
| S15 | **类型提示补全** | `scripts/chain_executor.py`（多处） | MEDIUM | ⭐ 小（6处返回类型注解） | 无 | 补充 `_state_path`→`str`、`_save_state`→`None`、`start_chain`、`run_chain`、`main`、`aggregate_parallel_results` 类型注解。对应问题：quality MEDIUM-4 |
| S16 | **魔法数字提取为常量** | `scripts/route_engine.py`, `scripts/chain_executor.py`（多处） | MEDIUM | ⭐ 小（6个常量抽取） | 无 | 抽取：SKILL_BONUS=0.2、DEFAULT_PRIORITY=99、_BORDERLINE_THRESHOLD=0.6、MAX_OUTPUT_LENGTH=2000、LOG_MAX_BYTES、LOG_BACKUP_COUNT 等。对应问题：quality MEDIUM-1/MEDIUM-3/MEDIUM-9, review M-1 |
| S17 | **priority 类型统一** | `route-map/index.yaml` (L44, L80) | MEDIUM | ⭐ 小（改1个 YAML 值） | 无 | triage `priority: 1.5`（float）与其余 agent 的 int 不统一。改 1.5 为 1 或 2，或统一为 float。对应问题：review M-1, quality MEDIUM-6 |
| S18 | **YAML 配置一致性修复** | `route-map/routes/triage.yaml`, `route-map/routes/error-analyst.yaml`, `route-map/chains/spec-agent-chain.yaml` | MEDIUM | ⭐ 小（3个 YAML 小修） | 无 | triage.yaml `agent: spec-agent` → `triage`；error-analyst.yaml 负权重注释格式化；spec-agent-chain.yaml 空 skills 数组加注释或移除。对应问题：review H-2/M-4, quality LOW-4/LOW-5 |
| S19 | **测试基础设施修复** | `tests/test_route_engine.py` (L39-42, L357-458), `scripts/test_chain_link.py` | MEDIUM | ⭐ 小（4处修改） | 无 | 测试中 `_clear_cache()` 复用模块函数而非重写；端到端测试参数化（subTest）；test_chain_link.py 迁移到 unittest。对应问题：quality MEDIUM-7/MEDIUM-8, quality LOW-7 |
| S20 | **错误处理统一加固** | `scripts/route_engine.py`, `scripts/chain_executor.py`（多处） | MEDIUM | ⭐ 小（4处 try/except 调整） | 无 | yaml 导入去掉静默（fail fast）；_load_skill_cache 去掉冗余 `json.JSONDecodeError`；_save_state fsync 加异常处理；_load_skill_cache 损坏时至少打 warning 日志。对应问题：quality LOW-1/LOW-2/MEDIUM-5, arch MEDIUM-3 |
| S21 | **隐式 chain 引用文档化** | `route-map/chains/follow-process-chain.yaml`, `spec-agent-chain.yaml` | LOW | ⭐ 极小（加注释/更新 index.yaml） | 无 | 两个 chain 仅通过目录扫描发现（无 index.yaml chain_ref）。加注释说明，或在 index.yaml 中显式注册。对应问题：review H-3 |
| S22 | **死代码清理** | `scripts/route_engine.py`（多处） | MEDIUM | ⭐ 小（删除死字段） | S10 建议先 | `decide()` 中 `matched_rules: []` 是死代码（route() 覆盖写入）；`load_route_map()` 中 overrides 加载后未使用；删除 orphan key：dual-review-chain `data-analyst@0` 等。对应问题：review M-3/M-5, arch LOW-1 |

---

## 优先级 P3 — LOW（建议性/长期优化）

| 编号 | 切片名 | 涉及文件 | 级别 | 改动量 | 依赖关系 | 描述 |
|------|--------|----------|------|--------|----------|------|
| S23 | **FORCE_ROUTE_THRESHOLD 调整** | `plugins/route-router/__init__.py` (L9) | LOW | ⭐ 极小（改1个常量） | S03 必须先完成（confidence 上限正确后再调阈值） | `FORCE_ROUTE_THRESHOLD = 2.0` 与 confidence 上限 1.0 冲突。改 2.0 → 1.0 或 0.9。对应问题：arch LOW-2 |
| S24 | **缓存策略文档化** | `scripts/route_engine.py`, `scripts/chain_executor.py` | LOW | ⭐ 极小（加注释/docstring） | 无 | 两模块缓存策略不同（内存 vs 文件），加注释说明设计意图和 TTL 机制。对应问题：arch MEDIUM-1 |
| S25 | **timeout=30 可配置化** | `scripts/chain_executor.py` (L452) | LOW | ⭐ 极小（从 chain_def 读取或加参数） | 无 | verification timeout 硬编码 30s，改为从 step 的 `completion_contract` 读取或默认值+覆盖。对应问题：quality LOW-3 |
| S26 | **负权重注释标准化** | `route-map/routes/*.yaml`（全部） | LOW | ⭐ 小（扫描全部15文件加注释） | 无 | 统一负权重规则的注释格式为 `# ── 误匹配防护——负权重，无技能`。对应问题：review M-4 |

---

## 依赖总图

```
S05 (per-rule chain_ref 清理)           S04 (shell 安全加固)          S02 (llm_fallback)
      │                                       │                            │
      ▼                                       ▼                            ▼
S01 (chain_step_skills key 格式)  ←──── S07 (共享配置模块) ←──── S03 (confidence clamp)
      │                                       │
      ▼                                       ▼
S08 (advance() 拆解)                    S09 (load_route_map 拆分)
      │                                       │
      ▼                                       ▼
S06 (chain_executor 测试) ──────────→ ▶ 验证全部通过 ◀
                                              │
                                     S10-S26 (后续非阻断修复)
```

## 执行顺序建议

| 阶段 | 切片 | 目标 | 验收条件 |
|------|------|------|----------|
| **Phase 1: 救火** | S01→S02→S03→S04→S05 | 修复全部 CRITICAL 功能阻断 | 所有链可启动；5 个 chain YAML 格式正确；6 个失败测试归零；confidence ∈ [0,1]；shell 命令安全 |
| **Phase 2: 清理死配置** | S07+S09 | 消除双份加载和重复路径 | chain 配置只在一个地方维护；路径常量共享 |
| **Phase 3: 重构** | S08+S10+S12+S13 | 拆超级函数、剥离日志、统一 CLI | advance < 80 行；route < 40 行；日志/CLI 独立 |
| **Phase 4: 测试加固** | S06+S14+S19 | 补齐 chain_executor 测试、docstring、测试基础设施 | chain_executor 覆盖率 > 70%；69+50 测试全通过 |
| **Phase 5: 扫尾** | S11+S15+S16+S17+S18+S20+S21+S22+S23+S24+S25+S26 | 余下 MEDIUM/LOW | 无安全警告；无类型提示缺失；无魔法数字；YAML 全部一致 |

## 统计

| 优先级 | 切片数 | 含 CRITICAL 问题 | 含 HIGH 问题 | 含 MEDIUM 问题 | 含 LOW 问题 | 改动量估计 |
|--------|--------|-----------------|-------------|---------------|------------|-----------|
| P0 (CRITICAL) | 6 | 14 | — | — | 2 | ⭐ 小×4 + ⭐⭐ 中×1 + ⭐⭐⭐ 大×1 |
| P1 (HIGH) | 8 | — | 15 | 1 | 2 | ⭐ 小×3 + ⭐⭐ 中×3 + ⭐⭐⭐ 大×2 |
| P2 (MEDIUM) | 8 | — | — | 14 | 5 | ⭐ 极小×1 + ⭐ 小×6 + ⭐⭐ 中×1 |
| P3 (LOW) | 4 | — | — | 1 | 5 | ⭐ 极小×3 + ⭐ 小×1 |
| **合计** | **26** | **14** | **15** | **16** | **14** | — |
