# Chain Executor — 状态机编排引擎

## 概述

Chain Executor 是 route_engine 的配套组件，负责执行链式多 Agent 编排。当路由引擎发现匹配的 Agent 带有 chain 定义时，由 chain_executor 接管后续编排流程。

**核心原则**：chain_executor 只产出决策 JSON，不直接调用 `delegate_task`。主 Agent 读取决策 JSON → 执行 `delegate_task` → 将结果回传给 chain_executor 推进状态机。

## 状态机设计

```
                    ┌──────────┐
                    │  START   │
                    └────┬─────┘
                         │
                         ▼
                    ┌──────────┐
                    │ ADVANCE  │ ←── 每步执行后返回此状态
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              │          │          │
              ▼          ▼          ▼
        ┌─────────┐ ┌─────────┐ ┌─────────┐
        │ SERIAL  │ │PARALLEL │ │INTERACT │
        └─────────┘ └─────────┘ └─────────┘
              │          │          │
              └──────────┼──────────┘
                         │
                         ▼
                    ┌──────────┐     ┌──────────┐
                    │ ADVANCE  │────→│  LOOP    │
                    └────┬─────┘     └────┬─────┘
                         │                │
                         ▼                │
                    ┌──────────┐          │
                    │ CONTINUE │──────────┘
                    └────┬─────┘
                         │
                         ▼
                    ┌──────────┐
                    │   DONE   │
                    └──────────┘
```

### 生命周期

1. **start** — 初始化 chain 状态机，返回第一个步骤
2. **advance** — 执行当前步骤后推进到下一步
3. **continue** — 继续执行（loop 类型专用）
4. **done** — 所有步骤完成，返回最终结果

## 4 种步骤类型

### serial — 串行执行

顺序执行，前一步的输出作为后一步的输入。

```json
{
  "type": "serial",
  "steps": [
    {"agent": "programmer", "goal": "实现核心逻辑"},
    {"agent": "error-analyst", "goal": "审查代码质量"},
    {"agent": "docs-writer", "goal": "编写使用文档"}
  ]
}
```

**执行流程**：A → B → C（等待 B 完成后才启动 C）

### parallel — 并行执行

多 Agent 同时执行，所有完成后汇总结果。

```json
{
  "type": "parallel",
  "steps": [
    {"agent": "programmer", "goal": "实现模块 A"},
    {"agent": "programmer", "goal": "实现模块 B"},
    {"agent": "programmer", "goal": "实现模块 C"}
  ]
}
```

**执行流程**：A + B + C（同时启动，全部完成后汇总）

### interactive — 交互式执行

需要用户输入的步骤，暂停等待外部输入。

```json
{
  "type": "interactive",
  "steps": [
    {"agent": "pm-agent", "goal": "分析需求，询问用户决策"},
    {"agent": "programmer", "goal": "按决策实现"}
  ]
}
```

**执行流程**：A（等待用户输入）→ B（用输入继续）

### loop — 循环执行

重复执行直到条件满足。

```json
{
  "type": "loop",
  "max_iterations": 3,
  "steps": [
    {"agent": "error-analyst", "goal": "审查代码"},
    {"agent": "programmer", "goal": "修复问题"}
  ]
}
```

**执行流程**：A → B →（检查条件）→ A → B →（条件满足）→ 结束

## start → advance → continue → done 生命周期详解

### start — 初始化

```bash
python3 scripts/chain_executor.py start \
  --task_id T-001 \
  --chain_def '[{"agent":"programmer","goal":"实现功能"}]' \
  --chain_step_skills '{"programmer_0":["test-driven-development"]}' \
  --chain_owner programmer
```

**输出**：

```json
{
  "status": "init",
  "task_id": "T-001",
  "current_step": 0,
  "total_steps": 1,
  "type": "serial",
  "step": {"agent": "programmer", "goal": "实现功能"}
}
```

### advance — 推进

```bash
python3 scripts/chain_executor.py advance \
  --task_id T-001 \
  --chain_def '[{"agent":"programmer","goal":"实现功能"}]' \
  --chain_step_skills '{"programmer_0":["test-driven-development"]}' \
  --last_result '{"agent":"programmer","status":"DONE","output_path":"..."}'
```

**输出**：

```json
{
  "status": "done",
  "task_id": "T-001",
  "step_results": [
    {"agent": "programmer", "status": "DONE", "output_path": "..."}
  ]
}
```

### continue — 循环继续

```bash
python3 scripts/chain_executor.py advance \
  --task_id T-001 \
  --chain_def '{"type":"loop","max_iterations":3,"steps":[...]}' \
  --chain_step_skills '{}' \
  --last_result '{"agent":"error-analyst","status":"DONE","issues_found":3}'
```

**输出**（还有问题，继续循环）：

```json
{
  "status": "continue",
  "iteration": 2,
  "max_iterations": 3,
  "step": {"agent": "programmer", "goal": "修复问题"}
}
```

### done — 完成

```bash
python3 scripts/chain_executor.py advance \
  --task_id T-001 \
  --chain_def '{"type":"loop","max_iterations":3,"steps":[...]}' \
  --chain_step_skills '{}' \
  --last_result '{"agent":"error-analyst","status":"DONE","issues_found":0}'
```

**输出**：

```json
{
  "status": "done",
  "task_id": "T-001",
  "step_results": [
    {"agent": "programmer", "status": "DONE"},
    {"agent": "error-analyst", "status": "DONE", "issues_found": 0}
  ],
  "iterations": 2,
  "message": "所有问题已修复，循环提前结束"
}
```

## 批量（batch）执行模式

chain_executor 支持批量执行模式，通过 `run` 子命令：

```bash
python3 scripts/chain_executor.py run \
  --task_id T-001 \
  --chain_agent programmer \
  --last_result '{"status":"init"}'
```

这会读取 `logs/chain_state.json` 中的持久化状态并推进到下一步。适用于主 Agent 在长时间任务中的恢复场景。

## 与 route_engine 的协作关系

```
route_engine.decide()
    │
    ├─ 返回结果包含 chain 定义
    │
    ▼
主 Agent 读取 chain 定义
    │
    ├─ chain_executor.start() → 获取第一个步骤
    │
    ▼
主 Agent 执行 delegate_task(step.agent, step.goal)
    │
    ├─ 拿到结果 → chain_executor.advance()
    │
    ▼
chain_executor 返回下一步或 done
    │
    ├─ 继续循环（serial/loop）或 done
    │
    ▼
主 Agent 重复直到 status == "done"
```

**关键设计决策**：
- Chain executor 不做执行，只做编排决策
- 主 Agent 负责实际的 delegate_task 调用
- 这种分离确保 chain_executor 保持轻量、可测试、零网络依赖

## Chain 定义文件示例

```yaml
# route-map/chains/debugger-chain.yaml
steps:
  - agent: error-analyst
    goal: 分析错误日志，定位根因
    type: serial
  - agent: programmer
    goal: 按分析结果修复代码
    type: serial
  - agent: error-analyst
    goal: 验证修复结果
    type: serial

chain_keywords:
  - 调试
  - debug
  - 错误修复
  - bug修复

report_only: false
chain_step_skills:
  error-analyst_0: [systematic-debugging]
  programmer_1: [test-driven-development]
  error-analyst_2: [verification-before-completion]
