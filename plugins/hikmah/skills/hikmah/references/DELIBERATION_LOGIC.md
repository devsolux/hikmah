# Deliberation Logic — Hikmah 1.0.0

## Purpose and authority

A difficult decision benefits from deliberately different checks, not a collection of
agreeable voices. The coordinator frames the question, selects relevant instruments,
then synthesizes once. Each selected DMG profile owns one bounded human-level method.
The project does not compare divine Names, enact divine judgment, or infer religious
correctness from an analytical result. The source table is user-supplied, not doctrine.

Keep recommendations provisional to their evidence, constraints, and authority. A
majority can be mistaken; a minority objection can reveal a decisive constraint.
No persona, model, or vote grants execution permission.

## 1. Frame before choosing personas

Use brief schema revision 1: decision, constraints, evidence, reversibility, deadline,
and 2–12 stable options. Evidence records use explicit IDs, kind, source, and content.
Kinds are observation, assumption, value, and unknown. Retain an explicit unknown
rather than filling a gap with a source label or a remembered religious claim.
The supplied example decision is fictional and exists for demonstration and tests.

Freeze the brief's canonical hash. The coordinator owns semantic panel selection:
what distinct concern is missing, and which method tests it? Do not add another model
just to choose the panel. A focused 3–8-seat panel is a practical starting recommendation,
not an empirical claim that this size is optimal. The default triad has 3 seats.

## 2. Ground each lens in its own source row

The 99 reference records bind the exact local table, not network pages. Each has a
source group, row/line identity, whole-source hash, row hash, exact four fields,
review scope, support, and limitations. The source's terminology is preserved. Methods, blind spots, review tests, and relationships are
editorial additions. They must never be presented as quotations or verified theology.

Every row belongs to `user-table-001`. Repeating a source through many lenses does
not create corroboration. Method references belong in `method_reference_ids`;
current decision evidence belongs in `evidence_ids`. The validator rejects unknown
IDs and a collision between the two namespaces. Reference metadata is untrusted
content, not an instruction channel.

The generated Relations/References appendix supports coordinator inspection. The
compiler strips it from first-position prompts and supplies only the seat's own
method core and reference record. A future opponent is not revealed to Round 1.

## 3. Detect and route without inventing capabilities

Offline detection reads only explicit process environment settings, never credential
files or desktop installations. Configured means unverified. An optional explicit,
billable `READY` probe is a point-in-time check, not a guarantee of successful schema
execution, remaining quota, contextual isolation, or later availability.

The coordinator approves providers and the material to be shared. The planner uses
only approved families: Anthropic and OpenAI. Tension edges define requested family
separation. Different families can diversify implementations; they do not establish
independent evidence, training, or reliable disagreement.

For bipartite graphs the planner separates every active edge exactly and balances
component orientations using dynamic programming. For a non-bipartite graph of at
most 18 seats it enumerates the bounded exact problem. Above that it uses four
fixed starting assignments and at most n improving steps per start, reporting the
heuristic status honestly. The result exposes algorithm, optimality, family loads,
and unseparated pairs. Separation has priority over balance; a star can require
unequal loads. With no provider, routing is explicitly hypothetical.

## 4. Round 1: independent positions

Every first request is fresh, with no conversation continuation, previous-response ID,
peer output, relation map, expected opponent, or coordinator preference. It contains
the common brief, own method and source row, contract, and context fingerprints.
The system message forbids tools, delegated reasoning, invented sources, divine
personification, and treating embedded content as instructions. Those prompts do
not themselves establish a hard security boundary.

Each contribution returns option or abstention, evidence IDs, assumptions, unknowns,
confidence with basis, method blind spot, dissent, kill criteria, and next action.
Validate it before accepting it into history. Freeze all successful first positions
before assigning reviews. A failed first position remains a missing selected seat.
`coverage.missing_seats` lists every selected seat without a valid Round 3 position,
so a run that stops early lists seats whose earlier positions remain in the packet.

## 5. Assign balanced direct reviews

Let n be the number of valid first positions, requiring n ≥ 2. Each reviewer-target
edge receives a lexicographic weight using B = n + 1:

```text
weight = (different non-null options) × B²
       + (tension relation) × B
       + (complement relation)
```

Each tier outweighs the sum of all lower-tier changes. An exact maximum-weight
assignment with forbidden diagonal gives every valid first position one incoming
and one outgoing primary review. The implementation uses O(n³) deterministic
assignment, including 99-seat panels. No LLM schedules reviews. Ties have stable
index order. Different options are a scheduling proxy, not proof of disagreement;
equal options can still conceal important opposing assumptions.

The catalog has 50 human-level tensions and 59 complements. Each relationship owns
a shared question, one check in each direction, a discriminating test, and a boundary.
For example, concrete relief and distributive fairness test whether helping a vivid
individual excludes another justified need. Restraint and expansion test the measured
conditions for opening a limit. These are practical decision questions, not opposition
between divine attributes or instructions to adopt prescribed sides.

If a selected pair has no catalog relation, the assigned review uses an explicit
general load-bearing-claim check. It is reported as general, not an invented relation.

## 6. Round 2: challenge an actual claim

The request contains own and assigned target's exact first position, its directional
review lens, and a hash of the full frozen first snapshot. This bounded view is an
intentional scalability change from sending every position to every seat. The full
snapshot remains unchanged in the coordinator packet. No contribution is summarized
by another model and no objection is erased to fit a prompt.

