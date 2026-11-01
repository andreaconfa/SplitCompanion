"""Ingress listener and manifest must agree without exposing the private port."""
import importlib.util
from pathlib import Path
import socket
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('ingress_runner', ROOT / 'homeassistant/splitcompanion/run.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class HomeAssistantIngressTests(unittest.TestCase):
    def test_manifest_enables_sidebar_but_only_publishes_direct_port(self):
        config = (ROOT / 'homeassistant/splitcompanion/config.yaml').read_text()
        self.assertIn('ingress: true\n', config)
        self.assertIn('ingress_port: 8099\n', config)
        self.assertNotIn('8099/tcp:', config)
        self.assertIn('8000/tcp: 8000', config)

    def test_listener_factory_binds_two_distinct_sockets_and_closes_them(self):
        with runner.listener_sockets('127.0.0.1', 0, ingress_port=0) as listeners:
            self.assertEqual(len(listeners), 2)
            self.assertNotEqual(listeners[0].getsockname(), listeners[1].getsockname())
            for listener in listeners:
                with socket.create_connection(listener.getsockname(), timeout=1):
                    connection, _ = listener.accept()
                    connection.close()
        self.assertTrue(all(s.fileno() == -1 for s in listeners))
