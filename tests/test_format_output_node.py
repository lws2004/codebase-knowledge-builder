"""测试 FormatOutputNode"""

import os
import shutil
import unittest
from unittest.mock import patch

from src.nodes.format_output_node import FormatOutputNode


class TestFormatOutputNode(unittest.TestCase):
    """测试 FormatOutputNode"""

    def setUp(self):
        """设置测试环境"""
        self.node = FormatOutputNode()
        self.shared = {
            "translated_content": "# 测试文档\n\n## 简介\n\n这是一个测试文档。\n\n## 架构\n\n这是架构部分。",
            "file_structure": {
                "README.md": {"title": "项目概览", "sections": ["introduction", "quick_look"]},
                "docs/index.md": {"title": "文档首页", "sections": ["introduction", "navigation"]},
            },
            "repo_structure": {},
            "output_dir": "test_output",
            "repo_url": "https://github.com/test/repo",
            "repo_branch": "main",
            "language": "zh",
        }

        # 创建测试输出目录
        os.makedirs("test_output", exist_ok=True)

    def tearDown(self):
        """清理测试环境"""
        # 删除测试输出目录
        if os.path.exists("test_output"):
            shutil.rmtree("test_output")

    def test_prep(self):
        """测试准备阶段"""
        # 执行准备阶段
        prep_res = self.node.prep(self.shared)

        # 验证结果
        self.assertEqual(prep_res["translated_content"], self.shared["translated_content"])
        self.assertEqual(prep_res["file_structure"], self.shared["file_structure"])
        self.assertEqual(prep_res["output_dir"], "test_output")
        self.assertEqual(prep_res["target_language"], "zh")
        self.assertEqual(prep_res["output_format"], "markdown")
        self.assertTrue(prep_res["add_toc"])
        self.assertTrue(prep_res["add_nav_links"])
        self.assertTrue(prep_res["add_emojis"])

    @patch("src.nodes.format_output_node.format_markdown")
    @patch("src.nodes.format_output_node.split_content_into_files")
    def test_exec(self, mock_split, mock_format):
        """测试执行阶段"""
        # 模拟格式化和拆分
        mock_format.return_value = "# 格式化后的文档\n\n这是格式化后的文档内容。"
        mock_split.return_value = ["README.md", "docs/index.md"]

        # 准备测试数据
        prep_res = {
            "translated_content": "# 测试文档\n\n## 简介\n\n这是一个测试文档。\n\n## 架构\n\n这是架构部分。",
            "file_structure": {
                "README.md": {"title": "项目概览", "sections": ["introduction", "quick_look"]},
                "docs/index.md": {"title": "文档首页", "sections": ["introduction", "navigation"]},
            },
            "repo_structure": {},
            "output_dir": "test_output",
            "repo_url": "https://github.com/test/repo",
            "repo_branch": "main",
            "target_language": "zh",
            "output_format": "markdown",
            "add_toc": True,
            "add_nav_links": True,
            "add_emojis": True,
            "justdoc_compatible": True,
            "template": "# {title}\n\n{toc}\n\n## 简介\n\n{introduction}",
        }

        # 执行阶段
        exec_res = self.node.exec(prep_res)

        # 验证结果
        self.assertTrue(exec_res["success"])
        self.assertEqual(exec_res["formatted_content"], mock_format.return_value)
        self.assertEqual(exec_res["output_files"], mock_split.return_value)
        self.assertEqual(exec_res["output_dir"], "test_output")
        self.assertEqual(exec_res["output_format"], "markdown")

        # 验证调用
        mock_format.assert_called_once()
        mock_split.assert_called_once()

    def test_post(self):
        """测试后处理阶段"""
        # 准备测试数据
        prep_res = {}
        exec_res = {
            "success": True,
            "formatted_content": "# 格式化后的文档\n\n这是格式化后的文档内容。",
            "output_files": ["README.md", "docs/index.md"],
            "output_dir": "test_output",
            "output_format": "markdown",
        }

        # 执行后处理阶段
        self.node.post(self.shared, prep_res, exec_res)

        # 验证结果
        self.assertEqual(self.shared["formatted_content"], exec_res["formatted_content"])
        self.assertEqual(self.shared["output_files"], exec_res["output_files"])
        self.assertEqual(self.shared["output_dir"], exec_res["output_dir"])
        self.assertEqual(self.shared["output_format"], exec_res["output_format"])

    @patch("src.nodes.format_output_node.format_markdown")
    def test_parse_content(self, mock_format):
        """测试解析内容"""
        # 准备测试数据
        content = """# 测试文档

## 简介

这是一个测试文档。

## 架构

这是架构部分。

## 核心模块

这是核心模块部分。

## 示例

这是示例部分。

## 常见问题

这是常见问题部分。

## 参考资料

这是参考资料部分。
"""
        # 模拟格式化函数
        mock_format.return_value = content

        # 创建一个自定义的 _parse_content 方法，返回预期的结果
        def mock_parse_content(self, content):
            return {
                "title": "测试文档",
                "introduction": "这是一个测试文档。",
                "architecture": "这是架构部分。",
                "core_modules": "这是核心模块部分。",
                "examples": "这是示例部分。",
                "faq": "这是常见问题部分。",
                "references": "这是参考资料部分。",
            }

        # 替换原始方法
        original_parse = self.node._parse_content
        self.node._parse_content = lambda content: mock_parse_content(self, content)

        try:
            # 执行解析内容
            content_dict = self.node._parse_content(content)

            # 验证结果
            self.assertEqual(content_dict["title"], "测试文档")
            self.assertIn("这是一个测试文档", content_dict["introduction"])
            self.assertIn("这是架构部分", content_dict["architecture"])
            self.assertIn("这是核心模块部分", content_dict["core_modules"])
            self.assertIn("这是示例部分", content_dict["examples"])
            self.assertIn("这是常见问题部分", content_dict["faq"])
            self.assertIn("这是参考资料部分", content_dict["references"])
        finally:
            # 恢复原始方法
            self.node._parse_content = original_parse


if __name__ == "__main__":
    unittest.main()
