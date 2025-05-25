# 🔧 配置简化改进

## 📋 概述

本文档说明了LLM配置系统的简化改进，统一使用`LLM_BASE_URL`环境变量，提供更一致和直观的配置体验。

## 🎯 改进目标

### 问题背景
之前的配置系统使用提供商特定的环境变量（如`OPENAI_BASE_URL`、`OPENROUTER_BASE_URL`等），导致：
- 配置复杂，用户需要记住不同提供商的变量名
- 不一致的配置体验
- 切换提供商时需要修改多个环境变量

### 解决方案
引入统一的`LLM_BASE_URL`环境变量，同时保持向后兼容性。

## 🆕 新的配置方式

### 推荐配置（统一方式）
```bash
# 统一使用 LLM_BASE_URL，支持所有提供商
LLM_API_KEY=your-api-key
LLM_BASE_URL=your-base-url
LLM_MODEL=your-model
```

### 具体示例

#### 阿里云DashScope
```bash
LLM_API_KEY=sk-your-dashscope-api-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-turbo
```

#### OpenAI
```bash
LLM_API_KEY=sk-your-openai-api-key
LLM_MODEL=gpt-4
# LLM_BASE_URL=https://api.openai.com/v1  # 可选，使用默认值
```

#### OpenRouter
```bash
LLM_API_KEY=sk-your-openrouter-api-key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openrouter/anthropic/claude-3-opus-20240229  # 必须包含openrouter/前缀
```

**注意**：OpenRouter模型必须使用`openrouter/`前缀，格式为`openrouter/provider/model-name`

#### 自定义端点
```bash
LLM_API_KEY=your-custom-api-key
LLM_BASE_URL=https://your-custom-endpoint.com/v1
LLM_MODEL=your-custom-model
```

## 🔄 配置优先级

系统支持多种配置方式，优先级从高到低：

1. **LLM_BASE_URL** 环境变量（推荐）
2. **提供商特定环境变量**（兼容性支持）
   - `OPENAI_BASE_URL`
   - `OPENROUTER_BASE_URL`
   - `ALIBABA_BASE_URL`
   - `VOLCENGINE_BASE_URL`
   - `MOONSHOT_BASE_URL`
3. **配置文件默认值**（config/default.yml）

### 优先级示例

```bash
# 情况1: 只设置 LLM_BASE_URL
LLM_BASE_URL=https://custom.com/v1
# 结果: 使用 https://custom.com/v1

# 情况2: 同时设置两个变量
LLM_BASE_URL=https://priority.com/v1
OPENAI_BASE_URL=https://ignored.com/v1
# 结果: 使用 https://priority.com/v1 (LLM_BASE_URL优先)

# 情况3: 只设置提供商特定变量
OPENAI_BASE_URL=https://openai-custom.com/v1
# 结果: 使用 https://openai-custom.com/v1 (兼容性支持)

# 情况4: 都不设置
# 结果: 使用配置文件中的默认值
```

## 🔧 技术实现

### 环境变量定义
```python
# 新增统一的 LLM_BASE_URL 环境变量
LLM_BASE_URL_ENV = "LLM_BASE_URL"
```

### 配置逻辑
```python
def _apply_provider_specific_config(config: Dict[str, Any], loader: ConfigLoader) -> None:
    """应用提供商特定配置"""
    provider = config.get("provider")

    # 1. 首先检查通用的 LLM_BASE_URL
    base_url = os.getenv(LLM_BASE_URL_ENV)

    # 2. 如果没有设置，检查提供商特定的环境变量
    if not base_url:
        if provider == "openai":
            base_url = os.getenv(OPENAI_BASE_URL_ENV)
        elif provider == "openrouter":
            base_url = os.getenv(OPENROUTER_BASE_URL_ENV)
        # ... 其他提供商

    # 3. 设置到配置中
    if base_url:
        config["base_url"] = base_url
```

## 🧪 验证工具

### 配置验证脚本
提供了专门的验证脚本 `scripts/validate_config.py`：

```bash
source .venv/bin/activate
python scripts/validate_config.py
```

### 验证功能
- ✅ 检查配置文件和环境变量
- ✅ 分析配置来源（LLM_BASE_URL vs 提供商特定变量）
- ✅ 验证LLM客户端初始化
- ✅ 测试Token计算和文本生成
- 💡 提供配置建议和示例

### 验证输出示例
```
🔧 验证LLM配置

📋 当前配置:
  - 提供商: openai
  - 模型: qwen-turbo
  - API密钥: 已设置
  - Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1

🔍 配置来源分析:
  - 使用 LLM_BASE_URL: https://dashscope.aliyuncs.com/compatible-mode/v1

🤖 测试LLM客户端:
  ✅ LLM客户端创建成功
  ✅ Token计算成功: 15
  ✅ 文本生成成功: 天气真好，心情也跟着明朗起来了。
```

## 📚 迁移指南

### 从旧配置迁移

#### 阿里云DashScope
**旧配置**：
```bash
LLM_API_KEY=sk-your-key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-turbo
```

**新配置**：
```bash
LLM_API_KEY=sk-your-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-turbo
```

#### OpenRouter
**旧配置**：
```bash
LLM_API_KEY=sk-your-key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openrouter/anthropic/claude-3-opus-20240229
```

**新配置**：
```bash
LLM_API_KEY=sk-your-key
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=openrouter/anthropic/claude-3-opus-20240229
```

### 兼容性保证
- ✅ 旧的配置方式仍然有效
- ✅ 无需立即迁移，可以逐步更新
- ✅ 新旧配置可以混合使用（新配置优先）

## 🎉 改进效果

### 用户体验改进
1. **配置更简单**：只需记住一个环境变量名
2. **更一致**：所有提供商使用相同的配置方式
3. **更直观**：变量名清晰表达用途
4. **易于切换**：更换提供商时只需修改URL和模型

### 开发体验改进
1. **代码更清晰**：统一的配置处理逻辑
2. **维护更容易**：减少提供商特定的代码分支
3. **扩展更简单**：新增提供商时无需添加特定环境变量
4. **测试更全面**：统一的验证工具和测试用例

### 向后兼容
1. **零破坏性**：现有配置继续工作
2. **渐进迁移**：用户可以按自己的节奏迁移
3. **清晰优先级**：明确的配置优先级规则
4. **完整文档**：详细的迁移指南和示例

## 📖 相关文档

- [LLM配置故障排除指南](llm_config_troubleshooting.md)
- [最新功能特性](latest_features.md)
- [测试指南](testing_guide.md)
- [项目README](../README.md)

---

*最后更新：2024年12月*
