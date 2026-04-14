from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    ai_root = Path(__file__).resolve().parents[1]
    if str(ai_root) not in sys.path:
        sys.path.insert(0, str(ai_root))

    from app.main import create_app

    schema = create_app().openapi()
    output_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    payload = json.dumps(schema, ensure_ascii=True, indent=2)

    if output_path is None:
        print(payload)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
