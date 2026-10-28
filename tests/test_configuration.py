"""Regression checks for public deployment config; never read real env files."""
import unittest
import re
import runpy
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class ConfigurationTests(unittest.TestCase):
    def test_env_template_covers_readme_and_contains_only_empty_values(self):
        template = (ROOT / '.env.example').read_text()
        entries = [line.split('=', 1) for line in template.splitlines() if line and not line.startswith('#')]
        self.assertTrue(all(len(entry) == 2 and entry[1] == '' for entry in entries))
        names = {entry[0] for entry in entries}
        readme_names = set(re.findall(r'^\| `([A-Z][A-Z_]+)` \|', (ROOT / 'README.md').read_text(), re.M))
        self.assertTrue(readme_names <= names)
        sys.path.insert(0, str(ROOT / 'mcp'))
        with patch.dict('os.environ', {name: '' for name in names}, clear=True):
            configuration = runpy.run_path(str(ROOT / 'mcp/server.py'))
        self.assertEqual(configuration['PPLX_DAILY_LIMIT'], 50)
        self.assertEqual(configuration['PORT'], 8000)
        self.assertEqual(configuration['SEARXNG_LANG'], 'auto')

    def test_container_defaults_to_unprivileged_user_and_immutable_image(self):
        dockerfile = (ROOT / 'mcp/Dockerfile').read_text()
        self.assertIn('USER 10001:10001', dockerfile)
        self.assertLess(dockerfile.index('USER 10001:10001'), dockerfile.index('CMD'))
        compose = (ROOT / 'docker-compose.yml').read_text()
        self.assertNotIn(':latest', compose)
        self.assertRegex(compose, r'image: searxng/searxng@sha256:[a-f0-9]{64}')

    def test_dockerfile_copies_every_runtime_module(self):
        dockerfile = (ROOT / 'mcp/Dockerfile').read_text()
        copied = set(re.search(r'^COPY (mcp/[\w.]+(?: mcp/[\w.]+)*) \./', dockerfile, re.M).group(1).split())
        runtime = {f'mcp/{path.name}' for path in (ROOT / 'mcp').glob('*.py')}
        self.assertEqual(runtime - copied, set())

    def test_public_settings_never_contain_a_secret_value(self):
        settings = (ROOT / 'searxng-settings.example.yml').read_text()
        key_lines = [line.strip() for line in settings.splitlines() if line.strip().startswith('secret_key:')]
        self.assertEqual(key_lines, ['secret_key: ""'])

    def test_compose_requires_environment_key_and_only_mounts_public_template(self):
        compose = (ROOT / 'docker-compose.yml').read_text()
        self.assertIn('SEARXNG_SECRET: ' + chr(36) + '{SEARXNG_SECRET:?', compose)
        self.assertIn('./searxng-settings.example.yml:/etc/searxng/settings.yml:ro', compose)
        self.assertNotIn('./searxng-settings.yml:', compose)
        self.assertIn('/searxng-settings.yml', (ROOT / '.gitignore').read_text().splitlines())

    def test_searxng_timeouts_and_compose_health_and_logging_are_configured(self):
        settings = (ROOT / 'searxng-settings.example.yml').read_text()
        self.assertIn('request_timeout: 3.0', settings)
        self.assertIn('max_request_timeout: 8.0', settings)
        self.assertIn('SearxEngineTooManyRequests: 600', settings)
        compose = (ROOT / 'docker-compose.yml').read_text()
        self.assertIn('http://127.0.0.1:8080/healthz', compose)
        self.assertIn('condition: service_healthy', compose)
        self.assertEqual(compose.count('driver: "json-file"'), 2)
