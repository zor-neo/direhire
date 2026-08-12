import html
import re
from html.parser import HTMLParser

from direhire.errors import AppError

MAX_PUBLIC_JD_CHARACTERS = 100_000
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d .()\-]{7,}\d)(?!\w)")
WHITESPACE_PATTERN = re.compile(r"[ \t]+")


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.casefold() in {"script", "style", "noscript", "svg"}:
            self.hidden_depth += 1
        elif tag.casefold() in {"p", "div", "li", "br", "section", "article", "h1", "h2", "h3"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"script", "style", "noscript", "svg"} and self.hidden_depth:
            self.hidden_depth -= 1
        elif tag.casefold() in {"p", "div", "li", "section", "article"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def sanitize_public_job_description(raw: str) -> str:
    if not raw.strip():
        raise AppError("JOB_CONTENT_EMPTY", "The job description is empty.", 422)
    parser = _VisibleTextParser()
    parser.feed(raw)
    visible = html.unescape("".join(parser.parts))
    visible = EMAIL_PATTERN.sub("[contact email removed]", visible)
    visible = PHONE_PATTERN.sub("[contact phone removed]", visible)
    lines = [WHITESPACE_PATTERN.sub(" ", line).strip() for line in visible.splitlines()]
    sanitized = "\n".join(line for line in lines if line)
    if not sanitized:
        raise AppError("JOB_CONTENT_EMPTY", "The job description is empty.", 422)
    return sanitized[:MAX_PUBLIC_JD_CHARACTERS]
