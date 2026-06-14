# 03 — 模块设计与接口规约

> 每开始写一个模块前，读对应小节。接口只给签名与 docstring，实现体自己写。
> 签名是"建议形态"——如果你写的过程中发现更合理的设计，可以改，但要想清楚为什么。

## 1. 项目目录结构

```
protocol-qa-agent/
├── docs/                        # 本套文档
├── data/                        # 运行时数据（git忽略）
│   ├── raw/{doc_id}/            # 原始上传文件
│   ├── pageindex/{doc_id}.json  # PageIndex 树
│   ├── chroma/                  # ChromaDB 持久化目录
│   ├── bm25/                    # BM25 索引落盘
│   └── app.db                   # SQLite
├── eval/
│   └── questions.jsonl          # 评测问题集
├── src/
│   ├── core/                    # 核心：配置、数据模型、异常、日志
│   │   ├── config.py
│   │   ├── models.py
│   │   ├── errors.py
│   │   └── logging.py
│   ├── providers/               # 模型适配层
│   │   ├── base.py              # 抽象接口
│   │   ├── openai_compat.py
│   │   ├── ollama.py
│   │   └── factory.py           # 按配置创建实例
│   ├── storage/                 # 持久化
│   │   ├── database.py          # SQLite 连接与建表
│   │   ├── doc_repo.py          # documents/chunks 表的增删改查
│   │   ├── chat_repo.py         # 会话历史
│   │   └── files.py             # 原始文件落盘
│   ├── ingestion/               # 入库流水线
│   │   ├── parsers/
│   │   │   ├── base.py          # 解析器接口 + IR 定义引用
│   │   │   ├── docx_parser.py
│   │   │   ├── xlsx_parser.py
│   │   │   └── pptx_parser.py
│   │   ├── chunker.py           # 结构感知切块
│   │   ├── tree_builder.py      # PageIndex 树构建
│   │   └── pipeline.py          # 编排：解析→切块→向量化→建索引
│   ├── retrieval/               # 检索层
│   │   ├── vector_store.py      # ChromaDB 封装
│   │   ├── bm25.py              # 手写 BM25
│   │   ├── tree_search.py       # PageIndex 树导航
│   │   └── fusion.py            # RRF 融合
│   ├── agent/                   # Agent 引擎
│   │   ├── prompts.py           # 所有 Prompt 模板集中管理
│   │   ├── query_rewriter.py
│   │   ├── orchestrator.py      # 核心循环
│   │   └── answerer.py          # 最终生成
│   └── api/                     # FastAPI 层
│       ├── main.py              # app 创建、路由注册、生命周期
│       ├── routes_documents.py
│       ├── routes_chat.py
│       └── schemas.py           # 请求/响应 Pydantic 模型
├── static/                      # 极简前端（单页 HTML+JS）
├── scripts/                     # 自测脚本（每阶段验收用）
│   ├── check_provider.py
│   ├── ingest_cli.py            # 命令行入库（不经过API，便于调试）
│   └── ask_cli.py               # 命令行问答
├── tests/                       # 单元测试（重点测 chunker/bm25/fusion）
├── .env.example
├── requirements.txt
└── pyproject.toml 或 setup 说明
```

## 2. 模块依赖图（只允许单向，禁止循环 import）

```
api ──► agent ──► retrieval ──► providers
 │        │           │            ▲
 │        │           └──► storage │
 │        └──► storage             │
 ├──► ingestion ──► providers ─────┘
 │        └──► storage
 └──► storage
所有模块 ──► core（core 不依赖任何业务模块）
```

> 自查方法：core 里绝不 import 业务模块；providers 不 import storage；出现循环 import 报错时，通常意味着某个数据模型该挪进 core/models.py。

## 3. core — 核心模块

### 3.1 `core/config.py`

用 `pydantic-settings` 从 `.env` 读配置。配置项清单：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `LLM_PROVIDER` | str | `"openai_compat"` | `openai_compat` / `ollama` |
| `LLM_BASE_URL` | str | — | API 地址 |
| `LLM_API_KEY` | str | `""` | Ollama 不需要 |
| `LLM_MODEL` | str | — | 对话模型名 |
| `EMBED_PROVIDER` / `EMBED_BASE_URL` / `EMBED_MODEL` | str | — | Embedding 可与 LLM 不同源 |
| `DATA_DIR` | Path | `./data` | 数据根目录 |
| `CHUNK_MAX_TOKENS` | int | 512 | 切块上限 |
| `RETRIEVAL_TOP_K` | int | 8 | 每路检索条数 |
| `FUSION_TOP_N` | int | 6 | 融合后送生成的条数 |
| `AGENT_MAX_ROUNDS` | int | 3 | Agent 循环上限 |
| `TREE_MAX_DEPTH` / `TREE_MAX_SELECT` | int | 3 / 3 | 树导航限制 |

