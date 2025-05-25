"""测试 Mermaid 验证和重新生成功能"""

from unittest.mock import Mock, patch

import pytest

from src.utils.mermaid_regenerator import MermaidRegenerator, validate_and_regenerate_mermaid
from src.utils.mermaid_validator import validate_mermaid_syntax_sync


class TestMermaidValidator:
    """测试 Mermaid 验证器"""

    def test_simple_validate_valid_mermaid(self):
        """测试简单验证 - 有效的 Mermaid 图表"""
        valid_mermaid = """
graph TD
    A[开始] --> B[处理]
    B --> C[结束]
"""
        is_valid, errors = validate_mermaid_syntax_sync(valid_mermaid)
        assert is_valid
        assert len(errors) == 0

    def test_simple_validate_invalid_mermaid(self):
        """测试简单验证 - 无效的 Mermaid 图表"""
        invalid_mermaid = """
这不是有效的 Mermaid 图表
"""
        is_valid, errors = validate_mermaid_syntax_sync(invalid_mermaid)
        assert not is_valid
        assert len(errors) > 0

    def test_simple_validate_syntax_errors(self):
        """测试简单验证 - 语法错误"""
        # 测试嵌套方括号错误
        invalid_mermaid = """
graph TD
    A[A[嵌套错误]]
"""
        is_valid, errors = validate_mermaid_syntax_sync(invalid_mermaid)
        assert not is_valid
        # 检查是否有任何错误（不依赖具体错误消息）
        assert len(errors) > 0

    def test_simple_validate_special_characters(self):
        """测试简单验证 - 特殊字符错误"""
        # 测试节点标签中的括号
        invalid_mermaid = """
graph TD
    A[文本(带括号)]
"""
        is_valid, errors = validate_mermaid_syntax_sync(invalid_mermaid)
        assert not is_valid
        # 检查是否有任何错误（不依赖具体错误消息）
        assert len(errors) > 0


class TestMermaidRegenerator:
    """测试 Mermaid 重新生成器"""

    def test_regenerator_init(self):
        """测试重新生成器初始化"""
        regenerator = MermaidRegenerator()
        assert regenerator.max_retries == 3
        assert regenerator.llm_client is None

    def test_regenerate_valid_content(self):
        """测试重新生成 - 有效内容无需修复"""
        valid_content = """
# 测试文档

这是一个有效的 Mermaid 图表：

```mermaid
graph TD
    A[开始] --> B[结束]
```

结束。
"""
        regenerator = MermaidRegenerator()
        result = regenerator.regenerate_mermaid_content(valid_content)
        # 有效内容应该保持不变
        assert "graph TD" in result
        assert "A[开始] --> B[结束]" in result

    def test_regenerate_no_mermaid(self):
        """测试重新生成 - 没有 Mermaid 图表"""
        content_without_mermaid = """
# 测试文档

这是一个没有 Mermaid 图表的文档。

只有普通文本。
"""
        regenerator = MermaidRegenerator()
        result = regenerator.regenerate_mermaid_content(content_without_mermaid)
        # 没有 Mermaid 图表的内容应该保持不变
        assert result == content_without_mermaid

    @patch("src.utils.mermaid_regenerator.validate_mermaid_syntax_sync")
    def test_regenerate_with_mock_llm(self, mock_validate):
        """测试重新生成 - 使用模拟 LLM"""
        # 模拟验证结果：第一次失败，第二次成功
        mock_validate.side_effect = [
            (False, ["语法错误"]),  # 原始内容有错误
            (True, []),  # 重新生成后正确
        ]

        # 模拟 LLM 客户端
        mock_llm = Mock()
        mock_llm.generate_text.return_value = """graph TD
    A[开始] --> B[结束]"""

        content_with_error = """
# 测试文档

```mermaid
graph TD
    A[A[错误的嵌套]]
```
"""

        regenerator = MermaidRegenerator(mock_llm)
        result = regenerator.regenerate_mermaid_content(content_with_error)

        # 验证 LLM 被调用
        mock_llm.generate_text.assert_called_once()

        # 验证结果包含修复后的内容
        assert "A[开始] --> B[结束]" in result
        assert "A[A[错误的嵌套]]" not in result

    def test_clean_llm_response(self):
        """测试清理 LLM 响应"""
        regenerator = MermaidRegenerator()

        # 测试带有代码块标记的响应
        response_with_markers = """```mermaid
graph TD
    A --> B
```"""
        cleaned = regenerator._clean_llm_response(response_with_markers)
        assert cleaned == "graph TD\n    A --> B"

        # 测试只有开始标记的响应
        response_start_only = """```mermaid
graph TD
    A --> B"""
        cleaned = regenerator._clean_llm_response(response_start_only)
        assert cleaned == "graph TD\n    A --> B"

        # 测试普通响应
        normal_response = "graph TD\n    A --> B"
        cleaned = regenerator._clean_llm_response(normal_response)
        assert cleaned == "graph TD\n    A --> B"


class TestMermaidValidationIntegration:
    """测试 Mermaid 验证集成功能"""

    def test_validate_and_regenerate_valid_content(self):
        """测试验证和重新生成 - 有效内容"""
        valid_content = """
# 测试文档

```mermaid
graph TD
    A[开始] --> B[结束]
```
"""
        result, was_fixed = validate_and_regenerate_mermaid(valid_content)
        assert not was_fixed  # 有效内容不需要修复
        assert result == valid_content

    @patch("src.utils.mermaid_regenerator.validate_mermaid_syntax_sync")
    def test_validate_and_regenerate_with_errors(self, mock_validate):
        """测试验证和重新生成 - 有错误的内容"""
        # 模拟验证结果
        mock_validate.side_effect = [
            (False, ["语法错误"]),  # 检查时发现错误
            (False, ["语法错误"]),  # 重新生成前的验证
            (True, []),  # 重新生成后正确
        ]

        # 模拟 LLM 客户端
        mock_llm = Mock()
        mock_llm.generate_text.return_value = "graph TD\n    A --> B"

        content_with_error = """
# 测试文档

```mermaid
graph TD
    A[A[错误]]
```
"""

        result, was_fixed = validate_and_regenerate_mermaid(content_with_error, mock_llm)
        assert was_fixed  # 应该进行了修复
        assert "A --> B" in result


class TestMermaidValidationNode:
    """测试 Mermaid 验证节点"""

    def test_node_init(self):
        """测试节点初始化"""
        from src.nodes.mermaid_validation_node import MermaidValidationNode

        node = MermaidValidationNode()
        assert node.config.max_retries == 3
        assert node.config.validate_all_files is True
        assert node.config.backup_original is True

    def test_node_prep_no_files(self):
        """测试节点准备阶段 - 没有文件"""
        from src.nodes.mermaid_validation_node import MermaidValidationNode

        node = MermaidValidationNode()
        shared = {}
        result = node.prep(shared)
        assert result["skip"] is True

    def test_node_prep_no_llm_config(self):
        """测试节点准备阶段 - 没有 LLM 配置"""
        from src.nodes.mermaid_validation_node import MermaidValidationNode

        node = MermaidValidationNode()
        shared = {"output_files": ["test.md"]}
        result = node.prep(shared)
        assert result["skip"] is True

    def test_node_prep_success(self):
        """测试节点准备阶段 - 成功"""
        from src.nodes.mermaid_validation_node import MermaidValidationNode

        node = MermaidValidationNode()
        shared = {"output_files": ["test.md"], "llm_config": {"model": "test"}}
        result = node.prep(shared)
        assert "skip" not in result
        assert result["output_files"] == ["test.md"]
        assert result["llm_config"] == {"model": "test"}


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
