# 06 — Python 语法学习点对照表

> 按模块组织。每条 = **在哪用 / 学什么 / 易踩的坑**。写到对应模块时回来对照。
> 学习方法：先读官方文档对应章节 → 自己写 → 跑通后问 AI"我这样写地道吗"，而不是直接要代码。

## core/config.py — 配置

| 学什么 | 在哪用 | 坑 |
|--------|--------|-----|
| `pydantic-settings` 的 `BaseSettings` | Settings 类 | v2 写法是 `model_config = SettingsConfigDict(env_file=".env")`，网上大量 v1 旧教程（`class Config:`）已过时 |
| 类型注解驱动校验 | 每个配置字段 | `Path` 类型字段会自动从字符串转换；给默认值的字段要放在无默认值字段后面 |
| 模块级单例 | `settings = Settings()` 全局一份 | 测试时想换配置怎么办？了解 `lru_cache` 包装 getter 的模式 |

## core/models.py — 数据模型

| 学什么 | 在哪用 | 坑 |
|--------|--------|-----|
| `@dataclass` | Chunk / IRElement 等 | **可变默认值**必须 `field(default_factory=list)`，写 `= []` 是经典大坑（所有实例共享同一个列表）|
| `Enum` / `StrEnum` | DocStatus | 存 SQLite 时要 `.value`，读出来要 `DocStatus(row["status"])`；3.11+ 的 `StrEnum` 可省事 |
| `typing`：`list[str]`、`X \| None` | 所有签名 | 3.10+ 可直接 `str \| None`，不需要 `Optional`/`List` 旧写法 |
| dataclass vs Pydantic 的取舍 | models vs api/schemas | 内部模型用 dataclass（轻），API 边界用 Pydantic（要校验）——体会"边界校验、内部信任"的分层思想 |

## core/errors.py — 异常

| 学什么 | 在哪用 | 坑 |
|--------|--------|-----|
| 自定义异常继承树 | AppError 体系 | 异常带上下文：`raise ProviderError(f"...") from e` 的 `from e` 保留原始链，调试时天差地别 |
| EAFP 风格 | 全项目 | Python 惯用"先做再捕获"而非"先检查再做"；但**捕获要具体**，裸 `except:` 和 `except Exception` 滥用是新手通病 |

## providers/ — 模型适配层

| 学什么 | 在哪用 | 坑 |
|--------|--------|-----|
| `abc.ABC` + `@abstractmethod` | base.py | 子类漏实现抽象方法时，**实例化时**才报错而非定义时 |
| 装饰器（带参数的） | 重试装饰器 | 三层嵌套函数（参数→装饰器→wrapper）画图理解；必须 `@functools.wraps(fn)` 否则函数名/docstring 丢失 |
| `httpx` 同步客户端 | 两个实现 | `Client` 要复用（连接池），不要每次请求新建；`timeout` 必须显式设置，默认 5s 对 LLM 太短 |
| 指数退避 | 重试逻辑 | `time.sleep(2 ** attempt)`；只对 5xx/超时重试，4xx（如 key 错误）重试毫无意义 |
| `ClassVar` | parsers 的 suffixes 也用到 | 类变量 vs 实例变量的区别——dataclass 里不加 ClassVar 的类级赋值会被当成默认值 |

## storage/ — 持久化

| 学什么 | 在哪用 | 坑 |
|--------|--------|-----|
| `sqlite3` DB-API | database.py / repo | **永远用 `?` 占位符**，f-string 拼 SQL = SQL 注入 + 引号灾难 |
| 上下文管理器 | 连接与事务 | `with conn:` 只管事务（自动 commit/rollback），**不关闭连接**——这是 sqlite3 最反直觉的设计；关闭用 `contextlib.closing` |
| `row_factory = sqlite3.Row` | 查询 | 之后可 `row["filename"]` 按列名取值；转 dataclass 写一个 `_row_to_doc(row)` 辅助函数 |
| `executemany` | insert_chunks | 比循环 execute 快一个数量级 |
| `pathlib.Path` | files.py | 用 `/` 运算符拼路径；`mkdir(parents=True, exist_ok=True)`；Windows 路径分隔符问题 pathlib 全帮你处理 |
| `hashlib` | 文件哈希 | `sha256(content).hexdigest()`；大文件应分块 update（本项目 30MB 上限，整读也可，但要知道为什么）|

## ingestion/ — 解析与切块

| 学什么 | 在哪用 | 坑 |
|--------|--------|-----|
| 注册表模式 | get_parser | dict[后缀→类] 比 if/elif 链优雅且开闭；可进阶玩 `__init_subclass__` 自动注册 |
| 生成器 `yield` | 解析器逐元素产出 | 解析器可以 `yield IRElement(...)` 而非攒 list——理解惰性求值；但注意生成器**只能消费一次** |
| 栈（用 list 模拟） | chunker 的章节路径 | `append`/`pop`；想清楚"遇到 level=n 的标题时，弹出栈中所有 level≥n 的项"的循环条件 |
| 字符串处理 | token 估算 / 表格转 Markdown | `str.join` 拼接（循环 `+=` 是 O(n²)）；中文字符判断可用 `'一' <= ch <= '鿿'` |
| 递归 | tree_builder 后序遍历 | 先写清楚递归三要素：终止条件（叶节点）、子问题（先处理 children）、合并（用子摘要生成父摘要）；Python 默认递归深度 1000，文档树不会触顶 |
| `enumerate` / `zip` | 各处遍历 | 不要 `range(len(x))` 风格 |

