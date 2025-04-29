"""
运行所有测试的脚本。
"""
import os
import sys
import argparse
import importlib
from dotenv import load_dotenv

def run_test(test_name):
    """运行指定的测试
    
    Args:
        test_name: 测试名称
        
    Returns:
        是否成功
    """
    try:
        # 导入测试模块
        module_name = f"tests.{test_name}"
        module = importlib.import_module(module_name)
        
        # 运行测试
        if hasattr(module, "main"):
            module.main()
            return True
        else:
            print(f"错误: 测试模块 {module_name} 没有 main 函数")
            return False
    except ImportError as e:
        print(f"错误: 无法导入测试模块 {module_name}: {str(e)}")
        return False
    except Exception as e:
        print(f"错误: 运行测试 {test_name} 失败: {str(e)}")
        return False

def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="运行测试")
    parser.add_argument("--test", type=str, help="要运行的测试名称，不包含 'test_' 前缀和 '.py' 后缀")
    parser.add_argument("--all", action="store_true", help="运行所有测试")
    args = parser.parse_args()
    
    # 加载环境变量
    load_dotenv()
    
    # 确保当前目录在 Python 路径中
    sys.path.insert(0, os.path.abspath("."))
    
    # 运行测试
    if args.test:
        # 运行指定的测试
        test_name = f"test_{args.test}" if not args.test.startswith("test_") else args.test
        success = run_test(test_name)
        sys.exit(0 if success else 1)
    elif args.all:
        # 运行所有测试
        test_dir = os.path.join(os.path.dirname(__file__), "tests")
        test_files = [f[:-3] for f in os.listdir(test_dir) if f.startswith("test_") and f.endswith(".py")]
        
        success = True
        for test_file in test_files:
            print(f"\n运行测试: {test_file}")
            print("=" * 80)
            if not run_test(test_file):
                success = False
            print("=" * 80)
        
        sys.exit(0 if success else 1)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()
