from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    seekdb_host: str = os.getenv("SEEKDB_HOST", "127.0.0.1")
    seekdb_port: int = int(os.getenv("SEEKDB_PORT", "13881"))
    seekdb_user: str = os.getenv("SEEKDB_USER", "root")
    seekdb_password: str = os.getenv("SEEKDB_PASSWORD", "")
    seekdb_database: str = os.getenv("SEEKDB_DATABASE", "ae02_minimax")

    powercontext_url: str = os.getenv("POWERCONTEXT_URL", "http://127.0.0.1:8000")
    powercontext_scope_key: str = os.getenv("POWERCONTEXT_SCOPE_KEY", "ae02-minimax-sdd")

    minimax_base_url: str = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
    minimax_model: str = os.getenv("MINIMAX_MODEL", "MiniMax-M2.5")
    # Key path only — never commit the key. Env MINIMAX_API_KEY also accepted.
    minimax_key_file: str = os.getenv("MINIMAX_KEY_FILE", "")

    sample_root: Path = Path(
        os.getenv("SAMPLE_ROOT", str(ROOT / "sample" / "billing_refund"))
    )
    evidence_root: Path = Path(os.getenv("EVIDENCE_ROOT", str(ROOT / "evidence")))


def get_settings() -> Settings:
    return Settings()


def load_minimax_key(settings: Settings) -> str:
    env_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if env_key:
        return env_key
    path = Path(settings.minimax_key_file)
    if not path.is_file():
        raise FileNotFoundError(
            f"MiniMax key not found. Set MINIMAX_API_KEY or create {path}"
        )
    return path.read_text(encoding="utf-8").strip()
