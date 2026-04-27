"""Startup helper: loads .env then launches the tarkov serve command."""
import os
from pathlib import Path

# Load .env from the backend directory
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

from tarkov.main import cli  # noqa: E402

if __name__ == "__main__":
    cli()