## retrieval/ — 检索

| 学什么 | 在哪用 | 坑 |
|--------|--------|-----|
| `collections.Counter` | BM25 词频/文档频率 | `Counter(tokens)` 一行得词频；两个 Counter 可直接相加 |
| `collections.defaultdict` | 倒排索引 | `defaultdict(list)` 免去"先判断 key 存在"的样板 |
| `math.log` | IDF 计算 | 注意 BM25 的 IDF 公式里 +0.5 平滑项，照公式翻译，写单测验证 |
| `sorted` + `key=lambda` | 各路排序 | `reverse=True` 降分序；学 `operator.itemgetter` 替代 lambda |
| 字典推导/集合去重 | fusion.py | RRF 累加分数用 `dict.get(k, 0)` 或 defaultdict(float)；去重保序可用 dict 的插入有序特性 |
| `json` 模块 | 树/索引落盘 | `ensure_ascii=False` 否则中文全变 `\uXXXX`；`indent=2` 便于人工检查 |
| 正则 `re` | LLM 输出提取 JSON | 从混杂文本中抓 `\{.*\}` 要用 `re.DOTALL`；贪婪 vs 非贪婪匹配的区别在这里会真实咬你 |

## agent/ — 引擎

| 学什么 | 在哪用 | 坑 |
|--------|--------|-----|
| f-string / `str.format` / 模板拼装 | prompts.py | 多行模板用三引号 + `textwrap.dedent` 去缩进；prompt 里有花括号时 `.format` 要 `{{}}` 转义 |
| 防御式 JSON 解析 | 所有 LLM 结构化输出 | 三板斧：正则提取→`json.loads` try/except→失败重试一次→仍失败走降级。封装成一个通用函数 `parse_llm_json(text, fallback)` 复用 |
| while 循环 + 状态累积 | orchestrator | evidence 用 dict[chunk_id, Hit] 天然去重；想清楚循环的**所有**退出条件：充分/轮数上限/新查询为空/新一轮零新增 |
| `time.perf_counter` | trace 计时 | 比 `time.time` 适合测耗时 |
| 切片与字符串截断 | citation snippet | `text[:200]` 注意别把多字节字符截坏的问题在 Python3 不存在（str 是字符不是字节）——但要明白为什么 |

## api/ — FastAPI

| 学什么 | 在哪用 | 坑 |
|--------|--------|-----|
| `async def` 路由 vs 普通 `def` 路由 | 所有路由 | FastAPI 对 `def` 路由自动丢线程池——**同步业务代码用 `def` 路由反而不阻塞**；`async def` 里调用耗时同步函数才会卡死事件循环。新手最大暗坑 |
| `UploadFile` | 上传 | `await file.read()`；`file.filename` 不可信，要清洗 |
| `BackgroundTasks` | 入库 | 后台异常静默吞掉——任务函数最外层必须 try/except 写日志置 failed |
| Pydantic v2 模型 | schemas.py | `model_dump()` 不是 v1 的 `.dict()`；响应模型用 `response_model=` 参数声明 |
| `lifespan` | main.py | 取代旧的 `@app.on_event`；用 `asynccontextmanager`，yield 前是启动、后是关闭 |
| 依赖注入 `Depends` | 路由获取共享资源 | 把 orchestrator/providers 放 app.state，写个 getter 依赖——比全局变量可测试 |

## tests/ — 测试

| 学什么 | 在哪用 | 坑 |
|--------|--------|-----|
| `pytest` 基础 | test_chunker / test_bm25 / test_fusion | 函数名必须 `test_` 开头；`assert` 直接用，失败信息 pytest 自动展开 |
| 参数化 `@pytest.mark.parametrize` | 边界用例 | 一组输入/期望表驱动，免复制粘贴测试函数 |
| `tmp_path` fixture | 测落盘逻辑 | pytest 内置临时目录，自动清理 |
| 不依赖 LLM 的测试设计 | 全部单测 | chunker/bm25/fusion 都是纯函数逻辑，**这正是它们值得手写的原因**——LLM 相关逻辑用"假 provider"（返回固定文本的 stub 类）测流程 |

## 通用工程习惯

- **小步快跑**：每写 20~30 行就跑一次（脚本/REPL/测试），不要写完一个文件才第一次运行。
- **print 调试 → logging 调试 → 断点调试**：尽早学会 VS Code/PyCharm 断点，看变量比猜变量快十倍。
- **读报错从最后一行往上读**，定位到**自己代码**的最深一帧。
- 类型检查：装个 `pyright`/`mypy`（或 IDE 自带），让注解真正干活，红线即学习点。
- git：每阶段一 commit；commit message 写"做了什么+为什么"。
