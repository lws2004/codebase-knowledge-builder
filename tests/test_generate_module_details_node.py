import pytest

from src.nodes.generate_module_details_node import AsyncGenerateModuleDetailsNode


@pytest.mark.asyncio
async def test_process_module_content():
    """测试模块内容处理功能"""
    node = AsyncGenerateModuleDetailsNode()
    result = node._process_module_content("test_content", "test_module", "test_repo")
    assert isinstance(result, str)
    assert "---" in result  # 验证元数据部分
    assert "# 📦" in result  # 验证标题部分
