# Spec 合规评审报告 — 路由引擎插件

**评审时间**: 2026-07-04  
**评审范围**: route_engine.py(662行)、chain_executor.py(960行)、route-map/index.yaml、route-map/routes/(15个YAML)、route-map/chains/(8个YAML)  
**参考规范**: SOUL.md、agent-environment.md、code-review/SKILL.md  
**评审类型**: report_only（只出报告，不修改）

---

## 合规评分：**64/100**

| 维度 | 权重 | 得分 | 说明 |
|------|------|------|------|
| 配置格式合规性 | 30% | 18/30 | 多 chain 的 chain_step_skills key 格式不匹配，链启动将失败 |
| 错误处理完整性 | 25% | 21/25 | 整体良好，少数边缘路径未覆盖 |
| 文档完整性 | 20% | 14/20 | route_engine.py 100% 覆盖，chain_executor.py 缺失4处 |
| 命名规范一致性 | 15% | 9/15 | 存在多处命名不一致和文档字段与实际代码不匹配 |
| SOUL.md 规范遵循 | 10% | 2/10 | chain_step_skills 格式与代码执行路径严重不一致 |

---

## 发现问题汇总

### 🔴 CRITICAL（5项 — 功能阻断）

#### C-1. debugger-chain chain_step_skills key 格式不匹配

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/route-map/chains/debugger-chain.yaml` |
| 行号 | 48-54 |
| 严重性 | **CRITICAL** |

**问题描述**：  
chain_step_skills 中定义的 key 使用 `programmer@N` 前缀，但 chain owner 为 `error-analyst`。`_validate_skills()` 函数（chain_executor.py 第227行）生成 key 的格式为 `{chain_owner}@{step_idx}`，即 `error-analyst@N`。

**证据**：
- 文件 owner: `error-analyst`（第4行）
- chain_step_skills 定义的 key: `programmer@0`, `programmer@1`, `programmer@2`, `programmer@3`（第48-54行）
- _validate_skills 期望的 key: `error-analyst@1`, `error-analyst@2`, `error-analyst@3`, `error-analyst@4`, `error-analyst@5`
- 实际匹配的仅 `error-analyst@0`（第49行），其余4个 step（第13、28、34、41行）均无有效 skills key

**影响**：调用 `chain_executor.py advance` 启动 debugger-chain 时，`_validate_skills` 将返回错误，链无法启动。这**直接阻断**所有路由到 debugger-chain 的用户输入（故障诊断类任务）。

---

#### C-2. dual-review-chain 缺少 step[2] 的 skills key

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/route-map/chains/dual-review-chain.yaml` |
| 行号 | 28-31 |
| 严重性 | **CRITICAL** |

**问题描述**：  
chain_step_skills 缺少 `dual-review@2` key（对应 step[2]，agent=data-analyst）。定义了 `data-analyst@0` 但该 key 不被 _validate_skills 识别。

**证据**：
- 链定义 step[2]（第21-27行）：agent=data-analyst, goal="Architecture 轴评审"
- chain_step_skills（第28-31行）：定义了 `dual-review@0`, `dual-review@1`, `data-analyst@0`
- 缺少 `dual-review@2`
- 同时 `data-analyst@0` 是 orphan key（不会被任何代码读取）

**影响**：spec 合规评审 → 代码质量评审 → 架构评审 的三步流水线无法完整执行，第3步会被 _validate_skills 拒绝。

---

#### C-3. learn-chain chain_step_skills key 格式不匹配

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/route-map/chains/learn-chain.yaml` |
| 行号 | 16-19 |
| 严重性 | **CRITICAL** |

**问题描述**：  
chain_step_skills 定义了 `programmer@1`, `reality-checker@2`，但 chain owner 为 `prompt-engineer`。_validate_skills 期望的 key 为 `prompt-engineer@1`, `prompt-engineer@2`。

**证据**：
- 文件 owner: `prompt-engineer`（第4行）
- step[1]（第11行）：agent=programmer → 期望 key `prompt-engineer@1` — 不存在
- step[2]（第14行）：agent=reality-checker → 期望 key `prompt-engineer@2` — 不存在
- 定义的 `programmer@1`, `reality-checker@2` 均为 orphan key

**影响**：技能蒸馏管线（分析→撰写SKILL.md→验证）无法启动。

---

#### C-4. research-chain chain_step_skills key 不匹配

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/route-map/chains/research-chain.yaml` |
| 行号 | 25-28 |
| 严重性 | **CRITICAL** |

