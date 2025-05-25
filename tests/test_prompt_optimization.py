"""测试提示词优化效果的简化脚本。

这个脚本直接测试优化后的提示词，展示文档生成质量的改进。
"""

import asyncio
import os
import sys
import tempfile

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.abspath("."))

from src.utils.env_manager import get_llm_config, load_env_vars
from src.utils.llm_wrapper.llm_client import LLMClient


def get_optimized_module_prompt():
    """获取优化后的模块文档生成提示词"""
    return """
你是一个专业的技术文档专家，擅长将复杂的代码转化为清晰易懂的教程文档。请为以下模块生成一份高质量的详细文档。

模块信息:
名称: DataProcessor
路径: src/data_processor.py
描述: 数据处理器，提供数据清洗和转换功能

代码内容:
```python
class DataProcessor:
    def __init__(self, config=None):
        self.config = config or {}
        self.processed_count = 0
    
    def process_data(self, data):
        processed_data = []
        for item in data:
            if self._validate_item(item):
                processed_item = self._transform_item(item)
                processed_data.append(processed_item)
                self.processed_count += 1
        return processed_data
    
    def _validate_item(self, item):
        return isinstance(item, dict) and "id" in item
    
    def _transform_item(self, item):
        transformed = item.copy()
        transformed["processed"] = True
        return transformed
```

## 📝 文档生成要求

请按照以下结构生成文档，确保内容清晰、逻辑性强、易于理解：

### 1. 📋 模块概述
- **模块名称**: 明确标注模块名称和完整路径
- **核心功能**: 用1-2句话概括模块的主要功能和价值
- **架构角色**: 说明该模块在整个系统中的定位和重要性
- **适用场景**: 描述什么情况下会使用这个模块

### 2. 🏗️ 架构设计
- **设计思路**: 解释模块的设计理念和架构思想
- **核心组件**: 列出模块中的主要类、函数和组件
- **数据流向**: 如果适用，使用Mermaid图表展示数据流或调用关系

### 3. 🔧 详细API文档
对于每个公共类和函数，提供：
- **功能描述**: 清晰说明其作用和用途
- **参数说明**: 详细列出所有参数，包括类型、默认值、是否必需
- **返回值**: 说明返回值的类型和含义
- **异常处理**: 列出可能抛出的异常和处理方式
- **使用注意**: 重要的使用注意事项和限制

### 4. 💡 实用示例
- **基础用法**: 提供最简单的使用示例
- **进阶用法**: 展示更复杂的使用场景
- **最佳实践**: 推荐的使用模式和技巧
- **常见错误**: 列出常见的使用错误和避免方法

### 5. 🔗 依赖关系
- **上游依赖**: 该模块依赖的其他模块和外部库
- **下游使用**: 哪些模块或组件使用了该模块
- **依赖图**: 如果关系复杂，使用Mermaid图表展示

### 6. ⚠️ 注意事项与最佳实践
- **性能考虑**: 使用时的性能注意事项
- **安全考虑**: 安全相关的注意事项
- **兼容性**: 版本兼容性和向后兼容性说明
- **调试技巧**: 常见问题的调试方法

## 🎯 质量要求

1. **清晰性**: 使用简洁明了的语言，避免过于技术化的表述
2. **完整性**: 覆盖模块的所有重要方面，不遗漏关键信息
3. **实用性**: 提供实际可用的代码示例，确保示例能够运行
4. **结构化**: 使用清晰的标题层级和列表结构
5. **可视化**: 适当使用Mermaid图表增强理解
6. **一致性**: 保持术语和格式的一致性

请确保生成的文档：
- 使用适当的emoji表情符号增强可读性 🎨
- 代码块使用正确的语法高亮
- 表格格式整齐，便于阅读
- 链接格式正确，便于导航
- 内容层次分明，逻辑清晰

**重要提示**: 请基于实际的代码内容生成文档，不要编造不存在的功能或API。如果某些信息无法从代码中获取，请明确说明。
"""


def get_original_module_prompt():
    """获取原始的模块文档生成提示词（用于对比）"""
    return """
你是一个代码库文档专家。请为以下模块生成详细的文档。

模块信息:
名称: DataProcessor
路径: src/data_processor.py
描述: 数据处理器，提供数据清洗和转换功能

代码内容:
```python
class DataProcessor:
    def __init__(self, config=None):
        self.config = config or {}
        self.processed_count = 0
    
    def process_data(self, data):
        processed_data = []
        for item in data:
            if self._validate_item(item):
                processed_item = self._transform_item(item)
                processed_data.append(processed_item)
                self.processed_count += 1
        return processed_data
    
    def _validate_item(self, item):
        return isinstance(item, dict) and "id" in item
    
    def _transform_item(self, item):
        transformed = item.copy()
        transformed["processed"] = True
        return transformed
```

请提供以下内容:
1. 模块概述
   - 模块名称和路径
   - 模块的主要功能和用途
   - 模块在整个代码库中的角色
2. 类和函数详解
   - 每个类的功能、属性和方法
   - 每个函数的功能、参数和返回值
   - 重要的代码片段解释
3. 使用示例
   - 如何使用该模块的主要功能
   - 常见用例和模式
4. 依赖关系
   - 该模块依赖的其他模块
   - 依赖该模块的其他模块
5. 注意事项和最佳实践
   - 使用该模块时需要注意的事项
   - 推荐的最佳实践

请以 Markdown 格式输出，使用适当的标题、列表、表格和代码块。
使用表情符号使文档更加生动，例如在标题前使用适当的表情符号。
确保文档中的代码引用能够链接到源代码。
"""


