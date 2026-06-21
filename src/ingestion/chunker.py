from ..core.models import Chunk, IRElement

class chunker:
    def chunk_elements(elements: list[IRElement], doc_id: str,
                   max_tokens: int = 512) -> list[Chunk]:
        """结构感知切块。"""
        
    def estimate_tokens(text: str) -> int:
        """粗估即可：中文字符数 + 英文单词数×1.3。不要为此引入 tiktoken。"""