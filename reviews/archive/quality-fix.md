# 代码质量复评审报告 — 路由引擎插件

**评审日期**: 2026-07-04  
**评审类型**: report_only（只出报告，不修改代码）  
**评审范围**: 
- `/opt/data/scripts/route_engine.py` (669行)
- `/opt/data/scripts/chain_executor.py` (1203行)
- `/opt/data/scripts/chain_config.py` (新建47行)
- `/opt/data/scripts/route_logger.py` (新建84行)
- `/opt/data/route-map/chains/*.yaml` (8个)
- `/opt/data/tests/test_chain_executor.py` (新建675行，53个测试)
- `/opt/data/tests/test_route_engine.py` (69个测试)

**参考**: 原始质量报告 `/opt/data/quality_report.md` (评分61/100)  
**验证环境**: Python 3.13.5, uv run pytest, 实际测试执行

---

## 总体评分：**63 / 100**

| 维度 | 原始得分 | 复评得分 | 变化 | 说明 |
|------|---------|---------|------|------|
| 代码可读性 | 65 | **72** | ↑+7 | advance() 拆分为15+个独立函数，docstring 完善，新建文件结构清晰 |
| 异常处理完整性 | 70 | **68** | ↓-2 | 新增了白名单校验和原子写入，但 _build_step_result step["goal"] 仍无防御 → KeyError |
| 性能 | 60 | **63** | ↑+3 | 冷加载优化不多，但函数拆分减少了重复遍历 |
| 测试覆盖 | 55 | **48** | ↓-7 | 新增 test_chain_executor.py (53个测试)，但 **6个失败**；route_engine CLI 5个测试全部失败 |
| 重复代码 | 45 | **55** | ↑+10 | advance() 内重复代码消除，但 batch/branch/loop 完成处理器仍~80%雷同 |
| 类型提示 | 75 | **76** | ↑+1 | 新函数和新建文件类型提示完整 |
| 代码异味 | 55 | **62** | ↑+7 | 魔术数字减少，超级函数消除，但 CLI argparse 设计新增 HIGH 缺陷 |

---

## 一、4个CRITICAL质量问题修复验证

### CRITICAL-1: chain_step_skills 键格式 ✅ **已修复**

| Chain 文件 | 修复前（错误格式） | 修复后（正确格式） | 证据 |
|-----------|-------------------|-------------------|------|
| `debugger-chain.yaml` | `error-analyst@0`, `programmer@0`... (混用 step_agent) | `error-analyst@0`~`error-analyst@5` (全 owner 前缀) | L48-54 |
| `dual-review-chain.yaml` | 缺 step[2], 有 `data-analyst@0` | `dual-review@0`~`dual-review@2` 完整3个 | L28-31 |
| `learn-chain.yaml` | `programmer@1`, `reality-checker@2` | `prompt-engineer@0`~`prompt-engineer@2` | 已验证 |
| `research-chain.yaml` | `pm-agent@0`, `pm-agent@2` | `data-analyst@0`~`data-analyst@2` | 已验证 |
| `programmer-chain.yaml` | 全部缺失 | `programmer@0`~`programmer@5` 完整6个 | L55-61 |

**验证方法**: 逐文件比对 chain owner + chain_step_skills key 格式，8/8 文件全部使用 `{chain_owner}@{idx}` 格式，key 数量与 step 数量一致。

---

### CRITICAL-2: decide() 返回 `unrouted` 而非 `llm_fallback` ✅ **已修复**

**文件**: `route_engine.py`  
**行号**: L399-411, L417-428  
**修复证据**:
```python
# L399-411 — 空评分
if not scores:
    return {
        "agent": fallback_agent,
        "method": "llm_fallback",   # ← 原为 "unrouted"，已改
        ...
    }

# L417-428 — 低于阈值
if top_score < min_confidence:
    return {
        "method": "llm_fallback",   # ← 原为 "unrouted"，已改
        ...
    }
```

