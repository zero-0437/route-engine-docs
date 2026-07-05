"""Tests for validate-route-map.py --fix/--apply and near-synonym detection

运行方式:
    cd /opt/data && .venv/bin/python -m pytest tests/test_validate_route_map.py -v
"""
import copy
import importlib.util
import os
import sys
import tempfile
import unittest

# ── 路径解析 ──────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SCRIPTS_PATH = os.path.join(_SCRIPT_DIR, "..", "scripts")
sys.path.insert(0, _SCRIPTS_PATH)

# 使用 importlib 加载带 '-' 的文件名
_spec = importlib.util.spec_from_file_location(
    "validate_route_map",
    os.path.join(_SCRIPTS_PATH, "validate-route-map.py"),
)
vr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vr)


# ════════════════════════════════════════════════════════════════
# P0-1: 短文本近义词误判修复
# ════════════════════════════════════════════════════════════════

class TestNearSynonymShortText(unittest.TestCase):
    """验证短文本（≤3 CJK 字符）不再被误判为近义词"""

    def test_short_text_not_synonym_simple(self):
        """双字词不同义：查找 vs 调查"""
        self.assertFalse(vr._is_near_synonym("查找", "调查"))

    def test_short_text_not_synonym_substring(self):
        """三字词不含于四字词：提示词 vs 提示工程"""
        self.assertFalse(vr._is_near_synonym("提示词", "提示工程"))

    def test_short_text_not_synonym_single_char(self):
        """单字不同义：修 vs 改"""
        self.assertFalse(vr._is_near_synonym("修", "改"))

    def test_short_text_not_synonym_empty(self):
        """空文本不崩溃"""
        self.assertFalse(vr._is_near_synonym("", "测试"))
        self.assertFalse(vr._is_near_synonym("测试", ""))

    def test_long_text_still_synonym(self):
        """长文本（>3 CJK）近义词仍可检测：系统备份 vs 备份系统"""
        self.assertTrue(vr._is_near_synonym("系统备份", "备份系统"))

    def test_long_text_still_synonym_convert(self):
        """长文本近义词：转换格式 vs 格式转换"""
        self.assertTrue(vr._is_near_synonym("转换格式", "格式转换"))

    def test_boundary_4_chars(self):
        """边界值：4 字符文本仍正常工作"""
        self.assertTrue(vr._is_near_synonym("数据备份", "数据备份"))


# ════════════════════════════════════════════════════════════════
# P0-3: --fix/--apply 相关函数测试
# ════════════════════════════════════════════════════════════════

class TestDedupAndGeneratePatch(unittest.TestCase):
    """验证去重合并及 patch 生成逻辑"""

    def setUp(self):
        self.sample_route_files = {
            "docs-writer.yaml": {
                "agent": "docs-writer",
                "rules": [
                    {"type": "keyword", "pattern": "文档", "weight": 0.8, "skills": ["doc-coauthoring"]},
                    {"type": "keyword", "pattern": "说明文档", "weight": 0.8, "skills": ["doc-coauthoring"]},
                    {"type": "keyword", "pattern": "技术文档", "weight": 0.6, "skills": ["doc-coauthoring"]},
                ],
            },
        }
        self.sample_pairs = [
            ("docs-writer.yaml", 1, 0, "说明文档", "文档", 0.8, ["doc-coauthoring"]),
        ]

    def test_dedup_selects_longer_pattern(self):
        """长 pattern 被保留，短 pattern 被标记为 drop"""
        patches = vr._dedup_and_generate_patch(self.sample_route_files, self.sample_pairs)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]["file"], "docs-writer.yaml")
        self.assertEqual(patches[0]["action"], "drop_rule")
        self.assertEqual(patches[0]["index"], 0)
        self.assertEqual(patches[0]["rule"]["pattern"], "文档")

    def test_dedup_no_duplicate_drops(self):
        """同一 index 被多对指向时只生成一个 patch"""
        pairs = [
            ("docs-writer.yaml", 2, 0, "技术文档", "文档", 0.6, ["doc-coauthoring"]),
            ("docs-writer.yaml", 1, 0, "说明文档", "文档", 0.8, ["doc-coauthoring"]),
        ]
        patches = vr._dedup_and_generate_patch(self.sample_route_files, pairs)
        self.assertEqual(len(patches), 1)
        self.assertEqual(patches[0]["index"], 0)

    def test_dedup_no_pairs(self):
        """空 pair 列表返回空 patch"""
        patches = vr._dedup_and_generate_patch(self.sample_route_files, [])
        self.assertEqual(patches, [])


