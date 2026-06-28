import sys
from pathlib import Path

# Add project root to path so `src` package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.models import IRElement, Kind
from src.ingestion.chunker import Chunker
from src.ingestion.parsers.docx_parser import DocxParser




if __name__ == "__main__":
    parser = DocxParser()
    result = parser.parse(Path(r"C:\Users\zhang\Desktop\DesktopDocument\客户资料\集控协议7593 7595\对周天线伺服机构DZSF-1403-05通讯协议.docx"))
    chunker = Chunker()
    chunks = chunker.chunk_IRElements(result, "test")
    for ire in result:
        print("="*80)
        print(ire.level)