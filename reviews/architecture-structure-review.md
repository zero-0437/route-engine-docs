# 架构质量评审报告 — data-analyst 视角

**项目**: hermes-zero-token-router
**日期**: 2026-07-21
**角色**: data-analyst (架构)

---

## 一、项目结构分层合理性

### 1.1 当前目录结构

```
hermes-zero-token-router/
├── src/                          # 公开版核心代码 ← 建议作为唯一源码目录
│   ├── route_engine.py           # 路由引擎核心
│   ├── chain_executor.py         # Chain 状态机
│   ├── chain_config.py           # YAML 配置加载
│   └── route_logger.py           # 日志模块（未引用）
├── scripts/                      # 旧版代码 + 工具脚本 ← 问题集中区
│   ├── route_engine.py           # ⚠️ 与 src/ 重复
│   ├── chain_executor.py         # ⚠️ 与 src/ 重复
│   ├── chain_config.py           # ⚠️ 完全一致
│   ├── analyze-route-log.py      # 日志分析工具
│   ├── route-log-suggest.py      # 规则建议工具
│   ├── validate-route-map.py     # 规则验证器
│   ├── hermes-route-add          # 交互式规则添加
│   └── agent-mgmt/               # Agent 管理模板
├── route-map/                    # ✅ 路由规则目录（设计良好）
│   ├── index.yaml
│   ├── shared.yaml
│   ├── routes/                   # 15 个 Agent 规则
│   └── chains/                   # 8 个 Chain 定义
├── tests/                        # ✅ 测试目录
├── docs/                         # ✅ 文档目录
├── logs/                         # ✅ 运行日志
├── plugins/                      # 插件目录
│   └── route-router/             # ⚠️ 命名不统一: route-router ≠ zero-token-router
├── reviews/                      # ❌ 10 个废弃审查文件
├── examples/                     # ✅ 示例目录
├── *.md (6个根级文件)            # ❌ 文档过多分散
└── mcp-router-server.py          # 💭 可移入 scripts/
```

### 1.2 理想目标结构

```
hermes-zero-token-router/
├── src/                           # 唯一源码目录
│   ├── __init__.py
│   ├── route_engine.py            # 路由引擎核心
│   ├── chain_executor.py          # Chain 状态机
│   ├── chain_config.py            # YAML 配置加载
│   └── route_logger.py            # 日志模块
├── scripts/                       # 仅维护/工具脚本
│   ├── validate-route-map.py
│   ├── analyze-route-log.py
│   ├── suggest-route-log.py       # 统一 snake_case
│   ├── mcp-router-server.py       # 从根目录移入
│   └── hermes-route-add
├── route-map/                     # 保持不变（设计良好）
│   ├── index.yaml
│   ├── shared.yaml
│   ├── routes/
│   └── chains/
├── docs/                          # 统一文档目录（根目录只留 README）
│   ├── CHANGELOG.md               # 合并后的单一 changelog
│   ├── ARCHITECTURE.md            # 从根目录移入
│   ├── ROUTE_MAP_SPEC.md          # 从根目录移入
│   ├── DELEGATION_PROTOCOL.md
│   ├── PLUGIN_INTEGRATION.md
│   └── ...
├── adr/                           # 🆕 新建 ADR 目录
│   ├── ADR-001-dual-directory-decision.md
│   └── ...
├── reviews/                       # 只保留最新一份，其余归档
│   └── latest-review.md
├── tests/
├── plugins/
│   └── zero-token-router/         # ✅ 统一命名
└── README.md                      # 根目录只留这一个
```

---

## 二、问题② 深入分析：根目录文档过多且分散

### 2.1 文档分布统计

| 位置 | 文件数 | 总行数 | 总大小 |
|------|--------|--------|--------|
| 根目录 *.md | 6 | 1,351 | ~60KB |
| docs/ | 8 | 920 | ~48KB |
| **总计** | **14** | **2,271** | **~108KB** |

### 2.2 文档拓扑问题

```
当前混乱拓扑：
  README.md (根) ──── 介绍项目
  ARCHITECTURE.md (根) ── 架构说明
  ROUTE_MAP_SPEC.md (根) ── 路由规则规范
  
  CHANGELOG-FULL.md (根) ←→ docs/CHANGELOG.md  ⚠️ 互相引用但内容不同
  ROUTE-ENGINE-CHANGELOG.md (根) ←→ docs/ROUTE-ENGINE-CHANGELOG.md ⚠️ 脱敏/内部版本
  
  CHAIN_EXECUTOR.md (根) ── chain 执行器文档（为何不在 docs/？）
```

### 2.3 分叉的 changelog

| 文件 | 行数 | 版本 | 内容说明 |
|------|------|------|---------|
| /CHANGELOG-FULL.md | 266 | v2.6 (2026-07-06) | 内部完全版，含架构全景 |
| /docs/CHANGELOG.md | 341 | 2026-07-04 | 更早的完全版，含修复流程 |
| /ROUTE-ENGINE-CHANGELOG.md | 318 | v2.5 (2026-07-05) | 脱敏公开版，聚焦架构改进 |
| /docs/ROUTE-ENGINE-CHANGELOG.md | 125 | 2026-07-04 | 脱敏版，架构优化发布 |

**四条 changelog 交织在一起，版本混乱。作为新开发者完全无法判断哪个是最新。**

### 2.4 整改方案

**短期方案（30min）**：
1. 将 4 个 changelog 合并为 `docs/CHANGELOG.md`
2. 根目录删除 `CHANGELOG-FULL.md` 和 `ROUTE-ENGINE-CHANGELOG.md`
3. 根目录保留 `README.md` 作为唯一入口

