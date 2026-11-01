"""Local administration and safe SQLite backup commands."""

import argparse
import getpass
import sqlite3
from datetime import datetime
from pathlib import Path
from sqlmodel import Session, select, delete
from sqlalchemy import text
from app.db import engine
from app.auth import hasher
from app.models import User, MFARecovery
from app.schemas import UserCreate
from app.config import get_settings


def main():
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("create-admin")
    admin.add_argument("--username", default="admin")
    admin.add_argument("--display-name", default="Amministratore")
    admin.add_argument("--password-stdin", action="store_true")
    reset = commands.add_parser("reset-password")
    reset.add_argument("username")
    reset.add_argument("--password-stdin", action="store_true")
    mfa = commands.add_parser("reset-mfa")
    mfa.add_argument("username")
    backup = commands.add_parser("backup")
    backup.add_argument("--output-dir")
    commands.add_parser("setup-token")
    full = commands.add_parser("backup-full")
    full.add_argument("--output-dir")
    full.add_argument("--kind", choices=["manual", "daily", "migration"], default="manual")
    restore = commands.add_parser("restore")
    restore.add_argument("archive")
    restore.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    if args.command == "restore":
        if not args.confirm:
            raise SystemExit("Conferma con --confirm; usa un volume nuovo e il server arrestato.")
        from app.backup import restore_full
        from app.container import schema_versions

        restore_full(get_settings(), args.archive, schema_versions()[1])
        print("Ripristino completato. Verifica restored-config.json prima dell’avvio.")
        return
    from app.runtime import resolve_secret

    resolve_secret(get_settings())
    if args.command == "setup-token":
        from app.bootstrap import issue_setup_token

        print(issue_setup_token(engine))
        return
    if args.command == "backup-full":
        from app.backup import backup_full

        print(backup_full(get_settings(), args.output_dir, args.kind))
        return
    if args.command == "backup":
        source = Path(get_settings().db)
        if not source.is_file():
            raise SystemExit("Database non trovato.")
        directory = Path(args.output_dir) if args.output_dir else source.parent / "backups"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"split-companion-{datetime.now():%Y-%m-%d-%H%M%S}.db"
        # Exclusive file creation refuses accidental overwrite within the same second.
        with target.open("xb"):
            pass
        target.chmod(0o600)
        try:
            with (
                sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src,
                sqlite3.connect(target) as dest,
            ):
                src.backup(dest)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        print(target)
        return
    if args.command == "reset-mfa":
        from app.services.mfa_service import revoke_user_auth

        with Session(engine) as s:
            s.execute(text("BEGIN IMMEDIATE"))
            user = s.exec(
                select(User).where(User.username == args.username.lower().strip())
            ).first()
            if not user:
                raise SystemExit("Utente non trovato.")
            user.mfa_enabled = False
            user.mfa_secret = None
            user.mfa_last_counter = -1
            s.add(user)
            s.exec(delete(MFARecovery).where(MFARecovery.user_id == user.id))
            revoke_user_auth(s, user.id)
            s.commit()
        print(
            "Verifica a due fattori reimpostata. Richiedi una nuova registrazione al prossimo accesso."
        )
        return
    password = (
        input().strip()
        if args.password_stdin
        else getpass.getpass("Password (almeno 10 caratteri): ")
    )
    if len(password) < 10 or len(password) > 256:
        raise SystemExit("La password deve avere da 10 a 256 caratteri.")
    with Session(engine) as s:
        s.execute(text("BEGIN IMMEDIATE"))
        username = args.username.lower().strip()
        user = s.exec(select(User).where(User.username == username)).first()
        if args.command == "create-admin":
            if user:
                raise SystemExit("Username già presente. Usa reset-password se necessario.")
            data = UserCreate(
                username=username, display_name=args.display_name, password=password, is_admin=True
            )
            user = User(
                **data.model_dump(exclude={"password"}), password_hash=hasher.hash(password)
            )
            s.add(user)
        else:
            if not user:
                raise SystemExit("Utente non trovato.")
            user.password_hash = hasher.hash(password)
            s.add(user)
            from app.services.mfa_service import revoke_user_auth

            revoke_user_auth(s, user.id)
        s.commit()
    print("Account aggiornato." if args.command == "reset-password" else "Amministratore creato.")


if __name__ == "__main__":
    main()