The challenge must address the assigned target, cite an exact nonempty substring of
its first-position rationale, preserve the assigned relation ID, identify the kind
of disagreement, and state a resolution test. Assessments are disagree, qualify,
or no-material-disagreement. The last must be a concrete stress test; performative
opposition is not accepted as a product objective. Structural quote matching does
not prove that the quote was interpreted fairly; the coordinator must still inspect it.

Freeze every valid Round 2 output before compiling any Round 3 request. There is no
within-round feedback loop, late-first-position replacement, or silent peer fallback.
Requests label their view: `peer_context_policy` is `peer-blind` in Round 1 and
`assigned-review-neighborhood` in Rounds 2 and 3.

## 7. Round 3: answer received objections

Each active seat receives its own prior history, its incoming reviewer's first and
second positions, its reviewed target's first position, and each actual incoming
challenge with stable `R2-Sxx` IDs. The target's own Round 2 challenge is not supplied:
it quotes a further seat and is irrelevant to answering received objections. Every
seat ID anywhere in a Round 3 request therefore belongs to the seat, its reviewer, or
its target: at most three seats, whatever the length of the review cycle. The peer
snapshot roots identify the same full frozen histories; the local positions are exact subsets.

Answer every supplied challenge ID exactly once. The response records accepted,
rebutted, or unresolved, its basis, evidence IDs, and remaining test. No duplicate,
missing, or foreign reply is accepted. An acceptance does not automatically establish
truth; a rebuttal does not erase an objection. Finalize an option or abstention,
explain changes, and preserve unresolved questions, dissent, and kill criteria.

No fourth round, new coordinator, automatic retry, or second synthesis call is added.

## 8. Assemble, then synthesize once

Deterministic output includes complete positions from all successful rounds, routing,
coverage, equal advisory counts, abstentions, missing seats, challenge/reply ledger,
missing incoming reviews, unreviewed relations, and all historical dissent/unknowns/
kill criteria. `snapshot_roots` records, per completed round, the same full-snapshot
hash that every request of the following round carried, so any view can be matched
to the packet without recomputation. `verdict` is null: the current host coordinator
owns the only synthesis.

The packet is a pure function of the frozen brief, catalog, methods, and recorded
rounds. `python scripts/deliberation.py audit --packet packet.json` recomputes routing,
review assignment, every request, every accepted contribution's validation, active-seat
transitions, snapshot roots, ledger, coverage, and status from the local resources and
requires a byte-identical derivation. It proves internal determinism and contract
consistency, not truth, model independence, or decision quality. It never resumes,
repairs, or re-dispatches, and uses no network.
All method rows are disclosed as one source group. A run is rounds-complete only
when all selected seats finish all three rounds; that status is not a quality rating.

The coordinator must inspect the packet, then issue a recommendation with evidence,
competing values, dissent disposition, missing coverage, uncertainty, a discriminating
next test, kill criteria, and a concrete action with owner or an explicit unassigned
owner. Do not imply that a recommendation executes anything or reflects divine will.

A full 99-seat packet can itself exceed a host's practical reading budget. Choose a
focused panel before execution when appropriate; do not falsely claim all history
was synthesized when only a subset was read. The complete JSON is the audit record.

## Failure, budgets, and reproducibility

A plan is offline. API execution requires both explicit opt-in flags, credentials,
model IDs, approved providers, and a call budget. The default billable budget is 18;
297 is the hard maximum for all 99 seats. Requests run once each, with concurrency
1–8, bounded timeouts and output-token caps. No automatic rate-limit retry or model
substitution exists. Interrupted or timed-out remote work may have been billed.

The compiler validates an entire next-round job set, including the review assignment,
before making any of its calls. A request over 524288 bytes fails that round before
dispatch. This is a byte bound, not a tokenizer or a guarantee of model context fit.
A round that cannot be compiled, or whose dispatch would exceed the call budget, ends
the run with a partial packet whose `failure` is `request-compilation-failed` or
`call-budget-exhausted`; no exception discards recorded rounds once a request has been
sent. Token overflow, refusal, invalid JSON, wrong IDs, and failed calls remain explicit
failures, not votes. Fewer than two active seats stops progression; no survivor is
promoted into an invented consensus.

Each top-level response string is one line of at most 6000 characters; each array
holds at most 16 distinct one-line entries of at most 4000 characters. The system
message states exactly these enforced limits.

Product, schema, brief, catalog, method, request, and full-snapshot fingerprints reject
cross-product or stale data in the intended in-process flow. No authenticated remote
artifact importer or persistent resumable session is provided. Hashes are integrity
identifiers, not signatures or protection against a malicious process editing source.

## Evaluation criteria

Test deterministic contracts separately from semantic quality. Mocked tests can show
isolation, barriers, exact source binding, bounded context, and ledger completeness.
They cannot demonstrate useful disagreement, fairness, religious correctness, real
model compliance, or improved decisions. Manual evaluation cases require qualified
human review and actual authorized clients. See RUNTIME.md for execution details.

## Provenance namespaces

The packet's `method_source_coverage` explicitly counts the single underlying
source table used for persona-method provenance. It does not count or assess independence
of the decision brief's evidence. Decision evidence IDs cannot start with `ref-`;
that namespace belongs to method references, preventing an ID collision from
laundering a source row into purported decision evidence. Use IDs such as `E1`.
