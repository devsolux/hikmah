#!/usr/bin/env python3
"""Validate, build, verify, and safely clean Hikmah. Python 3.11+, standard library only."""
from __future__ import annotations

import argparse
import ast
from contextlib import contextmanager
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import sys
import tempfile
from typing import Any, Iterator
from urllib.parse import unquote, urlsplit
import zipfile

# Resolve only bundled helpers, including when Python is started with -I.
# Never add the caller's working directory or an environment search path.
SCRIPT_DIR = str(Path(__file__).resolve().parent)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from contracts import (HikmahError as ProjectError, MAX_FILE_BYTES, MAX_JSON_DEPTH,
                       MAX_INTEGER_DIGITS, require, exact_keys, text, decode_json,
                       json_bytes, digest, fingerprint, parse_frontmatter)
from deliberation import (validate_config, validate_persona, persona_metadata, persona_appendix,
                          split_persona_catalog, response_schema, CONTRIBUTION_SCHEMA_VERSION, validate_source, MAX_SEATS,
                          SOURCE_PATH)

ROOT = Path(__file__).resolve().parents[1]
HOSTS = ('claude', 'chatgpt')
# The committed public marketplace serves both hosts from one plugin directory.
UNIVERSAL = 'universal'
SCHEMA_URL = 'https://agent-plugins.org/schemas/1.0.0/plugin.schema.json'
# Generated, committed public-marketplace roots; refreshed only by sync-marketplace.
MARKETPLACE_ROOTS = ('.claude-plugin', '.agents', 'plugins')
CLAUDE_MARKETPLACE = '.claude-plugin/marketplace.json'
CODEX_MARKETPLACE = '.agents/plugins/marketplace.json'
PLUGIN_DIR = 'plugins/hikmah'
MARKER = '.hikmah-build.json'
OWNER = 'hikmah-build-v1'
LOCK = '.hikmah-build.lock'
MAX_TREE_BYTES = 32 * MAX_FILE_BYTES
ROOT_FILES = ('project.json', 'README.md', 'AGENTS.md', 'LICENSE', 'NOTICE.md',
              'Makefile', '.gitignore', '.gitattributes')
SOURCE_DIRS = ('agents', 'personas', 'config', 'examples', 'skills', 'adapters', 'scripts', 'tests', 'docs', 'sources')
LOCAL_ENTRIES = {'dist', LOCK, '.git', '.claude', '.venv', '.idea', '.vscode', 'tmp', 'scratch',
                 '__pycache__', '.pytest_cache', '.coverage', 'coverage',
                 '.DS_Store', '__MACOSX', 'Thumbs.db'}
GENERATED_REFS = {'skills/hikmah/references/coordinator.md',
                  'skills/hikmah/references/host.md', 'skills/hikmah/references/build.json',
                  'skills/hikmah/references/catalog.md', 'skills/hikmah/references/RUNTIME.md',
                  'skills/hikmah/references/DELIBERATION_LOGIC.md',
                  'skills/hikmah/scripts/deliberation.py', 'skills/hikmah/scripts/contracts.py'}
RESERVED_NAMES = {'con', 'prn', 'aux', 'nul', *[f'com{i}' for i in range(1, 10)],
                  *[f'lpt{i}' for i in range(1, 10)]}
SLUG = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*\Z')
NUMBER = r'(?:0|[1-9][0-9]*)'
PRERELEASE = rf'(?:{NUMBER}|[0-9]*[A-Za-z-][0-9A-Za-z-]*)'
SEMVER = re.compile(rf'{NUMBER}\.{NUMBER}\.{NUMBER}'
                    rf'(?:-{PRERELEASE}(?:\.{PRERELEASE})*)?'
                    r'(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?\Z')


def safe_path(name: str) -> None:
    """Require normalized paths that are portable to the supported desktop filesystems."""
    require(isinstance(name, str) and bool(name), 'empty or non-string path')
    path = PurePosixPath(name)
    require(bool(path.parts) and name == path.as_posix() and not path.is_absolute() and '..' not in path.parts,
            f'unsafe path: {name!r}')
    for part in path.parts:
        require(bool(re.fullmatch(r'[A-Za-z0-9_.+-]+', part)) and part not in ('.', '..')
                and not part.endswith('.') and part.split('.')[0].lower() not in RESERVED_NAMES,
                f'non-portable or unsafe path: {name!r}')


def check_paths(names: set[str]) -> None:
    seen: dict[str, str] = {}
    for name in sorted(names):
        safe_path(name)
        path = PurePosixPath(name)
        for item in [path, *[p for p in path.parents if str(p) != '.']]:
            label = item.as_posix()
            require(label.casefold() not in seen or seen[label.casefold()] == label,
                    f'case-insensitive path collision: {label}')
            seen[label.casefold()] = label
        require(not any(p.as_posix() in names for p in path.parents if str(p) != '.'),
                f'file/directory path collision: {name}')