### 3.2 `core/models.py` — 数据模型（dataclass 或 Pydantic）

**DocStatus（enum）**：`UPLOADED / PARSING / CHUNKING / EMBEDDING / INDEXING / READY / FAILED`

**Document**

| 字段 | 类型 | 说明 |
|------|------|------|
| doc_id | str | UUID |
| filename | str | 原始文件名 |
| file_hash | str | sha256，用于去重提示 |
| file_type | str | docx/xlsx/pptx |
| status | DocStatus | 状态机 |
| error_msg | str \| None | 失败原因 |
| created_at | datetime | |

**IRElement（中间表示——解析器的统一输出）**

| 字段 | 类型 | 说明 |
|------|------|------|
| kind | enum | `HEADING / PARAGRAPH / TABLE / SHEET_ROWS` |
| level | int | 标题层级（HEADING 用，1~9；其他为 0）|
| text | str | 文本内容；TABLE 为 Markdown 表格串 |
| meta | dict | 来源信息：页码/sheet名/段落号等 |

> 解析器输出 `list[IRElement]`（按文档顺序）。这是全系统最重要的"防腐层"接口。

**Chunk**

| 字段 | 类型 | 说明 |
|------|------|------|
| chunk_id | str | `{doc_id前8位}-{序号}` |
| doc_id | str | 外键 |
| text | str | 块内容（送 embedding 与生成的文本）|
| section_path | str | 章节路径，如 `"3 帧格式>3.1 RTU模式"` |
| element_kinds | list[str] | 块内含哪些元素类型（含 TABLE 时检索展示有用）|
| token_count | int | 估算 token 数 |
| seq | int | 文档内顺序号（用于"取相邻块"扩展上下文）|

**RetrievalHit**

| 字段 | 类型 | 说明 |
|------|------|------|
| chunk | Chunk | |
| source | str | `vector / bm25 / pageindex` |
| rank | int | 在该路中的名次 |
| score | float \| None | 原始分（仅参考，不跨路比较）|

**AgentTrace** — 一次问答的全过程记录（list of 步骤），每步含：`step_type`（rewrite/retrieve/navigate/judge/answer）、输入摘要、输出摘要、耗时、token 消耗。最终随 API 响应可选返回，是你调试的生命线。

### 3.3 `core/errors.py`

自定义异常树（练习异常设计）：

```
AppError(Exception)
 ├── ProviderError        # 模型调用失败（含重试耗尽）
 ├── ParseError           # 文档解析失败
 ├── NotFoundError        # 文档/会话不存在
 └── LLMOutputError       # LLM 输出无法解析为预期 JSON
```

API 层统一捕获 AppError 转 HTTP 错误码（见 04 章错误码表）。

## 4. providers — 模型适配层

### 4.1 `providers/base.py`

```python
class ChatProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[dict], *, temperature: float = 0.2,
             json_mode: bool = False) -> str:
        """messages 为 OpenAI 风格 [{role, content}, ...]，返回助手文本。
        json_mode=True 时尽力让模型输出 JSON（openai兼容用 response_format，
        ollama 用 format=json；不支持时靠 prompt 约束）。"""

class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """批量向量化。实现内部要处理分批（如每批≤16条）。"""
```

设计说明：
- 学习阶段先用**同步**接口（httpx 同步客户端），跑通后阶段 7 可改 async——一开始就上 async 会让调试痛苦加倍。
- 两个实现类各自处理：超时（建议 60s）、重试（指数退避，最多 3 次——**自己写个 `@retry` 装饰器**，绝佳练习）、错误归一（HTTP 4xx/5xx → ProviderError，带上响应体便于排查）。
- `factory.py`：`def create_chat_provider(settings) -> ChatProvider`，按配置返回实例。API 层启动时创建一次，全局复用。

### 4.2 两个实现的差异点（写实现前先调通裸 HTTP）

| | OpenAI 兼容 | Ollama |
|--|------------|--------|
| chat 端点 | `POST {base}/chat/completions` | `POST {base}/api/chat` |
| embedding | `POST {base}/embeddings` | `POST {base}/api/embed` |
| 认证 | `Authorization: Bearer` | 无 |
| JSON 模式 | `response_format={"type":"json_object"}` | `format: "json"` |
| 响应取文本 | `choices[0].message.content` | `message.content` |

> 建议先在 `scripts/check_provider.py` 里用 httpx 把两家的裸接口各调通一次，看清原始 JSON，再回头写适配类。

## 5. storage — 持久化

### 5.1 `storage/database.py`

