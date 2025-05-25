#!/bin/bash
# 运行项目测试

# 激活虚拟环境
source .venv/bin/activate

# 设置测试环境变量
export TESTING_MODE=true

# 运行所有测试
echo "运行所有测试..."
python run_tests.py --all

echo "测试完成！"
