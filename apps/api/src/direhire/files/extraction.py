import io
import re
import zipfile
from typing import Protocol
from xml.etree import ElementTree

from pypdf import PdfReader

from direhire.files.validation import DOCX_MIME, PDF_MIME

MAX_EXTRACTED_CHARACTERS = 200_000
WHITESPACE = re.compile(r"[ \t]+")


class CvTextExtractor(Protocol):
    def extract(self, content: bytes, content_type: str) -> str: ...


class SafeCvTextExtractor:
    def extract(self, content: bytes, content_type: str) -> str:
        if content_type == PDF_MIME:
            text = self._pdf(content)
        elif content_type == DOCX_MIME:
            text = self._docx(content)
        else:
            raise ValueError("unsupported CV type")
        normalized = "\n".join(
            WHITESPACE.sub(" ", line).strip() for line in text.splitlines() if line.strip()
        )
        if not normalized:
            raise ValueError("CV contains no extractable text")
        return normalized[:MAX_EXTRACTED_CHARACTERS]

    @staticmethod
    def _pdf(content: bytes) -> str:
        reader = PdfReader(io.BytesIO(content), strict=True)
        if reader.is_encrypted or len(reader.pages) > 100:
            raise ValueError("PDF cannot be safely extracted")
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    @staticmethod
    def _docx(content: bytes) -> str:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            document = archive.read("word/document.xml")
        root = ElementTree.fromstring(document)
        return "\n".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))
