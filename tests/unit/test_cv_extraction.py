import io
import zipfile

import pytest
from direhire.files.extraction import MAX_EXTRACTED_CHARACTERS, SafeCvTextExtractor
from direhire.files.validation import DOCX_MIME


def make_text_docx(text: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "word/document.xml",
            '<w:document xmlns:w="urn:test"><w:body><w:p><w:r>'
            f"<w:t>{text}</w:t>"
            "</w:r></w:p></w:body></w:document>",
        )
    return buffer.getvalue()


def test_clean_docx_text_is_extracted_locally_and_bounded() -> None:
    result = SafeCvTextExtractor().extract(
        make_text_docx("Synthetic backend experience"), DOCX_MIME
    )
    assert result == "Synthetic backend experience"
    long_result = SafeCvTextExtractor().extract(
        make_text_docx("x" * (MAX_EXTRACTED_CHARACTERS + 100)), DOCX_MIME
    )
    assert len(long_result) == MAX_EXTRACTED_CHARACTERS


def test_empty_cv_extraction_fails_without_fabricating_text() -> None:
    with pytest.raises(ValueError, match="no extractable text"):
        SafeCvTextExtractor().extract(make_text_docx(""), DOCX_MIME)
