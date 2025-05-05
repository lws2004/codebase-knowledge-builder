#!/bin/bash

# 从 .env 文件加载环境变量
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

# 检查 API 密钥是否存在
if [ -z "$LLM_API_KEY" ]; then
  echo "错误: 未找到 LLM_API_KEY 环境变量"
  exit 1
fi

# 打印 API 密钥的前 8 位和后 4 位
echo "API 密钥: ${LLM_API_KEY:0:8}...${LLM_API_KEY: -4}"

# 使用 curl 调用 OpenRouter API
echo "尝试调用 OpenRouter API..."
curl -s -X POST \
  https://openrouter.ai/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $LLM_API_KEY" \
  -H "HTTP-Referer: http://localhost:3000" \
  -H "X-Title: Codebase Knowledge Builder" \
  -d '{
    "model": "qwen/qwen3-30b-a3b:free",
    "messages": [{"role": "user", "content": "Hello, world!"}],
    "max_tokens": 10
  }'

echo -e "\n"
