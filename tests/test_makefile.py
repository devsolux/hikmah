"""Exercise Make entry points without recursively invoking the whole test suite."""
from __future__ import annotations

import shutil
import subprocess
import sys
import unittest

from support import SourceCopy

MAKE = shutil.which('make')


@unittest.skipUnless(MAKE, 'GNU Make is not installed')
class MakefileTests(SourceCopy):
    def run_make(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([MAKE, '--no-print-directory', '-C', str(self.root),
                               f'PYTHON={sys.executable}', *args],
                              capture_output=True, text=True, check=False, timeout=30)

    def test_default_target_is_help_and_does_not_build(self) -> None:
        result = self.run_make()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('make rebuild', result.stdout)
        self.assertFalse((self.root / 'dist').exists())

    def test_doctor_info_and_validate_targets(self) -> None:
        for name in ('doctor', 'info', 'validate'):
            with self.subTest(target=name):
                result = self.run_make(name)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_build_verify_clean_and_repeated_clean(self) -> None:
        for name in ('build', 'verify', 'clean', 'clean'):
            with self.subTest(target=name):
                result = self.run_make(name)
                self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'dist').exists())

    def test_invalid_build_fails_make(self) -> None:
        self.edit_json('project.json', lambda doc: doc.update(version='invalid'))
        result = self.run_make('build')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / 'dist').exists())

    def test_release_and_rebuild_order_even_with_parallel_flag(self) -> None:
        # Dry runs verify command ordering without invoking make test recursively.
        for target in ('all', 'release', 'rebuild'):
            result = self.run_make('-j4', '-n', target)
            self.assertEqual(result.returncode, 0, result.stderr)
            commands = [line.strip() for line in result.stdout.splitlines() if 'project.py' in line or 'unittest' in line]
            expected = ['validate', 'unittest', 'build', 'verify']
            if target == 'rebuild':
                expected.insert(0, 'clean')
            self.assertEqual(len(commands), len(expected), result.stdout)
            for line, name in zip(commands, expected):
                self.assertIn(name, line)

    def test_offline_runtime_targets(self) -> None:
        # Missing configuration must never turn local convenience targets into API calls.
        for target in ('detect', 'plan', 'runtime-help'):
            with self.subTest(target=target):
                result = self.run_make(target)
                self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'dist').exists())

    def test_audit_target_requires_a_packet_path(self) -> None:
        result = self.run_make('audit')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('PACKET=', result.stdout + result.stderr)
        self.assertFalse((self.root / 'dist').exists())

    def test_sync_personas_target_is_offline_and_idempotent(self) -> None:
        before = {p.name: p.read_bytes() for p in (self.root / 'personas').glob('*.md')}
        result = self.run_make('sync-personas')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"updated_personas": []', result.stdout)
        self.assertEqual({p.name: p.read_bytes() for p in (self.root / 'personas').glob('*.md')}, before)
        self.assertFalse((self.root / 'dist').exists())

    def test_sync_marketplace_target_is_offline_and_idempotent(self) -> None:
        result = self.run_make('sync-marketplace')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"updated_files": []', result.stdout)
        self.assertIn('"network_used": false', result.stdout)
        self.assertFalse((self.root / 'dist').exists())

    def test_stale_marketplace_fails_validate_until_synced(self) -> None:
        self.append('docs/BUILD.md', '\nA maintainer clarification.\n')
        result = self.run_make('validate')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('make sync-marketplace', result.stderr)
        self.assertEqual(self.run_make('sync-marketplace').returncode, 0)
        self.assertEqual(self.run_make('validate').returncode, 0)

    def test_project_directory_with_spaces(self) -> None:
        renamed = self.root.with_name('hikmah project with spaces')
        self.root.rename(renamed)
        self.root = renamed
        for target in ('validate', 'build', 'verify', 'clean'):
            result = self.run_make(target)
            self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