**验证**: 3个相关测试 `test_below_threshold_fallback`、`test_empty_scores_fallback`、`test_low_confidence_input_fallsback` 全部通过（route_engine 64/64非CLI测试通过）。

---

### CRITICAL-3: run_verification() 使用 shell=True 执行命令 ⚠️ **已修复（部分残留）**

**文件**: `chain_executor.py`  
**行号**: L483-528  

**修复内容**:
1. 引入了 `VERIFY_COMMAND_BASENAMES` 白名单 (L57-61)
2. 简单命令使用 `shlex.split()` + `shell=False` (L521-528)
3. 仅含管道/重定向操作符的命令使用 `shell=True`，但先对每个 token 做白名单校验 (L485-518)

**已修复证据**:
```python
# L485-518 — 管道命令：白名单校验通过后才执行 shell=True
needs_shell = any(op in cmd for op in ("|", ">", "<", ";"))
...
for token in tokens:
    if token in ("|", ">", "<", ">>", "2>&1", "&", ";", "&&", "||"):
        continue
    base_cmd = token.split("/")[-1]
    if base_cmd not in VERIFY_COMMAND_BASENAMES and not base_cmd.startswith("-"):
        allowed = False
        ...
```

**⚠️ 残留问题**: `VERIFY_COMMAND_BASENAMES` 缺少 `uv`、`pytest`、`curl` 等常用工具，且 `git` 已被列入但 shell 管道测试 `test_shell_command_whitelist` 仍然失败（whitelist 校验通过后 mock_run 调用参数与测试预期不匹配）。

**⛔ 测试验证结果**: `test_shell_command_whitelist` 仍然 FAILED：
```
assert 'VERIFICATION_FAILED' == 'VERIFIED'
```
说明白名单校验逻辑或 mock 参数匹配存在问题。

---

### CRITICAL-4: confidence 可能超过 1.0 ✅ **已修复**

**文件**: `route_engine.py`  
**行号**: L438, L452, L586  

**三重防护**：
1. `decide()` 自动路由返回 (L452): `confidence: min(top_score, 1.0)`
2. `decide()` 平局裁决返回 (L438): `confidence: min(top_score, 1.0)`
3. `_evaluate_and_decide()` 兜底 (L586): `result["confidence"] = min(result.get("confidence", 0.0), 1.0)`

**验证**: `test_confidence_range` 测试通过（route_engine 非CLI测试）。

---

## 二、新发现的质量问题

### 🔴 CRITICAL (1项)

#### N-CRITICAL-1: CLI argparse 设计缺陷导致5个CLI测试全部失败

**文件**: `route_engine.py`  
**行号**: L630-665  
**严重度**: CRITICAL — 运行时阻断，用户无法通过 CLI 正常使用路由引擎  

**问题描述**: 
`main()` 函数的 argparse 配置将 `skills` 定义为子命令，同时将 `input` 定义为顶层位置参数。当用户输入普通文本（如 "NAS 备份"）时，argparse 将其解释为子命令名而非 `input` 参数，导致：

```
__main__.py: error: argument command: invalid choice: 'NAS 备份' (choose from skills)
```

**影响测试** (5个全部失败):
- `test_cli_docs_writer`
- `test_cli_output_is_json`
- `test_cli_pm_agent`
- `test_cli_programmer`
- `test_cli_synology`

**根本原因**: 子命令 `skills` 与位置参数 `input` 在 argparse 中不可共存。任何非 `skills` 的文本输入都会触发 `invalid choice` 错误。

**推荐修复**: 将 `input` 移出顶层解析，改为通过 `nargs='*'` 的独立子命令，或使用 `parse_known_args()` 处理未知参数。

---

### 🟠 HIGH (2项)

#### N-HIGH-1: 6个 chain_executor 测试失败

**文件**: `tests/test_chain_executor.py`  
**失败测试与原因**:

