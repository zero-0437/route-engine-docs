# Route Engine — 版本发布记录 (FULL)

> **版本:** v2.5+ (based on v2.5)
> **基础发布版本:** v2.5 — 61cd3fb (2026-07-05)
> **当前 HEAD:** b753b69 (2026-07-05)
> **作者:** zero-0437
> **日期:** 2026-07-05

---

## 变更清单

### 代码变更

| 提交 | 文件 | 变更摘要 |
|------|------|----------|
| b753b69 | tests/test_validate_route_map.py | test: unit tests for `--fix`/`--apply` and near-synonym detection (19 tests) |
| 8adfed9 | scripts/route-log-suggest.py, scripts/llm-rule-suggest.py | refactor: rename `llm-rule-suggest.py` → `route-log-suggest.py`, update internal refs |
| 5c7104d | scripts/validate-route-map.py | fix: short CJK text (≤3 chars) no longer flagged as near-synonyms |
| 38e5ace | route-map/routes/prompt-engineer.yaml | fix: restore '提示词' rule incorrectly dropped by `--fix --apply` (not synonym of '提示工程') |
| 49b3b48 | route-map/routes/ (8 files) | fix: apply `--fix --apply` dedup merge — 21 redundant rule pairs removed |
| 522076d | scripts/llm-rule-suggest.py | feat: add `llm-rule-suggest.py` for misroute analysis and YAML diff generation (~577 lines) |
| 0aad83e | scripts/validate-route-map.py | feat: add `--fix` mode for semi-auto rule dedup merge (~196 lines added) |
| a0847b8 | docs/ | docs: add `agent-rule-review-checklist.md` + `fuzzy-phase-B-status.md` |
| 1aad2de | CHANGELOG-FULL.md, CHANGELOG.md | P0-3: remove redundant CHANGELOG files (legacy v1, superseded by `docs/CHANGELOG.md` v2) |
| 41aca45 | examples/ | P0-2: sync examples from public repo — add `dual-review-chain.yaml`, `dual-review-route.yaml`, `pub-chain.yaml` |
| 1894ea9 | docs/task-slice.md | P0-1: move `task-slice.md` → `docs/` with `git mv` for history tracking |

---

### 已删除规则（`--fix --apply` 去重，commit 49b3b48）

21 对冗余规则在 8 个 route 文件中被去除（net -161 行）：

| 文件 | 删除规则数 | 净变更 |
|------|-----------|--------|
| `route-map/routes/docs-writer.yaml` | 23 条 | −73 行 |
| `route-map/routes/memory-agent.yaml` | 22 条 | −75 行 |
| `route-map/routes/file-ops.yaml` | 19 条 | −57 行 |
| `route-map/routes/spec-agent.yaml` | 19 条 | −62 行 |
| `route-map/routes/data-analyst.yaml` | 17 条 | −70 行 |
| `route-map/routes/synology-helper.yaml` | 14 条 | −48 行 |
| `route-map/routes/prompt-engineer.yaml` | 13 条 | −32 行 |
| `route-map/routes/pm-agent.yaml` | 12 条 | −38 行 |
| **合计** | **139 条 pattern 行** | **−161 行** |

去重依据：相同 `(weight, skills)` 分组内的 CJK 近义词规则，保留更长/更具体的 pattern。

---

### 关键指标

| 指标 | 数值 |
|------|------|
| 总测试通过率 | 19/19 通过 (`test_validate_route_map.py`) — 新增 19 个单元测试 |
| 净代码变更 (v2.5 以来) | +1867 / −782 = **+1085 行** (不含 CHANGELOG) |
| 规则去重 | 21 对冗余规则 / 净减 **−161 行** (8 个 route 文件) |
| 新增工具 | `route-log-suggest.py` (~577 行)，`validate-route-map.py --fix` (~196 行新增) |
| 重构文件 | `llm-rule-suggest.py` → `route-log-suggest.py`（内部路径对齐） |
| 文档新增 | `agent-rule-review-checklist.md`, `fuzzy-phase-B-status.md`, `docs/task-slice.md` |
| 示例同步 | `dual-review-chain.yaml`, `dual-review-route.yaml`, `pub-chain.yaml` |

---

### 文件统计（v2.5 → v2.5+ 增量）

```
 11 files changed, 885 insertions(+), 755 deletions(-)    # 非 CHANGELOG 变更
 19 files changed, 1768 insertions(+), 1485 deletions(-)  # 含 CHANGELOG 删除
```

**主要变更文件：**
| 文件 | 变更说明 |
|------|----------|
| `scripts/validate-route-map.py` | +201 行 — 新增 `--fix`/`--apply` 模式，4 个函数 (`_find_redundant_pairs`, `_dedup_and_generate_patch`, `_apply_patches`, `_output_fix_suggestions`) |
| `scripts/llm-rule-suggest.py` → `scripts/route-log-suggest.py` | ~577 行 — 新工具，重命名 |
| `tests/test_validate_route_map.py` | 新文件 — 19 个测试用例 |
| `route-map/routes/*.yaml` (8 个) | −161 行净变更 — 规则去重合并 |

---

*CHANGELOG-FULL.md — 内部完全版本，包含完整提交细节与内部路径。*
