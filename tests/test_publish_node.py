"""
测试 PublishNode
"""
import unittest
from unittest.mock import patch, MagicMock
import os
import shutil

from src.nodes.publish_node import PublishNode


class TestPublishNode(unittest.TestCase):
    """测试 PublishNode"""

    def setUp(self):
        """设置测试环境"""
        self.node = PublishNode()
        self.shared = {
            "publish_target": "github",
            "output_files": ["README.md", "docs/index.md"],
            "output_dir": "test_output",
            "repo_url": "https://github.com/test/repo",
            "repo_branch": "main"
        }
        
        # 创建测试输出目录和文件
        os.makedirs("test_output/docs", exist_ok=True)
        with open("test_output/README.md", "w") as f:
            f.write("# Test README")
        with open("test_output/docs/index.md", "w") as f:
            f.write("# Test Index")

    def tearDown(self):
        """清理测试环境"""
        # 删除测试输出目录
        if os.path.exists("test_output"):
            shutil.rmtree("test_output")

    def test_prep_with_target(self):
        """测试有发布目标时的准备阶段"""
        # 执行准备阶段
        prep_res = self.node.prep(self.shared)

        # 验证结果
        self.assertEqual(prep_res["publish_target"], "github")
        self.assertEqual(prep_res["output_files"], ["README.md", "docs/index.md"])
        self.assertEqual(prep_res["output_dir"], "test_output")
        self.assertEqual(prep_res["repo_url"], "https://github.com/test/repo")
        self.assertEqual(prep_res["repo_branch"], "main")

    def test_prep_without_target(self):
        """测试没有发布目标时的准备阶段"""
        # 移除发布目标
        shared_without_target = self.shared.copy()
        shared_without_target.pop("publish_target")

        # 执行准备阶段
        prep_res = self.node.prep(shared_without_target)

        # 验证结果
        self.assertTrue(prep_res["skip"])

    def test_prep_with_unsupported_target(self):
        """测试不支持的发布目标时的准备阶段"""
        # 设置不支持的发布目标
        shared_with_unsupported = self.shared.copy()
        shared_with_unsupported["publish_target"] = "unsupported"

        # 执行准备阶段
        prep_res = self.node.prep(shared_with_unsupported)

        # 验证结果
        self.assertIn("error", prep_res)
        self.assertIn("不支持的发布平台", prep_res["error"])

    def test_exec_github(self):
        """测试 GitHub 发布执行阶段"""
        # 准备测试数据
        prep_res = {
            "publish_target": "github",
            "output_files": ["README.md", "docs/index.md"],
            "output_dir": "test_output",
            "repo_url": "https://github.com/test/repo",
            "repo_branch": "main",
            "auth_info": {},
            "publish_repo": ""
        }

        # 模拟 GitHub Pages 发布
        with patch.object(self.node, "_publish_to_github_pages") as mock_publish:
            mock_publish.return_value = {
                "success": True,
                "publish_url": "https://test.github.io/repo",
                "publish_result": {
                    "platform": "github",
                    "repo_url": "https://github.com/test/repo",
                    "branch": "gh-pages",
                    "files_count": 2
                }
            }

            # 执行阶段
            exec_res = self.node.exec(prep_res)

        # 验证结果
        self.assertTrue(exec_res["success"])
        self.assertEqual(exec_res["publish_url"], "https://test.github.io/repo")
        self.assertEqual(exec_res["publish_result"]["platform"], "github")
        self.assertEqual(exec_res["publish_result"]["repo_url"], "https://github.com/test/repo")

    def test_post(self):
        """测试后处理阶段"""
        # 准备测试数据
        exec_res = {
            "success": True,
            "publish_url": "https://test.github.io/repo",
            "publish_result": {
                "platform": "github",
                "repo_url": "https://github.com/test/repo",
                "branch": "gh-pages",
                "files_count": 2
            }
        }

        # 执行后处理阶段
        self.node.post(self.shared, exec_res)

        # 验证结果
        self.assertEqual(self.shared["publish_url"], "https://test.github.io/repo")
        self.assertEqual(self.shared["publish_result"], exec_res["publish_result"])

    def test_create_github_pages_config(self):
        """测试创建 GitHub Pages 配置文件"""
        # 执行创建配置文件
        config_path = self.node._create_github_pages_config("test_output")

        # 验证结果
        self.assertTrue(os.path.exists(config_path))
        with open(config_path, "r") as f:
            content = f.read()
            self.assertIn("theme:", content)
            self.assertIn("title:", content)
            self.assertIn("description:", content)


if __name__ == "__main__":
    unittest.main()
