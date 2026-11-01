"""The Home Assistant adapter must preserve the durable single-use setup gate."""

import importlib.util
import os
from datetime import timedelta
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
spec = importlib.util.spec_from_file_location(
    "ha_setup_runner", ROOT / "homeassistant/splitcompanion/run.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)

# Import the shared database module with an isolated path, never /var/lib or user data.
with tempfile.TemporaryDirectory() as bootstrap_dir:
    with patch.dict(os.environ, {"SPLIT_COMPANION_DB": str(Path(bootstrap_dir) / "bootstrap.db")}):
        from app.config import Settings, get_settings

        get_settings.cache_clear()
        from sqlmodel import SQLModel, Session, select
        from app.auth import hash_token
        from app.bootstrap import utc
        from app.db import make_engine
        from app.models import SetupState, User, now
    get_settings.cache_clear()


class HomeAssistantSetupTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.engine = make_engine(str(Path(self.folder.name) / "instance.db"))
        self.addCleanup(self.engine.dispose)
        SQLModel.metadata.create_all(self.engine)
        config = Settings(secret_key="homeassistant-test-secret-1234567890", _env_file=None)
        config_patch = patch("app.auth.get_settings", return_value=config)
        config_patch.start()
        self.addCleanup(config_patch.stop)

    def state(self):
        with Session(self.engine) as session:
            return session.get(SetupState, 1)

    def test_automatic_code_is_random_single_use_hash_with_30_minute_expiry(self):
        code = runner.authorize_setup(self.engine)
        self.assertRegex(code, r"^[A-Za-z0-9_-]{43}$")
        state = self.state()
        self.assertEqual(state.token_hash, hash_token(code))
        self.assertNotEqual(state.token_hash, code)
        self.assertGreater(utc(state.expires_at), now() + timedelta(minutes=29))
        self.assertLessEqual(utc(state.expires_at), now() + timedelta(minutes=30))

    def test_restart_rotates_code_without_clearing_active_throttle(self):
        first = runner.authorize_setup(self.engine)
        with Session(self.engine) as session:
            state = session.get(SetupState, 1)
            state.attempts = 5
            state.attempt_window_expires_at = now() + timedelta(minutes=10)
            session.add(state)
            session.commit()
        before = self.state()
        second = runner.authorize_setup(self.engine)
        after = self.state()
        self.assertNotEqual(first, second)
        self.assertEqual(after.token_hash, hash_token(second))
        self.assertEqual(after.attempts, 5)
        self.assertEqual(after.attempt_window_expires_at, before.attempt_window_expires_at)

    def test_restart_renews_expired_code(self):
        first = runner.authorize_setup(self.engine)
        with Session(self.engine) as session:
            state = session.get(SetupState, 1)
            state.expires_at = now() - timedelta(minutes=1)
            session.add(state)
            session.commit()
        second = runner.authorize_setup(self.engine)
        self.assertNotEqual(first, second)
        self.assertGreater(utc(self.state().expires_at), now())

    def test_completed_setup_cannot_reopen_even_if_users_were_removed(self):
        with Session(self.engine) as session:
            session.add(SetupState(id=1, completed=True))
            session.commit()
        self.assertIsNone(runner.authorize_setup(self.engine))
        state = self.state()
        self.assertTrue(state.completed)
        self.assertIsNone(state.token_hash)
        self.assertIsNone(state.expires_at)
        with Session(self.engine) as session:
            self.assertEqual(session.exec(select(User)).all(), [])

    def test_existing_user_closes_uncompleted_gate_and_discards_code(self):
        runner.authorize_setup(self.engine)
        with Session(self.engine) as session:
            session.add(
                User(username="existing", display_name="Existing", password_hash="disabled")
            )
            session.commit()
        self.assertIsNone(runner.authorize_setup(self.engine))
        state = self.state()
        self.assertTrue(state.completed)
        self.assertIsNone(state.token_hash)
        self.assertIsNone(state.expires_at)


if __name__ == "__main__":
    unittest.main()
