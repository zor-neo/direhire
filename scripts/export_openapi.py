import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DIREHIRE_ENVIRONMENT", "test")
os.environ.setdefault("DIREHIRE_DATABASE_URL", "sqlite+pysqlite:///:memory:")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api" / "src"))

from direhire.main import app  # noqa: E402


def main() -> None:
    destination = Path("contracts/generated/openapi.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
