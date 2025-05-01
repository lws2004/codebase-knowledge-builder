"""语言工具，用于检测语言和提取技术术语。"""
import re
from typing import List, Optional, Set, Tuple


def detect_natural_language(text: str) -> Tuple[str, float]:
    """检测文本的自然语言

    Args:
        text: 文本

    Returns:
        检测到的语言和置信度
    """
    # 简单实现：根据中文字符比例判断
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
    total_chars = len(text)

    if total_chars == 0:
        return "en", 0.0

    chinese_ratio = chinese_chars / total_chars

    if chinese_ratio > 0.1:
        return "zh", chinese_ratio
    else:
        return "en", 1.0 - chinese_ratio


def extract_technical_terms(text: str, domain: Optional[str] = None, language: Optional[str] = None) -> List[str]:
    """提取技术术语

    Args:
        text: 文本
        domain: 领域
        language: 语言

    Returns:
        技术术语列表
    """
    # 如果未指定语言，检测语言
    if language is None:
        language, _ = detect_natural_language(text)

    # 提取技术术语
    terms = set()

    # 提取代码块中的术语
    code_blocks = re.findall(r'```.*?\n(.*?)```', text, re.DOTALL)
    for block in code_blocks:
        # 提取变量名、函数名、类名等
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', block)
        terms.update(identifiers)

    # 提取行内代码中的术语
    inline_codes = re.findall(r'`([^`]+)`', text)
    for code in inline_codes:
        # 提取变量名、函数名、类名等
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code)
        terms.update(identifiers)

    # 提取常见技术术语
    common_terms = _get_common_technical_terms(domain, language)
    for term in common_terms:
        if term.lower() in text.lower():
            terms.add(term)

    # 过滤掉常见的非技术词
    filtered_terms = _filter_common_words(terms)

    return list(filtered_terms)


def _get_common_technical_terms(domain: Optional[str] = None, language: Optional[str] = None) -> Set[str]:
    """获取常见技术术语

    Args:
        domain: 领域
        language: 语言

    Returns:
        常见技术术语集合
    """
    # 通用技术术语
    common_terms = {
        "API", "REST", "HTTP", "HTTPS", "JSON", "XML", "HTML", "CSS", "JavaScript",
        "Python", "Java", "C++", "C#", "Go", "Rust", "TypeScript", "SQL", "NoSQL",
        "MongoDB", "MySQL", "PostgreSQL", "Redis", "Docker", "Kubernetes", "Git",
        "GitHub", "GitLab", "CI/CD", "AWS", "Azure", "GCP", "CLI", "GUI", "UI", "UX",
        "SDK", "IDE", "VS Code", "PyCharm", "IntelliJ", "Eclipse", "Vim", "Emacs",
        "npm", "pip", "conda", "virtualenv", "venv", "requirements.txt", "package.json",
        "Markdown", "YAML", "TOML", "CSV", "TSV", "JWT", "OAuth", "SAML", "LDAP",
        "TLS", "SSL", "SSH", "FTP", "SFTP", "TCP", "UDP", "IP", "DNS", "URL", "URI",
        "LLM", "AI", "ML", "NLP", "CV", "DL", "RL", "GPT", "BERT", "Transformer",
        "CNN", "RNN", "LSTM", "GRU", "PyTorch", "TensorFlow", "Keras", "scikit-learn",
        "pandas", "NumPy", "SciPy", "Matplotlib", "Seaborn", "Plotly", "Jupyter",
        "Notebook", "Colab", "Kaggle", "Hugging Face", "OpenAI", "Anthropic", "Claude",
        "API Key", "Token", "Embedding", "Vector", "RAG", "Retrieval", "Augmented",
        "Generation", "Prompt", "Completion", "Fine-tuning", "Transfer Learning",
        "Langfuse", "LiteLLM", "PocketFlow", "Node", "Flow", "Agent", "Agentic"
    }

    # 根据领域添加特定术语
    if domain == "web":
        common_terms.update({
            "React", "Angular", "Vue", "Svelte", "Next.js", "Nuxt.js", "Gatsby",
            "Webpack", "Babel", "ESLint", "Prettier", "Jest", "Mocha", "Chai",
            "Cypress", "Selenium", "Puppeteer", "Playwright", "SPA", "PWA", "SSR",
            "SSG", "CSR", "SEO", "Accessibility", "a11y", "i18n", "l10n", "WCAG",
            "ARIA", "DOM", "BOM", "AJAX", "Fetch", "Axios", "GraphQL", "Redux",
            "Vuex", "MobX", "Pinia", "Tailwind", "Bootstrap", "Material UI", "Chakra UI"
        })
    elif domain == "data":
        common_terms.update({
            "ETL", "ELT", "Data Warehouse", "Data Lake", "Data Mesh", "Data Fabric",
            "Hadoop", "Spark", "Flink", "Kafka", "Airflow", "Dagster", "dbt", "Looker",
            "Tableau", "Power BI", "Superset", "Metabase", "Redshift", "Snowflake",
            "BigQuery", "Databricks", "Delta Lake", "Iceberg", "Hudi", "Parquet",
            "Avro", "ORC", "Arrow", "Dask", "Ray", "Polars", "DuckDB", "ClickHouse"
        })

    # 根据语言添加特定术语
    if language == "zh":
        common_terms.update({
            "人工智能", "机器学习", "深度学习", "自然语言处理", "计算机视觉", "强化学习",
            "神经网络", "卷积神经网络", "循环神经网络", "长短期记忆网络", "门控循环单元",
            "变换器", "注意力机制", "自注意力", "多头注意力", "编码器", "解码器",
            "嵌入", "向量", "检索增强生成", "提示", "补全", "微调", "迁移学习",
            "大语言模型", "生成式人工智能", "代码库", "知识库", "文档生成", "教程生成"
        })

    return common_terms