**问题描述**：  
chain_step_skills 定义了 `pm-agent@0`, `pm-agent@2` 等 key，但 chain owner 为 `data-analyst`。_validate_skills 期望 `data-analyst@0`, `data-analyst@2`。

**证据**：
- 文件 owner: `data-analyst`（第4行）
- step[0]（第6行）：agent=pm-agent → 期望 key `data-analyst@0` — 不存在
- step[2]（第23行）：agent=pm-agent → 期望 key `data-analyst@2` — 不存在
- 定义的 `pm-agent@0`, `pm-agent@2` 不被 _validate_skills 识别

**影响**：并行调研管线（拆解→多路调研→合并报告）的 step[0] 和 step[2] 会验证失败。

---

#### C-5. programmer-chain 缺少 programmer@1 skills key

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/route-map/chains/programmer-chain.yaml` |
| 行号 | 55-60 |
| 严重性 | **CRITICAL** |

**问题描述**：  
programmer-chain 的 chain_step_skills 缺少 `programmer@1` key（对应 step[1]，agent=error-analyst）。

**证据**：
- 链定义 step[1]（第13-18行）：agent=error-analyst, goal="spec 合规评审"
- chain_step_skills（第55-60行）：定义 `programmer@0`, `programmer@2`, `programmer@3`, `programmer@4`, `programmer@5`
- ❌ `programmer@1` 不存在
- 同时 `programmer@3`, `programmer@4` 是 orphan key（step[3] 为 parallel、step[4] 为 interactive，均被 _validate_skills 跳过）

**影响**：TDD 实现链的第二步（spec 合规评审）会被 _validate_skills 拒绝，导致编码管线卡在实现步骤之后无法推进。

---

### 🟠 HIGH（3项 — 文档/命名缺失）

#### H-1. chain_executor.py 4个函数缺少 docstring

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/scripts/chain_executor.py` |
| 行号 | 250, 255, 275, 851 |
| 严重性 | **HIGH** |

**问题描述**：chain_executor.py 中 4 个函数/方法没有 docstring：

1. `_state_path()` — 第250行：缺乏参数说明和返回值描述
2. `_load_state()` — 第255行：缺乏异常（损坏状态文件）场景说明
3. `_save_state()` — 第275行：缺乏原子写入（tmp+replace）的安全保障说明
4. `main()` — 第851行：CLI 入口函数无 docstring，没有参数使用说明

**对比**：route_engine.py 拥有 100% docstring 覆盖率（18/18），chain_executor.py 仅 76%（13/17）。

---

#### H-2. triage.yaml 内部 agent 声明与文件名不一致

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/route-map/routes/triage.yaml` |
| 行号 | 3 |
| 严重性 | **HIGH** |

**问题描述**：文件名为 `triage.yaml`，但内部 `agent:` 字段声明为 `spec-agent`。index.yaml 中 triage agent 的 `file:` 引用为 `routes/triage.yaml`。

**证据**：
```yaml
# triage.yaml 第3行
agent: spec-agent
```
```yaml
# index.yaml
triage:
    file: routes/triage.yaml
```

**影响**：虽然当前代码不使用 YAML 中的 `agent` 字段（实际 key 由 index.yaml 提供），但这是重要的**文档不一致**，在调试和人工审查时会产生混淆。未来的代码变更可能依赖此字段。

---

#### H-3. follow-process-chain / spec-agent-chain 无 chain_ref 引用但定义了 keywords

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/route-map/chains/follow-process-chain.yaml`（第2行）、`spec-agent-chain.yaml`（第2行） |
| 严重性 | **HIGH** |

