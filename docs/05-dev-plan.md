# 05 — 分阶段开发计划

> 这是开发主线。规则：**每阶段验收通过才进入下一阶段**；每阶段结束 git commit 一次（建议本目录 `git init`）。
> 标 ⚠ 的是预计最容易卡住的点，卡住超过 1 小时先看 06 章对应语法点，再缩小问题范围做最小复现。

---

## 阶段 0：环境与项目骨架（预计 0.5 天）

**目标**：跑起来一个空壳 FastAPI，配置能从 .env 读取。

任务：
- [ ] 创建 venv，安装：`fastapi uvicorn pydantic-settings httpx python-docx openpyxl python-pptx chromadb jieba python-multipart`
- [ ] 按 03 章目录结构建空目录与空 `__init__.py`
- [ ] 写 `core/config.py`（Settings 类）+ `.env.example`
- [ ] 写 `core/logging.py`（logging.basicConfig，格式带时间/模块名/级别）
- [ ] 写 `api/main.py`：空 app + `/api/v1/health` 返回 `{"status":"ok"}`
- [ ] `uvicorn src.api.main:app --reload` 启动成功

⚠ 包导入路径：决定好用 `src` 布局后，统一以项目根为工作目录、`src.xxx` 绝对导入；遇到 `ModuleNotFoundError` 先理解 sys.path 而不是乱加 `sys.path.append`。

**验收**：浏览器开 `http://127.0.0.1:8000/docs` 看到 Swagger；health 返回 ok；改 .env 里任一配置，代码里能读到新值。

---

## 阶段 1：模型适配层（预计 1 天）

**目标**：一套接口，两个后端（OpenAI 兼容 / Ollama），可配置切换。

任务：
- [ ] `scripts/check_provider.py`：先用 httpx **裸调**两家的 chat 和 embedding 接口，打印原始响应 JSON（理解协议差异，见 03 章 4.2 对照表）
- [ ] `providers/base.py`：两个 ABC
- [ ] `core/errors.py`：异常树
- [ ] 写一个重试装饰器（指数退避：1s/2s/4s，重试 3 次后抛 ProviderError）
- [ ] `openai_compat.py` / `ollama.py` 两个实现 + `factory.py`
- [ ] 把 check_provider.py 改为走适配层：切换 .env 的 `LLM_PROVIDER` 验证两边都通

⚠ json_mode 的差异处理；⚠ 装饰器要保留原函数签名（`functools.wraps`）。

**验收**：脚本在两种 provider 配置下都能：① 对话返回文本；② embedding 返回正确维度的浮点列表；③ 故意填错 API key，3 次重试后抛出含状态码的 ProviderError 而非裸 traceback。

---

## 阶段 2：文档上传与持久化（预计 1 天）

**目标**：文档能上传、落盘、入库（仅元数据），能列表/查询/删除。

任务：
- [ ] `storage/database.py`：建表 DDL（04 章 Schema 的 documents 表即可，其余表后补）
- [ ] `storage/files.py`：落盘 + sha256
- [ ] `storage/doc_repo.py`：insert / get / list / find_by_hash / update_status
- [ ] `api/schemas.py` + `routes_documents.py`：POST/GET/DELETE /documents（此阶段 status 停在 uploaded）
- [ ] 后缀与大小校验、文件名清洗、重复哈希提示

⚠ FastAPI 的 `UploadFile` 读取是 async 的（`await file.read()`）——路由函数声明为 `async def`，但内部调用你的同步 storage 函数没问题。

**验收**：Swagger 里上传一个 docx → 列表可见、`data/raw/{doc_id}/` 有文件、SQLite 有记录（用 DB 浏览工具或 sqlite3 命令行确认）；重复上传同一文件返回 duplicate_of；DELETE 后文件与记录都消失；上传 .exe 得到 400。

---

## 阶段 3：解析与切块（预计 2 天，难度高）

**目标**：三种格式 → IR → 结构感知 chunks，并持久化。

任务：
- [ ] `core/models.py`：IRElement / Chunk / DocStatus
- [ ] `parsers/base.py` + 注册表 `get_parser`
- [ ] `docx_parser.py`（⚠ 段落与表格按文档顺序混合遍历是 python-docx 的坑，见 03 章 6.1）
- [ ] `xlsx_parser.py`（⚠ 大表按行分组且每组重复表头）
- [ ] `pptx_parser.py`
- [ ] `chunker.py`：章节路径栈算法 + 表格不拆 + token 粗估
- [ ] chunks 表 DDL + `insert_chunks`（executemany）
- [ ] `pipeline.py` 第一版：parse → chunk → 存库，状态机推进（uploaded→parsing→chunking→ready）
- [ ] 接入上传路由的 BackgroundTasks（⚠ 后台异常必须自己捕获记日志并置 failed）
- [ ] `tests/test_chunker.py`：用手工构造的 IRElement 列表测边界（空文档/超长段落/无标题表格/层级跳跃）

**验收**：上传真实协议 docx（找一份 Modbus/MQTT 中文规范，或自己用 Word 造一份带多级标题+表格的测试文档）→ 状态推进到 ready；写个临时脚本打印所有 chunk 的 section_path 和前 50 字，**人工检查**：表格完整、章节路径正确、无空块；xlsx/pptx 同样跑通；chunker 单测全绿。

---

## 阶段 4：传统 RAG 链路 ★ MVP 里程碑（预计 2 天）

