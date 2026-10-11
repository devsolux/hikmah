# Runtime and execution

## Requirements

Python 3.11+ standard library. The source runtime is `scripts/deliberation.py`.
Installed plugins bundle the same runner at `skills/hikmah/scripts/deliberation.py`
and its resources at `skills/hikmah/references/`. It resolves only these documented
layouts, not home directories, desktop configuration, or credential files.

A full run needs actual isolated host tasks or explicitly approved API execution.
A plugin installation is not proof of either capability. Only Claude/ChatGPT are
host targets; only Anthropic/OpenAI are direct API executors. No other provider,
MCP server, always-on service, SDK dependency, or second synthesizer is included.

## Offline commands

```sh
python scripts/deliberation.py detect
python scripts/deliberation.py plan --brief examples/decision.json
python scripts/deliberation.py plan --brief examples/decision.json \
  --profile decision --providers anthropic,openai
python scripts/deliberation.py plan --brief examples/decision.json \
  --duo restraint-expansion --providers anthropic,openai
python scripts/deliberation.py plan --brief examples/decision.json \
  --members dmg-019,dmg-051,dmg-076
python scripts/deliberation.py plan --brief examples/decision.json \
  --full --providers anthropic,openai

python scripts/deliberation.py audit --packet packet.json
```

`audit` re-derives a saved packet from its recorded brief and rounds plus the local
catalog and methods, and fails unless the result is byte-identical. It proves internal
consistency only, never truth or decision quality; it does not resume, repair, or send.

Choose one selector: `--triad NAME`, `--duo [NAME]`, `--profile NAME`, `--members IDS`,
or `--full`. No selector uses the balanced triad. Bare `--duo` uses mercy-fairness.
An empty or unknown preset name is an error, never a silent fallback to the default. Stable IDs
must be used in CLI lists; the host can resolve exact DMG names through the catalog.
No fuzzy ASCII normalization or silent persona aliasing is performed.

The plan reports maximum seat calls, route algorithm/optimality, loads, and unmet
polarity separation. It never sends a model request or asserts verified availability.
A complete 99-seat selection has a maximum of 297 requests; default selection has 9.

## Explicit API setup

Configure secrets only through a suitable local process environment or your existing
secret manager. Never put real keys in project files, shell examples saved to the
repository, source tables, reports, or model prompts. These exact variable names are read:

| Provider | Secret variable | Required explicit model variable |
|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | `HIKMAH_ANTHROPIC_MODEL` |
| OpenAI | `OPENAI_API_KEY` | `HIKMAH_OPENAI_MODEL` |

Surrounding whitespace in these values is ignored. A key must otherwise be printable
ASCII without spaces, or `detect` reports the provider as not configured.

Use model IDs approved and available in your account that support the documented
structured-output endpoint. No model ID, price, capability, or entitlement is inferred.
The project does not supply API credits; a desktop subscription does not establish
configuration of this separate runtime.

An optional readiness probe is explicit and potentially billable:

```sh
python scripts/deliberation.py detect --probe --allow-network
```

The probe sends only a minimal READY exchange, not a decision or source table. It
does not test the full response schema, final context size, or decision quality.

## Billable run

Review the plan and approve the brief, method/source records, and later-round peer
content that will be transmitted to each selected provider. Both flags are required:

```sh
python scripts/deliberation.py run --brief examples/decision.json \
  --profile decision --providers anthropic,openai \
  --allow-network --confirm-data-sharing --max-calls 18
```

A deliberately approved complete selection needs a larger explicit budget:

```sh
python scripts/deliberation.py run --brief examples/decision.json \
  --full --providers anthropic,openai \
  --allow-network --confirm-data-sharing --max-calls 297
```

The CLI writes UTF-8 JSON to standard output regardless of console encoding. Its
output includes the decision and may be sensitive. Decide where to store it and protect that destination; no persistent run
store or auto-resume exists. Exit status: 0 for a completed offline command or all
three rounds completed; 3 for a partial deliberation; 2 for a contract/configuration
error. `audit` uses the same codes: 0 for a consistent rounds-complete packet, 3 for a
consistent partial packet, 2 when the packet is inconsistent with its own derivation. A failed, truncated, or malformed provider response is recorded as that seat's
sanitized failure in the packet, not raised as a traceback. “Rounds completed” does
not mean that a recommendation is proven correct.

Limits: `--max-calls` default 18, hard maximum 297 (at least three per selected seat);
`--concurrency` 1–8 (default 4); `--timeout` 1–120 seconds (default 90);
`--max-output-tokens` 128–8192 (default 2048). Caps
apply per request except call budget. A lower output limit may cause valid complex
answers to truncate and fail. There are no hidden retries or fallback providers.

## Execution flow

Round 1 has only own method, own exact source record, frozen brief, and structured
contract. Round 2 gets exact own/target first positions. Round 3 gets own history,
the incoming reviewer's both positions, the reviewed target's first position, and
required objection IDs; no Round 3 request names a seat outside those three. Full
snapshot roots bind all these neighborhood views and are recorded in the packet's
`snapshot_roots`; every complete original response stays in the packet. No AI summary or peer consensus is used to prepare another seat's first answer.

Every round is fully compiled before dispatch. Oversize or inconsistent input aborts
that round without new calls and records `request-compilation-failed` in the packet. Each request must be at most 524288 bytes; this is not
a model-token guarantee. At least two valid active seats are required to continue.
Failures remain failures; an invalid response is not automatically repaired or replaced.

The transport uses the fixed official HTTPS Messages and Responses endpoints, rejects
redirects, avoids environment proxies, sends no model tools, and does not continue a
previous conversation. It uses Anthropic `output_config.format` or OpenAI `text.format`
with a JSON schema. OpenAI requests specify `store: false`; this setting is not a
claim of zero provider retention. Provider refusal, truncation, and schema errors are
not retried silently. Errors are sanitized so response bodies or keys are not logged.

## Data contracts and final authority

Contribution/catalog/packet schema revision is 1 and product binding is `hikmah`.
Contributions also bind run ID, frozen brief hash, catalog hash, method hash, request
hash, round, and seat. The contract permits only canonical option IDs and supplied
evidence/reference IDs. Round 2 must quote its assigned peer; Round 3 must answer
every actual incoming challenge. Assertions inside content remain untrusted.

The packet retains all positions, unknowns, dissent, kill criteria, advisory counts,
abstentions, missing seats/reviews, relation coverage, and the challenge ledger.
The one-source provenance group is explicit. `verdict` remains null because the active
host coordinator consumes the packet and synthesizes once. Counts neither certify
truth nor authorize actions; the software never issues a divine verdict or religious ruling.

## Native execution and acceptance

A host-native implementation must supply genuinely fresh peer-blind tasks, the same
frozen brief, structural validation, stable IDs, and actual round barriers. This
release does not implement a host-specific native-task bridge. Do not claim native
execution merely because a skill or agent file is installed. Use the verified API
path when available, or disclose the missing capability and return a useful plan.

Live API calls, ChatGPT Desktop, and claude.ai upload have not been tested; see
the recorded CLI installation tests in docs/COMPATIBILITY.md.
Model-quality evaluation and any doctrinal review are separate unperformed work.
All external implementation references are listed in this project's docs/SOURCES.md.

## Evidence identifiers and resource paths

Use decision evidence IDs such as `E1`. The prefix `ref-` is reserved for method
provenance and is rejected in the brief. `method_source_coverage` counts the underlying
method source only, not the independence or truth of supplied decision evidence.
The resource loader rejects symlink/reparse-point roots and resource directories
as well as individual files. This is a path guard, not a concurrent-filesystem sandbox.
