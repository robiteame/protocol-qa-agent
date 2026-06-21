from abc import ABC, abstractmethod
from typing import ClassVar
from pathlib import Path
from ...core.models import IRElement
from ...core.errors import ParseError

class BaseParser(ABC):
    suffixes: ClassVar[set[str]]      # 如 {".docx"}

    @abstractmethod
    def parse(self, path: Path) -> list[IRElement]:
        """文件 → 中间表示。解析失败抛 ParseError。"""

def get_parser(suffix: str) -> BaseParser:
    """注册表模式：根据后缀返回解析器实例，不认识的后缀抛 ParseError。"""
    for parser_cls in BaseParser.__subclasses__():
        if suffix in parser_cls.suffixes:
            return parser_cls()
    raise ParseError(f"无法解析类型: {suffix}")
