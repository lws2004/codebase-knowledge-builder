# 🔧 LLM配置故障排除指南

## 📋 概述

本文档提供了LLM配置相关问题的故障排除指南，帮助您快速解决常见的配置问题。

## 🚨 常见错误及解决方案

### 1. AuthenticationError: Incorrect API key provided

**错误信息**：
```
litellm.AuthenticationError: AuthenticationError: OpenAIException - Incorrect API key provided.
```

**原因**：API密钥配置错误或无效

**解决方案**：
1. 检查`.env`文件中的`LLM_API_KEY`是否正确
2. 确认API密钥是否有效且未过期
3. 验证API密钥格式是否正确

### 2. LLM Provider NOT provided

**错误信息**：
```
litellm.BadRequestError: LLM Provider NOT provided. Pass in the LLM provider you are trying to call.
```

**原因**：LiteLLM不认识指定的提供商格式

**解决方案**：
- 对于阿里云DashScope，使用OpenAI兼容模式：
  ```bash
  OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
  LLM_MODEL=qwen-turbo  # 不需要alibaba/前缀
  ```

### 3. 计算token数失败

**错误信息**：
```
计算token数失败: litellm.BadRequestError: LLM Provider NOT provided
```

**原因**：模型格式不被LiteLLM支持

**解决方案**：使用LiteLLM支持的模型格式

## 🔧 阿里云DashScope配置

### 正确配置方式

```bash
# .env文件配置（推荐方式）
LLM_API_KEY=sk-your-dashscope-api-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-turbo
```

### 支持的模型

- `qwen-turbo`：通义千问Turbo版本
- `qwen-plus`：通义千问Plus版本
- `qwen-max`：通义千问Max版本
- `qwen-long`：通义千问Long版本

### 配置方式对比

❌ **旧方式（不推荐）**：
```bash
LLM_MODEL=alibaba/qwen-turbo
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

✅ **新方式（推荐）**：
```bash
LLM_MODEL=qwen-turbo
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 配置优先级

系统支持多种配置方式，优先级如下：

1. **LLM_BASE_URL**（推荐）：统一的Base URL配置，支持所有提供商
2. **提供商特定URL**：如OPENAI_BASE_URL、OPENROUTER_BASE_URL等
3. **配置文件默认值**：config/default.yml中的默认配置

## 🌐 其他提供商配置

### OpenAI
```bash
LLM_API_KEY=sk-your-openai-api-key
LLM_MODEL=gpt-4
# LLM_BASE_URL=https://api.openai.com/v1  # 可选，默认值
```

### OpenRouter
```bash
LLM_API_KEY=sk-your-openrouter-api-key
LLM_MODEL=openrouter/anthropic/claude-3-opus-20240229  # 必须包含openrouter/前缀
LLM_BASE_URL=https://openrouter.ai/api/v1
```

**重要说明**：
- ✅ **正确格式**：`openrouter/provider/model-name`
- ❌ **错误格式**：`anthropic/claude-3-opus-20240229`（会被识别为Anthropic直连）
- 💡 **原因**：LiteLLM需要`openrouter/`前缀来识别这是通过OpenRouter调用的模型

### Anthropic
```bash
LLM_API_KEY=sk-your-anthropic-api-key
LLM_MODEL=anthropic/claude-3-opus-20240229
# LLM_BASE_URL=https://api.anthropic.com  # 可选，如果需要自定义
```

### 自定义端点
```bash
LLM_API_KEY=your-custom-api-key
LLM_MODEL=your-custom-model
LLM_BASE_URL=https://your-custom-endpoint.com/v1
```

## 🧪 配置验证

### 快速测试脚本

创建`test_config.py`文件：

```python
#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.utils.env_manager import load_env_vars, get_llm_config
from src.utils.llm_client import LLMClient

def test_llm_config():
    """测试LLM配置"""
    print("🔧 测试LLM配置...")

    # 加载环境变量
    load_env_vars()

    # 获取LLM配置
    config = get_llm_config()

    print(f"📋 配置信息:")
    print(f"  - 提供商: {config.get('provider')}")
    print(f"  - 模型: {config.get('model')}")
    print(f"  - API密钥: {'已设置' if config.get('api_key') else '未设置'}")
    print(f"  - Base URL: {config.get('base_url', '默认')}")

    # 测试LLM客户端
    try:
        client = LLMClient(config)
        print("✅ LLM客户端创建成功")

        # 测试token计算
        token_count = client.count_tokens("Hello world")
        print(f"📊 Token计算测试: {token_count}")

        # 测试文本生成
        if config.get('api_key') and config.get('api_key') != 'your_api_key_here':
            response = client.generate_text("说一句话", max_tokens=20)
            print(f"✅ 文本生成测试成功: {response[:50]}...")
        else:
            print("⚠️  跳过文本生成测试（未设置有效API密钥）")

        return True
    except Exception as e:
        print(f"❌ 测试失败: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_llm_config()
    sys.exit(0 if success else 1)
```

### 运行测试

```bash
source .venv/bin/activate
python test_config.py
```

## 🔍 调试技巧

### 1. 启用详细日志

在`.env`文件中添加：
```bash
LITELLM_LOG=DEBUG
```

### 2. 检查环境变量

```bash
# 检查关键环境变量
echo "LLM_API_KEY: $LLM_API_KEY"
echo "LLM_MODEL: $LLM_MODEL"
echo "OPENAI_BASE_URL: $OPENAI_BASE_URL"
```

### 3. 验证API连通性

```bash
# 测试阿里云DashScope API
curl -X POST "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions" \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen-turbo",
    "messages": [{"role": "user", "content": "Hello"}],
    "max_tokens": 10
  }'
```

## 📚 参考资料

### LiteLLM文档
- [支持的提供商](https://docs.litellm.ai/docs/providers)
- [OpenAI兼容端点](https://docs.litellm.ai/docs/providers/openai_compatible)

### 阿里云DashScope
- [OpenAI兼容性文档](https://help.aliyun.com/zh/model-studio/compatibility-of-openai-with-dashscope)
- [API参考](https://help.aliyun.com/zh/model-studio/use-qwen-by-calling-api)

## 🆘 获取帮助

如果问题仍然存在：

1. **检查日志**：查看详细的错误日志信息
2. **验证网络**：确认网络连接正常
3. **更新依赖**：确保使用最新版本的LiteLLM
4. **提交Issue**：在项目仓库中提交详细的错误报告

### 提交Issue时请包含

- 错误的完整堆栈跟踪
- 使用的模型和提供商
- 环境变量配置（隐藏敏感信息）
- Python和依赖版本信息

---

*最后更新：2024年12月*
