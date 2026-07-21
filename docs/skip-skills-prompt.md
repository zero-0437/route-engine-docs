# Skills Prompt 注入截停 — 机制与恢复

## 背景

Hermes 每次对话启动时，会在 system prompt 中注入完整的 `<available_skills>...</available_skills>` 技能列表（约 150-200 个 skill 条目，~2000 tokens/轮）。

路由引擎已接管技能→Agent 映射决策，这份列表在 system prompt 中**完全冗余**——主 Agent 不再需要遍历它来匹配任务。

## 实现方式

**Monkey-patch** 在路由引擎插件注册时执行，代码位于独立文件：

```
位置: /opt/data/plugins/zero-token-router/patch_skills.py
函数: patch()
调用: __init__.py → from .patch_skills import patch as _patch_skills_prompt
```

将 `agent.prompt_builder.build_skills_system_prompt()` 替换为返回 `""` 的空函数。该函数是 Hermes 构建 system prompt 时生成技能列表的唯一入口，替换后整个技能列表块不再出现。

### 时序

```
Gateway 启动 → 插件加载 → register() → monkey-patch
                               ↓
                    用户发消息 → session 创建 → _build_system_prompt()
                                                  ↓
                                              build_skills_system_prompt()
                                                  ↓
                                              "" （patched，无注入）
```

`register()` 在 gateway 启动时调用，远早于第一个 session 构建系统提示词，时序安全。

## 影响范围

| 功能 | 受影响？ | 说明 |
|------|---------|------|
| `skill_view(name)` | ❌ 否 | 读磁盘 SKILL.md，不依赖 prompt 注入 |
| `skill_manage()` | ❌ 否 | 写磁盘 SKILL.md，不依赖 prompt 注入 |
| `skills_list()` | ❌ 否 | 读磁盘目录，不依赖 prompt 注入 |
| 路由引擎 | ❌ 否 | 读 skill-map.yaml，不依赖 prompt 注入 |
| 主 Agent 匹配技能 | ❌ 否 | 已用 SOUL.md 铁律⑥ 声明不扫描列表 |
| 系统提示词大小 | ✅ **是** | 每轮节省 ~2000 tokens |

## 恢复方法

### 方法 A：禁用插件（推荐）

```bash
hermes config set plugins.enabled []
```

然后重启 gateway：

```bash
# 找 gateway PID
ps aux | grep 'gateway run'
# 发送 SIGTERM（s6 自动拉起）
kill -TERM <PID>
```

等待几秒后 gateway 重启，插件不再加载，monkey-patch 消失。

要重新启用：

```bash
hermes config set plugins.enabled [zero-token-router]
# 再次重启 gateway
```

### 方法 B：删除 patch_skills.py 或注释调用

编辑 `/opt/data/plugins/zero-token-router/__init__.py`，注释掉 import 行：

```python
# from .patch_skills import patch as _patch_skills_prompt

def register(ctx) -> None:
    """注册插件钩子。"""
    # _patch_skills_prompt()    # ← 注释掉这行
    ...
```

或直接删除 `/opt/data/plugins/zero-token-router/patch_skills.py`。

然后重启 gateway。

### 方法 C：临时测试（不重启）

在当前 session 中手动恢复：

```python
import agent.prompt_builder as pb
# 需要知道原始函数，已存在 pb.build_skills_system_prompt 的备份
# 注：仅在当前进程生效，不影响 gateway 后续 session
```

### 验证恢复效果

恢复后，查看下一条消息的 system prompt 中是否出现 `<available_skills>...` 块即可确认。

## 升级兼容性

Monkey-patch 写在插件代码中（`/opt/data/plugins/`），不修改 Hermes 框架文件（`site-packages/`）。升级 Hermes 时：

- `pip install -U hermes-agent` → 框架文件被覆盖
- **不影响插件** — monkey-patch 代码在插件内，升级后继续生效
- 即使 `build_skills_system_prompt` 签名变更，lambda 的 `*a, **kw` 兼容任意参数

如需彻底移除，按方法 A 或 B 操作即可，无残留。
