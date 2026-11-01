from functools import lru_cache
from pathlib import Path
from ipaddress import ip_network
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from urllib.parse import urlsplit
from pydantic import model_validator, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SPLIT_COMPANION_", env_file=".env", extra="ignore"
    )
    source_archive: str = ""
    db: str = "/var/lib/split-companion/split-companion.db"
    push_vapid_path: str | None = None
    push_vapid_subject: str = ""
    push_enabled: bool = True
    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    timezone: str = "Europe/Rome"
    secret_key: str = ""
    secret_key_file: str | None = None
    allow_http: bool = False
    backups_enabled: bool = False
    backup_dir: str | None = None
    backup_hour: int = Field(default=3, ge=0, le=23)
    backup_retention: int = Field(default=14, ge=1, le=365)
    secure_cookie: bool = False
    trusted_proxy_ips: str = "127.0.0.1,::1"
    public_origin: str = ""
    mfa_required: bool = False
    session_hours: int = Field(default=168, ge=1, le=8760)
    scheduler: bool = True
    frontend_dir: str = str(Path(__file__).resolve().parents[2] / "frontend" / "dist")

    @model_validator(mode="after")
    def proxy_settings(self):
        for value in self.trusted_proxy_ips.split(","):
            if value.strip():
                ip_network(value.strip(), strict=False)
                if ip_network(value.strip(), strict=False).prefixlen == 0:
                    raise ValueError("Il proxy deve avere un indirizzo o una rete specifica.")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Fuso orario non valido.") from None
        if self.secret_key and self.secret_key_file:
            raise ValueError("Configura SECRET_KEY oppure SECRET_KEY_FILE, non entrambi.")
        if self.secret_key and (
            len(self.secret_key) < 32 or self.secret_key.startswith("replace-with-")
        ):
            raise ValueError("SECRET_KEY deve essere un segreto casuale di almeno 32 caratteri.")
        if self.public_origin:
            parsed = urlsplit(self.public_origin)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("PUBLIC_ORIGIN deve essere un’origine HTTPS senza percorso.")
            self.secure_cookie = True
        return self

    @property
    def imports_dir(self) -> Path:
        return Path(self.db).parent / "imports"


@lru_cache
def get_settings():
    return Settings()