def redirected(info: os.stat_result) -> bool:
    """Reject links and Windows reparse points, including directory junctions."""
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))


def ensure_root(root: Path) -> None:
    require(root.is_dir() and not redirected(root.lstat()), f'unsafe or missing project root: {root}')


def read_file(path: Path, limit: int = MAX_FILE_BYTES) -> bytes:
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and not redirected(info),
            f'non-regular file, symlink, or reparse point not allowed: {path}')
    require(info.st_size <= limit, f'file too large: {path}')
    data = path.read_bytes()
    require(len(data) <= limit, f'file too large: {path}')
    return data


def walk(directory: Path, *, source: bool = False) -> tuple[list[Path], set[str]]:
    require(directory.is_dir() and not redirected(directory.lstat()), f'unsafe or missing directory: {directory}')
    files: list[Path] = []
    directories: set[str] = set()
    def scan_error(error: OSError) -> None:
        raise ProjectError(f'cannot inspect directory: {error.filename or directory}: {error.strerror}') from error

    for current, dirs, names in os.walk(directory, followlinks=False, onerror=scan_error):
        kept: list[str] = []
        for name in sorted(dirs):
            path = Path(current) / name
            require(not redirected(path.lstat()), f'symlink or reparse point not allowed: {path}')
            if source and name in ('__pycache__', '.pytest_cache', '__MACOSX'):
                continue
            directories.add(path.relative_to(directory).as_posix())
            kept.append(name)
        dirs[:] = kept
        for name in sorted(names):
            path = Path(current) / name
            info = path.lstat()
            require(stat.S_ISREG(info.st_mode) and not redirected(info),
                    f'non-regular file, symlink, or reparse point not allowed: {path}')
            if source and (name in ('.DS_Store', 'Thumbs.db') or name.startswith('._') or name.endswith('.pyc')):
                continue
            files.append(path)
    return sorted(files), directories


def source_inputs(root: Path) -> dict[str, bytes]:
    ensure_root(root)
    for path in root.iterdir():
        name = path.name
        local = name in LOCAL_ENTRIES or name.startswith(('.hikmah-stage-', '.env', '._')) or name.endswith('.log')
        require(name in ROOT_FILES or name in SOURCE_DIRS or name in MARKETPLACE_ROOTS or local,
                f'unrecognized root entry: {name}; move local files to scratch/ or explicitly update source ownership')
    paths = [root / name for name in ROOT_FILES]
    for name in SOURCE_DIRS:
        paths.extend(walk(root / name, source=True)[0])
    require(len(paths) <= 1000, 'source inventory exceeds 1000 files')
    inputs: dict[str, bytes] = {}
    for path in paths:
        name = path.relative_to(root).as_posix()
        require(not path.name.startswith('.env') and path.suffix.lower() not in ('.pem', '.key', '.p12', '.pfx'),
                f'possible secret file in source inputs: {name}')
        require(path.parent == root or path.suffix in ('.md', '.json', '.py'), f'unsupported source file: {name}')
        data = read_file(path)
        try:
            data.decode('utf-8')
        except UnicodeError as exc:
            raise ProjectError(f'{name}: source must be UTF-8 text') from exc
        require(b'\r' not in data, f'{name}: source must use LF line endings; see .gitattributes')
        inputs[name] = data
    require(sum(map(len, inputs.values())) <= MAX_TREE_BYTES, 'source inventory is too large')
    check_paths(set(inputs))
    return dict(sorted(inputs.items()))


def outside_fences(raw: str, label: str) -> str:
    lines: list[str] = []
    fence: tuple[str, int] | None = None
    for line in raw.splitlines():
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', line)
        if match:
            mark, tail = match.groups()
            if fence is None:
                fence = (mark[0], len(mark))
            elif mark[0] == fence[0] and len(mark) >= fence[1] and not tail.strip():
                fence = None
            continue
        if fence is None:
            lines.append(line)
    require(fence is None, f'{label}: unclosed Markdown fence')
    return '\n'.join(lines)


def check_links(files: dict[str, bytes], virtual: set[str] | None = None) -> None:
    """Check inline local file links and code fences; no network or heading-anchor checks."""
    available = set(files) | (virtual or set())
    for name, data in files.items():
        if not name.endswith('.md'):
            continue
        content = outside_fences(data.decode('utf-8'), name)
        for target in re.findall(r'!?\[[^\]\n]+\]\(([^\s)]+)\)', content):
            try:
                parts = urlsplit(target)
            except ValueError as exc:
                raise ProjectError(f'{name}: malformed link URL') from exc
            if parts.scheme or parts.netloc:
                require(parts.scheme in ('https', 'http', 'mailto'), f'{name}: unsupported link scheme')
                continue
            if not parts.path:
                continue
            relative = unquote(parts.path)
            require(not relative.startswith('/') and '\\' not in relative, f'{name}: absolute or unsafe link')
            segments = list(PurePosixPath(name).parent.parts)
            for part in relative.split('/'):
                if part in ('', '.'):
                    continue
                if part == '..':
                    require(bool(segments), f'{name}: link escapes package')
                    segments.pop()
                else:
                    segments.append(part)
            resolved = '/'.join(segments)
            require(resolved in available or any(p.startswith(resolved + '/') for p in available),
                    f'{name}: missing local link target: {target}')


