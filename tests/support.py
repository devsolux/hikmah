"""Load project tooling and create isolated source copies without installing anything."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import deliberation as runtime

spec = importlib.util.spec_from_file_location('hikmah_project', ROOT / 'scripts/project.py')
assert spec is not None and spec.loader is not None
project = importlib.util.module_from_spec(spec)
spec.loader.exec_module(project)


class SourceCopy(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix='hikmah-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / 'hikmah'
        self.root.mkdir()
        for name in project.ROOT_FILES:
            shutil.copy2(ROOT / name, self.root / name)
        for name in (*project.SOURCE_DIRS, *project.MARKETPLACE_ROOTS):
            shutil.copytree(ROOT / name, self.root / name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store'))

    def sync_marketplace(self) -> list[str]:
        """Refresh the committed public marketplace after a deliberate source edit."""
        return project.sync_marketplace(self.root)

    def edit_json(self, relative: str, edit: Any) -> None:
        path = self.root / relative
        value = json.loads(path.read_text(encoding='utf-8'))
        edit(value)
        path.write_bytes(project.json_bytes(value))

    def append(self, relative: str, text: str) -> None:
        path = self.root / relative
        path.write_bytes(path.read_bytes() + text.encode('utf-8'))

    def symlink(self, link: Path, target: Path, *, directory: bool = False) -> None:
        try:
            link.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f'symlinks unavailable: {exc}')
