# Architecture

## Invariant

One active Claude/ChatGPT coordinator assigns distinct DMG methods to isolated seats.
A catalog of 99 lenses does not mean 99 autonomous coordinators or divine entities.
The same frozen decision precedes all positions. All modes retain three rounds and
one final synthesis; hard constraints and action authority remain outside model control.

## Responsibility boundaries

| Component | Consumes | Produces | Does not own |
|---|---|---|---|
| Host coordinator | User context, constraints, actual packet | Frozen brief, semantic panel selection, one recommendation | New runtime, invented outputs, permission changes |
| Persona method | Own source row, brief, assigned context | One structured analytical contribution | Browsing, orchestration, execution, religious rulings |
| Canonical catalog | Preserved source bindings and authored relations | Presets, source metadata, conditional review lenses | New decision facts or automatic semantic panel selection |
| Detector/planner | Explicit configuration and approved families | Honest readiness status and deterministic assignments | Desktop-login inference or guaranteed model diversity |
| Runtime | Authorized plan and immutable resources | Requests, barriers, validation, complete packet and ledger, deterministic packet audit | Final synthesis, truth certification, user action |
| Build tools | Validated source tree | Reproducible packages, the committed public marketplace, and guarded cleanup | Network calls, installation, publication |
| User and host | Recommendation and separate authorization | Any actual decision or action | Treating agreement as permission |

## Source model

`sources/hikmah.md` is the four-column source table. Each reference contains its
source group, source SHA-256, row number, line number, row SHA-256, and exact four
column values. Validation compares metadata against the bytes, including DMG Unicode.
The source supplies labels, not independently verified translations,
authored analytical algorithms, or facts about the current decision. Every reference
shares the same source group. The catalog is not a source-independence multiplier.

The profile core owns the editorial method and blind spots. Its generated appendix
is a view of canonical source records and relations. `make sync-personas` updates only
that appendix. Source text and authored method text must not be silently rewritten.

## State flow and 99-seat scaling

Round 1 contains no peer data or relationship expectations. Its complete valid outputs
freeze before review assignment. An exact O(n³) matching assigns one outgoing and one
incoming primary review, with no self-review. It prioritizes option contrast, tension,
then complement, not a required conclusion. All first positions may genuinely agree.

The coordinator packet retains complete immutable history. Later seat requests use
an exact, deterministic **review neighborhood** rather than repeat all 99 positions:
Round 2 includes own and assigned target; Round 3 includes own and incoming-reviewer
positions from both rounds and the reviewed target's first position, so every seat ID
in a request belongs to at most three seats. The packet includes every other position
unchanged. Full-snapshot hashes bind these different views to one state and are recorded
in the packet; an offline audit re-derives the whole packet from its recorded rounds.
No AI summary, second reasoning stage, or hidden truncation is introduced. A context
byte limit fails closed.

Round 3 must address every actual incoming challenge once. The ledger records the
challenge, response, unanswered state, and coordinator resolution authority. Missing
seats, missing reviews, unused relationships, and all rounds' dissent remain visible.

## Routing

For two families, bipartite tension graphs are colored exactly; dynamic programming
chooses component orientations for the best achievable load balance. This scales to
99 seats without enumerating 2^99 assignments. The supplied graph is bipartite.

A conflicting non-bipartite graph of up to 18 seats uses an exact exhaustive max-cut.
Larger conflicting graphs use a deterministic bounded local search and explicitly
report `routing_optimal: false`. No algorithm is falsely labeled exact. With one family,
contexts may still be separate but model-family diversity is absent. With none, only
planning is possible. Provider separation is not evidence independence or correctness.

## Distribution

One plugin directory, `plugins/hikmah/`, serves Claude Code and Codex from the public
`devsolux-hikmah` marketplace at the repository root. It carries both host manifests and
a combined host note. The per-host ZIPs in `dist/` keep their single-host layouts. All
of them are rendered from the same validated sources by `scripts/project.py`.

## Boundaries and failures

Responses bind product identity, schema, run, brief, catalog, method, and compiled
request. Shared snapshots cannot silently mix products or runs. Validation proves
structure and traceability, not meaning, evidence truth, or model obedience.

API calls require explicit user authorization, model IDs, approved providers, network
and data-sharing opt-ins, and a sufficient call budget. Fixed official endpoints,
redirect rejection, no proxy inheritance, no tools, and sanitized errors limit exposure.
No hidden retries, credentials in prompts, automatic reassignment, or second synthesis.

Builds use staged replacement, rollback preservation, locks, strict
paths, hash verification, source fingerprints, and guarded cleanup. These mechanisms
are not a sandbox against a hostile actor concurrently modifying the source filesystem.
Checksums establish integrity against the provided record, not publisher authenticity.
