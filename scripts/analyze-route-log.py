#!/usr/bin/env python3
"""
analyze-route-log.py — 路由日志分析维护脚本

子命令:
  summary   [默认] 输出统计摘要、Agent 排名、Flagged 条目清单及改进建议
  analyze   规则级命中统计 + 冗余检测报告

读取 logs/route-engine.jsonl，结合 route-map/*.yaml 规则定义进行分析。
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

import yaml

_LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "logs", "route-engine.jsonl"
)
_ROUTE_MAP_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "route-map"
)
_ROUTES_DIR = os.path.join(_ROUTE_MAP_DIR, "routes")


# ── 通用 ───────────────────────────────────────────────────────────


def load_entries():
    """加载所有日志条目"""
    if not os.path.exists(_LOG_PATH):
        print(f"[错误] 日志文件不存在: {_LOG_PATH}")
        return []

    entries = []
    with open(_LOG_PATH, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[警告] 第 {lineno} 行格式错误，已跳过: {e}")

    return entries


def load_route_map_rules():
    """加载所有 route-map routes/*.yaml 文件，返回
    {agent_name: [rule_dict, ...], ...}
    """
    agents_rules = {}
    if not os.path.isdir(_ROUTES_DIR):
        return agents_rules
    for fname in os.listdir(_ROUTES_DIR):
        if not fname.endswith(".yaml") or fname == "shared.yaml":
            continue
        fpath = os.path.join(_ROUTES_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not isinstance(data, dict):
                continue
            agent = data.get("agent") or fname.replace(".yaml", "")
            rules = data.get("rules", [])
            if isinstance(rules, list):
                # 给每个规则加上其在文件中的序号（1-based）
                for i, rule in enumerate(rules):
                    rule = dict(rule)  # copy
                    rule["_rule_index"] = i + 1
                    rule["_agent"] = agent
                    rules[i] = rule
                agents_rules[agent] = rules
        except (yaml.YAMLError, OSError):
            continue
    return agents_rules


# ── summary 子命令（原逻辑） ────────────────────────────────────────


def do_summary(entries):
    """原 analyze() 逻辑，输出统计摘要"""
    if not entries:
        print("没有日志数据可分析。")
        return

    total = len(entries)

    # ── 统计按 method ──────────────────────────────────────────────
    method_counter = Counter(e.get("method", "unknown") for e in entries)
    auto_count = method_counter.get("auto", 0)
    fallback_count = method_counter.get("llm_fallback", 0)
    tiebreak_count = method_counter.get("auto_tiebreak", 0)

    # ── Flagged 统计 ──────────────────────────────────────────────
    flagged_entries = [e for e in entries if e.get("flagged")]
    flagged_count = len(flagged_entries)

    # ── 按 Agent 调用次数 ──────────────────────────────────────────
    agent_counter = Counter(e.get("agent", "") for e in entries)
    agent_sorted = agent_counter.most_common()

    # ── 按 Agent 回退率 ───────────────────────────────────────────
    agent_fallback = defaultdict(lambda: {"total": 0, "fallback": 0})
    for e in entries:
        agent = e.get("agent", "")
        agent_fallback[agent]["total"] += 1
        if e.get("method") == "llm_fallback":
            agent_fallback[agent]["fallback"] += 1

    # ── 时间范围 ──────────────────────────────────────────────────
    timestamps = [e.get("ts", "") for e in entries if e.get("ts")]
    ts_min = min(timestamps)[:10] if timestamps else "N/A"
    ts_max = max(timestamps)[:10] if timestamps else "N/A"

    # ══════════════════════════════════════════════════════════════
    #  输出报告
    # ══════════════════════════════════════════════════════════════
    print("=== 路由日志分析报告 ===")
    print(f"统计周期: {ts_min} ~ {ts_max}")
    print(f"总路由次数: {total}")
    if total:
        print(f"auto: {auto_count} ({auto_count / total * 100:.1f}%)")
        print(f"llm_fallback: {fallback_count} ({fallback_count / total * 100:.1f}%)")
        print(f"auto_tiebreak: {tiebreak_count} ({tiebreak_count / total * 100:.1f}%)")
    else:
        print("auto: 0 (0.0%)")
        print("llm_fallback: 0 (0.0%)")
        print("auto_tiebreak: 0 (0.0%)")
    print(f"flagged: {flagged_count} ({flagged_count / total * 100:.1f}%)")

    # ── Top Agent ──────────────────────────────────────────────────
    print(f"\nTop Agent 调用:")
    for agent, count in agent_sorted:
        print(f"  {agent}: {count}")

    # ── Flagged 条目 ──────────────────────────────────────────────
    if flagged_entries:
        print(f"\nFlagged 条目:")
        for e in flagged_entries:
            reason = e.get("flag_reason", "?")
            snippet = e.get("input", "")[:40]
            agent = e.get("agent", "?")
            conf = e.get("confidence", "?")
            print(f"  [{reason}] \"{snippet}\" → {agent} (conf={conf})")

    # ── 改进建议 ──────────────────────────────────────────────────
    print(f"\n改进建议:")
    suggestions = []
    for agent, stats in sorted(agent_fallback.items(), key=lambda x: x[1]["fallback"] / max(x[1]["total"], 1), reverse=True):
        total_a = stats["total"]
        fall_a = stats["fallback"]
        rate = fall_a / total_a if total_a else 0
        if rate >= 0.15 and total_a >= 3:
            if fall_a == total_a:
                suggestions.append(
                    f"  - {agent} 回退率 {rate:.0%}（共 {total_a} 次全部回退），"
                    f"建议补充\"{agent.replace('-', '')}\"相关关键词规则"
                )
            else:
                suggestions.append(
                    f"  - {agent} 回退率 {rate:.0%}（{fall_a}/{total_a}），"
                    f"建议补充匹配关键词以降低回退"
                )

    # 额外建议：flagged 比例过高
    if flagged_count > 0 and total > 0:
        flagged_rate = flagged_count / total
        if flagged_rate > 0.2:
            suggestions.append(
                f"  - 异常标记比例 {flagged_rate:.0%}，建议审查路由规则阈值"
            )

    if not suggestions:
        print("  (暂无改进建议)")
    else:
        for s in suggestions:
            print(s)


# ── analyze 子命令（新增） ──────────────────────────────────────────


# 近义词/子串分组阈值
# 用于判断两个中文短语是否语义近似
CJK_RE = re.compile(r'[\u4e00-\u9fff]+')


def _extract_cjk_chars(text: str) -> str:
    """提取文本中的中文字符"""
    return "".join(CJK_RE.findall(text))


def _is_typo_variant(a: str, b: str) -> bool:
    """判断两个短语是否只有错别字区别（Levenshtein ≤ 1 且共享大部分 CJK 字符）"""
    a_cjk = _extract_cjk_chars(a)
    b_cjk = _extract_cjk_chars(b)
    if not a_cjk or not b_cjk:
        return False
    # 编辑距离 ≤ 2 且 CJK 字符集大部分重叠
    if abs(len(a_cjk) - len(b_cjk)) > 1:
        return False
    if len(a_cjk) < 2 or len(b_cjk) < 2:
        return _levenshtein(a_cjk, b_cjk) <= 1
    overlap = len(set(a_cjk) & set(b_cjk))
    min_len = min(len(set(a_cjk)), len(set(b_cjk)))
    if min_len == 0:
        return False
    return _levenshtein(a_cjk, b_cjk) <= 2 and overlap / min_len >= 0.5


def _levenshtein(s1: str, s2: str) -> int:
    """计算编辑距离"""
    if len(s1) < len(s2):
        s1, s2 = s2, s1
    if not s2:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            cost = 0 if c1 == c2 else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[-1]


def _is_near_synonym(a: str, b: str) -> bool:
    """判断两个中文短语是否为近义词/语义相近的规则

    判断标准：
    1. 错别字变体（如 泄漏↔泄露）
    2. 包含关系：一个短语被另一个完全包含（如 审查 被包含在 代码审查 / 审查代码）
    3. CJK Jaccard 相似度高（≥0.5）且长度相近
    """
    a_cjk = _extract_cjk_chars(a)
    b_cjk = _extract_cjk_chars(b)
    if not a_cjk or not b_cjk:
        return False

    # 错别字变体
    if _is_typo_variant(a, b):
        return True

    # 包含关系（一个短语是另一个的子串）
    if a_cjk in b_cjk or b_cjk in a_cjk:
        if a_cjk != b_cjk:
            return True

    # CJK Jaccard 相似度
    set_a = set(a_cjk)
    set_b = set(b_cjk)
    if not set_a or not set_b:
        return False
    jaccard = len(set_a & set_b) / len(set_a | set_b)
    # 长度相近且 Jaccard 高
    len_ratio = min(len(a_cjk), len(b_cjk)) / max(len(a_cjk), len(b_cjk))
    return jaccard >= 0.5 and len_ratio >= 0.5 and len(a_cjk) >= 2 and len(b_cjk) >= 2


def do_analyze(entries, agents_rules):
    """规则级命中统计 + 冗余检测报告"""
    if not entries:
        print("没有日志数据可分析。")
        return
    if not agents_rules:
        print("[警告] 未找到 route-map YAML 规则定义，analyze 功能需要规则定义做对照。")
        return

    total = len(entries)

    # ── 构建 pattern → (agent, rule_index) 的反向索引 ─────────────
    # pattern 可能重复（不同 Agent），所以用 list of tuples
    pattern_index = defaultdict(list)  # pattern → [(agent, rule_dict), ...]
    for agent, rules in agents_rules.items():
        for rule in rules:
            pattern = rule.get("pattern", "")
            if pattern:
                pattern_index[pattern].append((agent, rule))

    # ── 统计每个规则的命中次数 ──────────────────────────────────
    # rule_counts[agent][pattern] = hit_count
    rule_counts = defaultdict(lambda: defaultdict(int))
    # 跟踪每个规则的命中结果（正确/回退）
    rule_accuracy = defaultdict(lambda: {"hit": 0, "fallback": 0})

    for entry in entries:
        matched_patterns = entry.get("matched", [])
        agent = entry.get("agent", "")
        is_fallback = entry.get("method") == "llm_fallback"
        if not matched_patterns:
            continue
        for pattern in matched_patterns:
            # 跳过非规则匹配项（如 skill:xxx, chain_keyword:xxx）
            if pattern.startswith("skill:") or pattern.startswith("chain_keyword:"):
                continue
            rule_counts[agent][pattern] += 1
            rule_accuracy[pattern]["hit"] += 1
            if is_fallback:
                rule_accuracy[pattern]["fallback"] += 1

    # ══════════════════════════════════════════════════════════════
    #  输出：规则命中统计
    # ══════════════════════════════════════════════════════════════
    print("=== 规则命中统计 ===")
    # 按 Agent 分组输出
    for agent, rules in sorted(agents_rules.items()):
        rule_count = len(rules)
        print(f"\n{agent} ({rule_count} rules):")
        # 先输出有命中的规则，再输出 stale 规则
        hit_rules = []
        stale_rules = []
        for rule in rules:
            pattern = rule.get("pattern", "")
            idx = rule.get("_rule_index", "?")
            weight = rule.get("weight", 0)
            hits = rule_counts.get(agent, {}).get(pattern, 0)
            if hits > 0:
                acc_data = rule_accuracy.get(pattern, {"hit": 1, "fallback": 0})
                accuracy = (1 - acc_data["fallback"] / acc_data["hit"]) * 100 if acc_data["hit"] else 0
                hit_rules.append((idx, pattern, hits, accuracy, weight))
            else:
                stale_rules.append((idx, pattern, weight))
        # 按命中次数降序
        hit_rules.sort(key=lambda x: x[2], reverse=True)
        for idx, pattern, hits, acc, weight in hit_rules:
            print(f"  rule#{idx}: \"{pattern}\" → hit: {hits}, accuracy: {acc:.0f}%")
        for idx, pattern, weight in stale_rules:
            print(f"  rule#{idx}: \"{pattern}\" → hit: 0, STALE")

    # ══════════════════════════════════════════════════════════════
    #  输出：冗余规则报告
    # ══════════════════════════════════════════════════════════════
    print("\n=== 冗余规则报告 ===")
    found_any = False

    for agent, rules in sorted(agents_rules.items()):
        redundant_pairs = []

        # 按 (weight, skills_tuple) 分组
        weight_skill_groups = defaultdict(list)
        for rule in rules:
            key = (rule.get("weight", 0), tuple(sorted(rule.get("skills", [])) or []))
            weight_skill_groups[key].append(rule)

        # 在每组中检测相似 pattern
        for key, group in weight_skill_groups.items():
            if len(group) < 2:
                continue
            weight, skills = key
            skills_str = ", ".join(skills) if skills else "none"

            # 两两比较 group 内的规则
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    p_a = a.get("pattern", "")
                    p_b = b.get("pattern", "")
                    idx_a = a.get("_rule_index", "?")
                    idx_b = b.get("_rule_index", "?")

                    # 精确重复 pattern（已经在 validate 中检测，这里跳过）
                    if p_a == p_b:
                        continue

                    # 判断关系
                    if _is_near_synonym(p_a, p_b):
                        if _is_typo_variant(p_a, p_b):
                            redundant_pairs.append(
                                f"  - rule#{idx_a} (\"{p_a}\" weight:{weight}) → alias of "
                                f"rule#{idx_b} (\"{p_b}\" weight:{weight}) → 仅错别字区别"
                            )
                        else:
                            redundant_pairs.append(
                                f"  - rule#{idx_a} (\"{p_a}\" weight:{weight}) ↔ "
                                f"rule#{idx_b} (\"{p_b}\" weight:{weight}) "
                                f"→ 同skills({skills_str}), 同weight, 近义词"
                            )

        if redundant_pairs:
            found_any = True
            print(f"\n{agent}:")
            for pair in redundant_pairs:
                print(pair)

    if not found_any:
        print("  (未检测到冗余规则)")

    # ══════════════════════════════════════════════════════════════
    #  输出：低效规则排行榜
    # ══════════════════════════════════════════════════════════════
    print("\n=== 低效规则排行榜 ===")
    stale_entries = []
    for rule_agent, rules in agents_rules.items():
        for rule in rules:
            pattern = rule.get("pattern", "")
            idx = rule.get("_rule_index", "?")
            weight = rule.get("weight", 0)
            # 使用 rule 内嵌的 _agent 字段，兼容可能的跨 Agent 规则共享
            agent_name = rule.get("_agent", rule_agent)
            hits = rule_counts.get(agent_name, {}).get(pattern, 0)
            if hits == 0 and weight > 0:
                stale_entries.append((agent_name, idx, pattern, weight))
            elif hits == 0 and weight <= 0:
                stale_entries.append((agent_name, idx, pattern, weight))

    if stale_entries:
        # 按负权重优先（负权重且不命中可能是合理防护，但也列出），再按原始顺序
        stale_entries.sort(key=lambda x: (x[3], x[1]))
        for rank, (agent, idx, pattern, weight) in enumerate(stale_entries, 1):
            print(f"  #{rank} {agent}:rule#{idx} \"{pattern}\" → hit:0, STALE")
    else:
        print("  (无低效规则，所有规则均有命中)")


# ── CLI ────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="路由日志分析维护脚本 — 统计摘要 & 规则级命中分析"
    )
    parser.add_argument(
        "command", nargs="?",
        choices=["summary", "analyze"],
        default="summary",
        help="子命令: summary（默认，统计摘要）或 analyze（规则命中+冗余检测）"
    )
    args = parser.parse_args()

    entries = load_entries()

    if args.command == "analyze":
        agents_rules = load_route_map_rules()
        do_analyze(entries, agents_rules)
    else:
        do_summary(entries)


if __name__ == "__main__":
    main()
