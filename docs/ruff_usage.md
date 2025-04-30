# Ruff 使用指南

## 概述

[Ruff](https://github.com/astral-sh/ruff) 是一个快速的 Python linter 和代码格式化工具，它可以替代多个工具，包括 Black、isort、Flake8、pydocstyle 和 McCabe。本项目使用 Ruff 作为主要的代码质量工具，以简化依赖和配置。

## 功能

Ruff 提供了以下功能：

1. **代码格式化**：替代 Black，自动格式化代码
2. **导入排序**：替代 isort，对导入进行排序
3. **代码质量检查**：替代 Flake8，检查代码质量问题
4. **文档字符串检查**：替代 pydocstyle，检查文档字符串
5. **复杂度检查**：替代 McCabe，检查代码复杂度

## 配置

Ruff 的配置位于 `pyproject.toml` 文件中：

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
```

## 命令行使用

### 检查代码

```bash
# 检查整个项目
ruff check .

# 检查特定目录
ruff check src/

# 检查特定文件
ruff check src/main.py
```

### 自动修复问题

```bash
# 自动修复整个项目
ruff check --fix .

# 自动修复特定目录
ruff check --fix src/

# 自动修复特定文件
ruff check --fix src/main.py
```

### 格式化代码

```bash
# 格式化整个项目
ruff format .

# 格式化特定目录
ruff format src/

# 格式化特定文件
ruff format src/main.py
```

### 检查格式化（不修改文件）

```bash
# 检查整个项目的格式化
ruff format --check .
```

## VSCode 集成

在 VSCode 中，您可以安装 [Ruff 扩展](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff)，它提供了以下功能：

1. 实时代码质量检查
2. 自动修复问题
3. 格式化代码
4. 导入排序

VSCode 的配置位于 `.vscode/settings.json` 文件中：

```json
{
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

## 性能优势

Ruff 是用 Rust 编写的，比传统的 Python linter 和格式化工具快 10-100 倍。这意味着：

1. 更快的代码检查和格式化
2. 更快的 CI/CD 流程
3. 更好的开发体验

## 规则集

Ruff 支持多种规则集，每个规则集对应一个或多个检查类别：

- **E/W**：pycodestyle 错误和警告
- **F**：pyflakes 错误
- **I**：isort 规则
- **C**：McCabe 复杂度
- **N**：PEP8 命名规则
- **D**：pydocstyle 文档规则

您可以在 `pyproject.toml` 的 `select` 字段中指定要启用的规则集，在 `ignore` 字段中指定要禁用的规则。

## 更多资源

- [Ruff 官方文档](https://docs.astral.sh/ruff/)
- [Ruff GitHub 仓库](https://github.com/astral-sh/ruff)
- [Ruff VSCode 扩展](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff)
