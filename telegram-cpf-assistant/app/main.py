from __future__ import annotations

import logging

from telegram import Update

from app.bot import build_application
from app.config import Settings
from app.logger import setup_logging


def main() -> None:
    settings = Settings.load()
    setup_logging(level=settings.log_level)
    log = logging.getLogger("app.main")
    log.info(
        "starting telegram-cpf-assistant config=%s", settings.redacted()
    )

    application = build_application(settings)
    log.info("bot ready, starting polling")
    application.run_polling(allowed_updates=[Update.MESSAGE])


if __name__ == "__main__":
    main()
