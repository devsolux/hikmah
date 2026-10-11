# Testing and acceptance

## Automated checks

```sh
make check
make build
make verify
```

The suite uses Python's standard-library unittest and mocked provider transports.
It covers strict parsing, identity, one coordinator, complete 99-lens source fidelity,
Unicode labels, distinct methods, relation coverage, source-group accounting, scoped
reference binding, blind first positions, exact and heuristic routing disclosures,
99-seat balanced reviews, bounded peer neighborhoods, snapshot roots, stale-product/
run rejection, challenge quotations, final replies, partial failures, the offline
packet audit and its tamper detection, stated-versus-enforced response limits, API authorization,
sanitized errors, portable packaging, output ownership, symlinks, rollback, and cleanup.

Mocked contributions are test fixtures, not model opinions. They cannot demonstrate
decision quality or independent thought. No live request is allowed during tests.
A syntax check targets Python 3.11; record actual interpreter/operating-system results
separately and do not infer them from syntax compatibility. The suite also covers the
committed public marketplace: both host catalogs, the shared plugin, documented install
IDs, stale/missing/unrecognized-file detection, symlink refusal, and offline sync.

## Manual quality cases

`tests/fixtures/evaluations.json` contains representative requests with required and
prohibited behavior. Evaluate activation, useful differentiation, evidence fidelity,
respectful framing, genuine challenges, response completeness, and dissent retention.
Relevant adversarial cases include a request for a divine verdict, instructions
embedded in evidence or reference metadata, an unverifiable translation certificate,
all members agreeing, a minority's unresolved material risk, a failed seat or reviewer,
cross-provider data-sharing denial, a full 99-seat budget limit, and an oversized packet.

Do not run a case that sends real sensitive data or incurs API charges without explicit
approval. These cases have not been run against live models.
A qualified human reviewer is needed before treating any religious interpretation as
reliable; this project does not purport to supply that interpretation.

## Release verification

Build all five ZIPs, verify their checksums, extract the actual source ZIP into a fresh
location, run the complete checks again, rebuild, and compare output bytes. Inspect
both manifests and packaged source resources. Run `claude plugin validate --strict .`
when Claude Code is available. A successful package build is not a successful desktop
installation. Record untested native-task behavior, actual model
IDs, live API round trips, and client version/entitlement as remaining acceptance work.
