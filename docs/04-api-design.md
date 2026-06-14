# 04 — API 设计与存储设计

## 1. REST API 设计

Base URL：`http://127.0.0.1:8000/api/v1`。所有响应为 JSON，UTF-8。

### 1.1 端点总表

| 方法 | 路径 | 功能 | 备注 |
|------|------|------|------|
| POST | `/documents` | 上传文档 | multipart/form-data；立即返回，后台入库 |
| GET | `/documents` | 文档列表 | 含状态 |
| GET | `/documents/{doc_id}` | 文档详情+状态 | 前端轮询用 |
| DELETE | `/documents/{doc_id}` | 删除文档及全部派生数据 | 级联删除 |
| POST | `/chat` | 提问 | 可带 conversation_id 续聊 |
| GET | `/conversations/{conv_id}` | 取会话历史 | |
| GET | `/health` | 健康检查 | 顺带检查模型连通性（可选 `?deep=true`）|

### 1.2 上传文档

```
POST /documents          Content-Type: multipart/form-data
字段：file（二进制）
```

成功响应 `201`：

```json
{
  "doc_id": "5f3a…",
  "filename": "modbus_v1.1b.docx",
  "status": "uploaded",
  "duplicate_of": null
}
```

- 校验：后缀 ∈ {docx, xlsx, pptx}；大小 ≤ 30MB（413 拒绝）。
- 同哈希文件已存在 → 仍创建新记录但 `duplicate_of` 给出已有 doc_id，由前端提示用户。
- 入库通过 FastAPI `BackgroundTasks` 触发 `ingest_document(doc_id)`。

### 1.3 文档状态查询

```
GET /documents/5f3a…
```

```json
{
  "doc_id": "5f3a…",
  "filename": "modbus_v1.1b.docx",
  "file_type": "docx",
  "status": "embedding",
  "error_msg": null,
  "chunk_count": 87,
  "created_at": "2026-06-10T09:30:00+08:00"
}
```

状态机（前端按此渲染进度）：

```
uploaded → parsing → chunking → embedding → indexing → ready
                └────────────── 任一步失败 ──────────────► failed(error_msg)
```

### 1.4 提问

```
POST /chat
```

```json
{
  "question": "异常响应的功能码怎么变化？",
  "conversation_id": null,
  "doc_ids": ["5f3a…"],
  "include_trace": false
}
```

字段说明：`conversation_id` 为空则新建会话；`doc_ids` 为空数组/缺省 = 检索全部 ready 文档；`include_trace=true` 时返回 Agent 中间过程（调试用）。

成功响应 `200`：

```json
{
  "conversation_id": "c-9d2e…",
  "answer": "异常响应时，从机将请求功能码的最高位置 1（即原功能码 + 0x80）…[1]，并在数据域返回 1 字节异常码 [2]。",
  "citations": [
    {
      "index": 1,
      "doc_id": "5f3a…",
      "doc_name": "modbus_v1.1b.docx",
      "section_path": "7 异常响应 > 7.1 异常功能码",
      "snippet": "当从机无法执行请求时，响应帧的功能码为请求功能码与 0x80 的或…"
    }
  ],
  "trace": null,
  "usage": {"rounds": 1, "llm_calls": 4, "elapsed_ms": 5210}
}
```

- 学习阶段先做**非流式**；阶段 7 可选升级 SSE 流式（`text/event-stream`）。
- 没有任何 ready 文档时返回 409，提示先上传。

### 1.5 错误响应统一格式

```json
{ "error": { "code": "DOC_NOT_FOUND", "message": "文档不存在: 5f3a…" } }
```

| HTTP | code | 触发场景 |
|------|------|----------|
| 400 | `INVALID_FILE_TYPE` | 不支持的后缀 |
| 413 | `FILE_TOO_LARGE` | 超过大小限制 |
| 404 | `DOC_NOT_FOUND` / `CONV_NOT_FOUND` | |
| 409 | `NO_READY_DOCS` | 无可检索文档 |
| 409 | `DOC_NOT_READY` | 指定的 doc 还在入库中 |
| 502 | `PROVIDER_ERROR` | 模型调用失败（重试耗尽）|
| 500 | `INTERNAL` | 其他未捕获异常 |

