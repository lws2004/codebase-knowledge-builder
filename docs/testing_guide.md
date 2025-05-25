# 🧪 测试指南

## 📋 概述

本文档介绍了代码库知识构建器项目的测试体系，包括测试类型、测试覆盖范围、运行方法和最佳实践。

## 🏗️ 测试架构

### 测试分类

#### 1. 🔧 单元测试
- **目标**：测试单个函数和类的功能
- **覆盖范围**：工具函数、配置加载、数据处理
- **运行速度**：快速（< 1秒）

#### 2. 🔗 集成测试
- **目标**：测试模块间的交互
- **覆盖范围**：节点间通信、流程执行、API调用
- **运行速度**：中等（1-10秒）

#### 3. 🌐 端到端测试
- **目标**：测试完整的工作流程
- **覆盖范围**：从输入到输出的完整流程
- **运行速度**：较慢（10秒-5分钟）

#### 4. 🚀 性能测试
- **目标**：测试系统性能和并发能力
- **覆盖范围**：并行处理、内存使用、响应时间
- **运行速度**：较慢（1-10分钟）

## 📁 测试文件结构

```
tests/
├── unit/                           # 单元测试
│   ├── test_config_loader.py       # 配置加载器测试
│   ├── test_env_manager.py         # 环境管理器测试
│   ├── test_formatter.py           # 格式化工具测试
│   └── test_token_utils.py         # Token工具测试
├── integration/                    # 集成测试
│   ├── test_llm_client_optimized.py # LLM客户端集成测试
│   ├── test_mermaid_validation.py   # Mermaid验证集成测试
│   └── test_rag_utils.py           # RAG工具集成测试
├── e2e/                            # 端到端测试
│   ├── test_analyze_repo.py        # 仓库分析端到端测试
│   ├── test_generate_content_flow.py # 内容生成流程测试
│   └── test_with_requests.py       # 完整流程测试
├── performance/                    # 性能测试
│   ├── test_parallel_performance.py # 并行性能测试
│   └── test_optimized_docs_generation.py # 文档生成性能测试
└── fixtures/                       # 测试数据
    ├── sample_repos/               # 示例仓库
    └── expected_outputs/           # 期望输出
```

## 🆕 新增测试模块

### Mermaid验证测试
```python
# test_mermaid_validation.py
class TestMermaidValidation:
    def test_valid_mermaid_syntax(self):
        """测试有效的Mermaid语法验证"""
        
    def test_invalid_mermaid_syntax(self):
        """测试无效的Mermaid语法检测"""
        
    def test_mermaid_regeneration(self):
        """测试Mermaid图表重新生成"""
        
    def test_cli_validation_fallback(self):
        """测试CLI验证失败时的回退机制"""
```

### 优化文档生成测试
```python
# test_optimized_docs_generation.py
class TestOptimizedDocsGeneration:
    def test_quality_assessment(self):
        """测试文档质量评估"""
        
    def test_auto_regeneration(self):
        """测试自动重新生成功能"""
        
    def test_parallel_generation(self):
        """测试并行文档生成"""
        
    def test_mermaid_integration(self):
        """测试Mermaid验证集成"""
```

### 提示词优化测试
```python
# test_prompt_optimization.py
class TestPromptOptimization:
    def test_prompt_template_loading(self):
        """测试提示词模板加载"""
        
    def test_context_injection(self):
        """测试上下文注入"""
        
    def test_quality_improvement(self):
        """测试质量改进效果"""
```

## 🚀 运行测试

### 运行所有测试
```bash
# 使用脚本运行
./scripts/run_tests.sh

# 手动运行
source .venv/bin/activate
python -m pytest tests/ -v
```

### 运行特定类型的测试
```bash
# 单元测试
python -m pytest tests/unit/ -v

# 集成测试
python -m pytest tests/integration/ -v

# 端到端测试
python -m pytest tests/e2e/ -v

# 性能测试
python -m pytest tests/performance/ -v
```

