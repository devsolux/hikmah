# Claude and ChatGPT compatibility

Documentation checked: **2026-10-11**. Product **Hikmah 1.0.0** targets packaged skill
plugin surfaces in Claude and ChatGPT only, including Claude Code and Codex. Exact
desktop build numbers, account entitlements, and workspace permissions were not verified.
The formats are build targets, not a guarantee that every desktop chat mode accepts them.

## Public marketplace (recommended)

The repository root is a marketplace named `devsolux-hikmah` for both hosts. It lists
one plugin, `hikmah`, so the install ID is `hikmah@devsolux-hikmah` (plugin, then marketplace).

| Host | Catalog file | Commands |
|---|---|---|
| Claude Code | `.claude-plugin/marketplace.json` | `claude plugin marketplace add devsolux/hikmah`, then `claude plugin install hikmah@devsolux-hikmah` |
| Codex | `.agents/plugins/marketplace.json` | `codex plugin marketplace add devsolux/hikmah`, then `codex plugin add hikmah@devsolux-hikmah` |

Both catalogs use the relative source `./plugins/hikmah`. That one committed plugin
directory carries `.claude-plugin/plugin.json` for Claude and the portable root
`plugin.json` for ChatGPT/Codex, plus a combined host note with one section per host.
When both catalogs exist, Codex reads `.agents/plugins/marketplace.json`. Only the
plugin manifest declares the version; the Claude catalog entry deliberately omits it.

`make sync-marketplace` generates these files from source, and validation, build, and
`make github-push` refuse a stale or incomplete copy. Because the version stays 1.0.0,
hosts do not treat a newer commit as an update; refresh the marketplace and reinstall
(see the README), then compare the installed `references/build.json` fingerprint.

## Claude

The plugin ZIP contains `.claude-plugin/plugin.json` and `skills/hikmah/SKILL.md` at
archive root. The documented upload path is **Customize > Plugins > Add > Upload plugin**;
select the Claude plugin ZIP when this is permitted in your account. A separate Claude marketplace ZIP
contains `.claude-plugin/marketplace.json` and `plugins/hikmah/` for a local test
marketplace named `hikmah-local`. It is not the plugin ZIP to select in Upload plugin.
Claude's account-based Add marketplace flow expects a supported Git repository, which
the public repository provides; a local path is a separate Claude Code workflow.
The build itself creates neither a repository nor an account installation. Do not treat a skill plugin ZIP as an MCP desktop extension
bundle or assume that an `.mcpb` local server installation is necessary.

Claude's official plugin guidance covers upload/customization and marketplace paths;
features and sharing may depend on the surface and workspace policy. The project does
not automatically run Claude Code, alter a client directory, or install a plugin.

## ChatGPT Desktop and Codex

The portable plugin ZIP contains `plugin.json` and `skills/hikmah/SKILL.md`. The local
marketplace ZIP contains `.agents/plugins/marketplace.json` plus `plugins/hikmah/`.
OpenAI's documented local-plugin workflow resolves `source.path` relative to the
marketplace root and uses supported ChatGPT Desktop Work/Codex surfaces to test it.
An ordinary chat conversation or attachment is not proof that a local marketplace is loaded.

Use the complete marketplace root in an authorized test location. Do not overwrite
an existing personal marketplace, credential file, or workspace policy to install it.
A plain plugin ZIP and a marketplace ZIP have different layouts and purposes.
Restart or refresh through the host's documented flow after changing files, then
inspect the plugin's installed source fingerprint rather than version alone.

## Shared limitations

Both packages contain the same methods, original source, contracts, and optional
runtime, with separate host metadata. A skill can be instruction/resource based;
this project does not need an MCP server just to reason through a decision. An
installed skill does not itself grant an isolated task tool, shell, API credentials,
network access, or entitlement to another provider. Full deliberation is blocked
unless real isolation is available. Keep a non-independent rehearsal labeled as one.

## Acceptance checklist

In an authorized non-production test workspace, confirm the package is discovered,
its version and fingerprint match, the source table and exact DMG labels are readable,
and explicit requests activate the skill. A casual religious mention must not trigger
an unwanted deliberation. Verify that no divine voice or authority is claimed, first
positions are actually isolated, direct peer challenges occur, all received objections
are answered or reported missing, and dissent survives final synthesis.

## Installation tests actually run

On 2026-10-11, the committed marketplace passed `claude plugin validate --strict` and
installed from a local Git clone into temporary, isolated configuration directories:
Claude Code 2.1.282 (`claude plugin install hikmah@devsolux-hikmah`) and codex-cli
0.162.0-alpha.2 (`codex plugin add hikmah@devsolux-hikmah`). Both reported the plugin
installed and enabled at version 1.0.0. Installing from GitHub itself, claude.ai upload,
ChatGPT Desktop, live API execution, model quality, and a native task bridge were not
tested. See [sources](SOURCES.md) and [testing](TESTING.md).

## Packaging checks against published documentation

Claude's [plugin structure guide](https://claude.com/docs/plugins/build) documents the
manifest fields and direct plugin ZIP layout used here. Its [platform support page](https://claude.com/docs/plugins/platform-support)
currently permits up to 5,000 files and 200 MB per account-installed plugin; check the
built package's actual file count and size before uploading. Those limits were
reviewed on 2026-10-11, not asserted as permanent. Neither format review nor size
compliance replaces a live installation test. Claude Code's
[marketplace guide](https://code.claude.com/docs/en/plugin-marketplaces) and OpenAI's
[Codex plugin guide](https://developers.openai.com/codex/plugins/build/) document the
two catalog files, relative `./` sources, and the `plugin@marketplace` install ID.
