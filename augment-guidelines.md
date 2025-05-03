# Augment Guidelines: Agentic Coding

> 🚨 **注意**: 如果你是参与构建 LLM 系统的 AI 代理，请**非常、非常**仔细阅读本指南！这是整个文档中最重要的章节。在开发过程中，你应该始终 (1) 从小而简单的解决方案开始，(2) 在实现前进行高层次设计（`docs/design.md`），以及 (3) 经常向人类寻求反馈和澄清。

## Agentic Coding 步骤

Agentic Coding 应该是人类系统设计与代理实现之间的协作：

| 步骤                  | 人类      | AI        | 说明                                                                 |
|:-----------------------|:----------:|:---------:|:------------------------------------------------------------------------|
| 1. 需求分析 | ★★★ 高  | ★☆☆ 低   | 人类理解需求和上下文。                    |
| 2. 流程设计          | ★★☆ 中等 | ★★☆ 中等 | 人类指定高层设计，AI 填充细节。 |
| 3. 工具函数   | ★★☆ 中等 | ★★☆ 中等 | 人类提供可用的外部 API 和集成，AI 帮助实现。 |
| 4. 节点设计          | ★☆☆ 低   | ★★★ 高  | AI 根据流程帮助设计节点类型和数据处理。          |
| 5. 实现      | ★☆☆ 低   | ★★★ 高  | AI 根据设计实现流程。 |
| 6. 优化        | ★★☆ 中等 | ★★☆ 中等 | 人类评估结果，AI 帮助优化。 |
| 7. 可靠性         | ★☆☆ 低   | ★★★ 高  | AI 编写测试用例并处理边缘情况。     |

1. **需求分析**：明确项目需求，评估 AI 系统是否适合。
    - 了解 AI 系统的优势和局限性：
      - **适合**：需要常识的常规任务（填表、回复邮件）
      - **适合**：具有明确输入的创意任务（制作幻灯片、编写 SQL）
      - **不适合**：需要复杂决策的模糊问题（商业战略、创业规划）
    - **以用户为中心**：从用户角度解释"问题"，而不仅仅是列出功能。
    - **平衡复杂性与影响**：尽早提供最小复杂性的高价值功能。

2. **流程设计**：高层次概述，描述 AI 系统如何编排节点。
    - 确定适用的设计模式（例如 Map Reduce、Agent、RAG）。
      - 对于流程中的每个节点，从高层次的一行描述开始说明其功能。
      - 如使用 **Map Reduce**，指定如何映射（拆分什么）和如何归约（如何组合）。
      - 如使用 **Agent**，指定输入（上下文）和可能的操作。
      - 如使用 **RAG**，指定要嵌入的内容，注意通常有离线（索引）和在线（检索）工作流。
    - 概述流程并用 mermaid 图表绘制。例如：
      ```mermaid
      flowchart LR
          start[开始] --> batch[批处理]
          batch --> check[检查]
          check -->|正常| process
          check -->|错误| fix[修复]
          fix --> check
          
          subgraph process[处理]
            step1[步骤 1] --> step2[步骤 2]
          end
          
          process --> endNode[结束]
      ```
    - > **如果人类无法指定流程，AI 代理就无法自动化它！** 在构建 LLM 系统之前，通过手动解决示例输入来彻底理解问题和潜在解决方案，以发展直觉。

