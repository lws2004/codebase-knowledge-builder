#!/bin/bash
# 运行项目测试

# 激活虚拟环境
source .venv/bin/activate

# 运行所有测试
echo "运行所有测试..."
python run_tests.py --all

echo "测试完成！"