**中期方案（1h）**：
1. 将 `ARCHITECTURE.md`、`ROUTE_MAP_SPEC.md`、`CHAIN_EXECUTOR.md` 移入 `docs/`
2. 根目录只保留 `README.md`
3. 在 `README.md` 中提供到 `docs/` 的链接索引

---

## 三、问题③ 深入分析：reviews/ 废弃审查文件

### 3.1 文件清单

| 文件名 | 行数 | 文件大小 | 创建日期 | 内容类型 |
|--------|------|---------|----------|---------|
| architecture-final2.md | 416 | 21,377 | Jul 19 | 架构终审2 |
| architecture-fix.md | 443 | 22,141 | Jul 19 | 架构修复 |
| architecture-review.md | 462 | 23,888 | Jul 19 | 架构初审 |
| final-review.md | 30 | 1,450 | Jul 19 | 终审摘要 |
| final-review2.md | 325 | 15,264 | Jul 19 | 终审2 |
| quality-final2.md | 209 | 13,049 | Jul 19 | 质量终审2 |
| quality-fix.md | 347 | 16,143 | Jul 19 | 质量修复 |
| quality-review.md | 464 | 20,953 | Jul 19 | 质量初审 |
| review-fix.md | 263 | 16,272 | Jul 19 | 综合修复 |
| spec-review.md | 445 | 18,226 | Jul 19 | spec 初审 |

**全部 10 个文件共 3,404 行，约 170KB，且全部创建于同一日期（Jul 19）。**

### 3.2 评审迭代链重构

根据文件名推测的迭代过程：

```
Round 1: architecture-review → quality-review → spec-review
Round 2: architecture-fix → quality-fix → review-fix
Round 3: architecture-final2 → quality-final2 → final-review → final-review2
```

**问题**:
1. 每次迭代6-10个文件全部保留，无迭代标签（v1/v2/v3）
2. `reviews/` 不是归档目录，混入了正在进行的审查
3. 文件名含义不透明：`final-review.md` vs `final-review2.md` vs `review-fix.md` 无法区分
4. 大量已过时的审查结论残留在目录中，会被新审查者误当作最新结论

### 3.3 整改方案

**短期方案（15min）**：
1. 将全部 10 个旧审查文件移动到 `reviews/archive/` 子目录
2. 为旧文件添加 `.old` 后缀或归档标记

**命名规范建议**：
```
reviews/
├── archive/                        # 旧审查归档
│   ├── 20260719-architecture-v1.md
│   ├── 20260719-architecture-v2.md
│   ├── 20260719-quality-v1.md
│   ├── 20260719-quality-v2.md
│   ├── 20260719-spec-v1.md
│   └── ...
└── spec-compliance-review.md        # 本次产出（当前评审）
├── code-quality-review.md          # 本次产出
├── architecture-review.md          # 本次产出
```

**文件命名规范**：`<维度>-<迭代版本>.md`
- `spec-compliance-review.md`
- `code-quality-review.md`
- `architecture-structure-review.md`

---

## 四、架构分层评分

### 4.1 六维评估

| 维度 | 评分 | 说明 |
|------|------|------|
| **目录结构清晰度** | 4/10 | src/ vs scripts/ 严重重复，根目录文档混乱 |
| **模块内聚性** | 6/10 | route-map/ 设计良好，但 route_logger 未使用 |
| **依赖方向** | 8/10 | 依赖方向正确，无循环依赖 |
| **扩展性** | 7/10 | route-map/ YAML 驱动设计良好 |
| **可维护性** | 4/10 | 双目录分叉导致每次修改需要同步两份代码 |
| **技术债务** | 3/10 | reviews/ 45% 废弃文件，src/scripts/ 双倍维护成本 |

### 4.2 关键风险

| 风险 | 等级 | 影响 |
|------|------|------|
| src/ vs scripts/ 双目录分叉 | 🔴 高 | 已导致 manual_skills bug |
| 5 个死路由 Agent | 🔴 高 | 路由命中后无人执行 |
| 文档版本混乱 | 🟡 中 | 新开发者无法判断最新文档 |
| reviews/ 废弃文件残留 | 🟡 中 | 新旧评审结论混在一起 |
| plugin 目录命名不一致 | 💭 低 | 不影响功能 |

---

## 五、整改建议优先级（综合三轴）

| 优先级 | 问题 | 领域 | 预估工时 |
|--------|------|------|---------|
| 🔴 P0 | 确认 src/ 为主版本，scripts/ 改为工具目录 | 架构+代码 | 2h |
| 🔴 P0 | 删除 5 个死路由 Agent | Spec+架构 | 30min |
| 🔴 P0 | 修复 scripts/ 的 manual_skills bug | 代码 | 10min |
| 🟡 P1 | 合并 4 个 changelog → docs/CHANGELOG.md | Spec+架构 | 30min |
| 🟡 P1 | reviews/ 历史文件归档 → archive/ | 架构 | 15min |
| 🟡 P1 | 移入根目录文档到 docs/ | 架构 | 30min |
| 🟡 P2 | 创建 ADR 目录 | Spec | 1h |
| 🟡 P2 | 统一文件命名风格 | 代码 | 30min |
| 💭 P3 | 统一 plugins/ 目录名 | 代码 | 5min |
| 💭 P3 | 移动 mcp-router-server.py | 架构 | 5min |

---

## 六、总体架构健康度

```
架构健康度: 5.2/10

● 核心设计（route-map YAML 驱动）: 优秀
● 测试完整性: 良好
● 目录结构: 需要重构（双目录分叉是最大问题）
● 文档管理: 需要规范化
● 技术债务: 可管理但需立即处理
```

**一句话结论**: 项目核心设计良好（YAML 驱动的路由规则、chain 编排状态机），但双目录分叉策略和文档散乱带来了实质性维护负担和已发生的 bug。
