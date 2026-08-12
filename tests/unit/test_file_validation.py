import io
import zipfile

import pytest
from direhire.files.validation import (
    DOCX_MIME,
    PDF_MIME,
    FileValidationFailure,
    validate_file_structure,
)


def make_docx(*, macro: bool = False) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        content_type = (
            "application/vnd.ms-word.document.macroEnabled.main+xml"
            if macro
            else "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
        )
        archive.writestr(
            "[Content_Types].xml", f'<Types><Override ContentType="{content_type}"/></Types>'
        )
        archive.writestr("word/document.xml", "<document>synthetic</document>")
        if macro:
            archive.writestr("word/vbaProject.bin", b"synthetic macro")
    return buffer.getvalue()


def test_real_pdf_and_docx_structures_are_required() -> None:
    assert validate_file_structure(b"%PDF-1.7\nSynthetic\n%%EOF", PDF_MIME) == PDF_MIME
    assert validate_file_structure(make_docx(), DOCX_MIME) == DOCX_MIME
    with pytest.raises(FileValidationFailure):
        validate_file_structure(b"not a PDF", PDF_MIME)


def test_macro_enabled_docx_and_pdf_active_content_are_rejected() -> None:
    with pytest.raises(FileValidationFailure, match="FILE_ACTIVE_CONTENT_REJECTED"):
        validate_file_structure(make_docx(macro=True), DOCX_MIME)
    with pytest.raises(FileValidationFailure, match="FILE_ACTIVE_CONTENT_REJECTED"):
        validate_file_structure(b"%PDF-1.7\n/JavaScript evil\n%%EOF", PDF_MIME)
