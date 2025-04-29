"""
测试配置加载器的脚本。
"""
import os
import sys
import json

# 确保当前目录在 Python 路径中
sys.path.insert(0, os.path.abspath("."))

from src.utils.config_loader import ConfigLoader

def main():
    """主函数"""
    print("测试配置加载器")

    # 创建配置加载器
    config_loader = ConfigLoader()

    # 获取完整配置
    config = config_loader.get_config()

    # 打印默认配置
    print("\n默认配置:")
    print(json.dumps(config, indent=2, ensure_ascii=False))

    # 加载开发环境配置
    config_loader.load_env_config("development")

    # 获取更新后的配置
    config = config_loader.get_config()

    # 打印开发环境配置
    print("\n开发环境配置:")
    print(json.dumps(config, indent=2, ensure_ascii=False))

    # 获取特定配置项
    print("\n特定配置项:")
    print(f"应用名称: {config_loader.get('app.name')}")
    print(f"LLM 提供商: {config_loader.get('llm.provider')}")
    print(f"LLM 模型: {config_loader.get('llm.model')}")
    print(f"Git 默认分支: {config_loader.get('git.default_branch')}")

    # 获取节点配置
    print("\n节点配置:")
    analyze_history_config = config_loader.get_node_config("analyze_history")
    print(json.dumps(analyze_history_config, indent=2, ensure_ascii=False))

    # 测试不存在的配置项
    print("\n不存在的配置项:")
    print(f"不存在的配置项: {config_loader.get('not.exist', '默认值')}")

if __name__ == "__main__":
    main()