| 测试 | 期望 | 实际 | 根本原因 |
|------|------|------|---------|
| `test_needs_fix_unrecognized_type` | `"无法判断 retry 类型"` | 非法状态诊断 | `_infer_step_type("做一些奇怪的事情")` 返回 `"tdd"`，合法状态不含 `NEEDS_FIX` |
| `test_done_chain_complete` | `"DONE"` | `"ERROR"` | 最后一步 DONE 后 verification 执行失败或状态推进异常 |
| `test_approve_advances` | `"CONTINUE"` | `"ERROR"` | APPROVE 状态在 valid status 校验前被拦截 |
| `test_shell_command_whitelist` | `STATUS_VERIFIED` | `STATUS_VERIFICATION_FAILED` | shell 命令白名单 mock 参数不匹配 |
| `test_no_status_field` | `"CONTINUE"` | `"ERROR"` | 无 status 字段触发错误路径 |
| `test_missing_goal_in_step` | 返回 ERROR | `KeyError: 'goal'` | `_build_step_result()` L393 使用 `step["goal"]` 而非 `.get()` |

**严重度**: HIGH — 测试是37%的失败率（6/53），且 `test_missing_goal_in_step` 暴露了源码中 `step["goal"]` 无防御的缺陷。

#### N-HIGH-2: shell=True 白名单不完整

**文件**: `chain_executor.py`  
**行号**: L57-61  
**严重度**: HIGH — 限制了 verify 功能的实际可用性  

**问题**: `VERIFY_COMMAND_BASENAMES` 缺少 `uv`、`pytest`、`curl` 等实际需要的命令。当前集合仅包含系统基础工具，在实际 CI/验证场景中不够用。

**受影响**: 如果 YAML 配置中使用了 `uv run pytest` 或 `curl` 等命令，会被白名单拒绝。

---

### 🟡 MEDIUM (2项)

#### N-MEDIUM-1: `_build_step_result()` 中 `step["goal"]` 缺少防御性访问

**文件**: `chain_executor.py`  
**行号**: L393  
**代码引用**:
```python
next_item = {
    "agent": step["agent"],
    "goal": step["goal"],       # ← 使用 dict[] 而非 .get()
    "skills": skills,
}
```

**问题**: 当 step dict 缺少 `goal` 键时，会抛出 `KeyError` 而非返回友好的 ERROR 响应。测试 `test_missing_goal_in_step` 已验证此问题。

**影响**: 虽然是 step["agent"] 也使用 dict[] 访问，但 goal 缺失有实际场景（用户错误配置），代码应该 `.get("goal", "")` 或提前校验。

#### N-MEDIUM-2: batch/branch/loop 完成处理器重复代码

**文件**: `chain_executor.py`  
**行号**: L764-880  

`_handle_batch_complete` (L764-805)、`_handle_branch_complete` (L808-849)、`_handle_loop_complete` (L852-880) 三个函数的实现高度相似：

```
1. 从 last_result 提取对应结果数组
2. 保存到 state.context
3. 对当前 step 执行 verification
4. 如果 verification 失败 → 返回 VERIFICATION_FAILED
5. 推进 current_step += 1
6. 如果 step 超出 chain_def 长度 → 调用 _build_chain_done_result()
7. 否则返回 _build_step_result() 构建下一步
```

三个函数的差异仅在第1步（提取的 key 名称不同）。建议提取公共模板函数减少重复。

---

### 🔵 LOW (1项)

#### N-LOW-1: `STEP_VALID_STATUSES` 缺少 `APPROVE` 状态

**文件**: `chain_executor.py`  
**行号**: L64-69  
**问题**: `STEP_VALID_STATUSES["tdd"]` 和 `STEP_VALID_STATUSES["fix"]` 中未包含 `APPROVE`，但 `advance()` L1034 中明确处理了 `APPROVE` 状态（等效于 DONE）。

```python
if status in ("DONE", "APPROVE"):   # L1034
```

