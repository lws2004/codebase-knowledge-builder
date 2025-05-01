"""测试 CombineAndTranslateNode"""
import unittest
from unittest.mock import patch

from src.nodes.combine_and_translate_node import CombineAndTranslateNode


class TestCombineAndTranslateNode(unittest.TestCase):
    """测试 CombineAndTranslateNode"""

    def setUp(self):
        """设置测试环境"""
        self.node = CombineAndTranslateNode()
        self.shared = {
            "architecture_doc": {
                "success": True,
                "content": "# 架构文档\n\n这是架构文档的内容。"
            },
            "api_docs": {
                "success": True,
                "content": "# API 文档\n\n这是 API 文档的内容。"
            },
            "language": "zh",
            "output_dir": "test_output",
            "repo_url": "https://github.com/test/repo",
            "branch": "main",
            "code_structure": {},
            "core_modules": {}
        }

    @patch("src.nodes.combine_and_translate_node.detect_natural_language")
    def test_prep(self, mock_detect):
        """测试准备阶段"""
        # 执行准备阶段
        prep_res = self.node.prep(self.shared)

        # 验证结果
        self.assertIn("content_dict", prep_res)
        self.assertEqual(len(prep_res["content_dict"]), 2)
        self.assertEqual(prep_res["target_language"], "zh")
        self.assertEqual(prep_res["output_dir"], "test_output")
        self.assertEqual(prep_res["repo_url"], "https://github.com/test/repo")
        self.assertEqual(prep_res["repo_branch"], "main")

    @patch("src.nodes.combine_and_translate_node.detect_natural_language")
    def test_exec(self, mock_detect):
        """测试执行阶段"""
        # 模拟语言检测
        mock_detect.return_value = ("zh", 0.9)

        # 准备测试数据
        prep_res = {
            "content_dict": {
                "architecture_doc": "# 架构文档\n\n这是架构文档的内容。",
                "api_docs": "# API 文档\n\n这是 API 文档的内容。"
            },
            "llm_config": {},
            "target_language": "zh",
            "output_dir": "test_output",
            "repo_url": "https://github.com/test/repo",
            "repo_branch": "main",
            "code_structure": {},
            "core_modules": {},
            "retry_count": 3,
            "quality_threshold": 0.7,
            "model": "gpt-4",
            "preserve_technical_terms": True
        }

        # 执行阶段
        with patch.object(self.node, "_check_consistency", return_value=[]):
            exec_res = self.node.exec(prep_res)

        # 验证结果
        self.assertTrue(exec_res["success"])
        self.assertIn("combined_content", exec_res)
        self.assertIn("translated_content", exec_res)
        self.assertIn("file_structure", exec_res)
        self.assertIn("repo_structure", exec_res)

    def test_post(self):
        """测试后处理阶段"""
        # 准备测试数据
        exec_res = {
            "success": True,
            "combined_content": "# 组合文档\n\n这是组合文档的内容。",
            "translated_content": "# 翻译后的文档\n\n这是翻译后的文档的内容。",
            "file_structure": {},
            "repo_structure": {}
        }

        # 执行后处理阶段
        self.node.post(self.shared, exec_res)

        # 验证结果
        self.assertEqual(self.shared["combined_content"], exec_res["combined_content"])
        self.assertEqual(self.shared["translated_content"], exec_res["translated_content"])
        self.assertEqual(self.shared["file_structure"], exec_res["file_structure"])
        self.assertEqual(self.shared["repo_structure"], exec_res["repo_structure"])

    def test_combine_content(self):
        """测试组合内容"""
        # 准备测试数据
        content_dict = {
            "architecture_doc": "# 架构文档\n\n这是架构文档的内容。",
            "api_docs": "# API 文档\n\n这是 API 文档的内容。"
        }

        # 执行组合内容
        combined = self.node._combine_content(content_dict)

        # 验证结果
        self.assertIn("架构文档", combined)
        self.assertIn("API 文档", combined)
        self.assertIn("---", combined)


if __name__ == "__main__":
    unittest.main()
