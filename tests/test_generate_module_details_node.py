"""测试模块详情生成节点的功能。

此模块包含对AsyncGenerateModuleDetailsNode类的测试，验证其处理模块内容的能力。
"""

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