```python
def get_connection() -> sqlite3.Connection:
    """返回连接。开启 foreign_keys，row_factory 设为 sqlite3.Row。"""

def init_db() -> None:
    """执行建表 DDL（见 04 章 Schema），幂等（IF NOT EXISTS）。"""
```

- 用**上下文管理器**管理连接/事务（`with closing(get_connection()) as conn, conn:`）——理解 commit/rollback 时机。
- FastAPI 多线程访问 SQLite：每次请求新建连接即可（SQLite 足够快），不要全局共享一个连接。

### 5.2 `storage/doc_repo.py`（chat_repo 同理）

```python
def insert_document(doc: Document) -> None: ...
def update_status(doc_id: str, status: DocStatus, error_msg: str | None = None) -> None: ...
def get_document(doc_id: str) -> Document | None: ...
def list_documents() -> list[Document]: ...
def find_by_hash(file_hash: str) -> Document | None: ...
def insert_chunks(chunks: list[Chunk]) -> None:        # executemany 批量插入
def get_chunks_by_ids(chunk_ids: list[str]) -> list[Chunk]: ...
def get_adjacent_chunks(doc_id: str, seq: int, window: int = 1) -> list[Chunk]: ...
def delete_document_cascade(doc_id: str) -> None:
    """删除文档及其 chunks、向量、树文件、原始文件。注意删除顺序与失败处理。"""
```

> Repository 模式：SQL 只出现在 repo 文件里，业务层只见函数与模型对象。

### 5.3 `storage/files.py`

```python
def save_upload(doc_id: str, filename: str, content: bytes) -> Path: ...
def compute_hash(content: bytes) -> str: ...
def save_tree(doc_id: str, tree: dict) -> Path: ...
def load_tree(doc_id: str) -> dict: ...
```

全部用 `pathlib.Path`，注意文件名清洗（防路径穿越：只取 basename，过滤 `..`）。

## 6. ingestion — 入库流水线

### 6.1 `parsers/base.py`

```python
class BaseParser(ABC):
    suffixes: ClassVar[set[str]]      # 如 {".docx"}

    @abstractmethod
    def parse(self, path: Path) -> list[IRElement]:
        """文件 → 中间表示。解析失败抛 ParseError。"""

def get_parser(suffix: str) -> BaseParser:
    """注册表模式：根据后缀返回解析器实例，不认识的后缀抛 ParseError。"""
```

各格式解析要点：

- **docx**：遍历 `document.body` 的块级元素**保持顺序**（注意：python-docx 的 `paragraphs` 和 `tables` 是分开的两个列表，按文档顺序混合遍历需要走底层 element 迭代——这是该库著名的坑，先搜 "python-docx iterate paragraphs and tables in order"）。Heading 样式 → `HEADING` + level；表格 → 逐行取 cell 文本拼 Markdown。
- **xlsx**：每个 sheet 视为一个 `HEADING(level=1, text=sheet名)`；数据区按行读取。寄存器表这类大表**按行分组**输出多个 `SHEET_ROWS` 元素（如每 30 行一组，**每组都重复表头**——否则切块后没有表头的行毫无意义）。用 `openpyxl` 的 `read_only=True` 模式。
- **pptx**：每页标题 → `HEADING(level=1)`；正文文本框 → `PARAGRAPH`；页内表格 → `TABLE`。meta 里记页码。

### 6.2 `chunker.py`

```python
def chunk_elements(elements: list[IRElement], doc_id: str,
                   max_tokens: int = 512) -> list[Chunk]:
    """结构感知切块。"""

def estimate_tokens(text: str) -> int:
    """粗估即可：中文字符数 + 英文单词数×1.3。不要为此引入 tiktoken。"""
```

切块算法（自己实现，这是核心练习之一）：

1. 顺序扫描 elements，维护一个"当前章节路径栈"：遇到 HEADING 按 level 压栈/弹栈（level 2 出现时，弹掉栈里 level≥2 的旧标题）。
2. 同一小节内的 PARAGRAPH 依次累积进当前块；块满 `max_tokens` 则封块，新块**重复携带章节路径**。
3. **TABLE / SHEET_ROWS 元素永不与其他内容混块、永不从中间切开**；超长表格在解析阶段已按行分组解决。
4. 遇到新 HEADING 强制封块（章节边界即块边界）。
5. 每个 chunk 的 `text` 开头拼上章节路径行（如 `【3 帧格式 > 3.1 RTU模式】`）——让 embedding 和 LLM 都能看到上下文。

边界情况自测清单：空文档、只有一个超长段落、表格在文档开头（无标题）、标题层级跳跃（1 级直接到 3 级）。

### 6.3 `tree_builder.py`

