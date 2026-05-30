from __future__ import annotations

"""
Garmin Connect client — port de joaopdavila/garmin-dashboard/garmin_client.py.

Autentica via cache de token (default `data/garmin_session/`, configurável por
`GARMIN_TOKEN_DIR`) e cai para login com email/senha apenas se o cache não
existir ou expirar. Expõe métodos finos por domínio da API (sono, HRV, stress,
body battery, steps, daily summary, training readiness/status, max metrics,
atividades, composição corporal).

Reaproveitar o cache existente do garmin-dashboard (`~/.garminconnect/`) evita
re-2FA: basta copiar o conteúdo para `GARMIN_TOKEN_DIR` antes do cutover.
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

log = logging.getLogger(__name__)

DEFAULT_TOKEN_DIR = Path("./data/garmin_session")


class GarminClient:
    """Wrapper fino sobre `garminconnect` com cache de token persistente."""

    def __init__(
        self,
        email: Optional[str] = None,
        password: Optional[str] = None,
        token_dir: Optional[Path] = None,
    ):
        self.email = email or os.getenv("GARMIN_EMAIL")
        self.password = password or os.getenv("GARMIN_PASSWORD")
        env_dir = os.getenv("GARMIN_TOKEN_DIR")
        self.token_dir = Path(
            token_dir or env_dir or DEFAULT_TOKEN_DIR
        )
        self.client: Garmin | None = None

    # ── Auth ──────────────────────────────────────────────────────────────

    def authenticate(self) -> bool:
        """Resume a sessão pelo cache de token; cai para login fresco se falhar."""
        if self.token_dir.exists() and any(self.token_dir.iterdir()):
            try:
                log.info("resuming garmin session from %s", self.token_dir)
                self.client = Garmin()
                self.client.login(str(self.token_dir))
                log.info("garmin session resumed from cache")
                return True
            except Exception as exc:  # noqa: BLE001
                log.info(
                    "token cache invalid (%s); falling back to fresh login",
                    type(exc).__name__,
                )

        if not self.email or not self.password:
            log.error(
                "no token cache and GARMIN_EMAIL/GARMIN_PASSWORD unset; "
                "copy ~/.garminconnect into %s or set credentials",
                self.token_dir,
            )
            return False

        try:
            log.info("authenticating with garmin connect (email/password)")
            self.client = Garmin(email=self.email, password=self.password)
            self.client.login()
            self._save_token_cache_best_effort()
            log.info("garmin login ok")
            return True
        except (
            GarminConnectAuthenticationError,
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
        ) as exc:
            log.error("garmin authentication error: %s", type(exc).__name__)
            return False

    def _save_token_cache_best_effort(self) -> None:
        """Salva tokens no token_dir tentando as APIs conhecidas do garminconnect.

        A interface mudou entre versões; falha silenciosa — se nada funcionar o
        login fica vivo só durante o processo (sem impacto funcional)."""
        try:
            self.token_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:  # noqa: BLE001
            log.warning("could not create %s: %s", self.token_dir, exc)
            return

        target = str(self.token_dir)
        attempts = [
            ("client.garth.dump", lambda: self.client.garth.dump(target)),
            ("client.dump_tokens", lambda: self.client.dump_tokens(target)),
            ("client.dump", lambda: self.client.dump(target)),
            ("garth.save", lambda: __import__("garth").save(target)),
        ]
        for name, fn in attempts:
            try:
                fn()
                log.info("garmin token saved to %s via %s", target, name)
                return
            except Exception:  # noqa: BLE001
                continue
        log.info("garmin token cache could not be saved (unknown lib API)")

    def _ensure(self) -> Garmin:
        if not self.client:
            self.authenticate()
        if not self.client:
            raise RuntimeError("garmin client not authenticated")
        return self.client

    # ── Endpoints "live" ──────────────────────────────────────────────────

    def get_sleep(self, date: str):
        return self._ensure().get_sleep_data(date)

    def get_hrv(self, date: str):
        return self._ensure().get_hrv_data(date)

    def get_stress(self, date: str):
        return self._ensure().get_stress_data(date)

    def get_body_battery(self, start: str, end: str):
        return self._ensure().get_body_battery(start, end)

    def get_steps(self, date: str):
        return self._ensure().get_steps_data(date)

    def get_daily_summary(self, date: str):
        return self._ensure().get_user_summary(date)

    def get_training_readiness(self, date: str):
        return self._ensure().get_training_readiness(date)

    def get_training_status(self, date: str):
        return self._ensure().get_training_status(date)

    def get_max_metrics(self, date: str):
        return self._ensure().get_max_metrics(date)

    def get_body_composition(self, start: str, end: str):
        return self._ensure().get_body_composition(start, end)

    # ── Atividades ────────────────────────────────────────────────────────

    def get_recent_activities(self, limit: int = 20) -> list:
        """Últimas `limit` atividades (mais recentes primeiro)."""
        try:
            return self._ensure().get_activities(0, limit) or []
        except Exception as exc:  # noqa: BLE001
            log.warning("get_activities failed: %s", type(exc).__name__)
            return []

    def get_activities_since(self, days_back: int) -> list:
        """Atividades dos últimos `days_back` dias, paginando."""
        self._ensure()
        cutoff = datetime.now() - timedelta(days=days_back)
        out: list = []
        start, batch_size = 0, 100
        while True:
            try:
                batch = self.client.get_activities(start, batch_size)
            except Exception as exc:  # noqa: BLE001
                log.warning("get_activities offset %d failed: %s", start, exc)
                break
            if not batch:
                break
            reached = False
            for act in batch:
                ts = act.get("startTimeLocal") or act.get("startTimeGMT", "")
                try:
                    when = datetime.fromisoformat(ts.replace("Z", ""))
                except (ValueError, AttributeError):
                    continue
                if when < cutoff:
                    reached = True
                    break
                out.append(act)
            if reached or len(batch) < batch_size:
                break
            start += batch_size
        return out
