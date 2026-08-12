"""Generate deterministic synthetic ATS document samples for visual QA."""

import argparse
from pathlib import Path

from direhire.documents.ats_cv import AtsCvRenderer

SYNTHETIC_CV = {
    "title": "Jordan Lee | Backend Engineer",
    "professional_summary": (
        "Backend engineer with fictional experience delivering Python APIs and reliable "
        "PostgreSQL-backed services for internal business systems."
    ),
    "sections": [
        {
            "heading": "Experience",
            "items": [
                "Built documented FastAPI services for a fictional inventory platform.",
                "Improved PostgreSQL query reliability using measured test evidence.",
                "Collaborated with product and operations teams on safe releases.",
            ],
        },
        {
            "heading": "Skills",
            "items": ["Python", "FastAPI", "PostgreSQL", "AWS Lambda"],
        },
        {
            "heading": "Education",
            "items": ["BSc Computer Science, Fictional University, 2022"],
        },
    ],
    "omitted_or_deemphasized": [],
    "truthfulness_notes": ["All content is deterministic synthetic test data."],
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    renderer = AtsCvRenderer()
    (args.output_dir / "synthetic-ats-cv.docx").write_bytes(renderer.render(SYNTHETIC_CV, "DOCX"))
    (args.output_dir / "synthetic-ats-cv.pdf").write_bytes(renderer.render(SYNTHETIC_CV, "PDF"))


if __name__ == "__main__":
    main()