3. **工具函数**：根据流程设计，确定并实现必要的工具函数。
    - 将 AI 系统视为大脑。它需要一个身体——这些*外部工具函数*——与现实世界交互：
        <div align="center"><img src="https://github.com/the-pocket/PocketFlow/raw/main/assets/utility.png?raw=true" width="400"/></div>

        - 读取输入（例如，检索 Slack 消息、阅读邮件）
        - 写入输出（例如，生成报告、发送邮件）
        - 使用外部工具（例如，调用 LLM、搜索网络）
        - **注意**：*基于 LLM 的任务*（例如，总结文本、分析情感）**不是**工具函数；它们是 AI 系统内部的*核心功能*。
    - 对于每个工具函数，实现它并编写简单的测试。
    - 记录它们的输入/输出，以及为什么它们是必要的。例如：
      - `名称`: `get_embedding` (`utils/get_embedding.py`)
      - `输入`: `str`
      - `输出`: 3072 个浮点数的向量
      - `必要性`: 由第二个节点用于嵌入文本
    - 工具实现示例：
      ```python
      # utils/call_llm.py
      from openai import OpenAI

      def call_llm(prompt):    
          client = OpenAI(api_key="YOUR_API_KEY_HERE")
          r = client.chat.completions.create(
              model="gpt-4o",
              messages=[{"role": "user", "content": prompt}]
          )
          return r.choices[0].message.content
          
      if __name__ == "__main__":
          prompt = "What is the meaning of life?"
          print(call_llm(prompt))
      ```
    - > **有时，在流程之前设计工具**：例如，对于自动化遗留系统的 LLM 项目，瓶颈可能是该系统的可用接口。从设计最困难的接口工具开始，然后围绕它们构建流程。

4. **节点设计**：规划每个节点如何读写数据，以及使用工具函数。
   - PocketFlow 的一个核心设计原则是使用[共享存储](./core_abstraction/communication.md)，所以从共享存储设计开始：
      - 对于简单系统，使用内存字典。
      - 对于更复杂的系统或需要持久性时，使用数据库。
      - **不要重复自己**：使用内存引用或外键。
      - 共享存储设计示例：
        ```python
        shared = {
            "user": {
                "id": "user123",
                "context": {                # 另一个嵌套字典
                    "weather": {"temp": 72, "condition": "sunny"},
                    "location": "San Francisco"
                }
            },
            "results": {}                   # 存储输出的空字典
        }
        ```
   - 对于每个[节点](./core_abstraction/node.md)，描述其类型、如何读写数据以及使用哪个工具函数。保持具体但高层次，不含代码。例如：
     - `类型`: 常规（或批处理，或异步）
     - `准备`: 从共享存储读取"文本"
     - `执行`: 调用嵌入工具函数
     - `后处理`: 将"嵌入"写入共享存储

5. **实现**：根据设计实现初始节点和流程。
   - 🎉 如果你已经到达这一步，人类已经完成了设计。现在*Agentic Coding*开始！
   - **"保持简单，笨蛋！"** 避免复杂功能和全面类型检查。
   - **快速失败**！避免 `try` 逻辑，以便快速识别系统中的弱点。
   - 在代码中添加日志记录以便于调试。

6. **优化**:
   - **使用直觉**：对于快速初步评估，人类直觉通常是一个良好的开始。
   - **重新设计流程（回到步骤 3）**：考虑进一步分解任务，引入代理决策，或更好地管理输入上下文。
   - 如果你的流程设计已经很扎实，可以进行微优化：
     - **提示工程**：使用清晰、具体的指令和示例减少歧义。
     - **上下文学习**：为难以用指令指定的任务提供强大的示例。

   - > **你可能会多次迭代！** 预计会重复步骤 3-6 数百次。
     >
     > <div align="center"><img src="https://github.com/the-pocket/PocketFlow/raw/main/assets/success.png?raw=true" width="400"/></div>

7. **可靠性**  
   - **节点重试**：在节点 `exec` 中添加检查以确保输出满足要求，并考虑增加 `max_retries` 和 `wait` 时间。
   - **日志和可视化**：维护所有尝试的日志并可视化节点结果，以便更容易调试。
   - **自我评估**：当结果不确定时，添加单独的节点（由 LLM 驱动）来审查输出。

## LLM 项目文件结构示例

```
my_project/
├── main.py
├── nodes.py
├── flow.py
├── utils/
│   ├── __init__.py
│   ├── call_llm.py
│   └── search_web.py
├── requirements.txt
└── docs/
    └── design.md
```

- **`docs/design.md`**: 包含上述每个步骤的项目文档。这应该是*高层次*和*无代码*的。
- **`utils/`**: 包含所有工具函数。
  - 建议为每个 API 调用专门一个 Python 文件，例如 `call_llm.py` 或 `search_web.py`。
  - 每个文件还应包含一个 `main()` 函数来尝试该 API 调用
