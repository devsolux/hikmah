"""Regression coverage for one-coordinator ownership, portable packages, and safe output handling."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import zipfile

from support import ROOT, SourceCopy, project


class ValidationTests(SourceCopy):
    def test_product_and_single_agent_identity(self) -> None:
        meta, inputs = project.validate(self.root)
        self.assertEqual((meta['name'], meta['display_name'], meta['version']), ('hikmah', 'Hikmah', '1.0.0'))
        self.assertEqual(meta['supported_hosts'], ['claude', 'chatgpt'])
        self.assertEqual([name for name in inputs if name.startswith('agents/')], ['agents/hikmah.md'])
        self.assertEqual([name for name in inputs if name.startswith('skills/')], ['skills/hikmah/SKILL.md'])
        self.assertEqual(meta['repository'], 'https://github.com/devsolux/hikmah')
        self.assertEqual(meta['marketplace'], 'devsolux-hikmah')

    def test_additional_agent_rejected(self) -> None:
        shutil.copy2(self.root / 'agents/hikmah.md', self.root / 'agents/second.md')
        with self.assertRaisesRegex(project.ProjectError, 'exactly one agent'):
            project.validate(self.root)

    def test_missing_agent_rejected(self) -> None:
        (self.root / 'agents/hikmah.md').unlink()
        with self.assertRaisesRegex(project.ProjectError, 'exactly one agent'):
            project.validate(self.root)

    def test_additional_skill_rejected(self) -> None:
        path = self.root / 'skills/another/SKILL.md'
        path.parent.mkdir()
        shutil.copy2(self.root / 'skills/hikmah/SKILL.md', path)
        with self.assertRaisesRegex(project.ProjectError, 'exactly one skill'):
            project.validate(self.root)

    def test_generated_reference_is_not_an_editable_second_source(self) -> None:
        path = self.root / 'skills/hikmah/references/coordinator.md'
        path.parent.mkdir()
        shutil.copy2(self.root / 'agents/hikmah.md', path)
        with self.assertRaisesRegex(project.ProjectError, 'references are generated|resources are generated'):
            project.validate(self.root)

    def test_only_two_adapters_allowed(self) -> None:
        (self.root / 'adapters/third.md').write_text('# Unsupported\n', encoding='utf-8')
        with self.assertRaisesRegex(project.ProjectError, 'exactly the Claude and ChatGPT'):
            project.validate(self.root)

    def test_additional_runtime_script_rejected(self) -> None:
        (self.root / 'scripts/worker.py').write_text('pass\n', encoding='utf-8')
        with self.assertRaisesRegex(project.ProjectError, 'deterministic project tool'):
            project.validate(self.root)

    def test_unknown_root_component_rejected(self) -> None:
        (self.root / 'unknown-component').mkdir()
        with self.assertRaisesRegex(project.ProjectError, 'unrecognized root entry'):
            project.validate(self.root)

    def test_unknown_metadata_field_rejected(self) -> None:
        self.edit_json('project.json', lambda doc: doc.update(model='unrequested'))
        with self.assertRaisesRegex(project.ProjectError, 'exactly'):
            project.validate(self.root)

    def test_invalid_product_identity_rejected(self) -> None:
        self.edit_json('project.json', lambda doc: doc.update(name='another-product'))
        with self.assertRaisesRegex(project.ProjectError, 'identity'):
            project.validate(self.root)

    def test_boolean_schema_version_rejected(self) -> None:
        self.edit_json('project.json', lambda doc: doc.update(schema_version=True))
        with self.assertRaisesRegex(project.ProjectError, 'schema_version'):
            project.validate(self.root)

    def test_unsupported_host_rejected(self) -> None:
        self.edit_json('project.json', lambda doc: doc['supported_hosts'].append('other'))
        with self.assertRaisesRegex(project.ProjectError, 'only claude and chatgpt'):
            project.validate(self.root)

    def test_duplicate_keyword_rejected(self) -> None:
        self.edit_json('project.json', lambda doc: doc.update(keywords=['reasoning', 'reasoning']))
        with self.assertRaisesRegex(project.ProjectError, 'duplicate keywords'):
            project.validate(self.root)

    def test_invalid_metadata_url_rejected(self) -> None:
        for value in ('http://example.com', 'https://user:secret@example.com',
                      'https://[broken', 'https://example.com:invalid', 'https://example.com?secret=x'):
            with self.subTest(value=value):
                self.edit_json('project.json', lambda doc: doc.update(repository=value))
                with self.assertRaises(project.ProjectError):
                    project.validate(self.root)

    def test_wrong_agent_name_rejected(self) -> None:
        path = self.root / 'agents/hikmah.md'
        path.write_bytes(path.read_bytes().replace(b'name: "hikmah"', b'name: "another"', 1))
        with self.assertRaisesRegex(project.ProjectError, 'agent name'):
            project.validate(self.root)

    def test_wrong_skill_name_rejected(self) -> None:
        path = self.root / 'skills/hikmah/SKILL.md'
        path.write_bytes(path.read_bytes().replace(b'name: "hikmah"', b'name: "another"', 1))
        with self.assertRaisesRegex(project.ProjectError, 'skill name'):
            project.validate(self.root)

    def test_missing_method_stage_rejected(self) -> None:
        path = self.root / 'agents/hikmah.md'
        path.write_bytes(path.read_bytes().replace('## Round 2 — Direct cross-examination'.encode(), b'## Other'))
        with self.assertRaisesRegex(project.ProjectError, 'missing section'):
            project.validate(self.root)

    def test_root_environment_file_is_never_packaged(self) -> None:
        (self.root / '.env').write_text('SECRET=example-only\n', encoding='utf-8')
        _, inputs = project.validate(self.root)
        self.assertNotIn('.env', inputs)

    def test_claude_code_workspace_state_is_local_not_source(self) -> None:
        # Claude Code writes .claude/ into the project (settings, scheduled-task locks).
        # It once made validate, build, and github-push fail with "unrecognized root entry".
        (self.root / '.claude').mkdir()
        (self.root / '.claude/settings.local.json').write_text('{"permissions": {}}\n', encoding='utf-8')
        (self.root / '.claude/scheduled_tasks.lock').write_text('{"sessionId": "fixture"}\n', encoding='utf-8')
        _, inputs = project.validate(self.root)
        self.assertFalse(any(name.startswith('.claude/') for name in inputs))
        ignored = (self.root / '.gitignore').read_text(encoding='utf-8').splitlines()
        self.assertIn('.claude/', ignored)
        self.assertIn('._*', ignored)

    def test_secret_like_file_inside_source_rejected(self) -> None:
        (self.root / 'docs/private.key').write_text('example-only\n', encoding='utf-8')
        with self.assertRaisesRegex(project.ProjectError, 'possible secret'):
            project.validate(self.root)

    def test_local_state_and_os_metadata_excluded(self) -> None:
        (self.root / 'scratch').mkdir()
        (self.root / 'scratch/private.txt').write_text('local work\n', encoding='utf-8')
        (self.root / 'docs/.DS_Store').write_bytes(b'\x00\x01')
        (self.root / 'tests/__pycache__').mkdir()
        (self.root / 'tests/__pycache__/test.pyc').write_bytes(b'\x00\x01')
        _, inputs = project.validate(self.root)
        self.assertFalse(any('scratch/' in name or '.DS_Store' in name or '__pycache__' in name for name in inputs))

    def test_symlink_source_file_rejected(self) -> None:
        path = self.root / 'agents/hikmah.md'
        path.unlink()
        self.symlink(path, ROOT / 'agents/hikmah.md')
        with self.assertRaisesRegex(project.ProjectError, 'symlink'):
            project.validate(self.root)

    def test_symlink_source_directory_rejected(self) -> None:
        self.symlink(self.root / 'docs/linked', ROOT / 'docs', directory=True)
        with self.assertRaisesRegex(project.ProjectError, 'symlink'):
            project.validate(self.root)

    def test_directory_inspection_errors_fail_closed(self) -> None:
        def inaccessible(directory: Path, *, followlinks: bool, onerror: object):
            onerror(PermissionError(13, 'Permission denied', str(directory)))
            return iter(())
        with patch.object(project.os, 'walk', side_effect=inaccessible):
            with self.assertRaisesRegex(project.ProjectError, 'cannot inspect directory'):
                project.validate(self.root)

    def test_binary_source_rejected(self) -> None:
        (self.root / 'docs/broken.md').write_bytes(b'\xff\xfe')
        with self.assertRaisesRegex(project.ProjectError, 'UTF-8'):
            project.validate(self.root)

    def test_oversized_source_rejected(self) -> None:
        (self.root / 'docs/large.md').write_bytes(b'x' * (project.MAX_FILE_BYTES + 1))
        with self.assertRaisesRegex(project.ProjectError, 'too large'):
            project.validate(self.root)

    def test_crlf_source_rejected_with_useful_message(self) -> None:
        (self.root / 'docs/crlf.md').write_bytes(b'# Title\r\n')
        with self.assertRaisesRegex(project.ProjectError, 'LF line endings'):
            project.validate(self.root)

    def test_invalid_python_syntax_rejected(self) -> None:
        (self.root / 'tests/broken.py').write_text('def broken(\n', encoding='utf-8')
        with self.assertRaisesRegex(project.ProjectError, 'Python 3.11 syntax'):
            project.validate(self.root)

    def test_broken_source_link_rejected(self) -> None:
        self.append('README.md', '\n[Broken](docs/missing.md)\n')
        with self.assertRaisesRegex(project.ProjectError, 'missing local link'):
            project.validate(self.root)

    def test_unclosed_fence_rejected(self) -> None:
        self.append('README.md', '\n```text\nUnfinished\n')
        with self.assertRaisesRegex(project.ProjectError, 'unclosed Markdown fence'):
            project.validate(self.root)

    def test_code_example_links_are_not_live_references(self) -> None:
        self.append('README.md', '\n```text\n[Example](missing-example.md)\n```\n')
        self.sync_marketplace()
        project.validate(self.root)

    def test_manual_evaluation_fixture_has_complete_cases(self) -> None:
        value = json.loads((self.root / 'tests/fixtures/evaluations.json').read_text(encoding='utf-8'))
        self.assertEqual(value['schema_version'], 1)
        cases = value['cases']
        self.assertGreaterEqual(len(cases), 10)
        self.assertEqual(len({case['id'] for case in cases}), len(cases))
        for case in cases:
            self.assertEqual(set(case), {'id', 'request', 'required', 'prohibited'})
            self.assertTrue(project.SLUG.fullmatch(case['id']))
            self.assertTrue(case['request'].strip())
            for key in ('required', 'prohibited'):
                self.assertTrue(case[key])
                self.assertTrue(all(isinstance(item, str) and item.strip() for item in case[key]))


class ParserTests(unittest.TestCase):
    def test_strict_json_rejects_duplicates_and_nonfinite_numbers(self) -> None:
        for raw in ('{"a":1,"a":2}', '{"x":NaN}', '{"x":Infinity}', '{"x":1e9999}'):
            with self.subTest(raw=raw), self.assertRaises(project.ProjectError):
                project.decode_json(raw, 'example')

    def test_excessive_json_complexity_is_an_actionable_error(self) -> None:
        for raw in ('{"n":' + '9' * 20_000 + '}', '[' * 2000 + '0' + ']' * 2000):
            with self.assertRaises(project.ProjectError):
                project.decode_json(raw, 'example')

    def test_json_complexity_boundaries_do_not_depend_on_interpreter_defaults(self) -> None:
        digits = '9' * project.MAX_INTEGER_DIGITS
        self.assertEqual(project.decode_json(digits, 'integer'), int(digits))
        with self.assertRaisesRegex(project.ProjectError, 'integer is excessively large'):
            project.decode_json(digits + '9', 'integer')
        raw = '[' * project.MAX_JSON_DEPTH + '0' + ']' * project.MAX_JSON_DEPTH
        project.decode_json(raw, 'nested')
        with self.assertRaisesRegex(project.ProjectError, 'nesting is excessively deep'):
            project.decode_json('[' + raw + ']', 'nested')
        self.assertEqual(project.decode_json('"' + '[' * 100 + '"', 'string'), '[' * 100)

    def test_link_and_windows_reparse_metadata_are_rejected(self) -> None:
        for mode, attributes in ((stat.S_IFLNK, 0), (stat.S_IFDIR, 0x400), (stat.S_IFREG, 0x400)):
            self.assertTrue(project.redirected(SimpleNamespace(st_mode=mode, st_file_attributes=attributes)))
        self.assertFalse(project.redirected(SimpleNamespace(st_mode=stat.S_IFREG)))
        self.assertFalse(project.redirected(SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0)))

    def test_invalid_unicode_metadata_rejected(self) -> None:
        with self.assertRaises(project.ProjectError):
            project.text('\ud800', 'bad text')

    def test_semver_supports_prerelease_and_build_metadata(self) -> None:
        for value in ('1.0.0', '1.2.3-rc.1', '1.0.0-0', '1.0.0-alpha.0+build.7'):
            self.assertIsNotNone(project.SEMVER.fullmatch(value), value)
        for value in ('v1.0.0', '01.0.0', '1.0', '1.0.0-01', '1.0.0-', '1.0.0+'):
            self.assertIsNone(project.SEMVER.fullmatch(value), value)

    def test_frontmatter_requires_safe_unique_json_values(self) -> None:
        invalid = ('name: "x"\n', '---\nname: "x"\n', '---\nname: x\n---\nBody',
                   '---\nname: "x"\nname: "y"\n---\nBody', '---\nname: "x"\n---\n')
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(project.ProjectError):
                project.parse_frontmatter(raw, 'test')

    def test_unsafe_or_nonportable_archive_paths_rejected(self) -> None:
        invalid = ('', '.', '../x', '/x', 'a/../../x', 'a\\x', 'C:/x', 'a\x00x',
                   'a//b', './a', 'a/', 'a.', 'CON', 'aux.txt', 'a/NUL.md', 'a /b')
        for name in invalid:
            with self.subTest(name=name), self.assertRaises(project.ProjectError):
                project.archive({name: b'not written'})

    def test_case_and_file_directory_collisions_rejected(self) -> None:
        for files in ({'A.md': b'a', 'a.md': b'b'}, {'A/x.md': b'a', 'a/y.md': b'b'},
                      {'a': b'a', 'a/x.md': b'b'}):
            with self.subTest(files=list(files)), self.assertRaises(project.ProjectError):
                project.archive(files)

    def test_links_cannot_escape_or_use_unsafe_schemes(self) -> None:
        for target in ('../x', '%2E%2E/x', '/absolute.md', 'javascript:alert', 'file:///private'):
            with self.subTest(target=target), self.assertRaises(project.ProjectError):
                project.check_links({'README.md': f'[Bad]({target})\n'.encode()})

    def test_malformed_url_is_a_validation_error(self) -> None:
        with self.assertRaisesRegex(project.ProjectError, 'malformed link'):
            project.check_links({'README.md': b'[Bad](https://[broken)\n'})

    def test_serialization_and_fingerprints_are_order_independent(self) -> None:
        self.assertEqual(project.json_bytes({'b': 2, 'a': 1}), project.json_bytes({'a': 1, 'b': 2}))
        self.assertEqual(project.fingerprint({'b': b'2', 'a': b'1'}), project.fingerprint({'a': b'1', 'b': b'2'}))


class PackageTests(SourceCopy):
    def test_host_manifests_and_same_single_agent_resources(self) -> None:
        meta, inputs = project.validate(self.root)
        packages = {host: project.package_files(host, meta, inputs) for host in project.HOSTS}
        claude, chatgpt = packages['claude'], packages['chatgpt']
        self.assertIn('.claude-plugin/plugin.json', claude)
        self.assertNotIn('plugin.json', claude)
        self.assertIn('plugin.json', chatgpt)
        self.assertNotIn('.claude-plugin/plugin.json', chatgpt)
        for files in packages.values():
            self.assertEqual(files['skills/hikmah/references/coordinator.md'], inputs['agents/hikmah.md'])
            self.assertEqual([p for p in files if p.endswith('/hikmah.md')], ['skills/hikmah/references/sources/hikmah.md'])
            self.assertEqual(files['skills/hikmah/SKILL.md'], inputs['skills/hikmah/SKILL.md'])
            self.assertEqual([p for p in files if p.endswith('/SKILL.md')], ['skills/hikmah/SKILL.md'])
            self.assertFalse(any(p.startswith(('agents/', 'hooks/')) or 'mcp' in p.lower()
                                 for p in files))
            info = json.loads(files['skills/hikmah/references/build.json'])
            self.assertEqual((info['name'], info['agent'], info['agent_count']), ('hikmah', 'hikmah', 1))
            self.assertEqual(info['source_sha256'], project.fingerprint(inputs))
            self.assertEqual(info['persona_count'], 99)
            self.assertEqual(len([p for p in files if '/personas/' in p]), 99)
            self.assertEqual(files['skills/hikmah/scripts/deliberation.py'], inputs['scripts/deliberation.py'])
            self.assertEqual(files['skills/hikmah/scripts/contracts.py'], inputs['scripts/contracts.py'])
            manifest_path = '.claude-plugin/plugin.json' if files is claude else 'plugin.json'
            manifest = json.loads(files[manifest_path])
            self.assertEqual(manifest['version'], meta['version'])
            self.assertEqual(manifest['repository'], meta['repository'])
        self.assertNotEqual(claude['skills/hikmah/references/host.md'], chatgpt['skills/hikmah/references/host.md'])
        self.assertEqual(json.loads(chatgpt['plugin.json'])['$schema'], project.SCHEMA_URL)

    def test_optional_verified_repository_propagates(self) -> None:
        self.edit_json('project.json', lambda doc: doc.update(repository='https://example.com/verified-project'))
        self.sync_marketplace()
        meta, inputs = project.validate(self.root)
        for host in project.HOSTS:
            files = project.package_files(host, meta, inputs)
            key = '.claude-plugin/plugin.json' if host == 'claude' else 'plugin.json'
            self.assertEqual(json.loads(files[key])['repository'], meta['repository'])
        for key in ('.claude-plugin/plugin.json', 'plugin.json'):
            path = self.root / project.PLUGIN_DIR / key
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['repository'], meta['repository'])

    def test_null_repository_is_omitted_from_manifests(self) -> None:
        self.edit_json('project.json', lambda doc: doc.update(repository=None))
        self.sync_marketplace()
        meta, inputs = project.validate(self.root)
        for host in (*project.HOSTS, project.UNIVERSAL):
            files = project.package_files(host, meta, inputs)
            for key in ('.claude-plugin/plugin.json', 'plugin.json'):
                if key in files:
                    self.assertNotIn('repository', json.loads(files[key]))

    def test_version_propagates_to_all_generated_outputs(self) -> None:
        self.edit_json('project.json', lambda doc: doc.update(version='1.2.3-rc.1+build.2'))
        with self.assertRaisesRegex(project.ProjectError, 'sync-marketplace'):
            project.validate(self.root)
        self.sync_marketplace()
        meta, inputs = project.validate(self.root)
        for key in ('.claude-plugin/plugin.json', 'plugin.json', 'skills/hikmah/references/build.json'):
            path = self.root / project.PLUGIN_DIR / key
            self.assertEqual(json.loads(path.read_text(encoding='utf-8'))['version'], meta['version'])
        output = project.render_outputs(meta, inputs)
        zips = [p for p in output if p.endswith('.zip')]
        self.assertEqual(len(zips), 5)
        self.assertTrue(all('1.2.3-rc.1+build.2' in p for p in zips))
        for host in project.HOSTS:
            info = json.loads(output[f'{host}-marketplace/plugins/hikmah/skills/hikmah/references/build.json'])
            self.assertEqual(info['version'], meta['version'])

    def test_unsupported_package_host_rejected(self) -> None:
        meta, inputs = project.validate(self.root)
        with self.assertRaisesRegex(project.ProjectError, 'unsupported host'):
            project.package_files('other', meta, inputs)

    def test_marketplace_paths_resolve_from_their_roots(self) -> None:
        project.build(self.root)
        for host, marker in (('claude', '.claude-plugin/marketplace.json'), ('chatgpt', '.agents/plugins/marketplace.json')):
            directory = self.root / 'dist' / f'{host}-marketplace'
            marketplace = json.loads((directory / marker).read_text(encoding='utf-8'))
            self.assertEqual(marketplace['name'], 'hikmah-local')
            self.assertEqual(len(marketplace['plugins']), 1)
            entry = marketplace['plugins'][0]
            source = entry['source'] if host == 'claude' else entry['source']['path']
            self.assertEqual(entry['name'], 'hikmah')
            self.assertEqual(source, './plugins/hikmah')
            self.assertTrue((directory / source / 'skills/hikmah/SKILL.md').is_file())
            if host == 'chatgpt':
                self.assertEqual(entry['policy'], {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'})

    def test_source_archive_contains_build_inputs_not_generated_state(self) -> None:
        project.build(self.root)
        with zipfile.ZipFile(self.root / 'dist/hikmah-1.0.0.zip') as z:
            files = {p: z.read(p) for p in z.namelist()}
        tree = {**project.source_inputs(self.root), **project.repository_inputs(self.root)}
        expected = {f'hikmah/{p}': data for p, data in tree.items()}
        self.assertEqual(files, expected)
        self.assertIn('hikmah/Makefile', files)
        self.assertIn('hikmah/.claude-plugin/marketplace.json', files)
        self.assertIn('hikmah/plugins/hikmah/skills/hikmah/SKILL.md', files)
        self.assertFalse(any('/dist/' in p or project.LOCK in p for p in files))

    def test_archive_format_is_reproducible_and_portable(self) -> None:
        data = project.archive({'b.md': b'b', 'a.md': b'a'})
        self.assertEqual(data, project.archive({'a.md': b'a', 'b.md': b'b'}))
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(z.namelist(), ['a.md', 'b.md'])
            for info in z.infolist():
                self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                self.assertEqual(info.external_attr >> 16, stat.S_IFREG | 0o644)
                self.assertFalse(info.is_dir())

    def test_build_verify_and_rebuild_agree(self) -> None:
        first = project.build(self.root)
        self.assertEqual(len(first), 5)
        self.assertEqual(project.verify(self.root), first)
        self.assertEqual(project.build(self.root), first)
        sums = (self.root / 'dist/SHA256SUMS').read_text(encoding='ascii').splitlines()
        self.assertEqual(len(sums), 5)
        for line in sums:
            value, name = line.split('  ')
            self.assertEqual(value, project.digest((self.root / 'dist' / name).read_bytes()))

    def test_license_is_preserved_byte_for_byte_in_both_packages(self) -> None:
        meta, inputs = project.validate(self.root)
        for host in project.HOSTS:
            self.assertEqual(project.package_files(host, meta, inputs)['LICENSE'], (ROOT / 'LICENSE').read_bytes())


class PublicMarketplaceTests(SourceCopy):
    def test_committed_marketplace_serves_both_hosts_from_one_plugin(self) -> None:
        meta, inputs = project.validate(self.root)
        claude = json.loads((self.root / project.CLAUDE_MARKETPLACE).read_text(encoding='utf-8'))
        codex = json.loads((self.root / project.CODEX_MARKETPLACE).read_text(encoding='utf-8'))
        for catalog in (claude, codex):
            self.assertEqual(catalog['name'], 'devsolux-hikmah')
            self.assertEqual([entry['name'] for entry in catalog['plugins']], ['hikmah'])
        self.assertEqual(claude['plugins'][0]['source'], './plugins/hikmah')
        # The plugin manifest alone owns the version; Claude warns when both declare one.
        self.assertNotIn('version', claude['plugins'][0])
        self.assertEqual(claude['owner'], meta['author'])
        self.assertEqual(codex['plugins'][0]['source'], {'source': 'local', 'path': './plugins/hikmah'})
        self.assertEqual(codex['plugins'][0]['policy'], {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'})
        plugin = self.root / project.PLUGIN_DIR
        for key in ('.claude-plugin/plugin.json', 'plugin.json'):
            manifest = json.loads((plugin / key).read_text(encoding='utf-8'))
            self.assertEqual((manifest['name'], manifest['version']), ('hikmah', meta['version']))
        self.assertEqual(json.loads((plugin / 'plugin.json').read_text(encoding='utf-8'))['$schema'], project.SCHEMA_URL)
        info = json.loads((plugin / 'skills/hikmah/references/build.json').read_text(encoding='utf-8'))
        self.assertEqual((info['host'], info['source_sha256']), (project.UNIVERSAL, project.fingerprint(inputs)))
        self.assertEqual((plugin / 'skills/hikmah/SKILL.md').read_bytes(), inputs['skills/hikmah/SKILL.md'])
        self.assertEqual(len(list((plugin / 'skills/hikmah/references/personas').glob('*.md'))), 99)
        host = (plugin / 'skills/hikmah/references/host.md').read_text(encoding='utf-8')
        self.assertEqual([line for line in host.splitlines() if line.startswith('# ')], ['# Host adapters'])
        self.assertIn('## Claude adapter', host)
        self.assertIn('## ChatGPT adapter', host)

    def test_documented_install_ids_match_marketplace_and_plugin_names(self) -> None:
        readme = (self.root / 'README.md').read_text(encoding='utf-8')
        for command in ('claude plugin marketplace add devsolux/hikmah',
                        'claude plugin install hikmah@devsolux-hikmah',
                        'codex plugin marketplace add devsolux/hikmah',
                        'codex plugin add hikmah@devsolux-hikmah'):
            self.assertIn(command, readme)
        self.assertNotIn('devsolux@hikmah', readme)

    def test_stale_marketplace_blocks_validate_build_and_cli(self) -> None:
        self.append('skills/hikmah/SKILL.md', '\nA deliberate skill clarification.\n')
        with self.assertRaisesRegex(project.ProjectError, r'stale: plugins/hikmah/skills/hikmah/SKILL\.md.*sync-marketplace'):
            project.validate(self.root)
        with self.assertRaisesRegex(project.ProjectError, 'sync-marketplace'):
            project.build(self.root)
        self.assertFalse((self.root / 'dist').exists())
        result = subprocess.run([sys.executable, '-B', '-I', str(self.root / 'scripts/project.py'), 'validate'],
                                cwd=self.root, capture_output=True, text=True, check=False, timeout=60)
        self.assertEqual(result.returncode, 2)
        self.assertIn('make sync-marketplace', result.stderr)
        self.assertNotIn('Traceback', result.stderr)
        self.assertIn('plugins/hikmah/skills/hikmah/SKILL.md', self.sync_marketplace())
        project.validate(self.root)

    def test_missing_marketplace_detected_and_recreated(self) -> None:
        shutil.rmtree(self.root / '.agents')
        (self.root / project.PLUGIN_DIR / 'plugin.json').unlink()
        with self.assertRaisesRegex(project.ProjectError, 'missing: .agents/plugins/marketplace.json'):
            project.validate(self.root)
        self.assertEqual(self.sync_marketplace(), [project.CODEX_MARKETPLACE, f'{project.PLUGIN_DIR}/plugin.json'])
        project.validate(self.root)

    def test_sync_is_idempotent_and_offline(self) -> None:
        before = project.repository_inputs(self.root)
        with patch('urllib.request.urlopen', side_effect=AssertionError('network forbidden')):
            self.assertEqual(self.sync_marketplace(), [])
        self.assertEqual(project.repository_inputs(self.root), before)
        self.assertFalse((self.root / 'dist').exists())

    def test_unrecognized_marketplace_file_is_preserved_not_overwritten(self) -> None:
        extra = self.root / project.PLUGIN_DIR / 'notes.md'
        extra.write_text('maintainer notes\n', encoding='utf-8')
        self.append('skills/hikmah/SKILL.md', '\nAnother clarification.\n')
        before = project.repository_inputs(self.root)
        with self.assertRaisesRegex(project.ProjectError, 'unrecognized: plugins/hikmah/notes.md'):
            project.validate(self.root)
        with self.assertRaisesRegex(project.ProjectError, 'unrecognized public-marketplace files: plugins/hikmah/notes.md'):
            self.sync_marketplace()
        self.assertEqual(project.repository_inputs(self.root), before)
        self.assertFalse((self.root / project.LOCK).exists())

    def test_os_metadata_in_marketplace_is_ignored(self) -> None:
        (self.root / project.PLUGIN_DIR / '.DS_Store').write_bytes(b'\x00\x01')
        project.validate(self.root)
        self.assertEqual(self.sync_marketplace(), [])

    def test_sync_never_follows_marketplace_symlinks(self) -> None:
        outside = self.root.parent / 'outside.md'
        outside.write_text('outside\n', encoding='utf-8')
        path = self.root / project.PLUGIN_DIR / 'README.md'
        path.unlink()
        self.symlink(path, outside)
        for command in (project.validate, project.sync_marketplace):
            with self.assertRaisesRegex(project.ProjectError, 'symlink'):
                command(self.root)
        self.assertEqual(outside.read_text(encoding='utf-8'), 'outside\n')

    def test_sync_refuses_existing_lock(self) -> None:
        (self.root / project.LOCK).mkdir()
        with self.assertRaisesRegex(project.ProjectError, 'already exists'):
            self.sync_marketplace()
        self.assertTrue((self.root / project.LOCK).is_dir())

    def test_marketplace_name_must_be_a_slug(self) -> None:
        for value in ('Devsolux Hikmah', '', 'devsolux_hikmah', None):
            with self.subTest(value=value):
                self.edit_json('project.json', lambda doc: doc.update(marketplace=value))
                with self.assertRaisesRegex(project.ProjectError, 'marketplace'):
                    project.validate(self.root)

    def test_extracted_source_archive_validates_without_sync(self) -> None:
        project.build(self.root)
        extracted = self.root.parent / 'extracted'
        with zipfile.ZipFile(self.root / 'dist/hikmah-1.0.0.zip') as z:
            z.extractall(extracted)
        meta, _ = project.validate(extracted / 'hikmah')
        self.assertEqual(meta['marketplace'], 'devsolux-hikmah')


class SafeOutputTests(SourceCopy):
    def test_verify_before_build_fails(self) -> None:
        with self.assertRaisesRegex(project.ProjectError, 'dist is missing'):
            project.verify(self.root)
        self.assertFalse((self.root / project.LOCK).exists())

    def test_safe_clean_is_idempotent_and_preserves_source_and_local_state(self) -> None:
        self.assertFalse(project.clean(self.root))
        before = project.source_inputs(self.root)
        (self.root / 'scratch').mkdir()
        local = self.root / 'scratch/notes.txt'
        local.write_text('retain me\n', encoding='utf-8')
        project.build(self.root)
        self.assertTrue(project.clean(self.root))
        self.assertFalse(project.clean(self.root))
        self.assertFalse((self.root / 'dist').exists())
        self.assertEqual(project.source_inputs(self.root), before)
        self.assertEqual(local.read_text(encoding='utf-8'), 'retain me\n')

    def test_unmanaged_output_preserved_by_build_and_clean(self) -> None:
        directory = self.root / 'dist'
        directory.mkdir()
        file = directory / 'my-work.txt'
        file.write_text('keep me\n', encoding='utf-8')
        for command in (project.build, project.clean):
            with self.assertRaisesRegex(project.ProjectError, 'unmanaged dist'):
                command(self.root)
            self.assertEqual(file.read_text(encoding='utf-8'), 'keep me\n')

    def test_modified_output_preserved_by_build_clean_and_verify(self) -> None:
        project.build(self.root)
        path = self.root / 'dist/chatgpt-marketplace/plugins/hikmah/README.md'
        path.write_text('manual change\n', encoding='utf-8')
        for command in (project.build, project.clean, project.verify):
            with self.assertRaisesRegex(project.ProjectError, 'changed or unowned'):
                command(self.root)
            self.assertEqual(path.read_text(encoding='utf-8'), 'manual change\n')

    def test_unowned_nested_marker_and_os_metadata_preserved(self) -> None:
        project.build(self.root)
        for name in (f'chatgpt-marketplace/{project.MARKER}', '.DS_Store'):
            path = self.root / 'dist' / name
            path.write_bytes(b'user-owned')
            for command in (project.build, project.clean):
                with self.assertRaisesRegex(project.ProjectError, 'changed or unowned'):
                    command(self.root)
            self.assertEqual(path.read_bytes(), b'user-owned')
            path.unlink()

    def test_unowned_empty_directory_preserved(self) -> None:
        project.build(self.root)
        path = self.root / 'dist/private-empty-folder'
        path.mkdir()
        for command in (project.build, project.clean):
            with self.assertRaisesRegex(project.ProjectError, 'unowned directories'):
                command(self.root)
        self.assertTrue(path.is_dir())

    def test_deleted_generated_file_detected(self) -> None:
        project.build(self.root)
        (self.root / 'dist/SHA256SUMS').unlink()
        with self.assertRaisesRegex(project.ProjectError, 'changed or unowned'):
            project.verify(self.root)

    def test_tampered_checksum_list_is_not_accepted(self) -> None:
        project.build(self.root)
        (self.root / 'dist/SHA256SUMS').write_text('0  fake.zip\n', encoding='ascii')
        with self.assertRaisesRegex(project.ProjectError, 'changed or unowned'):
            project.verify(self.root)

    def test_stale_build_detected_and_rebuild_updates_it(self) -> None:
        first = project.build(self.root)
        self.append('README.md', '\nA relevant documentation update.\n')
        self.sync_marketplace()
        with self.assertRaisesRegex(project.ProjectError, 'dist is stale'):
            project.verify(self.root)
        second = project.build(self.root)
        self.assertNotEqual(first, second)
        self.assertEqual(project.verify(self.root), second)

    def test_clean_does_not_require_unchanged_or_valid_source(self) -> None:
        project.build(self.root)
        self.edit_json('project.json', lambda doc: doc.update(version='invalid'))
        self.assertTrue(project.clean(self.root))
        self.assertFalse((self.root / 'dist').exists())

    def test_output_symlink_never_followed(self) -> None:
        target = self.root.parent / 'outside-output'
        target.mkdir()
        file = target / 'keep.txt'
        file.write_text('outside\n', encoding='utf-8')
        self.symlink(self.root / 'dist', target, directory=True)
        for command in (project.build, project.clean):
            with self.assertRaisesRegex(project.ProjectError, 'safe directory'):
                command(self.root)
        self.assertEqual(file.read_text(encoding='utf-8'), 'outside\n')

    def test_generated_file_symlink_rejected(self) -> None:
        project.build(self.root)
        path = self.root / 'dist/SHA256SUMS'
        path.unlink()
        self.symlink(path, self.root / 'README.md')
        for command in (project.build, project.clean):
            with self.assertRaisesRegex(project.ProjectError, 'symlink'):
                command(self.root)

    def test_marker_symlink_rejected(self) -> None:
        project.build(self.root)
        path = self.root / 'dist' / project.MARKER
        path.unlink()
        self.symlink(path, self.root / 'project.json')
        with self.assertRaisesRegex(project.ProjectError, 'unmanaged'):
            project.clean(self.root)

    def test_lock_prevents_competing_output_commands(self) -> None:
        with project.output_lock(self.root):
            marker = (self.root / project.LOCK / 'owner.json').read_bytes()
            for command in (project.build, project.clean, project.verify):
                with self.assertRaisesRegex(project.ProjectError, 'already exists'):
                    command(self.root)
            self.assertEqual((self.root / project.LOCK / 'owner.json').read_bytes(), marker)
        self.assertFalse((self.root / project.LOCK).exists())

    def test_invalid_source_leaves_prior_build_unchanged_and_releases_lock(self) -> None:
        project.build(self.root)
        before = (self.root / 'dist/SHA256SUMS').read_bytes()
        self.edit_json('project.json', lambda doc: doc.update(version='invalid'))
        with self.assertRaises(project.ProjectError):
            project.build(self.root)
        self.assertEqual((self.root / 'dist/SHA256SUMS').read_bytes(), before)
        self.assertFalse((self.root / project.LOCK).exists())
        self.assertEqual(list(self.root.glob('.hikmah-stage-*')), [])

    def test_source_changes_during_build_abort_without_replacing_output(self) -> None:
        project.build(self.root)
        before = (self.root / 'dist/SHA256SUMS').read_bytes()
        render = project.render_outputs
        def change_source(meta: object, inputs: object) -> dict[str, bytes]:
            result = render(meta, inputs)
            self.append('README.md', '\nConcurrent source change.\n')
            return result
        with patch.object(project, 'render_outputs', side_effect=change_source):
            with self.assertRaisesRegex(project.ProjectError, 'source changed'):
                project.build(self.root)
        self.assertEqual((self.root / 'dist/SHA256SUMS').read_bytes(), before)
        self.assertEqual(list(self.root.glob('.hikmah-stage-*')), [])

    def test_replacement_failure_restores_previous_build(self) -> None:
        project.build(self.root)
        before = (self.root / 'dist/SHA256SUMS').read_bytes()
        replace = os.replace
        def fail_new(source: object, destination: object) -> None:
            if Path(source).name == 'new':
                raise OSError('simulated replacement failure')
            replace(source, destination)
        with patch.object(project.os, 'replace', side_effect=fail_new), self.assertRaises(OSError):
            project.build(self.root)
        self.assertEqual((self.root / 'dist/SHA256SUMS').read_bytes(), before)
        project.check_owned_output(self.root / 'dist', required=True)
        self.assertEqual(list(self.root.glob('.hikmah-stage-*')), [])

    def test_failed_rollback_preserves_recovery_directory(self) -> None:
        project.build(self.root)
        before = (self.root / 'dist/SHA256SUMS').read_bytes()
        replace = os.replace
        def fail_new_and_restore(source: object, destination: object) -> None:
            if Path(source).name in ('new', 'previous'):
                raise OSError('simulated filesystem failure')
            replace(source, destination)
        with patch.object(project.os, 'replace', side_effect=fail_new_and_restore):
            with self.assertRaisesRegex(project.ProjectError, 'preserved at'):
                project.build(self.root)
        stages = list(self.root.glob('.hikmah-stage-*'))
        self.assertEqual(len(stages), 1)
        self.assertEqual((stages[0] / 'previous/SHA256SUMS').read_bytes(), before)
        self.assertFalse((self.root / project.LOCK).exists())

    def test_clean_does_not_delete_unknown_recovery_directory(self) -> None:
        path = self.root / '.hikmah-stage-recovery'
        path.mkdir()
        (path / 'notes.txt').write_text('preserve recovery\n', encoding='utf-8')
        project.clean(self.root)
        self.assertTrue((path / 'notes.txt').exists())


class CliTests(SourceCopy):
    def run_cli(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, '-B', '-I', str(self.root / 'scripts/project.py'), *args],
                              cwd=cwd or self.root, capture_output=True, text=True, check=False, timeout=30)

    def test_info_from_another_working_directory(self) -> None:
        result = self.run_cli('info', cwd=self.root.parent)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual((value['display_name'], value['version'], value['agent_count']), ('Hikmah', '1.0.0', 1))

    def test_doctor_reports_environment_without_claiming_desktop_tests(self) -> None:
        result = self.run_cli('doctor')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['desktop_clients_tested'])

    def test_obsolete_or_unknown_commands_and_flags_rejected(self) -> None:
        for args in (('plan',), ('list',), ('build', '--force'), ('clean', '--force')):
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn('Traceback', result.stderr)

    def test_invalid_source_reports_nonzero_without_traceback(self) -> None:
        self.edit_json('project.json', lambda doc: doc.update(supported_hosts=['unsupported']))
        result = self.run_cli('build')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Hikmah project error:', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_missing_required_source_reports_actionable_error(self) -> None:
        (self.root / 'Makefile').unlink()
        result = self.run_cli('validate')
        self.assertEqual(result.returncode, 2)
        self.assertIn('Makefile', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_help_and_clean_do_not_build(self) -> None:
        for args in (('help',), ('clean',), ('clean',)):
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'dist').exists())


if __name__ == '__main__':
    unittest.main()
