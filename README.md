<h1 align="center">代码库知识构建器</h1>

<p align="center">
  <a href="https://github.com/The-Pocket/PocketFlow" target="_blank">
    <img
      src="./assets/banner.png" width="600"
    />
  </a>
</p>

这个项目是一个代码库知识构建工具，基于 [Pocket Flow](https://github.com/The-Pocket/PocketFlow) 框架开发，用于分析 Git 仓库并生成知识文档。

## 功能

- 🔍 分析 Git 仓库的提交历史和代码结构
- 🧩 识别重要文件、模块和贡献者
- 🤖 使用 LLM 生成全面的代码库文档
- 📊 生成架构图、依赖关系图和时间线图表
- 📝 直接以用户指定语言生成内容，无需额外翻译
- 🌐 支持多种 LLM 提供商（OpenAI、OpenRouter、阿里百炼、火山引擎、硅基流动）
- ⚡ 支持异步并行处理，提高生成效率
- 🔄 提供内容质量检查和自动优化
- 💬 支持交互式问答，深入了解代码库
- 🎨 **Mermaid图表验证和自动修复**，确保图表语法正确
- 📈 **智能质量评估**，7维度文档质量检查
- 🚀 **高性能并行处理**，支持大型代码库快速分析
- 🔧 **模块化架构**，易于扩展和定制
- 💾 **智能缓存机制**，避免重复计算和API调用

## 安装

1. 克隆仓库：

```bash
git clone https://github.com/yourusername/codebase-knowledge-builder.git
cd codebase-knowledge-builder
```

2. 确保已安装 uv：

```bash
# 使用 pip 安装 uv
pip install uv

# 或使用 curl 安装
curl -sSf https://install.python-uv.org | python3
```

3. 使用提供的脚本设置环境：

```bash
./scripts/setup.sh
```

这个脚本会使用 uv 创建虚拟环境并安装所有依赖。

### VSCode 集成

本项目包含 VSCode 配置文件，提供以下功能：

- 自动激活虚拟环境
- 代码格式化和检查设置
- 调试配置
- 常用任务快捷方式
- 推荐扩展

使用 VSCode 打开项目时，它会自动使用项目的虚拟环境。您还可以通过以下方式访问预配置的任务：

1. 按下 `Ctrl+Shift+P`（Windows/Linux）或 `Cmd+Shift+P`（macOS）
2. 输入 "Tasks: Run Task"
3. 选择要运行的任务，如 "设置环境"、"运行测试" 等

## 配置

### 环境变量配置

环境变量主要用于配置敏感信息（如 API 密钥）或需要在不同环境中覆盖的配置。

1. 复制 `.env.example` 文件为 `.env`：

```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，设置必要的 API 密钥：

```
# 必需的配置
LLM_API_KEY=your_api_key_here  # LLM API密钥
LANGFUSE_PUBLIC_KEY=your_public_key_here  # Langfuse公钥（可选，用于跟踪和评估）
LANGFUSE_SECRET_KEY=your_secret_key_here  # Langfuse私钥（可选，用于跟踪和评估）

# LLM配置（可选）
LLM_MODEL=openai/gpt-4  # 格式: "provider/model"，例如: "openai/gpt-4", "anthropic/claude-3-opus-20240229"
LLM_BASE_URL=https://api.openai.com/v1  # 自定义API基础URL
LLM_MAX_TOKENS=4000  # 控制LLM输出的最大token数
# LLM_MAX_INPUT_TOKENS=25000  # 控制输入到LLM的最大token数（可选）
```

其他配置项已在配置文件中设置默认值，只有在需要覆盖默认值时才需要在环境变量中设置。

#### LLM提供商配置

支持的LLM提供商格式：

- **OpenAI**: `openai/gpt-4`、`openai/gpt-3.5-turbo`
- **Anthropic**: `anthropic/claude-3-opus-20240229`、`anthropic/claude-3-sonnet-20240229`
- **OpenRouter**: `openrouter/anthropic/claude-3-opus-20240229`
- **阿里百炼**: `alibaba/qwen-max`
- **火山引擎**: `volcengine/moonshot-v1-8k`
- **硅基流动**: `moonshot/moonshot-v1-8k`

### YAML 配置文件

项目使用 YAML 配置文件来存储默认配置，位于 `config` 目录下：

- `config/default.yml`：默认配置文件，包含所有配置项的默认值
- `config/{env}.yml`：环境特定配置文件，如 `development.yml`、`production.yml` 等

大多数配置都应该在 YAML 配置文件中设置，而不是环境变量。这样可以：

1. 集中管理配置
2. 更好地组织和分类配置
3. 支持层次结构和复杂配置
4. 便于版本控制和审查

您可以通过创建环境特定的配置文件来覆盖默认配置，例如：

```bash
cp config/default.yml config/production.yml
```

然后编辑 `config/production.yml` 文件，只修改需要覆盖的配置项。例如：

```yaml
# 生产环境配置
llm:
  model: "gpt-3.5-turbo"  # 使用更经济的模型
  temperature: 0.5        # 降低随机性

git:
  cache_ttl: 3600         # 缓存时间缩短为 1 小时
```

运行程序时，可以通过 `--env` 参数指定环境：

```bash
python main.py --repo-url https://github.com/username/repo.git --env production
```

### 🆕 新增配置选项

#### Mermaid图表验证配置
```yaml
mermaid_validation:
  enabled: true                    # 启用Mermaid验证
  use_cli: true                   # 优先使用mermaid-cli
  fallback_to_rules: true         # CLI失败时回退到规则验证
  backup_files: true              # 修复前备份文件
  max_regeneration_attempts: 2    # 最大重新生成次数
```

#### 并行处理配置
```yaml
parallel_processing:
  enabled: true                   # 启用并行处理
  max_workers: 4                  # 最大工作线程数
  max_concurrent_llm_calls: 3     # 最大并发LLM调用数
  enable_async: true              # 启用异步处理
```

#### 质量评估配置
```yaml
quality_assessment:
  enabled: true                   # 启用质量评估
  overall_threshold: 7.0          # 总体质量阈值
  auto_regenerate: true           # 自动重新生成低质量文档
  detailed_feedback: true         # 提供详细反馈
```

## 使用方法

### 使用脚本运行

我们提供了几个便捷的脚本来简化常见操作：

#### 运行主程序

```bash
./scripts/run.sh https://github.com/username/repo.git [branch] [language] [env] [parallel]
```

参数说明：
- 第一个参数：Git 仓库 URL（必需）
- 第二个参数：分支名称（可选，默认为 `main`）
- 第三个参数：文档语言（可选，默认为 `zh`）
- 第四个参数：环境名称（可选，默认为 `default`）
- 第五个参数：是否启用并行处理（可选，默认为 `false`）

例如：
```bash
# 基本用法
./scripts/run.sh https://github.com/username/repo.git

# 指定分支和语言
./scripts/run.sh https://github.com/username/repo.git develop en

# 完整参数
./scripts/run.sh https://github.com/username/repo.git develop zh production true
```

#### 运行所有测试

```bash
./scripts/run_tests.sh
```

#### 更新依赖

```bash
./scripts/update_deps.sh
```

#### 清理环境

```bash
./scripts/clean.sh
```

### 手动运行

如果您想手动运行程序，可以使用以下命令：

#### 直接使用主程序

```bash
source .venv/bin/activate
python main.py --repo-url https://github.com/username/repo.git --branch main --env default --language zh
```

可用的命令行参数：

- `--repo-url`：Git 仓库 URL（必需）
- `--branch`：分支名称（可选，默认使用配置文件中的 `git.default_branch`）
- `--output-dir`：输出目录路径（可选，默认为 `docs_output`）
- `--language`：文档语言（可选，默认为 `zh`）
- `--env`：环境名称（可选，默认为 `default`）
- `--parallel`：是否启用并行处理（可选，默认为 `False`）
- `--interactive`：是否启用交互式问答（可选，默认为 `False`）

#### 运行测试脚本

```bash
source .venv/bin/activate

# 分析 Git 仓库历史
python tests/test_analyze_history.py --repo-path /path/to/repo --max-commits 100

# 测试代码解析
python tests/test_code_parser.py --repo-path /path/to/repo

# 测试内容生成
python tests/test_generate_content_flow.py --repo-url https://github.com/username/repo.git

# 测试并行性能
python tests/test_parallel_performance.py --repo-url https://github.com/username/repo.git
```

#### 运行完整流程（测试脚本）

```bash
source .venv/bin/activate
python tests/test_flow.py --repo-url https://github.com/username/repo.git --branch main --language zh
```

#### 运行所有测试

```bash
source .venv/bin/activate
python run_tests.py --all
```

#### 查看生成的文档

生成的文档将保存在 `docs_output/{repo_name}/` 目录下，包括：

- `index.md`：文档首页
- `overview.md`：系统架构
- `dependency.md`：依赖关系
- `glossary.md`：术语表
- `timeline.md`：演变历史
- `quick_look.md`：快速浏览
- `modules/`：模块详细文档

## 项目结构

- `src/`: 源代码
  - `nodes/`: 节点实现
    - `ai_understand_core_modules_node.py`: AI理解核心模块节点
    - `analyze_history_node.py`: 历史分析节点
    - `analyze_repo_flow.py`: 仓库分析流程
    - `async_parallel_batch_node.py`: 异步并行批处理节点
    - `async_parallel_flow.py`: 异步并行流程
    - `combine_content_node.py`: 内容组合节点
    - `content_quality_check_node.py`: 内容质量检查节点
    - `flow_connector_nodes.py`: 流程连接器节点
    - `format_output_node.py`: 输出格式化节点
    - `generate_api_docs_node.py`: API文档生成节点
    - `generate_content_flow.py`: 内容生成流程
    - `generate_dependency_node.py`: 依赖关系生成节点
    - `generate_glossary_node.py`: 术语表生成节点
    - `generate_module_details_node.py`: 模块详情生成节点
    - `generate_overall_architecture_node.py`: 整体架构生成节点
    - `generate_quick_look_node.py`: 快速浏览生成节点
    - `generate_timeline_node.py`: 时间线生成节点
    - `input_node.py`: 输入节点
    - `interactive_qa_node.py`: 交互式问答节点
    - `mermaid_validation_node.py`: **Mermaid图表验证节点**
    - `module_quality_check_node.py`: 模块质量检查节点
    - `parallel_generate_content_flow.py`: 并行内容生成流程
    - `parallel_start_node.py`: 并行启动节点
    - `parse_code_batch_node.py`: 代码批量解析节点
    - `parse_code_node.py`: 代码解析节点
    - `prepare_rag_data_node.py`: RAG数据准备节点
    - `prepare_repo_node.py`: 仓库准备节点
    - `publish_node.py`: 发布节点
  - `utils/`: 工具类
    - `git_utils/`: Git 相关工具
      - `history_analyzer.py`: 历史分析器
      - `repo_manager.py`: 仓库管理器
    - `llm_wrapper/`: LLM 调用工具
      - `llm_client_async.py`: 异步LLM客户端
      - `llm_client_base.py`: 基础LLM客户端
      - `llm_client_langfuse.py`: Langfuse集成客户端
      - `llm_client_sync.py`: 同步LLM客户端
      - `llm_client_utils.py`: LLM客户端工具
      - `llm_client.py`: LLM客户端
      - `token_utils.py`: Token工具
    - `logger/`: 日志工具
    - `code_parser_base.py`: 代码解析基类
    - `code_parser_extractors.py`: 代码解析提取器
    - `code_parser_file.py`: 文件代码解析器
    - `code_parser_repo.py`: 仓库代码解析器
    - `code_parser.py`: 代码解析器
    - `config_loader.py`: 配置加载器
    - `env_manager.py`: 环境管理器
    - `formatter.py`: 格式化工具
    - `language_utils.py`: 语言工具
    - `llm_client.py`: LLM客户端
    - `logging_config.py`: 日志配置
    - `mermaid_validator.py`: **Mermaid图表验证器**
    - `mermaid_regenerator.py`: **Mermaid图表重新生成器**
    - `performance.py`: 性能工具
    - `rag_utils.py`: RAG工具
- `tests/`: 测试脚本
  - `test_analyze_history.py`: 历史分析测试
  - `test_analyze_repo.py`: 仓库分析测试
  - `test_code_parser.py`: 代码解析测试
  - `test_combine_content_node.py`: 内容组合节点测试
  - `test_config_loader.py`: 配置加载器测试
  - `test_env_manager.py`: 环境管理器测试
  - `test_flow.py`: 流程测试
  - `test_format_output_node.py`: 输出格式化节点测试
  - `test_formatter.py`: 格式化工具测试
  - `test_generate_content_flow.py`: 内容生成流程测试
  - `test_generate_docs.py`: 文档生成测试
  - `test_generate_module_details_node.py`: 模块详情生成节点测试
  - `test_input_prepare.py`: 输入准备测试
  - `test_interactive_qa_node.py`: 交互式问答节点测试
  - `test_litellm_logging.py`: LiteLLM日志测试
  - `test_llm_call.py`: LLM调用测试
  - `test_llm_client_optimized.py`: 优化LLM客户端测试
  - `test_mermaid_validation.py`: **Mermaid验证测试**
  - `test_model_config.py`: 模型配置测试
  - `test_openrouter.py`: OpenRouter测试
  - `test_optimized_docs_generation.py`: **优化文档生成测试**
  - `test_parallel_performance.py`: 并行性能测试
  - `test_prompt_optimization.py`: **提示词优化测试**
  - `test_publish_node.py`: 发布节点测试
  - `test_rag_utils.py`: RAG工具测试
  - `test_token_utils.py`: Token工具测试
  - `test_with_requests.py`: Requests库测试
- `docs/`: 文档
  - `design.md`: 设计文档
  - `prompt_optimization_summary.md`: **提示词优化总结**
- `docs_output/`: 文档输出目录
  - `{repo_name}/`: 按仓库名组织的文档
    - `modules/`: 模块文档
    - `index.md`: 文档首页
    - `overview.md`: 系统架构
    - `dependency.md`: 依赖关系
    - `glossary.md`: 术语表
    - `timeline.md`: 演变历史
    - `quick_look.md`: 快速浏览
- `config/`: 配置文件
  - `default.yml`: 默认配置文件
  - `{env}.yml`: 环境特定配置文件
- `scripts/`: 便捷脚本
  - `setup.sh`: 设置环境脚本
  - `update_deps.sh`: 更新依赖脚本
  - `run_tests.sh`: 运行测试脚本
  - `run.sh`: 运行主程序脚本
  - `clean.sh`: 清理环境脚本
- `assets/`: 资源文件
  - `banner.png`: 项目横幅图片
- `examples/`: 示例文件
- `typings/`: 类型定义
  - `pocketflow/`: PocketFlow类型定义
- `.vscode/`: VSCode 配置目录
  - `settings.json`: VSCode 设置
  - `launch.json`: 调试配置
  - `tasks.json`: 任务配置
  - `extensions.json`: 推荐扩展
- `pyproject.toml`: 项目配置文件
- `requirements.txt`: 依赖列表
- `main.py`: 主程序入口
- `run_tests.py`: 测试运行脚本

## 项目架构和工作流程

项目基于 [PocketFlow](https://github.com/The-Pocket/PocketFlow) 框架开发，采用节点式流程设计，主要包含以下几个阶段：

1. **输入与准备阶段**：接收用户输入，准备代码库
   - 输入节点：接收用户参数
   - 准备仓库节点：克隆或验证本地代码库

2. **代码库分析阶段**：分析代码库结构和历史
   - 代码解析节点：解析代码结构和依赖关系
   - 历史分析节点：分析提交历史和贡献者信息
   - AI理解核心模块节点：使用LLM理解代码库核心架构

3. **内容生成阶段**：生成各类文档内容
   - 整体架构生成节点：生成系统架构文档
   - 依赖关系生成节点：生成依赖关系文档
   - 时间线生成节点：生成演变历史文档
   - 术语表生成节点：生成术语表文档
   - 快速浏览生成节点：生成快速浏览文档
   - 模块详情生成节点：生成模块详细文档

4. **质量检查阶段**：检查生成内容质量
   - 内容质量检查节点：评估文档质量并提供改进建议
   - 模块质量检查节点：评估模块文档质量并提供改进建议
   - **Mermaid验证节点**：验证和修复文档中的Mermaid图表

5. **内容组合与格式化阶段**：组合和格式化最终文档
   - 内容组合节点：组合各部分内容
   - 格式化输出节点：格式化最终文档

6. **交互问答阶段**（可选）：支持用户交互式问答
   - 交互式问答节点：回答用户关于代码库的问题

### 并行处理

项目支持多种并行处理模式，显著提升处理效率：

1. **批处理并行**：将大量文件分批并行处理
   - 代码批量解析节点：并行解析多个代码文件
   - 模块批量生成节点：并行生成多个模块文档

2. **流程并行**：并行执行多个内容生成流程
   - 并行内容生成流程：同时生成多种类型的文档
   - **异步并行流程**：支持异步节点的并行执行

3. **智能并发控制**：
   - 可配置的最大并发数，避免资源过载
   - 信号量机制控制并发访问
   - 异常隔离，单个任务失败不影响其他任务

### 🎨 Mermaid图表验证

项目内置了强大的Mermaid图表验证和修复功能：

1. **多层验证机制**：
   - 优先使用mermaid-cli进行真实渲染验证
   - 回退到基于规则的语法检查
   - 支持多种图表类型验证

2. **自动修复功能**：
   - 检测到语法错误时自动调用LLM重新生成
   - 保留原始文件备份
   - 智能错误定位和修复建议

3. **性能优化**：
   - 进程池隔离，避免主线程阻塞
   - 异步验证，提升处理效率
   - 缓存验证结果，避免重复检查

### 📈 质量评估系统

项目采用7维度质量评估体系：

1. **评估维度**：
   - 📚 完整性：内容覆盖度和信息完整性
   - ✅ 准确性：技术信息和代码示例的正确性
   - 📖 可读性：语言表达和逻辑结构的清晰度
   - 🎨 格式化：Markdown语法和排版的规范性
   - 📊 可视化：图表和示意图的丰富程度
   - 🎓 教学价值：文档的教学效果和学习价值
   - 🔧 实用性：代码示例和实践指导的实用性

2. **智能优化**：
   - 低于阈值的文档自动触发重新生成
   - 提供具体的改进建议和优先级
   - 支持迭代优化，持续提升质量

## 贡献

欢迎提交 Pull Request 和 Issue。如果您有任何问题或建议，请随时提出。

## 许可证

MIT