async def test_prompt_comparison():
    """对比优化前后的提示词效果"""
    print("🧪 开始测试提示词优化效果\n")

    # 加载环境变量
    load_env_vars(env="default")
    llm_config = get_llm_config()

    if not llm_config.get("model"):
        print("❌ LLM配置不完整，跳过测试")
        return

    # 创建LLM客户端
    llm_client = LLMClient(llm_config)

    print("📝 测试原始提示词...")
    original_prompt = get_original_module_prompt()

    try:
        # 测试原始提示词
        messages = [
            {"role": "system", "content": "你是一个专业的技术文档专家。"},
            {"role": "user", "content": original_prompt},
        ]

        response = llm_client.completion(
            messages=messages, temperature=0.7, model=llm_config.get("model"), trace_name="原始提示词测试"
        )

        original_content = llm_client.get_completion_content(response)

        # 保存原始结果
        with tempfile.NamedTemporaryFile(mode="w", suffix="_original.md", delete=False, encoding="utf-8") as f:
            f.write(original_content)
            original_file = f.name

        print(f"✅ 原始提示词生成完成，文档长度: {len(original_content)} 字符")
        print(f"💾 原始文档已保存到: {original_file}")

    except Exception as e:
        print(f"❌ 原始提示词测试失败: {str(e)}")
        return

    print("\n📝 测试优化后提示词...")
    optimized_prompt = get_optimized_module_prompt()

    try:
        # 测试优化后提示词
        messages = [
            {"role": "system", "content": "你是一个专业的技术文档专家，擅长将复杂的代码转化为清晰易懂的教程文档。"},
            {"role": "user", "content": optimized_prompt},
        ]

        response = llm_client.completion(
            messages=messages, temperature=0.7, model=llm_config.get("model"), trace_name="优化提示词测试"
        )

        optimized_content = llm_client.get_completion_content(response)

        # 保存优化结果
        with tempfile.NamedTemporaryFile(mode="w", suffix="_optimized.md", delete=False, encoding="utf-8") as f:
            f.write(optimized_content)
            optimized_file = f.name

        print(f"✅ 优化提示词生成完成，文档长度: {len(optimized_content)} 字符")
        print(f"💾 优化文档已保存到: {optimized_file}")

    except Exception as e:
        print(f"❌ 优化提示词测试失败: {str(e)}")
        return

    # 对比分析
    print("\n📊 对比分析:")
    print(f"  原始文档长度: {len(original_content)} 字符")
    print(f"  优化文档长度: {len(optimized_content)} 字符")
    print(
        f"  长度增长: {len(optimized_content) - len(original_content)} 字符 ({((len(optimized_content) - len(original_content)) / len(original_content) * 100):.1f}%)"
    )

    # 简单的质量指标分析
    original_sections = original_content.count("#")
    optimized_sections = optimized_content.count("#")

    original_code_blocks = original_content.count("```")
    optimized_code_blocks = optimized_content.count("```")

    original_emojis = sum(1 for char in original_content if ord(char) > 127 and ord(char) < 65536)
    optimized_emojis = sum(1 for char in optimized_content if ord(char) > 127 and ord(char) < 65536)

    print(f"  标题数量: {original_sections} → {optimized_sections}")
    print(f"  代码块数量: {original_code_blocks // 2} → {optimized_code_blocks // 2}")
    print(f"  表情符号数量: {original_emojis} → {optimized_emojis}")

    # 检查是否包含Mermaid图表
    original_mermaid = "mermaid" in original_content.lower()
    optimized_mermaid = "mermaid" in optimized_content.lower()

    print(f"  包含Mermaid图表: {'是' if original_mermaid else '否'} → {'是' if optimized_mermaid else '否'}")

    print("\n🎉 提示词优化测试完成！")
    print("📁 请查看生成的文档文件进行详细对比:")
    print(f"   原始版本: {original_file}")
    print(f"   优化版本: {optimized_file}")


async def main():
    """主函数"""
    await test_prompt_comparison()


if __name__ == "__main__":
    asyncio.run(main())
