from ...core.models import IRElement, Kind
from .base import BaseParser
from docx import Document
from docx.oxml.ns import qn
from pathlib import Path

class DocxParser(BaseParser):
    suffixes = {".docx"}

    def parse(self, path: Path) -> list[IRElement]:
        doc = Document(path)
        elements = []

        # 按文档原始顺序遍历 body 中的段落和表格
        for child in doc.element.body:
            if child.tag == qn("w:p"):
                # 段落 - 直接从 XML 元素构建 Paragraph 对象
                from docx.text.paragraph import Paragraph
                para = Paragraph(child, doc)
                level = 0
                if para.style.name.startswith("Heading"):
                    level = int(para.style.name.split()[-1])
                if para.text.strip():  # 跳过空段落
                    elements.append(IRElement(
                        Kind.HEADING if level > 0 else Kind.PARAGRAPH,
                        level, para.text
                    ))

            elif child.tag == qn("w:tbl"):
                # 表格
                from docx.table import Table
                table = Table(child, doc)
                rows = []
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    rows.append(" | ".join(cells))
                table_text = "\n".join(rows)
                if table_text.strip():
                    elements.append(IRElement(Kind.TABLE, 0, table_text))

        return elements