**问题描述**：这两个 chain 文件定义了 `chain_keywords`，但没有任何 index.yaml 中的 agent 通过 `chain_ref` 引用它们。它们仅通过 route_engine.py 的 chain 目录扫描（第130-165行）被发现。

**证据**：
```
follow-process-chain.yaml: chain_keywords: [按流程走, 标准流程, standard-flow, 全流程管线]
spec-agent-chain.yaml: chain_keywords: [新项目管线, spec-chain, prd管线, 需求分析管线]
```

**问题**：这种"隐式引用"模式虽然可以工作，但与 index.yaml 的显式 `chain_ref` 机制不一致。如果目录扫描代码未来被修改（如加上 `already_loaded` 检查），这些 chain 可能被遗漏。

---

### 🟡 MEDIUM（5项 — 轻微违规/不一致）

#### M-1. 混合 priority 类型（float vs int）

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/route-map/index.yaml` |
| 行号 | 82（triage priority: 1.5） |
| 严重性 | **MEDIUM** |

**问题描述**：triage agent 的 priority 值为 `1.5`（float），而其他所有 agent 使用整数值。虽然 Python 的 `min()` 正确处理混合类型比较，但这破坏了类型一致性。

**证据**：
- triage: `priority: 1.5`（第82行）
- 其他 agents: `priority: 0`, `1`, `2`, `3` 等（全部为整数）

---

#### M-2. route_engine.py 变量命名不一致

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/scripts/route_engine.py` |
| 行号 | 30（`_SCRIPT_DIR`）vs chain_executor.py 41（`_SCRIPT_DIR_CHAIN`） |
| 严重性 | **MEDIUM** |

**问题描述**：两个模块使用不同的变量名表示相同概念（脚本所在目录）。route_engine.py 使用 `_SCRIPT_DIR`，chain_executor.py 使用 `_SCRIPT_DIR_CHAIN`。虽然功能正确，但降低了代码的一致性和可维护性。

**证据**：
```python
# route_engine.py 第30行
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# chain_executor.py 第41行
_SCRIPT_DIR_CHAIN = os.path.dirname(os.path.abspath(__file__))
```

---

#### M-3. 多个 chain 的 chain_step_skills 中存在 orphan key

| 字段 | 值 |
|------|------|
| 文件 | 多个 chain YAML |
| 严重性 | **MEDIUM** |

**问题描述**：多个 chain 文件中定义了不被任何代码使用的 chain_step_skills key（orphan key），包括：

| 文件 | Orphan key | 期望 key |
|------|-----------|---------|
| debugger-chain.yaml | `programmer@0`, `programmer@1`, `programmer@2`, `programmer@3` | `error-analyst@2..5` |
| dual-review-chain.yaml | `data-analyst@0` | `dual-review@2` |
| learn-chain.yaml | `programmer@1`, `reality-checker@2` | `prompt-engineer@1`, `prompt-engineer@2` |
| research-chain.yaml | `pm-agent@0`, `pm-agent@2` | `data-analyst@0`, `data-analyst@2` |
| programmer-chain.yaml | `programmer@3`, `programmer@4` | （对应的 step[3] 和 step[4] 被 _validate_skills 跳过） |

虽然 orphan key 不直接导致功能错误，但它们增加了维护负担，且是 bug 的信号（真正的 skills 没有被正确分配）。

---

#### M-4. error-analyst.yaml 中负权重规则未遵循统一注释约定

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/route-map/routes/error-analyst.yaml` |
| 行号 | 117-143 |
| 严重性 | **MEDIUM** |

**问题描述**：负权重规则用于防止误匹配（mis-match guard），但不同文件的注释风格不一致：
- 部分文件标注 `# ── 误匹配防护——负权重，无技能`（如 error-analyst.yaml 第117行）
- 部分文件直接使用负权重而无注释说明（如 programmer.yaml 第145行 `weight: -0.5`）

缺少标准化注释，可能导致未来维护者不理解负权重的意图。

---

