import uvicorn
from pathlib import Path
from app.config import get_settings
from app.runtime import resolve_secret, instance_lock

if __name__ == "__main__":
    cfg = get_settings()
    with instance_lock(Path(cfg.db).parent / ".instance.lock"):
        resolve_secret(cfg)
        uvicorn.run(
            "app.main:app",
            host=cfg.host,
            port=cfg.port,
            workers=1,
            proxy_headers=True,
            forwarded_allow_ips=cfg.trusted_proxy_ips,
            access_log=False,
        )
