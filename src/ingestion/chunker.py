from ..core.models import Chunk, IRElement, Kind


class Chunker:
    """把解析器输出的 IR 元素切成适合检索的 Chunk。

    设计思路分两步：
    1. 先按文档结构切：标题形成章节路径，表格/Excel 行组永远单独成块。
    2. 再按长度切：普通文本块超过 max_tokens 时继续拆，避免送入 embedding 的文本过长。

    注意：这里的 token 只是粗估，用于控制 chunk 大小，不追求和具体模型完全一致。
    """

    def __init__(self, max_tokens: int = 512):
        self.max_tokens = max_tokens

    def chunk_IRElements(self, elements: list[IRElement], doc_id: str) -> list[Chunk]:
        chunks: list[Chunk] = []
        section_stack: list[tuple[str, int]] = []     # (heading_text, level)
        block_stack: list[IRElement] = []
        token_count = 0
        seq = 0

        def _estimate_tokens(text: str) -> int:
            """粗略估算 token 数。

            中文大约按 0.67 token/字估算，非中文字符按 0.25 token/字符估算。
            这里的目标是稳定控制 chunk 大小，而不是精确复刻某个模型 tokenizer。
            """
            cn = sum(1 for c in text if '一' <= c <= '鿿')
            total = len(text)
            return max(1, int(cn * 0.67 + (total - cn) * 0.25 + 0.5))

        def flush():
            nonlocal seq, token_count
            if block_stack:
                chunks.append(
                    Chunk(
                        doc_id=doc_id,
                        element_kinds=[el.kind for el in block_stack],
                        section_path=" > ".join(t for t, _ in section_stack) if section_stack else "",
                        seq=seq,
                        text="\n".join(el.text for el in block_stack),
                        token_count=token_count
                    )
                )
                seq += 1
                token_count = 0
                block_stack.clear()

        for el in elements:
            kind = el.kind
            if kind == Kind.HEADING:
                # 遇到新标题时，把同级或更深的旧标题弹出
                while section_stack and section_stack[-1][1] >= el.level:
                    section_stack.pop()
                section_stack.append((el.text, el.level))
                flush()

            elif kind == Kind.PARAGRAPH:
                estimated = _estimate_tokens(el.text)
                if token_count + estimated > self.max_tokens:
                    flush()
                # flush 后仍然要加入当前元素，否则会丢失
                block_stack.append(el)
                token_count += _estimate_tokens(el.text)

            elif kind == Kind.TABLE:
                # 表格独立成块，前后都 flush
                flush()
                block_stack.append(el)
                token_count = _estimate_tokens(el.text)
                flush()

        flush()  # 处理最后剩余的元素
        return chunks