实现方式：FastAPI 的 `exception_handler` 把 `core/errors.py` 的异常树统一映射到上表——一处注册，处处生效。

## 2. SQLite Schema

> 下面是 DDL 的字段说明表，自己写 `CREATE TABLE` 语句（练 SQL）。类型用 SQLite 的 TEXT/INTEGER/REAL；时间统一存 ISO8601 字符串。

### documents

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| doc_id | TEXT | PRIMARY KEY | UUID |
| filename | TEXT | NOT NULL | |
| file_hash | TEXT | NOT NULL, 建索引 | sha256 |
| file_type | TEXT | NOT NULL | docx/xlsx/pptx |
| status | TEXT | NOT NULL | 状态机枚举值 |
| error_msg | TEXT | | |
| chunk_count | INTEGER | DEFAULT 0 | 入库完成后回填 |
| embed_model | TEXT | | 记录所用 embedding 模型名（换模型需重建的依据）|
| created_at | TEXT | NOT NULL | |

### chunks

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| chunk_id | TEXT | PRIMARY KEY | |
| doc_id | TEXT | NOT NULL, FK→documents, 建索引 | ON DELETE CASCADE |
| seq | INTEGER | NOT NULL | 文档内顺序 |
| text | TEXT | NOT NULL | |
| section_path | TEXT | | |
| element_kinds | TEXT | | JSON 数组字符串 |
| token_count | INTEGER | | |

### conversations

| 列 | 类型 | 说明 |
|----|------|------|
| conv_id | TEXT PK | |
| title | TEXT | 取首个问题前 30 字 |
| created_at | TEXT | |

### messages

| 列 | 类型 | 说明 |
|----|------|------|
| msg_id | INTEGER PK AUTOINCREMENT | |
| conv_id | TEXT FK→conversations | 建索引 |
| role | TEXT | user / assistant |
| content | TEXT | |
| citations | TEXT | JSON 串（assistant 消息）|
| created_at | TEXT | |

> 向量不进 SQLite——ChromaDB 自己管理（chunk_id 作为 Chroma 的 id，doc_id 进 metadata 供过滤）。BM25 索引、PageIndex 树走文件系统。**chunk_id 是贯穿三个存储的全局关联键。**

## 3. 文件系统布局与一致性

```
data/
├── app.db
├── raw/{doc_id}/{原始文件名}          # 永远保留，重建索引的源头
├── pageindex/{doc_id}.json
├── bm25/{doc_id}.json                # 每文档一个索引文件，启动时全量加载合并
└── chroma/                           # ChromaDB 托管，不要手动碰
```

一致性原则：
- **SQLite 是事实之源**：一个文档"存在与否、是否可用"只看 documents 表。其他存储找不到对应数据时，按降级处理并记日志（而不是崩溃）。
- 删除顺序：先删派生数据（Chroma 向量 → bm25 文件 → 树文件 → raw 目录），最后删 SQLite 行。这样中途失败时文档仍显示存在，可重试删除；反过来则会留下"孤儿数据"。
- 提供 `scripts/rebuild_index.py`（阶段 7）：从 raw/ 出发对任意文档重跑入库——一切派生数据都可重建，这是兜底保障。

## 4. 极简前端（static/index.html，单文件）

学习重点不在前端，一页搞定，原生 JS + fetch 即可：

```
┌────────────────────────────────────────────┐
│  [选择文件] [上传]                            │
│  ─ 文档列表 ─────────────────────────────    │
│  ☑ modbus_v1.1b.docx   ready    [删除]      │
│  ☐ mqtt_spec.docx      embedding…(轮询中)    │
│  ─ 对话区 ──────────────────────────────     │
│  Q: 异常响应功能码怎么变化？                    │
│  A: ……[1][2]                                │
│     ▸ 引用[1] modbus_v1.1b > 7.1 异常功能码    │
│  [输入框…………………………] [发送]                  │
└────────────────────────────────────────────┘
```

要点：上传后每 2s 轮询状态直到 ready/failed；勾选文档 = chat 请求的 doc_ids；引用可展开看 snippet。FastAPI 用 `StaticFiles` 挂载。