### 运行特定测试文件
```bash
# Mermaid验证测试
python -m pytest tests/test_mermaid_validation.py -v

# 并行性能测试
python -m pytest tests/test_parallel_performance.py -v

# 优化文档生成测试
python -m pytest tests/test_optimized_docs_generation.py -v
```

### 运行带覆盖率的测试
```bash
# 生成覆盖率报告
python -m pytest tests/ --cov=src --cov-report=html --cov-report=term

# 查看覆盖率报告
open htmlcov/index.html
```

## 📊 测试覆盖率

### 当前覆盖率状态
| 模块 | 覆盖率 | 状态 |
|------|--------|------|
| 核心节点 | 85% | ✅ 良好 |
| 工具函数 | 92% | ✅ 优秀 |
| LLM客户端 | 78% | ⚠️ 需改进 |
| Mermaid验证 | 95% | ✅ 优秀 |
| 并行处理 | 82% | ✅ 良好 |
| 配置管理 | 90% | ✅ 优秀 |

### 覆盖率目标
- **总体目标**：≥ 85%
- **核心模块**：≥ 90%
- **新功能**：≥ 95%

## 🔧 测试配置

### pytest配置
```ini
# pytest.ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
markers =
    unit: 单元测试
    integration: 集成测试
    e2e: 端到端测试
    performance: 性能测试
    slow: 慢速测试
```

### 测试环境配置
```yaml
# config/test.yml
llm:
  model: "openai/gpt-3.5-turbo"  # 使用更经济的模型
  max_tokens: 1000
  temperature: 0.1

parallel_processing:
  max_workers: 2                 # 降低并发数
  max_concurrent_llm_calls: 1

quality_assessment:
  enabled: false                 # 测试时禁用质量评估
```

## 🎯 测试最佳实践

### 1. 测试命名规范
```python
def test_should_validate_mermaid_when_syntax_is_correct():
    """测试：当Mermaid语法正确时应该验证通过"""
    
def test_should_regenerate_mermaid_when_syntax_is_invalid():
    """测试：当Mermaid语法错误时应该重新生成"""
```

### 2. 使用Fixture
```python
@pytest.fixture
def sample_mermaid_content():
    """提供示例Mermaid内容"""
    return """
    graph TD
        A[开始] --> B[处理]
        B --> C[结束]
    """

@pytest.fixture
def mock_llm_client():
    """提供模拟LLM客户端"""
    with patch('src.utils.llm_client.LLMClient') as mock:
        yield mock
```

### 3. 参数化测试
```python
@pytest.mark.parametrize("chart_type,content,expected", [
    ("graph", "graph TD\n    A --> B", True),
    ("flowchart", "flowchart TD\n    A --> B", True),
    ("invalid", "invalid syntax", False),
])
def test_mermaid_validation(chart_type, content, expected):
    """参数化测试Mermaid验证"""
    result = validate_mermaid_syntax(content)
    assert result[0] == expected
```

### 4. 异步测试
```python
@pytest.mark.asyncio
async def test_async_parallel_processing():
    """测试异步并行处理"""
    tasks = [async_process_item(item) for item in items]
    results = await asyncio.gather(*tasks)
    assert len(results) == len(items)
```

## 🐛 调试测试

### 运行单个测试并查看详细输出
```bash
python -m pytest tests/test_mermaid_validation.py::test_valid_syntax -v -s
```

### 使用pdb调试
```python
def test_complex_scenario():
    import pdb; pdb.set_trace()
    # 测试代码
```

### 查看测试日志
```bash
python -m pytest tests/ -v --log-cli-level=DEBUG
```

## 📈 持续集成

### GitHub Actions配置
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: pytest tests/ --cov=src --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v1
```

## 🔮 测试改进计划

### 短期目标
- [ ] 提升LLM客户端测试覆盖率至90%
- [ ] 添加更多边界条件测试
- [ ] 完善性能基准测试

### 中期目标
- [ ] 实现自动化测试报告生成
- [ ] 添加压力测试和负载测试
- [ ] 集成代码质量检查工具

### 长期目标
- [ ] 建立测试数据管理系统
- [ ] 实现智能测试用例生成
- [ ] 构建测试环境自动化部署

---

*最后更新：2024年12月*
