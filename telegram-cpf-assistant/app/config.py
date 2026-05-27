from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: int
    timezone: str
    database_path: Path
    log_level: str

    @classmethod
    def load(cls, env_file: Optional[Path] = None) -> "Settings":
        if env_file is None:
            env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            load_dotenv(env_file, encoding="utf-8", override=False)

        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id_raw = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        timezone = os.getenv("TIMEZONE", "America/Sao_Paulo").strip()
        db_path_raw = os.getenv("DATABASE_PATH", "./data/cpf_assistant.db").strip()
        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()

        missing: list[str] = []
        if not token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not chat_id_raw:
            missing.append("TELEGRAM_CHAT_ID")
        if missing:
            raise RuntimeError(
                "Missing required environment variables: "
                + ", ".join(missing)
                + ". Copy .env.example to .env and fill them in."
            )

        try:
            chat_id = int(chat_id_raw)
        except ValueError as exc:
            raise RuntimeError(
                f"TELEGRAM_CHAT_ID must be an integer, got: {chat_id_raw!r}"
            ) from exc

        db_path = Path(db_path_raw)
        if not db_path.is_absolute():
            db_path = (PROJECT_ROOT / db_path).resolve()
        else:
            db_path = db_path.resolve()

        return cls(
            telegram_bot_token=token,
            telegram_chat_id=chat_id,
            timezone=timezone,
            database_path=db_path,
            log_level=log_level,
        )

    def redacted(self) -> dict[str, object]:
        token = self.telegram_bot_token
        masked = f"{token[:4]}...{token[-4:]}" if len(token) >= 8 else "***"
        return {
            "telegram_bot_token": masked,
            "telegram_chat_id": self.telegram_chat_id,
            "timezone": self.timezone,
            "database_path": str(self.database_path),
            "log_level": self.log_level,
        }
