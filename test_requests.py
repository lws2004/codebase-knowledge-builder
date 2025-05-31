"""
测试请求模块

该模块用于测试 requests 库的基本功能，包括虚拟环境加载和简单的GET请求测试。
"""

import os

import requests

# 自动加载虚拟环境（如果存在）
venv_path = os.path.join(os.path.dirname(__file__), "venv")
if os.path.exists(venv_path):
    activate_this = os.path.join(venv_path, "bin", "activate_this.py")
    with open(activate_this) as f:
        exec(f.read(), {"__file__": activate_this})

# 测试请求
try:
    response = requests.get("https://api.github.com")
    print(f"Requests测试成功! 状态码: {response.status_code}")
except Exception as e:
    print(f"Requests测试失败: {str(e)}")
