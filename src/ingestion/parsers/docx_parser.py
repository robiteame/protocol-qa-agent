from ...core.models import IRElement
from .base import BaseParser
from docx import Document
from pathlib import Path

class DocxParser(BaseParser):
    suffixes = {".docx"}

    def parse(self, path: Path) -> list[IRElement]:
        doc = Document(path)
        elements = []
        for para in doc.paragraphs:
            level = 0
            if para.style.name.startswith("Heading"):
                level = int(para.style.name.split()[-1])
            elements.append(IRElement(IRElement.Kind.HEADING if level > 0 else IRElement.Kind.PARAGRAPH, level, para.text))