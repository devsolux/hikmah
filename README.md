# Hikmah

![Hikmah](docs/hikmah.png)

**One coordinator. A catalog of 99 DMG analytical lenses. Three deliberate rounds.**

Hikmah (Arabic for *wisdom*) is a decision-deliberation software project for Claude and ChatGPT. It assigns a difficult question to deliberately different analytical methods, keeps first positions independent, requires direct engagement with an actual peer claim, and returns a recommendation that preserves dissent, unresolved questions, kill criteria, and the next concrete action.

The DMG labels in its source table serve as names of **bounded human-level analytical lenses**. No persona speaks as Allah, embodies a divine attribute, or claims revelation, infallibility, religious authority, or a divine verdict. Relations concern tensions and complements in human decision-making, not contradictions between divine Names.

## What the source table contributes

The source table is [sources/hikmah.md](sources/hikmah.md): **99 entries**, each with its number, exact DMG label, supplied meaning, and vision core. Stable IDs `dmg-001` through `dmg-099` avoid ambiguous ASCII transliterations and preserve similarly spelled but distinct labels.

The source table is not a verified theological source or a ready-made decision algorithm. The grounded method, blind spots, tests, presets, and relationships in this project are explicitly **editorial adaptations**. All 99 row references belong to **one source group**; they are not 99 independent authorities.

Read the [complete lens catalog](docs/PERSONAS.md), [source policy](docs/SOURCES.md), and [notices](NOTICE.md).

## Install from the public marketplace

