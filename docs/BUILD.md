# Build and release

Run from the extracted `hikmah/` source root. Python 3.11+ is required; GNU Make is
optional. There are no pip dependencies and no build-time network or API calls.

```sh
make doctor
make all
make verify
```

`make all` serially validates, tests, builds, and verifies. `.NOTPARALLEL` prevents
clean/build races under `make -j`. `make rebuild` cleans only owned intact output,
then performs the same full pipeline. `make release` creates local files only; it
does not upload, publish, install, register a plugin, or modify client configuration.

## Outputs

| File in dist/ | Contents |
|---|---|
| `hikmah-1.0.0.zip` | Complete source under `hikmah/`, including the committed public marketplace and excluding generated dist/ |
| `hikmah-1.0.0-claude.zip` | Claude plugin at archive root |
| `hikmah-1.0.0-chatgpt.zip` | Portable ChatGPT plugin at archive root |
| `hikmah-1.0.0-claude-marketplace.zip` | Claude marketplace plus plugin directory |
| `hikmah-1.0.0-chatgpt-marketplace.zip` | ChatGPT local marketplace plus plugin directory |
| `SHA256SUMS` | Release ZIP SHA-256 checksums |
| `claude-marketplace/`, `chatgpt-marketplace/` | Unpacked copies of the two marketplace ZIPs (`hikmah-local`) |

The output directory also contains its private ownership/integrity marker. Each
plugin includes one skill, one coordinator resource, all 99 profiles, the canonical
catalog, exact source table, runtime and schema, and source fingerprint metadata.
It registers no native subagents, automatic hooks, network service, or permissions.

## Committed public marketplace

The repository root doubles as the public `devsolux-hikmah` marketplace:
`.claude-plugin/marketplace.json` (Claude Code), `.agents/plugins/marketplace.json`
(Codex), and one shared plugin directory, `plugins/hikmah/`. These files are generated,
committed, and never hand-edited. `make sync-marketplace` writes them from validated
sources, atomically per file. It refuses symlinks, an existing lock, and unrecognized
files inside those roots; it preserves such files and stops before writing anything.

Validation, build, verify, and `make github-push` fail when the committed copy is
missing, stale, or contains unrecognized files. The plugin's `build.json` records the
whole-source fingerprint, so any source edit requires `make sync-marketplace`. That
check keeps a stale marketplace from ever reaching public installs.

## Integrity and cleanup

Archives are deterministic: sorted paths, fixed ZIP timestamps, controlled permissions,
and content-derived fingerprints. Rebuilding unchanged source on the same supported
tooling should reproduce bytes; compression-library changes can affect ZIP bytes and
must not be misrepresented as source changes.

Builds stage all files, verify expected names and hashes, acquire an ownership lock,
and replace only verified owned output. Unknown or modified dist/ is preserved, not
overwritten. On replacement failure the builder attempts rollback and retains
recoverable material if rollback itself fails. `make clean` is safe to repeat and
refuses unknown, changed, linked, or unowned output. Never suggest a blind recursive
removal to get past a safeguard. Inspect and preserve the unexpected files first.

Validation rejects source symlinks/reparse points, unsafe paths, duplicate/case-colliding
archive names, oversized files, binary/non-UTF-8 source, stale generated appendices,
broken local links, malformed strict JSON/frontmatter, wrong product/host resources,
and source-provenance mismatches. Local state and `.env` are not packaged. Source
files need LF line endings; the original supplied table already uses that representation.

Hashes are not digital signatures. Cooperative locks and path checks are not a sandbox
against a malicious actor racing filesystem changes. Use a controlled build directory.

## Interrupted-operation lock recovery

The tools never remove an existing `.hikmah-build.lock` automatically. A process
termination can leave its `owner.json` behind. Inspect that file, confirm the named
operation has stopped, and ensure no other build, verification, synchronization, or
cleanup command is using this exact tree. A PID alone is not proof: it may have been
reused or the directory may have come from another machine. Do not break a live or
uncertain lock.

Only after establishing that the known local lock is stale, preserve its owner record
outside the source tree, remove that known `owner.json`, and remove the now-empty lock
directory. Do not recursively delete a lock containing unexpected files. Keep any
staging/recovery directories and their contents until they have been inspected. Then
rerun `make verify`; use `make build` when source changes legitimately made output
stale. A modified or unowned output remains protected and needs separate inspection.

## Authored and generated files

Edit methods in personas/ and relations/presets/reference scope in config/panels.json.
Run `make sync-personas` to refresh only marked reference/relationship appendices,
then `make sync-marketplace`; ordinary validation never silently modifies source. Multi-file synchronization is
preflighted with atomic per-file replacement, not a whole-tree transaction. An
interruption may leave stale appendices; rerun synchronization and validate.

Keep the preserved source bytes intact. Translation or doctrine corrections require
a separately attributed source revision and explicit review, not a search-and-replace.
The current product version remains 1.0.0; compare source fingerprints for revisions.

## Without GNU Make

```sh
python scripts/project.py doctor
python -B scripts/project.py sync-marketplace
python -B scripts/project.py validate
python -B -m unittest discover -s tests -v
python -B scripts/project.py build
python -B scripts/project.py verify
python -B scripts/project.py clean
```

On Windows use your available Python 3.11+ launcher and direct commands, or provide
`make PYTHON=python`. Tests inspect Python 3.11 syntax; a live interpreter/platform
matrix must be run separately when claiming support beyond the tested environment.