- **`nodes.py`**: 包含所有节点定义。
  ```python
  # nodes.py
  from pocketflow import Node
  from utils.call_llm import call_llm

  class GetQuestionNode(Node):
      def exec(self, _):
          # 直接从用户输入获取问题
          user_question = input("Enter your question: ")
          return user_question
      
      def post(self, shared, prep_res, exec_res):
          # 存储用户的问题
          shared["question"] = exec_res
          return "default"  # 转到下一个节点

  class AnswerNode(Node):
      def prep(self, shared):
          # 从共享存储读取问题
          return shared["question"]
      
      def exec(self, question):
          # 调用 LLM 获取答案
          return call_llm(question)
      
      def post(self, shared, prep_res, exec_res):
          # 将答案存储在共享存储中
          shared["answer"] = exec_res
  ```
- **`flow.py`**: 通过导入节点定义并连接它们来实现创建流程的函数。
  ```python
  # flow.py
  from pocketflow import Flow
  from nodes import GetQuestionNode, AnswerNode

  def create_qa_flow():
      """创建并返回问答流程。"""
      # 创建节点
      get_question_node = GetQuestionNode()
      answer_node = AnswerNode()
      
      # 按顺序连接节点
      get_question_node >> answer_node
      
      # 创建以输入节点开始的流程
      return Flow(start=get_question_node)
  ```
- **`main.py`**: 作为项目的入口点。
  ```python
  # main.py
  from flow import create_qa_flow

  # 示例主函数
  # 请用你自己的主函数替换
  def main():
      shared = {
          "question": None,  # 将由 GetQuestionNode 从用户输入填充
          "answer": None     # 将由 AnswerNode 填充
      }

      # 创建流程并运行
      qa_flow = create_qa_flow()
      qa_flow.run(shared)
      print(f"Question: {shared['question']}")
      print(f"Answer: {shared['answer']}")

  if __name__ == "__main__":
      main()
  ```

## 核心抽象

我们将 LLM 工作流建模为 **图 + 共享存储**：

- [节点](./core_abstraction/node.md) 处理简单的 (LLM) 任务。
- [流程](./core_abstraction/flow.md) 通过 **操作**（标记边）连接节点。
- [共享存储](./core_abstraction/communication.md) 使流程内的节点之间能够通信。
- [批处理](./core_abstraction/batch.md) 节点/流程允许数据密集型任务。
- [异步](./core_abstraction/async.md) 节点/流程允许等待异步任务。
- [(高级) 并行](./core_abstraction/parallel.md) 节点/流程处理 I/O 绑定任务。

## 设计模式

从这里，很容易实现流行的设计模式：

- [代理](./design_pattern/agent.md) 自主做出决策。
- [工作流](./design_pattern/workflow.md) 将多个任务链接成管道。
- [RAG](./design_pattern/rag.md) 将数据检索与生成集成。
- [Map Reduce](./design_pattern/mapreduce.md) 将数据任务分为 Map 和 Reduce 步骤。
- [结构化输出](./design_pattern/structure.md) 一致地格式化输出。
- [(高级) 多代理](./design_pattern/multi_agent.md) 协调多个代理。

## 工具函数

我们**不**提供内置工具。相反，我们提供*示例*——请*实现你自己的*：

- [LLM 包装器](./utility_function/llm.md)
- [可视化和调试](./utility_function/viz.md)
- [网络搜索](./utility_function/websearch.md)
- [分块](./utility_function/chunking.md)
- [嵌入](./utility_function/embedding.md)
- [向量数据库](./utility_function/vector.md)
- [文本转语音](./utility_function/text_to_speech.md)

**为什么不内置？**：我认为在通用框架中使用特定供应商的 API 是一种*不良实践*：
- *API 波动性*：频繁变化导致硬编码 API 的维护成本高。
- *灵活性*：你可能想切换供应商，使用微调模型，或在本地运行它们。
- *优化*：没有供应商锁定，提示缓存、批处理和流式处理更容易。