**目标**：完成"提问 → 向量+BM25 检索 → 生成带引用回答"的最小闭环。

任务：
- [ ] `retrieval/vector_store.py`：Chroma 封装（add/search/delete，metadata 带 doc_id）
- [ ] pipeline 加入 embedding 步骤（⚠ 分批调用；状态 chunking→embedding→ready）
- [ ] `retrieval/bm25.py`：tokenize（jieba + 术语保护）→ 建索引 → 打分 → save/load（建议手写，写完用 rank-bm25 对拍前 10 名重合度）
- [ ] `tests/test_bm25.py`：构造 5 个小 chunk，验证罕见词得分 > 常见词
- [ ] `agent/prompts.py` + `answerer.py`：第一版生成（暂不做改写与循环：问题直接当查询，两路检索 → 简单合并去重 → 生成）
- [ ] `scripts/ask_cli.py`：命令行问答（打印答案 + 引用 + 两路各自召回了什么——观察两路差异，建立手感）
- [ ] chat 相关表 DDL + `chat_repo.py` + `POST /chat` 路由（最简版）
- [ ] 建立 `eval/questions.jsonl`（≥20 题，覆盖 02 章 5 节的五种类型）

**验收**：CLI 与 API 都能问答；细节型问题（"X 功能码是多少"）答案正确且引用指向正确章节；问文档里没有的内容时回答"未找到"而不是编造；对比实验：只用向量 vs 只用 BM25 vs 两路合并，在评测集上肉眼比较——**记下结论**，这是你的第一份调参笔记。

> 🎉 到这里你已经拥有一个完整可用的 RAG 问答系统。之后的一切都是增强，随时可回退到这条基线。

---

## 阶段 5：PageIndex 引擎（预计 2 天）

**目标**：为文档建树，实现树上导航检索。

任务：
- [ ] `tree_builder.py`：`build_skeleton`（栈算法产嵌套 dict，挂 chunk_ids）
- [ ] `fill_summaries`：后序遍历生成摘要（⚠ 递归；⚠ 大节点 map-reduce 两级摘要；打进度日志）
- [ ] pipeline 加入建树步骤（状态加 indexing），树落盘 `data/pageindex/`
- [ ] `retrieval/tree_search.py`：逐层导航（⚠ LLM 输出 JSON 的健壮解析：提取-重试-降级三板斧，这段代码值得精心打磨，后面到处复用）
- [ ] `scripts/ask_cli.py` 加 `--engine pageindex` 选项单独测试这一路
- [ ] 控制台打印导航轨迹（每层选了哪些节点、理由）

**验收**：打开树 JSON 人工检查：层级与原文档目录一致、摘要准确概括各章内容；全局型问题（"这份文档主要定义了哪些内容？"）PageIndex 路能召回正确章节而向量路不能（亲眼确认这个差异，理解 PageIndex 存在的意义）；导航轨迹可读、每层 LLM 调用 ≤ max_select 限制。

---

## 阶段 6：融合与 Agent 循环（预计 2 天）

**目标**：三路融合 + 查询改写 + 充分性判断循环，成为真正的 Agent。

任务：
- [ ] `retrieval/fusion.py`：RRF（含权重参数）+ `tests/test_fusion.py`（手工构造三路结果验证排序符合公式）
- [ ] `agent/query_rewriter.py`（解析失败降级返回原问题）
- [ ] `agent/orchestrator.py`：核心循环（见 03 章 8 伪代码）；AgentTrace 全程记录
- [ ] 充分性判断 prompt（⚠ 防"永远说不够"：上限 3 轮硬约束 + prompt 倾向性引导）
- [ ] `/chat` 切换到 orchestrator；`include_trace` 参数生效
- [ ] 多轮对话：messages 表存取，近 3 轮 Q/A 进改写与生成的上下文

**验收**：跨章节比较型问题（评测集中准备的）能在第 2 轮检索后答对——查看 trace 确认确实发生了"判断不充分 → 生成新查询 → 再检索"；简单问题 1 轮就结束（不浪费）；连续追问"那写多个寄存器呢？"能正确理解指代；全评测集过一遍，与阶段 4 基线对比记录提升。

---

## 阶段 7：完善与收尾（预计 2 天，按兴趣选做）

任务（按优先级）：
- [ ] `static/index.html` 极简前端（04 章 4 节布局）
- [ ] 全局 exception_handler：错误码表落地
- [ ] `scripts/rebuild_index.py`：从 raw/ 重建任意文档的全部派生数据
- [ ] 启动加载优化：lifespan 中加载所有 ready 文档的 BM25 与树
- [ ] 选做：SSE 流式回答（最终生成那一步改流式，前端逐字渲染）
- [ ] 选做：LLM-as-judge 自动评测脚本（把评测集的"期望要点"和实际回答交给 LLM 打分）
- [ ] 选做：providers 改 async 版（体验 sync→async 迁移）

**验收**：浏览器完成"上传→等 ready→提问→看引用→删除"全流程；杀掉进程重启后，已入库文档无需重新处理即可问答（持久化完整性）；README 补一份"如何运行"说明。

---

## 总时间预估

| 阶段 | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 |
|------|---|---|---|---|---|---|---|---|
| 天数 | 0.5 | 1 | 1 | 2 | 2 | 2 | 2 | 2 |

合计约 12.5 个有效开发日。新手实际耗时通常 ×1.5~2，属正常，不要赶进度跳过验收。