当前代码能通过显式的 OR 逻辑绕过这个问题，但 STEP_VALID_STATUSES 数据定义与运行时行为不一致，属于文档/维护隐患。

---

## 三、新建文件代码质量评估

### chain_config.py (47行) ⭐ 优秀

| 维度 | 评价 |
|------|------|
| 命名 | 常量名 `SCRIPT_DIR`、`ROUTE_MAP_DIR`、`INDEX_YAML_PATH`、`SKILL_CACHE_FILE` 清晰规范 |
| 功能 | 成功消除了 `route_engine.py` 和 `chain_executor.py` 之间的路径重复代码 |
| 异常处理 | `load_yaml_safe()` 中 `yaml is None` 检查到位，ImportError 清晰 |
| 缺陷 | 无功能缺陷。`load_index()` 和 `load_chain()` 是 thin wrapper，设计合理 |
| 建议 | 可考虑添加缓存避免重复读取同一 YAML 文件 |

### route_logger.py (84行) ⭐ 优秀

| 维度 | 评价 |
|------|------|
| 命名 | `LOG_FILE`、`LOG_MAX_BYTES`、`LOG_BACKUP_COUNT`、`LOW_CONFIDENCE_THRESHOLD` 命名规范 |
| 功能 | `_rotate_log()` 实现了标准日志轮转（删除最旧 → 依次重命名 → 重命名当前） |
| 异常处理 | `_rotate_log()` 中使用 `try/except OSError` 处理文件操作异常，粒度合理 |
| 逻辑 | `log_route()` 中 flagged 判断清晰（3种标记条件：llm_fallback/auto_tiebreak/low_confidence） |
| 缺陷 | 小问题：L13 使用 `os.pardir` 而不是 `".."` 虽然正确但略显不常见 |
| 建议 | `user_input[:200]` 截断长度应定义为常量 |

---

## 四、测试质量评估

### test_chain_executor.py (675行, 53个测试)

**测试组织结构**:
| 测试类 | 测试数 | 覆盖内容 |
|--------|--------|---------|
| `TestValidateSkills` | 4 | 合法/缺失/跳过/部分 skills |
| `TestStartChain` | 6 | 正常启动/缺owner/空chain/缺skills/report_only/持久化 |
| `TestAdvanceInit` | 3 | init状态/缺owner/空chain |
| `TestAdvanceBlocked` | 1 | BLOCKED状态 |
| `TestAdvanceNeedsContext` | 2 | NEEDS_CONTEXT/缺message |
| `TestAdvanceDoneWithConcerns` | 1 | DONE_WITH_CONCERNS积累 |
| `TestAdvanceNeedsFix` | 4 | spec/quality/unrecognized/max_retry |
| `TestAdvanceDone` | 5 | 推进/完成/APPROVE/非法状态/report_only |
| `TestBatchBranchLoop` | 5 | batch/branch/loop complete + progress |
| `TestRunVerification` | 5 | 无契约/空命令/简单命令/管道命令/超时 |
| `TestStatePersistence` | 4 | 缺失/回读/损坏/推进持久化 |
| `TestEdgeCases` | 8 | 缺current_step/越界/缺status/缺goal/target_idx/save_path/sanitize |
| `TestHelperFunctions` | 4 | build_done/handle_blocked |

**评分**:
- **结构**: ⭐⭐⭐⭐⭐ 测试类按功能分组，fixture 隔离 state 目录，命名清晰
- **深度**: ⭐⭐⭐⭐ 覆盖了正常流程 + 边界条件（空/损坏/越界）+ 异常路径
- **深度不足**: ❌ 缺少对 `_evaluate_and_decide()`、`aggregate_parallel_results()`、`_build_loop_result()` 的独立单元测试
- **失败率**: ❌ 6/53 ≈ 11.3% 失败率偏高，需修复后方可视为有效覆盖

### test_route_engine.py (69个测试)

- 64/64 非CLI 测试全部通过 ✅
- 5/5 CLI 测试全部失败 ❌ (见 N-CRITICAL-1)

