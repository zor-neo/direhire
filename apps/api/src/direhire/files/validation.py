import io
import subprocess
import zipfile
from dataclasses import dataclass
from typing import Protocol

PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
ALLOWED_UPLOAD_TYPES = {PDF_MIME: ".pdf", DOCX_MIME: ".docx"}


class FileValidationFailure(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def validate_file_structure(content: bytes, declared_content_type: str) -> str:
    if declared_content_type == PDF_MIME:
        _validate_pdf(content)
        return PDF_MIME
    if declared_content_type == DOCX_MIME:
        _validate_docx(content)
        return DOCX_MIME
    raise FileValidationFailure("FILE_TYPE_UNSUPPORTED")


def _validate_pdf(content: bytes) -> None:
    if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]:
        raise FileValidationFailure("FILE_STRUCTURE_INVALID")
    lowered = content.lower()
    if any(marker in lowered for marker in (b"/javascript", b"/launch", b"/embeddedfile")):
        raise FileValidationFailure("FILE_ACTIVE_CONTENT_REJECTED")


def _validate_docx(content: bytes) -> None:
    if not content.startswith(b"PK"):
        raise FileValidationFailure("FILE_STRUCTURE_INVALID")
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            names = archive.namelist()
            if len(names) > 5000:
                raise FileValidationFailure("FILE_ARCHIVE_LIMIT_EXCEEDED")
            normalized = {name.replace("\\", "/").casefold() for name in names}
            if "[content_types].xml" not in normalized or "word/document.xml" not in normalized:
                raise FileValidationFailure("FILE_STRUCTURE_INVALID")
            if any(
                "vbaproject.bin" in name
                or name.endswith(".exe")
                or name.startswith("../")
                or "/../" in name
                for name in normalized
            ):
                raise FileValidationFailure("FILE_ACTIVE_CONTENT_REJECTED")
            total_uncompressed = sum(info.file_size for info in archive.infolist())
            if total_uncompressed > 50_000_000:
                raise FileValidationFailure("FILE_ARCHIVE_LIMIT_EXCEEDED")
            content_types = archive.read("[Content_Types].xml").lower()
            if b"macroenabled" in content_types:
                raise FileValidationFailure("FILE_ACTIVE_CONTENT_REJECTED")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise FileValidationFailure("FILE_STRUCTURE_INVALID") from exc


@dataclass(frozen=True, slots=True)
class ScanResult:
    clean: bool
    engine: str
    version: str


class MalwareScanner(Protocol):
    def scan(self, content: bytes) -> ScanResult: ...


class ClamAvScanner:
    def scan(self, content: bytes) -> ScanResult:
        result = subprocess.run(
            ["clamscan", "--no-summary", "-"],
            input=content,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if result.returncode == 0:
            return ScanResult(True, "CLAMAV", "runtime")
        if result.returncode == 1:
            return ScanResult(False, "CLAMAV", "runtime")
        raise RuntimeError("malware scanner unavailable")
