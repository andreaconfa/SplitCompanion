"""Use Home Assistant's actual comparator to verify App update eligibility."""
from pathlib import Path
import re
import unittest

from awesomeversion import AwesomeVersion

ROOT = Path(__file__).resolve().parents[2]


class HomeAssistantVersionTests(unittest.TestCase):
    def test_published_app_version_is_newer_than_both_legacy_packages(self):
        manifest = (ROOT / 'homeassistant/splitcompanion/config.yaml').read_text()
        current = re.search(r'^version: "([^"]+)"$', manifest, re.MULTILINE).group(1)
        for installed in ('1.2.0-rc.5-homeassistant', '1.2.0-rc.6-homeassistant'):
            with self.subTest(installed=installed):
                self.assertGreater(AwesomeVersion(current), AwesomeVersion(installed))

    def test_app_uses_server_version_in_a_distinct_image_repository(self):
        manifest = (ROOT / 'homeassistant/splitcompanion/config.yaml').read_text()
        namespace = {}
        exec((ROOT / 'backend/app/version.py').read_text(), namespace)
        self.assertIn(f'version: "{namespace["SERVER_VERSION"]}"', manifest)
        self.assertIn('image: ghcr.io/andreaconfa/splitcompanion-homeassistant\n', manifest)

    def test_next_candidates_and_stable_release_keep_correct_order(self):
        versions = ['1.2.1-rc.1', '1.2.1-rc.2', '1.2.1-rc.10', '1.2.1', '1.2.2-rc.1']
        for older, newer in zip(versions, versions[1:]):
            with self.subTest(older=older, newer=newer):
                self.assertGreater(AwesomeVersion(newer), AwesomeVersion(older))


if __name__ == '__main__':
    unittest.main()
