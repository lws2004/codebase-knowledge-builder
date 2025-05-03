"""并行生成内容示例脚本，比较串行和并行流程的性能。"""

import asyncio
import os
import sys
import time
from typing import Dict, Tuple

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.nodes import GenerateContentFlow, ParallelGenerateContentFlow
from src.utils.env_manager import load_env_vars


async def run_parallel_flow(shared: Dict) -> Tuple[Dict, float]:
    """运行并行流程

    Args:
        shared: 共享存储

    Returns:
        流程结果和执行时间
    """
    # 创建并行生成内容流程
    flow = ParallelGenerateContentFlow()

    # 记录开始时间
    start_time = time.time()

    # 运行流程
    result = await flow.run_async(shared)

    # 记录结束时间
    end_time = time.time()

    return result, end_time - start_time


def run_serial_flow(shared: Dict) -> Tuple[Dict, float]:
    """运行串行流程

    Args:
        shared: 共享存储

    Returns:
        流程结果和执行时间
    """
    # 创建串行生成内容流程
    flow = GenerateContentFlow()

    # 记录开始时间
    start_time = time.time()

    # 运行流程
    result = flow.run(shared)

    # 记录结束时间
    end_time = time.time()

    return result, end_time - start_time


async def main():
    """主函数"""
    # 加载环境变量
    load_env_vars()

    # 创建共享存储
    shared = {
        "repo_path": "../example-repo",  # 替换为实际的代码库路径
        "code_structure": {
            "files": {
                "main.py": {
                    "content": "print('Hello, World!')",
                    "language": "python",
                    "size": 23,
                },
                "utils.py": {
                    "content": "def add(a, b):\n    return a + b",
                    "language": "python",
                    "size": 32,
                },
            },
            "directories": {
                "src": {
                    "files": ["main.py"],
                    "subdirectories": [],
                },
                "utils": {
                    "files": ["utils.py"],
                    "subdirectories": [],
                },
            },
            "languages": {
                "python": 2,
            },
            "total_files": 2,
            "total_size": 55,
        },
        "core_modules": {
            "main": {
                "description": "主模块，包含程序入口点",
                "dependencies": [],
            },
            "utils": {
                "description": "工具模块，包含通用工具函数",
                "dependencies": [],
            },
        },
    }

    # 运行并行流程
    print("运行并行流程...")
    parallel_result, parallel_time = await run_parallel_flow(shared.copy())
    print(f"并行流程完成，耗时: {parallel_time:.2f} 秒")
    print(f"生成的文档数量: {len([k for k in parallel_result if k.endswith('_doc')])}")

    # 运行串行流程
    print("\n运行串行流程...")
    serial_result, serial_time = run_serial_flow(shared.copy())
    print(f"串行流程完成，耗时: {serial_time:.2f} 秒")
    print(f"生成的文档数量: {len([k for k in serial_result if k.endswith('_doc')])}")

    # 比较性能
    speedup = serial_time / parallel_time if parallel_time > 0 else 0
    print("\n性能比较:")
    print(f"- 并行流程: {parallel_time:.2f} 秒")
    print(f"- 串行流程: {serial_time:.2f} 秒")
    print(f"- 加速比: {speedup:.2f}x")

    # 输出生成的文档标题
    print("\n生成的文档:")
    for doc_key, doc_value in parallel_result.items():
        if isinstance(doc_value, Dict) and "title" in doc_value:
            print(f"- {doc_value['title']}")


if __name__ == "__main__":
    asyncio.run(main())
