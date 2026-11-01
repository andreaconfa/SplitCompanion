"""Home Assistant adapter: read managed options, drop privileges, use normal startup."""
import json
from contextlib import contextmanager
import socket
import os
from pathlib import Path
import secrets
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
    # Older App versions stored a manual code here. Ignore it on upgrade.
    return env


def authorize_setup(engine):
    """Generate an operator-only code on startup, never reopen completed setup."""
    from sqlalchemy import text
    from sqlmodel import Session
    from app.auth import hash_token
    from app.bootstrap import setup_state, TOKEN_LIFETIME
    from app.models import now

    with Session(engine) as session:
        session.execute(text('BEGIN IMMEDIATE'))
        state = setup_state(session)
        code = None
        if not state.completed:
            code = secrets.token_urlsafe(32)
            state.token_hash = hash_token(code)
            state.expires_at = now() + TOKEN_LIFETIME
            # A restart must not clear an active failed-attempt window.
            session.add(state)
        session.commit()
        return code


@contextmanager
def listener_sockets(host, port, ingress_port=8099):
    """One Uvicorn process/lifespan owns both ports and closes them together."""
    listeners = []
    try:
        for number in (port, ingress_port):
            listener = socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET, socket.SOCK_STREAM)
            listeners.append(listener)
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind((host, number))
            listener.listen(2048)
            listener.setblocking(False)
        yield listeners
    finally:
        for listener in listeners:
            listener.close()


def main():
    os.umask(0o077)
    options = json.loads(Path('/data/options.json').read_text())
    env = configuration(options)
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
        code = authorize_setup(engine)
        if code:
            # Intentional one-time delivery to the operator's protected HA App log.
            print('Split Companion initial setup code: ' + code, flush=True)
            print('Open Web UI and enter this code within 30 minutes. '
                  'Keep it private. Restart the App for a new code if needed. '
                  'Codes are no longer generated after setup is completed.', flush=True)
        del code, options
        import uvicorn
        from app.main import app
        from app.ingress import HomeAssistantApp
        # Proxy processing happens only after dispatch by the actual local socket.
        server = uvicorn.Server(uvicorn.Config(
            HomeAssistantApp(app, cfg.trusted_proxy_ips), proxy_headers=False,
            access_log=False, workers=1,
        ))
        with listener_sockets(cfg.host, cfg.port) as sockets:
            server.run(sockets=sockets)


if __name__ == '__main__':
    try:
        main()
    except ValueError as error:
        print(f'Split Companion configuration error: {error}', file=sys.stderr, flush=True)
        sys.exit(1)