#### M-5. route_engine.py overrides 与 evaluate() 共享同一 route_map 但逻辑重复

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/scripts/route_engine.py` |
| 行号 | 57-61, 459-488 |
| 严重性 | **MEDIUM** |

**问题描述**：`load_route_map()` 将 overrides 合并到 route_map（第57-61行），但 `route()` 函数（第459行起）又独立处理 overrides 逻辑。如果 overrides 格式与 evaluate 评分路径不一致，可能导致优先级冲突。

**证据**：
```python
# load_route_map 第57-61行
overrides = index.get("overrides", [])  # 加载到 route_map
# route() 第459-488行
overrides = route_map.get("overrides", [])  # 再次处理 override
```

实际代码中 overrides 仅在 `route()` 中独立处理而不进入 `evaluate()`，`load_route_map` 中加载的 overrides 实际上未被使用（仅存在于 route_map dict 中）。这是死代码。

---

### 🟢 LOW（3项 — 建议性）

#### L-1. index.yaml 中 dual-review 的 chain_ref 与 YAML 注释冲突

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/route-map/routes/dual-review.yaml` |
| 行号 | 13 |
| 严重性 | **LOW** |

**问题描述**：dual-review.yaml 第13行注释写着 `# chain_ref: dual-review-chain (moved to index.yaml agent entry)`，这是历史遗留注释，但注释说 "moved to" 暗示该字段不应该在 route YAML 中存在。建议清除注释或将其改为文档引用。

---