The public repository [devsolux/hikmah](https://github.com/devsolux/hikmah) is itself the
`devsolux-hikmah` marketplace for both hosts. It lists one plugin, `hikmah`, so the install
ID is always `hikmah@devsolux-hikmah`: plugin name first, then marketplace name.

Claude Code:

```sh
claude plugin marketplace add devsolux/hikmah
claude plugin install hikmah@devsolux-hikmah
```

Inside a Claude Code session, use `/plugin marketplace add devsolux/hikmah` and
`/plugin install hikmah@devsolux-hikmah`. The full URL `https://github.com/devsolux/hikmah`
also works. Machines without a GitHub SSH key can set `CLAUDE_CODE_PLUGIN_PREFER_HTTPS=1`.

Codex (the ChatGPT coding surface):

```sh
codex plugin marketplace add devsolux/hikmah
codex plugin add hikmah@devsolux-hikmah
```

Claude reads `.claude-plugin/marketplace.json`; Codex reads `.agents/plugins/marketplace.json`.
Both point at the same committed plugin, [plugins/hikmah](plugins/hikmah/README.md), which
carries a Claude manifest and the portable `plugin.json`. Installation adds instructions
and resources only: no MCP server, hooks, credentials, or permissions.

The product version stays 1.0.0, and both hosts cache an installed plugin by version,
so a newer commit is not delivered as an update. To pick up repository changes, refresh
the marketplace and reinstall. Compare `references/build.json` fingerprints to confirm.

```sh
claude plugin marketplace update devsolux-hikmah
claude plugin uninstall hikmah@devsolux-hikmah
claude plugin install hikmah@devsolux-hikmah
```

```sh
codex plugin marketplace upgrade devsolux-hikmah
codex plugin add hikmah@devsolux-hikmah
```

## Decision before personas

Record the decision, constraints, evidence, reversibility, deadline, and canonical options before selecting a panel. Missing facts remain unknown. Choose lenses for materially different responsibilities, not because their labels sound impressive.

```text
Decision brief and authorized evidence
        ↓ freeze
Coordinator selects a focused panel and approves execution
        ↓
Round 1: independent, peer-blind positions
        ↓ freeze all valid first positions
Deterministic balanced review assignment
        ↓
Round 2: challenge a specific peer claim through a conditional relation lens
        ↓ freeze
Round 3: answer received objections and finalize bounded positions
        ↓
Complete evidence-linked packet, objection ledger, and coverage report
        ↓
One coordinator recommendation
Dissent · unknowns · kill criteria · next action · human decision authority
```

The catalog contains **109 typed relations: 50 tensions and 59 complements**. Every lens has at least one of each. The default is the balanced triad: `ar-Raḥīm` (`dmg-002`), `al-ʿAdl` (`dmg-029`), and `al-Ḥaqq` (`dmg-051`). Their human-level checks are concrete relief, distributional fairness, and evidence that distinguishes reality from a preferred story. A six-seat `decision` profile adds stability and timing checks.

The full 99-seat selection is available explicitly. It is not the default, a religious ceremony, or a guarantee of better decisions. At most three requests are issued per selected seat; a full run can require **297 billable requests**. Focused panels are normally the more manageable starting point.

## Build and verify

Python **3.11+**. GNU Make is an optional command interface. Build tools and tests use only the standard library, with no network access or credentials.

```sh
make doctor
make all
```

`make all` validates the source, runs tests, builds packages, and verifies them. The source ZIP intentionally excludes generated `dist/`; a build creates it. It does include the committed public marketplace, so an extracted archive validates as-is.

```sh
make check          # Source validation and automated tests.
make build          # Source ZIP, both plugins, and both local marketplaces.
make verify         # Integrity and source-freshness checks.
make clean          # Remove only intact, owned build output.
make rebuild        # Serial clean, check, build, and verify.
make detect         # Offline API-configuration report; never prints keys.
make plan           # Offline example brief and balanced triad.
make audit PACKET=p.json  # Offline re-derivation of a saved packet.
make sync-personas  # Refresh only marked Relations/References appendices.
make sync-marketplace  # Refresh the committed public marketplace.
make help
```

Without Make:

```sh
python -B scripts/project.py validate
python -B -m unittest discover -s tests -v
python -B scripts/project.py build
python -B scripts/project.py verify
```

## Plan a deliberation without making model calls

```sh
python scripts/deliberation.py plan --brief examples/decision.json \
  --profile decision --providers anthropic,openai

python scripts/deliberation.py plan --brief examples/decision.json \
  --duo restraint-expansion --providers anthropic,openai

python scripts/deliberation.py plan --brief examples/decision.json \
  --members dmg-019,dmg-051,dmg-076

python scripts/deliberation.py plan --brief examples/decision.json \
  --full --providers anthropic,openai
```

`python scripts/deliberation.py audit --packet packet.json` re-derives a saved packet
offline and fails unless it is byte-identical to its own deterministic derivation.

A route preview is hypothetical. It does not prove that either account, desktop client, model, or isolated execution capability is available. The supplied full tension graph permits complete separation across two providers. The planner reports actual loads, unseparated pairs, the algorithm, and whether its optimization is exact.

## Use the installed skill

Ask the host: “Use the Hikmah project's decision profile to deliberate this choice. Preserve unresolved objections and identify the next reversible action.”

The current conversation remains the only coordinator. The plugin supplies instructions, persona resources, and an optional Python runtime; it does **not** add an MCP server, a new model backend, a self-running agent service, or permissions. Execution needs either genuinely isolated host tasks or explicitly approved Anthropic/OpenAI API calls. Without isolation, return a brief and execution blocker; do not invent a completed debate.

See [installation and compatibility](docs/COMPATIBILITY.md), [runtime and data sharing](docs/RUNTIME.md), and [deliberation logic](docs/DELIBERATION_LOGIC.md). Desktop installation and live model quality require acceptance testing in the intended environment.

## Maintain the project

`project.json` owns **Hikmah / hikmah / 1.0.0**. `agents/hikmah.md` owns the coordinator protocol. `personas/` owns the methods. `config/panels.json` owns presets, relationships, and source bindings. `sources/hikmah.md` is the source table. `scripts/deliberation.py` compiles and validates work; it never produces another model-generated synthesis.

Edit a method in its profile. Edit relationships or source scope in the canonical catalog, then run `make sync-personas`, `make sync-marketplace`, and `make check`. Any source change makes the committed marketplace stale, because its `build.json` records the source fingerprint; validation refuses it until `make sync-marketplace` runs. Never hand-edit `.claude-plugin/`, `.agents/`, `plugins/`, or `dist/`, and never silently correct the original source. See [authoring](docs/AUTHORING.md), [architecture](docs/ARCHITECTURE.md), [build guarantees](docs/BUILD.md), and [testing](docs/TESTING.md).

Product and data-schema versions are separate. Product `hikmah` uses contribution/catalog/packet schema revision **1**; packets that name another product are rejected. Check `references/build.json` fingerprints when refreshing a same-version installation.

Publishing is a deliberate maintainer step. The `github-*` Make targets (for example `make github-bootstrap` and `make github-push`) contact GitHub only when invoked by name; `make github-push` runs validation first, so a stale marketplace is never pushed.