---

## 五、代码异味专项检查

### 已消除的异味
| 原始异味 | 状态 | 说明 |
|---------|------|------|
| `advance()` 360 行超级函数 | ✅ 消除 | 拆分为15+个独立辅助函数，main advance() ~160行 |
| 3个"链结束"相同代码块 | ✅ 消除 | 统一使用 `_build_chain_done_result()` |
| 路径字符串重复 | ✅ 消除 | 提取到 `chain_config.py` |
| 日志内联代码 | ✅ 消除 | 提取到 `route_logger.py` |

### 新引入/残留的异味
| 异味类型 | 位置 | 说明 |
|---------|------|------|
| **重复代码** (~80%) | `chain_executor.py` L764-880 | `_handle_batch_complete`/`_handle_branch_complete`/`_handle_loop_complete` 结构完全相同 |
| **魔法数字** `0.2` | `route_engine.py` L262 | Skill 匹配加分 0.2，未定义为命名常量 |
| **魔法数字** `3` | `chain_executor.py` L356 | `batch_count` 默认值 3，应定义为常量 `DEFAULT_BATCH_COUNT` |
| **无防御 dict 访问** | `chain_executor.py` L393 | `step["goal"]` → 应使用 `.get("goal", "")` |
| **过多 `_save_state` 调用** | `chain_executor.py` 多处 | 单个 advance 调用中多次 `_save_state()` 写入，可考虑内存脏标记 |
| **docstring 参数描述冗余** | `chain_executor.py` 多处辅助函数 | 参数描述过于详细，几乎重复函数签名 |

---

## 六、修复前后对比总结

| 对比项 | 修复前 (原始质量报告) | 修复后 (本报告) |
|--------|---------------------|----------------|
| 总分 | 61/100 | **63/100** |
| 4个CRITICAL | 全部未修复 | 3个完全修复，1个部分修复（shell白名单） |
| 函数过长 | advance() 360行 | advance() ~160行 + 15个辅助函数 |
| 重复代码 | 3个链结束块 | 链结束已消除，但3个完成处理器产生新重复 |
| 新建文件 | 无 | chain_config.py + route_logger.py (质量优秀) |
| 新问题引入 | — | CLI argparse 缺陷 (CRITICAL), 6个测试失败 (HIGH) |
| 测试覆盖 | 无 chain_executor 测试 | 新增53个测试（但6个失败） |

---

## 七、评审结论

修复工作成功解决了原始质量报告中的 **3/4 个 CRITICAL 问题**（chain_step_skills 格式、decide/unrouted、confidence 超1.0），并对 `advance()` 超级函数进行了有效的拆分重构。新建的 `chain_config.py` 和 `route_logger.py` 代码质量优秀，达到了模块化解耦的设计目标。

然而，修复过程引入了 **1 个新的 CRITICAL 问题**（CLI argparse 设计缺陷导致 5 个测试全挂），且 **6 个 chain_executor 测试失败**尚未解决，其中 `test_missing_goal_in_step` 还暴露了 `_build_step_result()` 中 `step["goal"]` 缺少防御访问的源码缺陷。

**复评评分**: **63/100** — 较原始 61/100 微增 2 分，主要改善在代码可读性和重复代码维度，但测试覆盖率和新增缺陷拉低了整体得分。

**改进优先级建议**:
1. 🔴 修复 CLI argparse 设计缺陷（影响 5 个测试 + 所有 CLI 用户）
2. 🔴 修复 6 个 chain_executor 测试失败（其中 `step["goal"]` 缺陷最严重）
3. 🟠 补全 `VERIFY_COMMAND_BASENAMES` 白名单（uv/pytest/curl）
4. 🟡 提取 batch/branch/loop 完成处理器的公共模板
5. 🔵 定义 `SKILL_SCORE_BONUS = 0.2` 和 `DEFAULT_BATCH_COUNT = 3` 命名常量