#### L-2. route_engine.py 日志记录使用硬编码路径（无配置化）

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/scripts/route_engine.py` |
| 行号 | 569 |
| 严重性 | **LOW** |

**问题描述**：日志路径 `_LOG_FILE` 硬编码为相对于脚本目录的固定路径，不支持通过环境变量或配置文件覆盖。

---

#### L-3. chain_executor.py 中 `run_verification` 使用 shell=True 执行命令

| 字段 | 值 |
|------|------|
| 文件 | `/opt/data/scripts/chain_executor.py` |
| 行号 | 448 |
| 严重性 | **LOW** |

**问题描述**：`run_verification()` 使用 `subprocess.run(cmd, shell=True, ...)` 执行 verify_command。虽然代码注释说明信任 chain_def 中的预定义命令，但从安全最佳实践来看 `shell=True` 是风险点。当前环境下 risk 较低，但文档化此设计决策更为妥当。

---

## 合规性分项详评

### 1. 配置格式合规性（18/30）

**YAML parse 检查**：全部通过 ✅  
15 个 route YAML 和 8 个 chain YAML 均可被 PyYAML 正确加载。

**index.yaml 完整性**：通过 ✅  
包含 15 个 agent 定义、defaults、overrides、schema_version、last_updated、maintainer。

**route YAML 结构**：通过 ✅  
所有 route YAML 包含 `agent`、`rules` 字段。rules 数组元素均包含 `type`、`pattern`、`weight` 字段。

**chain YAML chain_step_skills 完整性**：**严重违反 ❌**  
5 个 chain 文件存在 key 格式不匹配问题（C-1 至 C-5），链启动将失败。

### 2. 错误处理完整性（21/25）

**route_engine.py 错误处理**：良好 ✅
- `load_route_map`：处理 FileNotFoundError、YAML 解析异常 ✅
- `_load_skill_cache`：处理 JSONDecodeError ✅
- `match_rule`：处理未知 rule_type → raise ValueError ✅
- `evaluate`：负权重钳位到 0.0 ✅
- `route`：空输入 → unrouted ✅
- `main`：参数检查 ✅

**chain_executor.py 错误处理**：良好 ✅
- `_sanitize_task_id`：路径遍历防护 ✅
- `_load_state`：JSONDecodeError / OSError 处理 ✅
- `_save_state`：原子写入（tmp + replace + fsync）✅
- `run_verification`：超时、异常、空命令 ✅
- `advance`：状态损坏检测、索引越界检查、非法状态检查 ✅

**不足**：
- `run_verification` `shell=True` 无 shell 注入防护（L-3）
- `route()` 函数在 override 路径失败后没有降级到 evaluate（当前仅返回 override 结果）

### 3. 文档完整性（14/20）

| 文件 | 函数总数 | 有 docstring | 覆盖率 |
|------|---------|-------------|--------|
| route_engine.py | 18 | 18 | **100%** ✅ |
| chain_executor.py | 17 | 13 | **76%** ❌ |

chain_executor.py 缺少 docstring 的函数：`_state_path`、`_load_state`、`_save_state`、`main`。

模块级 docstring（文件开头）两文件均有 ✅

### 4. 命名规范一致性（9/15）

**一致处** ✅：
- 模块级常量使用 `_` 前缀（Python 约定）
- 函数名使用 snake_case
- YAML 字段名使用 kebab-case（`chain_ref`, `chain_step_skills`, `schema_version`）

**不一致处** ❌：
- `_SCRIPT_DIR` vs `_SCRIPT_DIR_CHAIN`（H-3）
- triage.yaml 文件 vs 内部 agent 字段（H-2）
- `_SKILL_CACHE_FILE` 使用 `.json` 扩展名但实际数据为 JSON 格式（技术上正确，但与内部变量命名风格不统一）

### 5. SOUL.md 规范遵循（2/10）

**SOUL.md 路由规范要求**：
> - 目标 Agent + 置信度 → 立即 delegate_task
> - chain 编排：状态机返回的 status 按分支处理

检查结果：
- `route()` 正确返回 agent + confidence ✅
- chain 状态机支持 CONTINUE / CONTINUE_PARALLEL / CONTINUE_BATCH / NEEDS_CONTEXT / BRANCH_PROGRESS / DONE / REPORT_ONLY ✅

**SOUL.md 委派纪律要求**：
> 失败回滚路径存在；（连续失败→挂起→升级用户）

检查结果：
- chain_executor 实现了 NEEDS_FIX → RETRY → MAX_RETRY → BLOCKED 完整的回滚路径 ✅
- 修复：C-1 至 C-5 表明**实际的 chain 根本启动不了**，被 _validate_skills 阻断在第一步。这与 "失败回滚路径" 精神相悖——系统没有降级到无 chain 模式运行。

**agent-environment.md §3 技能要求**：
> 仅从该文件匹配技能，白名单外禁止使用

检查结果：
- route_map 中 route/chain 定义的技能通过 `_validate_skills` 校验 ✅
- 但 chain_step_skills 的 key 格式不匹配意味着技能无法被正确分配 ❌

---

## 修复优先级建议

| 优先级 | 问题 | 修复方法 |
|--------|------|---------|
| P0 | C-1至C-5 | 将 chain_step_skills 的 key 格式改为 `{chain_owner}@{step_idx}` |
| P1 | H-1 | 补全 chain_executor.py 4 处缺失的 docstring |
| P2 | H-2 | 统一 triage.yaml 的 `agent` 字段为 `triage` |
| P3 | M-1 | 将 triage priority 改为整数（2.0 或 1） |
| P4 | M-3 | 清理所有 orphan chain_step_skills key |
| P5 | M-2, M-4, M-5 | 统一命名风格、清理死代码、标准化注释 |
| P6 | L-1至L-3 | 按建议优化 |

---

## 证据清单 (Evidence Ledger)

| # | 验证项 | 方法 | 结果 |
|---|--------|------|------|
| E1 | Python 语法检查 | `py_compile.compile()` | route_engine.py ✅ / chain_executor.py ✅ |
| E2 | YAML 语法检查 | `yaml.safe_load()` 全部 24 个文件 | 全部通过 ✅ |
| E3 | docstring 覆盖率 | AST 遍历 | route_engine.py: 18/18 (100%); chain_executor.py: 13/17 (76%) |
| E4 | chain_step_skills 完整性 | _validate_skills 逻辑模拟 | 5/8 chain 缺失正确 key |
| E5 | index.yaml ↔ route 文件一致性 | 交叉验证 | 全部 route 文件可被 index.yaml 定位 ✅ |
| E6 | chain_ref 引用完整性 | 交叉验证 | follow-process-chain 和 spec-agent-chain 无显式 chain_ref |

---

*报告由 error-analyst 自动生成，基于实际运行检查和代码阅读。*
