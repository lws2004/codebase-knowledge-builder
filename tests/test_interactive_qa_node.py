"""测试 InteractiveQANode"""

import unittest
from unittest.mock import MagicMock, patch

from src.nodes.interactive_qa_node import InteractiveQANode


class TestInteractiveQANode(unittest.TestCase):
    """测试 InteractiveQANode"""

    def setUp(self):
        """设置测试环境"""
        self.node = InteractiveQANode()
        self.shared = {
            "user_query": "如何使用这个代码库？",
            "vector_index": {"dummy": "index"},  # 确保不为空
            "text_chunks": ["这是第一个文本块", "这是第二个文本块"],
            "llm_config": {},
            "language": "zh",
            "code_structure": {},
            "core_modules": {},
            "conversation_history": [],
        }

    def test_prep_with_query(self):
        """测试有查询时的准备阶段"""
        # 执行准备阶段
        prep_res = self.node.prep(self.shared)

        # 验证结果
        # 检查是否有错误
        self.assertNotIn("error", prep_res)
        self.assertNotIn("skip", prep_res)

        # 检查关键字段
        self.assertIn("vector_index", prep_res)
        self.assertIn("text_chunks", prep_res)
        self.assertIn("target_language", prep_res)
        self.assertEqual(prep_res["target_language"], "zh")
        self.assertEqual(prep_res["conversation_history"], [])
        self.assertEqual(prep_res["retry_count"], 3)
        self.assertEqual(prep_res["max_context_chunks"], 5)

    def test_prep_without_query(self):
        """测试没有查询时的准备阶段"""
        # 移除查询
        shared_without_query = self.shared.copy()
        shared_without_query.pop("user_query")

        # 执行准备阶段
        prep_res = self.node.prep(shared_without_query)

        # 验证结果
        self.assertTrue(prep_res["skip"])

    @patch("src.nodes.interactive_qa_node.LLMClient")
    def test_exec(self, mock_llm_client):
        """测试执行阶段"""
        # 模拟 LLM 客户端
        mock_client = MagicMock()
        mock_llm_client.return_value = mock_client
        mock_client.completion.return_value = {"choices": [{"message": {"content": "这是回答"}}]}
        mock_client.get_completion_content.return_value = "这是回答"

        # 准备测试数据
        prep_res = {
            "user_query": "如何使用这个代码库？",
            "vector_index": {},
            "text_chunks": ["这是第一个文本块", "这是第二个文本块"],
            "llm_config": {},
            "target_language": "zh",
            "code_structure": {},
            "core_modules": {},
            "conversation_history": [],
            "retry_count": 3,
            "quality_threshold": 0.7,
            "model": "gpt-4",
            "max_context_chunks": 5,
        }

        # 模拟方法
        with patch.object(self.node, "_analyze_question", return_value=("usage", "explanation")):
            with patch.object(self.node, "_retrieve_context", return_value="相关上下文"):
                with patch.object(self.node, "_prepare_code_info", return_value="代码库信息"):
                    with patch.object(self.node, "_generate_answer", return_value=("这是回答", 0.8, True)):
                        # 执行阶段
                        exec_res = self.node.exec(prep_res)

        # 验证结果
        self.assertTrue(exec_res["success"])
        self.assertEqual(exec_res["answer"], "这是回答")
        self.assertEqual(exec_res["quality_score"], 0.8)
        self.assertEqual(len(exec_res["conversation_history"]), 2)

    def test_post(self):
        """测试后处理阶段"""
        # 准备测试数据
        exec_res = {
            "success": True,
            "answer": "这是回答",
            "quality_score": 0.8,
            "conversation_history": [
                {"role": "user", "content": "如何使用这个代码库？"},
                {"role": "assistant", "content": "这是回答"},
            ],
        }

        # 执行后处理阶段
        self.node.post(self.shared, exec_res)

        # 验证结果
        self.assertEqual(self.shared["answer"], "这是回答")
        self.assertEqual(self.shared["conversation_history"], exec_res["conversation_history"])
        self.assertEqual(len(self.shared["custom_answers"]), 1)
        self.assertEqual(self.shared["custom_answers"][0]["question"], "如何使用这个代码库？")
        self.assertEqual(self.shared["custom_answers"][0]["answer"], "这是回答")

    def test_evaluate_answer_quality(self):
        """测试评估回答质量"""
        # 准备测试数据
        question = "如何使用这个代码库？"
        answer = "这是回答，包含代码示例：\n```python\nimport example\n```\n这个代码库可以这样使用。"
        context = "代码库使用方法：导入 example 模块，然后调用相关函数。"

        # 执行评估
        quality_score = self.node._evaluate_answer_quality(question, answer, context)

        # 验证结果
        self.assertGreaterEqual(quality_score, 0.0)
        self.assertLessEqual(quality_score, 1.0)


if __name__ == "__main__":
    unittest.main()
