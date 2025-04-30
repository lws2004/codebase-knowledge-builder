# 配置管理指南

## 概述

为了解决配置在多个文件中重复存在的问题，本项目采用了集中式配置管理方法，使用 `pyproject.toml` 作为唯一的主要配置文件。这种方法简化了配置管理，避免了配置不一致的问题。

## 配置文件

项目中的配置文件及其用途：

1. **pyproject.toml** - 主要配置文件，包含所有工具和代码风格的配置
2. **.editorconfig** - 仅包含编辑器特定的设置，如缩进、换行符等

## 修改配置

当需要修改配置时，只需编辑 `pyproject.toml` 文件中的相应部分。所有工具都将从这个文件中读取配置。

## 配置项说明

### 代码长度约束

在 `pyproject.toml` 的 `[tool.code-style]` 部分定义：

```toml
[tool.code-style]
# 代码长度约束
max_file_lines = 300        # 单文件代码行数限制（不含注释和空行）
max_function_lines = 30     # 单个函数/方法行数限制
max_line_length = 120       # 单行长度限制（字符数）
max_class_lines = 200       # 单个类行数限制
max_node_class_lines = 100  # 单个节点类行数限制
max_nesting_level = 2       # 嵌套层级限制
max_function_params = 5     # 函数参数数量限制
```

### 工具配置

各种工具的配置也在 `pyproject.toml` 中定义：

```toml
[tool.ruff]
# Python linter 配置
line-length = 120
target-version = "py310"
# E: pycodestyle 错误
# F: pyflakes 错误
# W: pycodestyle 警告
# I: isort 规则
# C: McCabe 复杂度
# N: PEP8 命名规则
# D: pydocstyle 文档规则
select = ["E", "F", "W", "I", "C", "N", "D"]
ignore = ["E203", "D203", "D212"]
exclude = [".git", "__pycache__", "build", "dist", ".venv"]
# 允许自动修复
fixable = ["ALL"]
unfixable = []

[tool.ruff.mccabe]
max-complexity = 10

[tool.ruff.pydocstyle]
convention = "google"

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = "test_*.py"
python_functions = "test_*"
python_classes = "Test*"
addopts = "--verbose"
```

## 工具兼容性

本项目使用的工具都支持从 `pyproject.toml` 读取配置：

- **Ruff**：完全支持 `pyproject.toml`，用于代码格式化、导入排序和代码质量检查
- **mypy**：完全支持 `pyproject.toml`，用于类型检查
- **pytest**：完全支持 `pyproject.toml`，用于测试

Ruff 是一个快速的 Python linter 和代码格式化工具，它可以替代多个工具：
- 替代 **Black** 进行代码格式化
- 替代 **isort** 进行导入排序
- 替代 **Flake8** 进行代码质量检查
- 替代 **pydocstyle** 进行文档字符串检查
- 替代 **McCabe** 进行复杂度检查

## 自定义代码检查

项目中的自定义代码检查工具也应该从 `pyproject.toml` 的 `[tool.code-style]` 部分读取配置。这些配置项包括代码长度约束、文档风格约束、命名约定和导入规则。

## 编辑器集成

`.editorconfig` 文件仅包含编辑器特定的设置，如缩进、换行符等。代码风格相关的配置（如行长度）应该从 `pyproject.toml` 中读取。

大多数现代编辑器和 IDE 都支持 `pyproject.toml` 配置，包括：

- **VS Code**：通过插件支持 Ruff、mypy 等工具的 `pyproject.toml` 配置
- **PyCharm**：内置支持 Ruff、mypy 等工具的 `pyproject.toml` 配置
- **Vim/Neovim**：通过插件支持各种工具的 `pyproject.toml` 配置

### VSCode 集成

为了确保 VSCode 中的 linting 和 formatting 工具正确读取配置，我们采取了以下措施：

1. 在 `.vscode/settings.json` 中添加了最小化配置，主要用于指定 Python 解释器和启用格式化
2. 使用 Ruff 作为主要的代码质量工具，它原生支持 `pyproject.toml`
3. 配置 VSCode 使用 Ruff 进行格式化和 linting

VSCode 的 `.vscode/settings.json` 配置示例：

```json
{
    // Python 虚拟环境设置
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python.terminal.activateEnvironment": true,

    // 基本编辑器设置
    "editor.formatOnSave": true,
    "editor.rulers": [120],

    // 代码格式化设置 - 使用 Ruff 进行格式化和 linting
    "[python]": {
        "editor.formatOnSave": true,
        "editor.defaultFormatter": "charliermarsh.ruff",
        "editor.codeActionsOnSave": {
            "source.fixAll.ruff": "explicit",
            "source.organizeImports.ruff": "explicit"
        }
    }
}
```

推荐安装的 VSCode 扩展：
- `ms-python.python` - Python 语言支持
- `ms-python.vscode-pylance` - Python 语言服务器
- `charliermarsh.ruff` - Ruff 集成（替代 Black、isort 和 Flake8）

所有开发依赖都已添加到 `requirements-dev.txt` 文件中，您可以通过以下命令安装：

```bash
uv pip install -r requirements-dev.txt
```