def _filter_common_words(terms: Set[str]) -> Set[str]:
    """过滤常见的非技术词

    Args:
        terms: 术语集合

    Returns:
        过滤后的术语集合
    """
    # 常见的非技术词
    common_words = {
        "a", "an", "the", "and", "or", "but", "if", "then", "else", "when", "where",
        "what", "who", "how", "why", "which", "this", "that", "these", "those", "it",
        "its", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "do", "does", "did", "can", "could", "will", "would", "shall", "should", "may",
        "might", "must", "for", "to", "in", "on", "at", "by", "with", "about", "from",
        "of", "as", "into", "onto", "upon", "out", "over", "under", "above", "below",
        "between", "among", "through", "throughout", "during", "before", "after",
        "since", "until", "while", "because", "although", "though", "even", "just",
        "only", "also", "too", "very", "quite", "rather", "somewhat", "so", "such",
        "like", "unlike", "same", "different", "other", "another", "each", "every",
        "all", "some", "any", "no", "none", "not", "nor", "either", "neither", "both",
        "much", "many", "more", "most", "less", "least", "few", "little", "several",
        "enough", "plenty", "lot", "lots", "get", "got", "getting", "make", "made",
        "making", "take", "took", "taken", "taking", "give", "gave", "given", "giving",
        "put", "putting", "set", "setting", "go", "went", "gone", "going", "come",
        "came", "coming", "see", "saw", "seen", "seeing", "look", "looked", "looking",
        "find", "found", "finding", "use", "used", "using", "try", "tried", "trying",
        "call", "called", "calling", "work", "worked", "working", "want", "wanted",
        "wanting", "need", "needed", "needing", "start", "started", "starting", "end",
        "ended", "ending", "turn", "turned", "turning", "play", "played", "playing",
        "move", "moved", "moving", "live", "lived", "living", "believe", "believed",
        "believing", "feel", "felt", "feeling", "think", "thought", "thinking", "say",
        "said", "saying", "tell", "told", "telling", "know", "knew", "known", "knowing",
        "understand", "understood", "understanding", "remember", "remembered",
        "remembering", "forget", "forgot", "forgotten", "forgetting", "learn", "learned",
        "learning", "mean", "meant", "meaning", "show", "showed", "shown", "showing",
        "hear", "heard", "hearing", "listen", "listened", "listening", "speak", "spoke",
        "spoken", "speaking", "read", "reading", "write", "wrote", "written", "writing"
    }

    # 过滤掉常见的非技术词和长度小于 2 的词
    return {term for term in terms if term.lower() not in common_words and len(term) > 1}