class TestApplyPatches(unittest.TestCase):
    """验证 _apply_patches 实际删除规则"""

    def setUp(self):
        self.route_files = {
            "docs-writer.yaml": {
                "agent": "docs-writer",
                "rules": [
                    {"pattern": "文档", "weight": 0.8},
                    {"pattern": "说明文档", "weight": 0.8},
                    {"pattern": "技术文档", "weight": 0.6},
                ],
            },
        }

    def test_apply_single_patch(self):
        """应用单条 patch 正确删除规则"""
        patches = [
            {"file": "docs-writer.yaml", "action": "drop_rule", "index": 0,
             "rule": {"pattern": "文档", "weight": 0.8}},
        ]
        result = vr._apply_patches(copy.deepcopy(self.route_files), patches)
        rules = result["docs-writer.yaml"]["rules"]
        self.assertEqual(len(rules), 2)
        self.assertEqual(rules[0]["pattern"], "说明文档")

    def test_apply_multiple_patches(self):
        """应用多条 patch 逆序删除（索引不漂移）"""
        patches = [
            {"file": "docs-writer.yaml", "action": "drop_rule", "index": 0,
             "rule": {"pattern": "文档", "weight": 0.8}},
            {"file": "docs-writer.yaml", "action": "drop_rule", "index": 2,
             "rule": {"pattern": "技术文档", "weight": 0.6}},
        ]
        result = vr._apply_patches(copy.deepcopy(self.route_files), patches)
        rules = result["docs-writer.yaml"]["rules"]
        self.assertEqual(len(rules), 1)
        self.assertEqual(rules[0]["pattern"], "说明文档")

    def test_apply_no_patches(self):
        """空 patch 列表不修改"""
        result = vr._apply_patches(copy.deepcopy(self.route_files), [])
        rules = result["docs-writer.yaml"]["rules"]
        self.assertEqual(len(rules), 3)

    def test_apply_invalid_index(self):
        """越界索引被安全跳过"""
        patches = [
            {"file": "docs-writer.yaml", "action": "drop_rule", "index": 99,
             "rule": {"pattern": "invalid", "weight": 0}},
        ]
        result = vr._apply_patches(copy.deepcopy(self.route_files), patches)
        rules = result["docs-writer.yaml"]["rules"]
        self.assertEqual(len(rules), 3)


class TestFindRedundantPairs(unittest.TestCase):
    """验证 _find_redundant_pairs 集成检测"""

    def setUp(self):
        self.route_files_with_redundancy = {
            "docs-writer.yaml": {
                "agent": "docs-writer",
                "rules": [
                    {"type": "keyword", "pattern": "系统备份", "weight": 0.8,
                     "skills": ["doc-coauthoring"]},
                    {"type": "keyword", "pattern": "备份系统", "weight": 0.8,
                     "skills": ["doc-coauthoring"]},
                    {"type": "keyword", "pattern": "文档撰写", "weight": 0.6,
                     "skills": ["doc-coauthoring"]},
                ],
            },
        }
        self.route_files_no_redundancy = {
            "prompt-engineer.yaml": {
                "agent": "prompt-engineer",
                "rules": [
                    {"type": "keyword", "pattern": "提示工程", "weight": 0.8,
                     "skills": ["prompt-engineering"]},
                    {"type": "keyword", "pattern": "LLM 调优", "weight": 0.6,
                     "skills": ["prompt-engineering"]},
                ],
            },
        }

    def test_finds_redundant_pairs(self):
        """可以找到同 weight+同 skills 的近义词对"""
        pairs = vr._find_redundant_pairs(self.route_files_with_redundancy)
        self.assertGreaterEqual(len(pairs), 1)
        fname, keep_idx, drop_idx, keep_pattern, drop_pattern, w, skills = pairs[0]
        self.assertEqual(fname, "docs-writer.yaml")
        self.assertIn("系统备份", (keep_pattern, drop_pattern))
        self.assertIn("备份系统", (keep_pattern, drop_pattern))
        self.assertEqual(w, 0.8)

    def test_no_redundant_pairs(self):
        """非近义词规则不产生冗余对"""
        pairs = vr._find_redundant_pairs(self.route_files_no_redundancy)
        self.assertEqual(len(pairs), 0)

    def test_short_text_no_longer_redundant(self):
        """短文本（≤3 CJK）不再产生冗余对"""
        route_files = {
            "prompt-engineer.yaml": {
                "agent": "prompt-engineer",
                "rules": [
                    {"type": "keyword", "pattern": "提示词", "weight": 0.8,
                     "skills": ["prompt-engineering"]},
                    {"type": "keyword", "pattern": "提示工程", "weight": 0.8,
                     "skills": ["prompt-engineering"]},
                ],
            },
        }
        pairs = vr._find_redundant_pairs(route_files)
        self.assertEqual(len(pairs), 0)


class TestOutputFixSuggestions(unittest.TestCase):
    """验证 _output_fix_suggestions 输出格式"""

    def test_dry_run_output(self):
        """dry-run 模式输出不修改文件"""
        route_files = copy.deepcopy({
            "docs-writer.yaml": {
                "agent": "docs-writer",
                "rules": [
                    {"type": "keyword", "pattern": "系统备份", "weight": 0.8,
                     "skills": ["doc-coauthoring"]},
                    {"type": "keyword", "pattern": "备份系统", "weight": 0.8,
                     "skills": ["doc-coauthoring"]},
                ],
            },
        })
        result = {
            "_redundant_pairs": [
                ("docs-writer.yaml", 1, 0, "备份系统", "系统备份", 0.8, ["doc-coauthoring"]),
            ],
            "_route_files": route_files,
        }
        from io import StringIO
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            vr._output_fix_suggestions(result, apply_changes=False)
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        self.assertIn("dry-run", output)
        self.assertNotIn("Applied", output)

    def test_no_pairs_output(self):
        """无冗余对时输出提示信息"""
        result = {
            "_redundant_pairs": [],
            "_route_files": {},
        }
        from io import StringIO
        captured = StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            vr._output_fix_suggestions(result, apply_changes=False)
        finally:
            sys.stdout = old_stdout
        output = captured.getvalue()
        self.assertIn("No redundant pairs", output)


if __name__ == "__main__":
    unittest.main()
