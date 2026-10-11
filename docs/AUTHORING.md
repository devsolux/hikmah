# Authoring lenses, relations, and presets

The source catalog is deliberately bound to the supplied 99 DMG rows. Stable IDs are
`dmg-001` through `dmg-099`; display labels retain exact supplied Unicode. There are no
persona aliases and no silent transliteration normalization. This project does
not claim that this particular table is a definitive enumeration or translation.

## Refine a method

Edit the authored core of the matching `personas/dmg-NNN.md`. Preserve its exact ID,
DMG name, own reference ID, required sections, and a distinct reasoning_method slug.
Improve concrete checks, grounding, blind spots, and failure criteria—not a theatrical
voice. The `## Method` text is the editable analytical adaptation. It must identify a
unique decision responsibility and must not claim to embody a divine attribute.

The role, source terminology, and source-fidelity bindings must remain explicit.
Do not convert a supplied meaning or vision core into a measured fact or project
evidence. When a method is irrelevant, select a different panel rather than force it.

## Refine relations

Edit config/panels.json. Each relation has a unique ID, two sorted different known
members, kind tension/complement, a shared question, one check per direction, a
resolution test, and a misuse boundary. Every persona needs both relation kinds.
A pair has one canonical relation; do not duplicate the same pair under another ID.

Relationships apply only to bounded human methods. Avoid claims that Names disagree,
that one Name is more important, or that the final vote has spiritual authority.
Use an actual competing concern, not manufactured polarity. Methods can honestly
agree. The first-round compiler never exposes the relationship graph to a seat.

A new relation can introduce odd cycles into the provider-separation graph. Inspect
`routing_algorithm`, `routing_optimal`, and unseparated pairs. Large non-bipartite
graphs use a bounded heuristic; never describe them as a proven optimum.

## Refine source scope

The canonical references contain exact source records and hashes. Source content is
not editable translation prose. Do not change the original table to make a method
look better grounded. An explicit source revision needs preserved originals, its own
attribution, changed bindings, tests, and a documented schema/source policy decision.
Do not silently add remembered Qur'an or hadith passages as verified support.

Reference support/limitations may clarify what was and was not used without pretending
to change the original. Every reference remains part of the same single source group.
Adding a genuinely independent religious or linguistic source is out of the current
strict single-table catalog contract and requires an explicit extension, not invented
metadata. A new source should distinguish translation, commentary, and application.

When changing descriptions, presets, or responsibilities, also review the authored
README, docs/PERSONAS.md index, and architecture narrative. They explain the catalog;
they are not an alternate executable source of truth.

## Synchronize and validate

```sh
make sync-personas
make sync-marketplace
make check
make build
make verify
```

Synchronization replaces only the marked Relations/References appendix and preserves
user-authored method text. `make sync-marketplace` then refreshes the committed public
marketplace, whose packaged personas and fingerprint would otherwise be stale. Ordinary build/check must reject stale appendices. Tests
must reflect an intentional product change without weakening unrelated safety checks.
Run the decision-quality evaluation cases after meaningful method changes; passing
structural tests is not evidence that the revised perspective is useful.