```python
def build_skeleton(elements: list[IRElement], chunks: list[Chunk]) -> dict:
    """按 HEADING 层级构建树骨架（不调LLM），把 chunk_ids 挂到对应节点。
    与 chunker 相同的栈算法，但产出是嵌套 dict。"""

def fill_summaries(tree: dict, provider: ChatProvider) -> dict:
    """后序遍历（先子后父）为每个节点生成 summary：
    叶节点 → 用其 chunks 文本生成；父节点 → 用子节点 summaries 汇总生成。
    递归练习。注意节点多时的进度日志与失败重试。"""
```

### 6.4 `pipeline.py`

```python
def ingest_document(doc_id: str) -> None:
    """入库总编排（在 BackgroundTask 中运行）：
    读文件 → parse → chunk → 存chunks → embed入Chroma → 建BM25 →
    build_tree → 落盘，每步前后更新文档状态；任何异常 → 状态FAILED+错误信息。
    注意：后台任务里的异常不会自动出现在任何地方，必须自己 try/except + 日志。"""
```

## 7. retrieval — 检索层

```python
# vector_store.py
class VectorStore:
    def __init__(self, persist_dir: Path, embedder: EmbeddingProvider): ...
    def add_chunks(self, chunks: list[Chunk]) -> None: ...
    def search(self, query: str, top_k: int,
               doc_ids: list[str] | None = None) -> list[RetrievalHit]:
        """doc_ids 用 Chroma 的 metadata 过滤实现（用户可限定问某几个文档）。"""
    def delete_by_doc(self, doc_id: str) -> None: ...

# bm25.py
class BM25Index:
    def build(self, chunks: list[Chunk]) -> None: ...
    def search(self, query: str, top_k: int,
               doc_ids: list[str] | None = None) -> list[RetrievalHit]: ...
    def save(self, path: Path) -> None: ...
    @classmethod
    def load(cls, path: Path) -> "BM25Index": ...

def tokenize(text: str) -> list[str]:
    """jieba 中文分词 + 英文/十六进制 token 保护 + 小写化。单独函数，单独测试。"""

# tree_search.py
def navigate_tree(tree: dict, query: str, provider: ChatProvider,
                  max_depth: int = 3, max_select: int = 3) -> list[RetrievalHit]:
    """逐层下钻（见02章2.3）。LLM输出解析失败时记日志并返回已收集结果。"""

# fusion.py
def rrf_fuse(hit_lists: dict[str, list[RetrievalHit]], k: int = 60,
             weights: dict[str, float] | None = None,
             top_n: int = 6) -> list[RetrievalHit]: ...
```

## 8. agent — 问答引擎

```python
# prompts.py — 所有模板集中此处（常量字符串 + .format/f-string 填充）
#   集中管理的理由：调 prompt 时不用满项目找；将来可版本化对比效果。

# query_rewriter.py
def rewrite(question: str, history_summary: str,
            provider: ChatProvider) -> list[str]:
    """返回1~3个子查询。LLM输出解析失败 → 降级返回 [question] 原文。"""

# orchestrator.py
class AgentOrchestrator:
    def __init__(self, vector_store, bm25, trees, chat_provider, settings): ...

    def run(self, question: str, doc_ids: list[str] | None,
            history: list[dict]) -> AgentResult:
        """核心循环（伪代码，自己翻译成 Python）：

        queries = rewrite(question)
        evidence = {}                          # chunk_id -> RetrievalHit
        for round in 1..MAX_ROUNDS:
            for q in queries:
                三路检索(q) → rrf融合 → 并入 evidence（去重）
            judgment = 充分性判断(question, evidence)
            if judgment.sufficient: break
            queries = judgment.next_queries    # 空则 break
        answer = answerer.generate(question, evidence, history)
        return AgentResult(answer, citations, trace)
        """

# answerer.py
def generate(question: str, hits: list[RetrievalHit],
             history: list[dict], provider: ChatProvider) -> Answer:
    """组装最终 prompt（见02章4.4），调用LLM，
    解析出引用编号映射回 chunk 出处。Answer 含 text + list[Citation]。"""
```

AgentResult / Citation 字段：

| Citation 字段 | 说明 |
|------|------|
| index | 引用编号 [1] |
| doc_name / section_path | 出处展示 |
| snippet | 原文片段（截断 200 字）|

## 9. api — 接口层

`schemas.py` 定义请求/响应 Pydantic 模型（与 04 章 JSON 示例一一对应）。路由函数保持薄：参数校验 → 调业务函数 → 包装响应，不写业务逻辑。

启动生命周期（`main.py` 的 lifespan）要做的事：`init_db()`、创建 providers、加载 VectorStore、加载所有 ready 文档的 BM25 索引与树到内存（dict[doc_id, tree]）。
