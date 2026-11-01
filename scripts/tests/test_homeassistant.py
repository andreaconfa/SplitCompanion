"""Home Assistant option validation must fail closed before running the service."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ha_runner', ROOT / 'homeassistant/splitcompanion/run.py')
runner = importlib.util.module_from_spec(spec)
if spec.loader and spec.origin and Path(spec.origin).exists():
    spec.loader.exec_module(runner)


class HomeAssistantOptionsTests(unittest.TestCase):
    def test_defaults_use_persistent_private_directories(self):
        env = runner.configuration({})
        self.assertEqual(env['SPLIT_COMPANION_DB'], '/data/instance/split-companion.db')
        self.assertEqual(env['SPLIT_COMPANION_BACKUP_DIR'], '/data/backups')
        self.assertEqual(env['SPLIT_COMPANION_MFA_REQUIRED'], 'true')
        self.assertEqual(env['SPLIT_COMPANION_TRUSTED_PROXY_IPS'], '')

    def test_custom_options_cannot_change_paths_or_add_environment(self):
        env = runner.configuration({'db': '/etc/passwd', 'timezone': 'Europe/London', 'secret_key': 'unsafe'})
        self.assertEqual(env['SPLIT_COMPANION_TIMEZONE'], 'Europe/London')
        self.assertEqual(env['SPLIT_COMPANION_DB'], '/data/instance/split-companion.db')
        self.assertNotIn('SPLIT_COMPANION_SECRET_KEY', env)

    def test_false_boolean_and_integer_ranges(self):
        env = runner.configuration({'allow_http': False, 'backup_hour': 23, 'backup_retention': 14})
        self.assertEqual(env['SPLIT_COMPANION_ALLOW_HTTP'], 'false')
        for options in ({'allow_http': 'false'}, {'backup_hour': 24}, {'backup_retention': 0}, {'backup_hour': True}):
            with self.assertRaises(ValueError):
                runner.configuration(options)

    def test_legacy_manual_code_is_ignored_including_previously_invalid_values(self):
        for code in ('short', 'x' * 129, 'symbols!@#', None):
            env = runner.configuration({'initial_setup_code': code})
            self.assertEqual(env, runner.configuration({}))
            self.assertNotIn('SPLIT_COMPANION_INITIAL_SETUP_CODE', env)


if __name__ == '__main__':
    unittest.main()