def https_url(value: Any, label: str) -> None:
    text(value, label, 2048)
    try:
        parsed = urlsplit(value)
        valid = (parsed.scheme == 'https' and bool(parsed.hostname) and parsed.port != 0
                 and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
                 and not any(c.isspace() or c == '\\' for c in value))
    except ValueError as exc:
        raise ProjectError(f'{label}: invalid HTTPS URL') from exc
    require(valid, f'{label}: use an HTTPS URL without credentials, query, or fragment')


def validate(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Validate sources, then refuse a stale or incomplete committed public marketplace."""
    project, inputs = validate_sources(root)
    check_marketplace(root, project, inputs)
    return project, inputs


def validate_sources(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, bytes]]:
    inputs = source_inputs(root)
    project = decode_json(inputs['project.json'].decode('utf-8'), 'project.json')
    exact_keys(project, {'schema_version', 'name', 'display_name', 'version', 'description', 'author',
                         'repository', 'marketplace', 'license', 'supported_hosts', 'keywords'}, 'project.json')
    require(type(project['schema_version']) is int and project['schema_version'] == 1, 'schema_version must be 1')
    require(project['name'] == 'hikmah' and project['display_name'] == 'Hikmah', 'identity must be Hikmah / hikmah')
    text(project['version'], 'version', 80)
    require(bool(SEMVER.fullmatch(project['version'])), 'version must be valid SemVer')
    text(project['description'], 'description', 500)
    exact_keys(project['author'], {'name', 'url'}, 'author')
    text(project['author']['name'], 'author name', 200)
    https_url(project['author']['url'], 'author URL')
    if project['repository'] is not None:
        https_url(project['repository'], 'repository')
    text(project['marketplace'], 'marketplace', 64)
    require(bool(SLUG.fullmatch(project['marketplace'])), 'marketplace must be a lowercase slug')
    require(project['license'] == 'MIT', 'license must match the supplied MIT attribution')
    require(project['supported_hosts'] == list(HOSTS), 'only claude and chatgpt are supported')
    keywords = project['keywords']
    require(isinstance(keywords, list) and 1 <= len(keywords) <= 20, 'keywords must be a non-empty array')
    for keyword in keywords:
        text(keyword, 'keyword', 64)
        require(bool(SLUG.fullmatch(keyword)), 'keyword must be a lowercase slug')
    require(len(set(keywords)) == len(keywords), 'duplicate keywords')

    require({p for p in inputs if p.startswith('agents/')} == {'agents/hikmah.md'},
            'exactly one agent is allowed: agents/hikmah.md')
    require({p for p in inputs if p.startswith('skills/')} == {'skills/hikmah/SKILL.md'},
            'exactly one skill source is allowed; reference resources are generated')
    require({p for p in inputs if p.startswith('adapters/')} == {'adapters/claude.md', 'adapters/chatgpt.md'},
            'exactly the Claude and ChatGPT adapters are required')
    require({p for p in inputs if p.startswith('scripts/')} == {'scripts/project.py', 'scripts/contracts.py', 'scripts/deliberation.py'},
            'only the deterministic project tools and approved runtime belong in scripts/')
    require({p for p in inputs if p.startswith('config/')} == {'config/panels.json'}, 'config/panels.json is the only panel source')
    config = decode_json(inputs['config/panels.json'].decode('utf-8'), 'panel config')
    validate_config(config)
    require({p for p in inputs if p.startswith('sources/')} == {SOURCE_PATH}, f'exactly the source table {SOURCE_PATH} is required')
    validate_source(config, inputs[SOURCE_PATH])
    require({p for p in inputs if p.startswith('personas/')} == {f'personas/{m}.md' for m in config['members']},
            'the complete 99-persona catalog must match its source files')
    used_references, methods = set(), set()
    for member in config['members']:
        name = f'personas/{member}.md'
        meta = validate_persona(inputs[name].decode('utf-8'), member, config)
        used_references.update(meta['reference_ids'])
        require(meta['reasoning_method'] not in methods, 'each persona must own a distinct reasoning method')
        methods.add(meta['reasoning_method'])
    require(used_references == set(config['references']), 'reference registry has unused entries')
    agent_meta, agent_body = parse_frontmatter(inputs['agents/hikmah.md'].decode('utf-8'), 'agents/hikmah.md')
    exact_keys(agent_meta, {'name', 'description'}, 'agent frontmatter')
    require(agent_meta['name'] == project['name'], 'agent name must be hikmah')
    text(agent_meta['description'], 'agent description')
    for heading in ('Role and authority', 'Decision brief before personas', 'Select and route the panel',
                    'Independence and execution gate', 'Round 1 — Blind-first positions',
                    'Round 2 — Direct cross-examination', 'Round 3 — Final positions',
                    'Verdict contract', 'Failure and stopping'):
        require(f'## {heading}\n' in agent_body, f'agent is missing section: {heading}')
    skill_meta, _ = parse_frontmatter(inputs['skills/hikmah/SKILL.md'].decode('utf-8'), 'skills/hikmah/SKILL.md')
    exact_keys(skill_meta, {'name', 'description', 'compatibility'}, 'skill frontmatter')
    require(skill_meta['name'] == project['name'], 'skill name must be hikmah')
    text(skill_meta['description'], 'skill description')
    text(skill_meta['compatibility'], 'skill compatibility', 500)
    require(len(inputs['skills/hikmah/SKILL.md'].splitlines()) < 500, 'skill must stay below 500 lines')
    for name, data in inputs.items():
        if name.endswith('.json'):
            decode_json(data.decode('utf-8'), name)
        if name.endswith('.py'):
            try:
                ast.parse(data.decode('utf-8'), filename=name, feature_version=(3, 11))
            except SyntaxError as exc:
                raise ProjectError(f'{name}: invalid Python 3.11 syntax: {exc.msg}') from exc
    for host in HOSTS:
        package_files(host, project, inputs)
    # Source docs may link into generated skill references and the committed marketplace.
    check_links(inputs, GENERATED_REFS | set(repository_files(project, inputs)))
    return project, inputs


def host_note(host: str, inputs: dict[str, bytes]) -> bytes:
    """Return one adapter, or both with demoted headings for the two-host package."""
    if host in HOSTS:
        return inputs[f'adapters/{host}.md']
    sections = ['# Host adapters\n\nThis package is shared by Claude and ChatGPT/Codex surfaces. Follow only the '
                'section for the surface that is actually running; neither section implies the other host is available.\n']
    for name in HOSTS:
        lines, fenced = [], False
        for line in inputs[f'adapters/{name}.md'].decode('utf-8').splitlines():
            fenced ^= bool(re.match(r'^ {0,3}(`{3,}|~{3,})', line))
            lines.append('#' + line if not fenced and re.match(r'#{1,5} ', line) else line)
        sections.append('\n'.join(lines) + '\n')
    return '\n'.join(sections).encode('utf-8')


def package_files(host: str, project: dict[str, Any], inputs: dict[str, bytes]) -> dict[str, bytes]:
    require(host in HOSTS or host == UNIVERSAL, f'unsupported host: {host}')
    files = {
        'skills/hikmah/SKILL.md': inputs['skills/hikmah/SKILL.md'],
        'skills/hikmah/references/coordinator.md': inputs['agents/hikmah.md'],
        'skills/hikmah/references/host.md': host_note(host, inputs),
        'skills/hikmah/references/build.json': json_bytes({
            'schema_version': 1, 'name': project['name'], 'display_name': project['display_name'],
            'version': project['version'], 'host': host, 'agent': 'hikmah',
            'agent_count': 1, 'persona_count': MAX_SEATS, 'protocol': 'blind-first-neighborhood-review-final', 'source_group_count': 1,
            'contribution_schema_version': CONTRIBUTION_SCHEMA_VERSION,
            'source_sha256': fingerprint(inputs)}),
        'LICENSE': inputs['LICENSE'],
        'NOTICE.md': inputs['NOTICE.md'],
    }
    require('docs/RUNTIME.md' in inputs, 'runtime documentation is required')
    config = decode_json(inputs['config/panels.json'].decode('utf-8'), 'panels')
    files['skills/hikmah/references/panels.json'] = inputs['config/panels.json']
    files[f'skills/hikmah/references/{SOURCE_PATH}'] = inputs[SOURCE_PATH]
    files['skills/hikmah/references/RUNTIME.md'] = inputs['docs/RUNTIME.md']
    files['skills/hikmah/references/DELIBERATION_LOGIC.md'] = inputs['docs/DELIBERATION_LOGIC.md']
    files['skills/hikmah/references/response-schema.json'] = json_bytes(response_schema())
    for script in ('contracts.py', 'deliberation.py'):
        files[f'skills/hikmah/scripts/{script}'] = inputs[f'scripts/{script}']
    catalog = '# Hikmah analytical personas\n\nOne coordinator assigns selected instruments to isolated seats. These are bounded human-level lenses, not divine entities or people participating.\n\n'
    for member in config['members']:
        data = inputs[f'personas/{member}.md']
        files[f'skills/hikmah/references/personas/{member}.md'] = data
        meta, _ = parse_frontmatter(data.decode('utf-8'), member)
        catalog += f'- [{meta["name"]}](personas/{member}.md): {meta["description"]}.\n'
    catalog += '\n[Panel presets, method references, and relation graph](panels.json). All modes retain three rounds.\n'
    catalog += '\n[Deliberation logic and reference boundaries](DELIBERATION_LOGIC.md).\n'
    catalog += '\n## Editorial method relationships\n\n'
    catalog += '| ID | Type | Methods | Shared question |\n|---|---|---|---|\n'
    for relation in config['relations']:
        a, b = relation['members']
        catalog += (f'| {relation["id"]} | {relation["kind"]} | [{a}](personas/{a}.md) / '
                    f'[{b}](personas/{b}.md) | {relation["question"]} |\n')
    catalog += ('\nThe graph is coordinator-facing. It does not enter blind-first requests. '
                'Provider separation uses tension edges; balanced reviews are assigned only after Round 1.\n')
    files['skills/hikmah/references/catalog.md'] = catalog.encode('utf-8')
    base = {key: project[key] for key in ('name', 'version', 'description', 'author', 'license', 'keywords')}
    if project['repository'] is not None:
        base['repository'] = project['repository']
    # Claude reads .claude-plugin/plugin.json; ChatGPT/Codex prefer the portable root plugin.json.
    if host in ('claude', UNIVERSAL):
        files['.claude-plugin/plugin.json'] = json_bytes({**base, 'displayName': project['display_name']})
    if host in ('chatgpt', UNIVERSAL):
        files['plugin.json'] = json_bytes({'$schema': SCHEMA_URL, **base, 'extensions': {'com.openai': {
            'interface': {'displayName': project['display_name'],
                          'shortDescription': 'Source-grounded decision deliberation.',
                          'developerName': project['author']['name'], 'category': 'Productivity',
                          'defaultPrompt': ['Use the Hikmah project to deliberate this decision with contrasting analytical lenses and preserve dissent in the recommendation.']}}}})
    label = 'Claude and ChatGPT' if host == UNIVERSAL else host.title()
    files['README.md'] = (f'# Hikmah {project["version"]} — {label} plugin\n\n'
        'One Hikmah coordinator, 99 DMG analytical lenses, blind-first positions, and direct cross-examination.\n\n'
        '- [Start Hikmah](skills/hikmah/SKILL.md)\n'
        '- [Coordinator protocol](skills/hikmah/references/coordinator.md)\n'
        '- [Persona catalog](skills/hikmah/references/catalog.md)\n'
        '- [Deliberation logic](skills/hikmah/references/DELIBERATION_LOGIC.md)\n'
        '- [Optional API runtime](skills/hikmah/references/RUNTIME.md)\n'
        '- [Host note](skills/hikmah/references/host.md)\n'
        '- [Build identity](skills/hikmah/references/build.json)\n'
        '- [Notices](NOTICE.md) and [license](LICENSE)\n\n'
        'This package includes persona resources and an optional Python runner. It registers no native subagents, '
        'MCP server, credentials, or permissions. Full deliberation requires real isolated execution; a '
        'successful build is not a live desktop, API, or model-quality test.\n').encode('utf-8')
    check_paths(set(files))
    check_links(files)
    return dict(sorted(files.items()))


def archive(files: dict[str, bytes]) -> bytes:
    check_paths(set(files))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return stream.getvalue()


def marketplace_manifest(host: str, project: dict[str, Any], name: str, display_name: str) -> bytes:
    """One marketplace entry for ./plugins/hikmah. The plugin manifest alone owns the version."""
    if host == 'claude':
        return json_bytes({'name': name, 'description': f'{display_name}: {project["description"]}',
                           'owner': project['author'], 'plugins': [{
                               'name': project['name'], 'source': f'./{PLUGIN_DIR}',
                               'description': project['description']}]})
    return json_bytes({'name': name, 'interface': {'displayName': display_name}, 'plugins': [{
        'name': project['name'], 'source': {'source': 'local', 'path': f'./{PLUGIN_DIR}'},
        'policy': {'installation': 'AVAILABLE', 'authentication': 'ON_INSTALL'}, 'category': 'Productivity'}]})


def repository_files(project: dict[str, Any], inputs: dict[str, bytes]) -> dict[str, bytes]:
    """Render the committed public marketplace: both host catalogs and one shared plugin."""
    files = {f'{PLUGIN_DIR}/{name}': data for name, data in package_files(UNIVERSAL, project, inputs).items()}
    files[CLAUDE_MARKETPLACE] = marketplace_manifest('claude', project, project['marketplace'], project['display_name'])
    files[CODEX_MARKETPLACE] = marketplace_manifest('chatgpt', project, project['marketplace'], project['display_name'])
    check_paths(set(files))
    check_links(files)
    return dict(sorted(files.items()))


def repository_inputs(root: Path) -> dict[str, bytes]:
    """Read the committed marketplace without following links; OS metadata is ignored."""
    files: dict[str, bytes] = {}
    for name in MARKETPLACE_ROOTS:
        path = root / name
        if not path.exists() and not path.is_symlink():
            continue
        for item in walk(path, source=True)[0]:
            files[item.relative_to(root).as_posix()] = read_file(item)
    require(len(files) <= 1000 and sum(map(len, files.values())) <= MAX_TREE_BYTES,
            'public marketplace is too large')
    return dict(sorted(files.items()))


def check_marketplace(root: Path, project: dict[str, Any], inputs: dict[str, bytes]) -> None:
    expected, actual = repository_files(project, inputs), repository_inputs(root)
    problems = {'missing': sorted(set(expected) - set(actual)),
                'stale': sorted(n for n in set(expected) & set(actual) if expected[n] != actual[n]),
                'unrecognized': sorted(set(actual) - set(expected))}
    detail = '; '.join(f'{kind}: {", ".join(names[:3])}{", ..." if len(names) > 3 else ""}'
                       for kind, names in problems.items() if names)
    require(not detail, f'committed public marketplace differs from sources ({detail}); run make sync-marketplace'
            + (' after moving unrecognized files elsewhere' if problems['unrecognized'] else ''))


def render_outputs(project: dict[str, Any], inputs: dict[str, bytes]) -> dict[str, bytes]:
    output: dict[str, bytes] = {}
    prefix = f'hikmah-{project["version"]}'
    for host in HOSTS:
        plugin = package_files(host, project, inputs)
        marketplace = {f'{PLUGIN_DIR}/{name}': data for name, data in plugin.items()}
        manifest_name = CLAUDE_MARKETPLACE if host == 'claude' else CODEX_MARKETPLACE
        marketplace[manifest_name] = marketplace_manifest(host, project, 'hikmah-local', 'Hikmah (local)')
        marketplace['README.md'] = (f'# Hikmah {project["version"]} — local {host.title()} marketplace\n\n'
            'Keep this root intact, including hidden metadata. The plugin is at '
            '[plugins/hikmah/README.md](plugins/hikmah/README.md).\n\n'
            'This is a local test/distribution layout, not a published directory listing. '
            'No host configuration has been modified.\n').encode('utf-8')
        check_links(marketplace)
        output.update({f'{host}-marketplace/{name}': data for name, data in marketplace.items()})
        output[f'{prefix}-{host}.zip'] = archive(plugin)
        output[f'{prefix}-{host}-marketplace.zip'] = archive(marketplace)
    # Source archive deliberately excludes dist but keeps the committed public marketplace,
    # so an extracted archive validates and remains installable as a repository.
    source_tree = {**inputs, **repository_files(project, inputs)}
    output[f'{prefix}.zip'] = archive({f'hikmah/{name}': data for name, data in source_tree.items()})
    releases = {name: digest(data) for name, data in output.items() if '/' not in name and name.endswith('.zip')}
    output['SHA256SUMS'] = ''.join(f'{value}  {name}\n' for name, value in sorted(releases.items())).encode('ascii')
    output[MARKER] = json_bytes({'owner': OWNER, 'files': {name: digest(data) for name, data in sorted(output.items())}})
    return dict(sorted(output.items()))


def check_owned_output(destination: Path, *, required: bool = False) -> dict[str, str]:
    if not destination.exists() and not destination.is_symlink():
        require(not required, 'dist is missing; run make build first')
        return {}
    require(destination.is_dir() and not redirected(destination.lstat()), 'dist is not a safe directory')
    marker = destination / MARKER
    require(marker.is_file() and not marker.is_symlink(), 'refusing unmanaged dist; preserve its contents elsewhere first')
    previous = decode_json(read_file(marker).decode('utf-8'), MARKER)
    exact_keys(previous, {'owner', 'files'}, 'build ownership marker')
    require(previous['owner'] == OWNER and isinstance(previous['files'], dict) and bool(previous['files']),
            'unrecognized build ownership marker')
    expected = previous['files']
    require(len(expected) <= 1000 and MARKER not in expected, 'invalid ownership inventory')
    check_paths(set(expected))
    require(all(isinstance(v, str) and re.fullmatch(r'[0-9a-f]{64}', v) for v in expected.values()),
            'invalid ownership hash')
    files, actual_dirs = walk(destination)
    expected_dirs = {p.as_posix() for name in expected for p in PurePosixPath(name).parents if str(p) != '.'}
    require(actual_dirs == expected_dirs, 'dist contains changed or unowned directories; preserve them before cleanup or rebuilding')
    actual = {p.relative_to(destination).as_posix(): digest(read_file(p, MAX_TREE_BYTES))
              for p in files if p != marker}
    require(actual == expected, 'dist contains changed or unowned files; preserve them before cleanup or rebuilding')
    return expected


@contextmanager
def output_lock(root: Path) -> Iterator[None]:
    """Serialize cooperating build, verify, and clean commands; never break an existing lock."""
    ensure_root(root)
    lock = root / LOCK
    try:
        lock.mkdir()
    except FileExistsError as exc:
        raise ProjectError(f'{LOCK} already exists; another command may be running. See docs/BUILD.md for recovery.') from exc
    try:
        (lock / 'owner.json').write_bytes(json_bytes({'pid': os.getpid(), 'operation': 'generated-output'}))
        yield
    finally:
        # Only remove files created by this invocation; an unexpected entry is preserved.
        (lock / 'owner.json').unlink(missing_ok=True)
        lock.rmdir()


def build(root: Path = ROOT) -> dict[str, str]:
    with output_lock(root):
        project, inputs = validate(root)
        destination = root / 'dist'
        check_owned_output(destination)
        output = render_outputs(project, inputs)
        stage = Path(tempfile.mkdtemp(prefix='.hikmah-stage-', dir=root))
        preserve_stage = False
        try:
            staged, previous = stage / 'new', stage / 'previous'
            staged.mkdir()
            for name, data in output.items():
                path = staged.joinpath(*PurePosixPath(name).parts)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            require(source_inputs(root) == inputs, 'source changed during build; retry after finishing edits')
            check_owned_output(destination)
            if destination.exists():
                os.replace(destination, previous)
            try:
                os.replace(staged, destination)
            except OSError as install_error:
                if previous.exists():
                    try:
                        os.replace(previous, destination)
                    except OSError as restore_error:
                        preserve_stage = True
                        raise ProjectError(f'output replacement and rollback failed; previous output is preserved at {previous}. '
                                           f'Replacement: {install_error}; rollback: {restore_error}') from restore_error
                raise
        finally:
            if not preserve_stage:
                shutil.rmtree(stage)
        return {name: digest(data) for name, data in output.items() if '/' not in name and name.endswith('.zip')}


def verify(root: Path = ROOT) -> dict[str, str]:
    with output_lock(root):
        recorded = check_owned_output(root / 'dist', required=True)
        project, inputs = validate(root)
        expected = render_outputs(project, inputs)
        expected_hashes = {name: digest(data) for name, data in expected.items() if name != MARKER}
        require(recorded == expected_hashes, 'dist is stale for the current sources; run make build')
        require(source_inputs(root) == inputs, 'source changed during verification; retry after finishing edits')
        check_owned_output(root / 'dist', required=True)
        return {name: value for name, value in recorded.items() if '/' not in name and name.endswith('.zip')}


def clean(root: Path = ROOT) -> bool:
    with output_lock(root):
        destination = root / 'dist'
        if not destination.exists() and not destination.is_symlink():
            return False
        check_owned_output(destination, required=True)
        # All descendants, including normally hidden metadata and empty directories,
        # were checked. There is deliberately no force option or broad rm command.
        shutil.rmtree(destination)
        return True


def sync_personas(root: Path = ROOT) -> list[str]:
    """Explicitly regenerate only marked appendices, preserving all authored method text.

    Preflight the complete source and markers before writing. Each replacement is
    atomic; interrupted multi-file synchronization is recoverable by rerunning it.
    A subsequent validate/build refuses any stale appendix. No network is used.
    """
    with output_lock(root):
        inputs = source_inputs(root)
        config = decode_json(inputs['config/panels.json'].decode('utf-8'), 'panel config')
        validate_config(config)
        validate_source(config, inputs[SOURCE_PATH])
        expected = {f'personas/{m}.md' for m in config['members']}
        require({p for p in inputs if p.startswith('personas/')} == expected, 'the complete 99-persona catalog is required')
        updates = {}
        for member in config['members']:
            name = f'personas/{member}.md'
            raw = inputs[name].decode('utf-8')
            meta = persona_metadata(raw, member, config)
            core, _ = split_persona_catalog(raw)
            revised = (core + persona_appendix(config, member, meta['reference_ids'])).encode('utf-8')
            if revised != inputs[name]:
                updates[name] = revised
        with tempfile.TemporaryDirectory(prefix='.hikmah-stage-', dir=root) as temporary:
            stage = Path(temporary)
            for name, data in updates.items():
                (stage / Path(name).name).write_bytes(data)
            require(source_inputs(root) == inputs, 'source changed during persona synchronization')
            for name, data in updates.items():
                require(read_file(root / name) == inputs[name], 'persona changed during synchronization')
                require(read_file(root / 'config/panels.json') == inputs['config/panels.json'],
                        'catalog changed during synchronization')
                os.replace(stage / Path(name).name, root / name)
            require(source_inputs(root) == {**inputs, **updates}, 'source changed during persona synchronization')
        return list(updates)


def sync_marketplace(root: Path = ROOT) -> list[str]:
    """Explicitly regenerate the committed public marketplace from validated sources.

    Only known generated paths are written, each atomically. Unrecognized files are
    preserved and stop the command before any write. Links are never followed.
    """
    with output_lock(root):
        project, inputs = validate_sources(root)
        expected, current = repository_files(project, inputs), repository_inputs(root)
        unknown = sorted(set(current) - set(expected))
        require(not unknown, 'refusing to overwrite or remove unrecognized public-marketplace files: '
                + ', '.join(unknown[:5]) + ('' if len(unknown) <= 5 else ', ...') + '; move them elsewhere first')
        updates = {name: data for name, data in expected.items() if current.get(name) != data}
        with tempfile.TemporaryDirectory(prefix='.hikmah-stage-', dir=root) as temporary:
            stage = Path(temporary)
            staged = {}
            for index, (name, data) in enumerate(sorted(updates.items())):
                staged[name] = stage / f'{index}.tmp'
                staged[name].write_bytes(data)
            require(source_inputs(root) == inputs and repository_inputs(root) == current,
                    'source changed during marketplace synchronization')
            for name, path in staged.items():
                target = root.joinpath(*PurePosixPath(name).parts)
                for parent in reversed(PurePosixPath(name).parents[:-1]):
                    directory = root.joinpath(*parent.parts)
                    if directory.exists() or directory.is_symlink():
                        require(directory.is_dir() and not redirected(directory.lstat()),
                                f'unsafe public-marketplace directory: {parent}')
                    else:
                        directory.mkdir()
                os.replace(path, target)
        require(repository_inputs(root) == expected, 'public marketplace changed during synchronization')
        return sorted(updates)


def help_text() -> str:
    return '''Hikmah project commands (run from the source root)
  make help       Show this command list (default)
  make doctor     Check Python and report the local environment
  make info       Show validated product and single-agent identity
  make validate   Validate sources and both in-memory plugin packages
  make detect     Inspect optional API configuration offline (no secrets printed)
  make plan       Preview the example brief and default panel; never runs a model
  make audit PACKET=file.json  Re-derive a saved packet offline; consistency, not truth
  make runtime-help  Show the optional runtime CLI and explicit network flags
  make sync-personas  Refresh marked Relations/References from the canonical catalog
  make sync-marketplace  Refresh the committed public marketplace (.claude-plugin, .agents, plugins)
  make test       Run dependency-free regression tests
  make check      Validate, then test
  make build      Build both plugins, both marketplaces, and the source ZIP
  make verify     Check generated integrity and freshness against current sources
  make clean      Remove only intact, owned dist output; safe to repeat
  make rebuild    Clean, validate, test, build, and verify (serially)
  make all        Validate, test, build, and verify
  make release    Same local checks/artifacts as all; does not publish

Override the interpreter with make PYTHON=python (or PYTHON="py -3").
Without Make: python scripts/project.py <command>.
Tests: python -B -m unittest discover -s tests -v.
Build/test/plan: Python 3.11+, no dependencies, keys, or network. Optional API runs require explicit authorization.'''


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('help', 'doctor', 'info', 'validate', 'build', 'verify', 'clean',
                                            'sync-personas', 'sync-marketplace'))
    args = parser.parse_args(argv)
    try:
        require(sys.version_info >= (3, 11), 'Python 3.11 or later is required')
        if args.command == 'help':
            print(help_text())
        elif args.command == 'doctor':
            print(json.dumps({'python': platform.python_version(), 'executable': sys.executable,
                              'platform': platform.platform(), 'make': shutil.which('make'),
                              'dependencies': 'standard library only', 'desktop_clients_tested': False}, indent=2))
        elif args.command == 'sync-personas':
            print(json.dumps({'updated_personas': sync_personas(), 'network_used': False}, indent=2))
        elif args.command == 'sync-marketplace':
            print(json.dumps({'updated_files': sync_marketplace(), 'network_used': False}, indent=2))
        elif args.command == 'clean':
            print('Removed owned dist output.' if clean() else 'Nothing to clean: dist is absent.')
        elif args.command in ('build', 'verify'):
            result = build() if args.command == 'build' else verify()
            print(json.dumps({'project': 'Hikmah', 'operation': args.command, 'output': 'dist', 'sha256': result}, indent=2))
        else:
            project, inputs = validate()
            if args.command == 'info':
                print(json.dumps({**project, 'agent': 'hikmah', 'agent_count': 1, 'persona_count': MAX_SEATS,
                                  'source_sha256': fingerprint(inputs)}, indent=2))
            else:
                print(f'Valid: Hikmah {project["version"]}; one coordinator; 99 personas; Claude and ChatGPT packages '
                      f'and the {project["marketplace"]} public marketplace checked.')
    except (OSError, UnicodeError, ProjectError, zipfile.BadZipFile) as exc:
        print(f'Hikmah project error: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
