# Hermes Zero Token Router

> Zero-token routing engine for Hermes Agent — intelligent agent dispatch via route-map, chain execution, and multi-review quality assurance.

## Overview

The **Zero Token Router** is a routing and execution framework for [Hermes Agent](https://hermes-agent.nousresearch.com). It enables zero-token-cost dispatch of tasks to specialized agent roles via a declarative route-map, with support for chained multi-agent workflows.

### Key Components

| Component | Path | Description |
|---|---|---|
| Route Engine | `src/route_engine.py` | Core routing logic — matches tasks to agents via pattern-based rules |
| Chain Executor | `src/chain_executor.py` | Multi-step chain execution for sequential agent workflows |
| Chain Config | `src/chain_config.py` | Configuration loader for chain definitions |
| Route Logger | `src/route_logger.py` | Structured logging and analytics for route decisions |

### Route Map

| Directory | Description |
|---|---|
| `route-map/index.yaml` | Master routing index — agent definitions, patterns, and dispatch rules |
| `route-map/routes/` | Per-agent route configurations (15 agents) |
| `route-map/chains/` | Multi-agent chain definitions (8 chains) |

### Agents

| Agent | File | Purpose |
|---|---|---|
| Triage | `routes/triage.yaml` | Initial request classification |
| Programmer | `routes/programmer.yaml` | Code generation & engineering |
| Spec Agent | `routes/spec-agent.yaml` | Specification authoring |
| Docs Writer | `routes/docs-writer.yaml` | Documentation generation |
| PM Agent | `routes/pm-agent.yaml` | Project management oversight |
| Prompt Engineer | `routes/prompt-engineer.yaml` | Prompt design & optimization |
| UI Designer | `routes/ui-designer.yaml` | Interface design |
| Data Analyst | `routes/data-analyst.yaml` | Data analysis & visualization |
| Error Analyst | `routes/error-analyst.yaml` | Error analysis & debugging |
| Reality Checker | `routes/reality-checker.yaml` | Factual verification |
| Dual Review | `routes/dual-review.yaml` | Collaborative review workflow |
| Document Processor | `routes/document-processor.yaml` | Document processing |
| File Ops | `routes/file-ops.yaml` | File operations |
| Memory Agent | `routes/memory-agent.yaml` | Memory management |
| Synology Helper | `routes/synology-helper.yaml` | Synology NAS operations |

### Chains

| Chain | File | Agents Involved |
|---|---|---|
| Triage Chain | `chains/triage-chain.yaml` | Triage → routing decision |
| Programmer Chain | `chains/programmer-chain.yaml` | Spec → Programmer → Review |
| Spec Agent Chain | `chains/spec-agent-chain.yaml` | Research → Spec → Review |
| Dual Review Chain | `chains/dual-review-chain.yaml` | Dual independent review |
| Research Chain | `chains/research-chain.yaml` | Research → Analysis → Report |
| Debugger Chain | `chains/debugger-chain.yaml` | Error → Analysis → Fix |
| Follow Process Chain | `chains/follow-process-chain.yaml` | Process enforcement |
| Learn Chain | `chains/learn-chain.yaml` | Knowledge acquisition |

### Changelog

See [CHANGELOG.md](./CHANGELOG.md) for the complete version history.

### Quality Reviews

All specifications, architecture, and code have undergone rigorous multi-round review:

| Review | File |
|---|---|
| Spec Review (R1) | `reviews/spec-review.md` |
| Quality Review (R1) | `reviews/quality-review.md` |
| Architecture Review (R1) | `reviews/architecture-review.md` |
| Spec Fix (R2) | `reviews/review-fix.md` |
| Quality Fix (R2) | `reviews/quality-fix.md` |
| Architecture Fix (R2) | `reviews/architecture-fix.md` |
| Final Review (R3) | `reviews/final-review.md` |
| Final Review 2 (R3) | `reviews/final-review2.md` |
| Quality Final (R3) | `reviews/quality-final2.md` |
| Architecture Final (R3) | `reviews/architecture-final2.md` |

### Task Slice

See [task-slice.md](./task-slice.md) for the complete task breakdown and implementation plan.

## License

Private repository — internal use only.
