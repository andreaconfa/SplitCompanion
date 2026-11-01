"""Home Assistant adapter: read managed options, drop privileges, use normal startup."""
import json
import os
from pathlib import Path
import re
import sys


def configuration(options):
    if not isinstance(options, dict):
        raise ValueError('App options must be an object.')
    defaults = {
        'timezone': 'UTC', 'allow_http': True, 'public_origin': '',
        'trusted_proxy_ips': '', 'mfa_required': True, 'push_enabled': False,
        'push_vapid_subject': '', 'backup_hour': 3, 'backup_retention': 14,
    }
    env = {
        'SPLIT_COMPANION_DB': '/data/instance/split-companion.db',
        'SPLIT_COMPANION_BACKUP_DIR': '/data/backups',
        'SPLIT_COMPANION_BACKUPS_ENABLED': 'true',
        'SPLIT_COMPANION_SCHEDULER': 'true',
    }
    for key, default in defaults.items():
        value = options.get(key, default)
        if type(value) is not type(default):
            raise ValueError(f'Invalid option type: {key}')
        if key == 'backup_hour' and not 0 <= value <= 23:
            raise ValueError('Backup hour must be between 0 and 23.')
        if key == 'backup_retention' and not 1 <= value <= 365:
            raise ValueError('Backup retention must be between 1 and 365.')
        env['SPLIT_COMPANION_' + key.upper()] = str(value).lower() if isinstance(value, bool) else str(value)
    code = options.get('initial_setup_code', '')
    if not isinstance(code, str) or (code and not re.fullmatch(r'[A-Za-z0-9_-]{32,128}', code)):
        raise ValueError('Initial setup code must contain 32–128 random letters, digits, hyphens or underscores.')
    return env, code


def authorize_setup(engine, code):
    """Explicit operator secret; same code never extends its expiry or resets attempts."""
    if not code:
        return
    from sqlalchemy import text
    from sqlmodel import Session
    from app.auth import hash_token
    from app.bootstrap import setup_state, TOKEN_LIFETIME
    from app.models import now

    with Session(engine) as session:
        session.execute(text('BEGIN IMMEDIATE'))
        state = setup_state(session)
        digest = hash_token(code)
        if not state.completed and state.token_hash != digest:
            state.token_hash = digest
            state.expires_at = now() + TOKEN_LIFETIME
            state.attempts = 0
            state.attempt_window_expires_at = None
            session.add(state)
        session.commit()


def main():
    os.umask(0o077)
    options = json.loads(Path('/data/options.json').read_text())
    env, code = configuration(options)
    os.environ.update(env)
    # Supervisor owns /data and options.json. Only our dedicated directories change owner.
    for path in (Path('/data/instance'), Path('/data/backups')):
        path.mkdir(mode=0o700, exist_ok=True)
        if path.is_symlink():
            raise ValueError('App storage must not be a symlink.')
        if os.getuid() == 0:
            os.chown(path, 10001, 10001)
    if os.getuid() == 0:
        os.setgroups([])
        os.setgid(10001)
        os.setuid(10001)
    if len(sys.argv) > 1:
        from app.cli import main as cli_main
        cli_main()
        return
    from app.config import get_settings
    from app.container import prepare
    from app.runtime import instance_lock
    cfg = get_settings()
    with instance_lock(Path(cfg.db).parent / '.instance.lock'):
        prepare(cfg)
        from app.db import engine
        authorize_setup(engine, code)
        del code, options
        import uvicorn
        uvicorn.run('app.main:app', host=cfg.host, port=cfg.port, workers=1,
                    proxy_headers=True, forwarded_allow_ips=cfg.trusted_proxy_ips, access_log=False)


if __name__ == '__main__':
    main()
