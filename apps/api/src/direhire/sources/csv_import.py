import csv
import io

from pydantic import TypeAdapter, ValidationError

from direhire.errors import AppError
from direhire.watches.schemas import WatchSourceInput

MAX_CSV_BYTES = 100_000
MAX_CSV_ROWS = 100


def parse_source_csv(content: bytes) -> list[WatchSourceInput]:
    if len(content) > MAX_CSV_BYTES:
        raise AppError("CSV_TOO_LARGE", "The source CSV is too large.", 413)
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AppError("CSV_INVALID", "The source CSV must use UTF-8.", 422) from exc
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames != ["source_kind", "adapter_key", "url"]:
        raise AppError(
            "CSV_INVALID",
            "CSV columns must be source_kind, adapter_key, url in that order.",
            422,
        )
    rows = list(reader)
    if not rows or len(rows) > MAX_CSV_ROWS:
        raise AppError("CSV_INVALID", "CSV must contain between 1 and 100 sources.", 422)
    try:
        return TypeAdapter(list[WatchSourceInput]).validate_python(rows)
    except ValidationError as exc:
        raise AppError("CSV_INVALID", "One or more source rows are invalid.", 422) from exc
