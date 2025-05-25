#!/usr/bin/env python3
"""验证LLM配置的脚本"""

import os
import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def validate_config():
    """验证LLM配置"""
    print("🔧 验证LLM配置\n")

    try:
        from src.utils.env_manager import get_llm_config, load_env_vars
        from src.utils.llm_client import LLMClient

        # 加载环境变量
        load_env_vars()

        # 获取配置
        config = get_llm_config()

        print("📋 当前配置:")
        print(f"  - 提供商: {config.get('provider')}")
        print(f"  - 模型: {config.get('model')}")
        print(f"  - API密钥: {'已设置' if config.get('api_key') else '未设置'}")
        print(f"  - Base URL: {config.get('base_url', '默认')}")
        print(f"  - 最大Token数: {config.get('max_tokens')}")
        print(f"  - 温度: {config.get('temperature')}")

        # 检查配置来源
        print("\n🔍 配置来源分析:")
        llm_base_url = os.getenv("LLM_BASE_URL")
        openai_base_url = os.getenv("OPENAI_BASE_URL")

        if llm_base_url:
            print(f"  - 使用 LLM_BASE_URL: {llm_base_url}")
        elif openai_base_url:
            print(f"  - 使用 OPENAI_BASE_URL: {openai_base_url}")
        else:
            print("  - 使用默认配置或配置文件")

        # 测试LLM客户端
        print("\n🤖 测试LLM客户端:")
        client = LLMClient(config)
        print("  ✅ LLM客户端创建成功")

        # 测试token计算
        test_text = "Hello, this is a test."
        token_count = client.count_tokens(test_text)
        print(f"  ✅ Token计算成功: {token_count}")

        # 测试文本生成（如果API密钥有效）
        if config.get("api_key") and config.get("api_key") not in ["your_api_key_here", "test-key"]:
            print("  🔄 测试文本生成...")
            try:
                response = client.generate_text("请说一句话", max_tokens=10)
                print(f"  ✅ 文本生成成功: {response[:50]}...")
            except Exception as e:
                print(f"  ❌ 文本生成失败: {str(e)}")
                return False
        else:
            print("  ⚠️  跳过文本生成测试（未设置有效API密钥）")

        print("\n🎉 配置验证完成！")
        return True

    except Exception as e:
        print(f"❌ 配置验证失败: {str(e)}")
        return False


def show_config_examples():
    """显示配置示例"""
    print("\n📚 配置示例:")

    print("\n🔹 阿里云DashScope (推荐):")
    print("LLM_API_KEY=sk-your-dashscope-api-key")
    print("LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1")
    print("LLM_MODEL=qwen-turbo")

    print("\n🔹 OpenAI:")
    print("LLM_API_KEY=sk-your-openai-api-key")
    print("LLM_MODEL=gpt-4")
    print("# LLM_BASE_URL=https://api.openai.com/v1  # 可选")

    print("\n🔹 OpenRouter:")
    print("LLM_API_KEY=sk-your-openrouter-api-key")
    print("LLM_MODEL=openrouter/anthropic/claude-3-opus-20240229  # 必须包含openrouter/前缀")
    print("LLM_BASE_URL=https://openrouter.ai/api/v1")
    print("# 注意：模型格式必须为 openrouter/provider/model-name")

    print("\n🔹 自定义端点:")
    print("LLM_API_KEY=your-custom-api-key")
    print("LLM_MODEL=your-custom-model")
    print("LLM_BASE_URL=https://your-custom-endpoint.com/v1")


def main():
    """主函数"""
    print("🚀 LLM配置验证工具\n")

    # 检查.env文件
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env文件不存在")
        print("💡 请复制.env.example为.env并配置API密钥")
        show_config_examples()
        return False

    # 验证配置
    success = validate_config()

    if not success:
        print("\n💡 配置建议:")
        show_config_examples()
        print("\n📖 更多帮助请参考: docs/llm_config_troubleshooting.md")

    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
