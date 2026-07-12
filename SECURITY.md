# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.6.x | Yes (security fixes on a best-effort basis) |
| 0.5.x | Best-effort only (no committed fix timeline) |
| < 0.5 | Best-effort only |

**No SLA.** RowGuard is community-maintained under the MIT license. We aim to
**acknowledge** vulnerability reports within a few business days. Fix timelines
depend on severity and maintainer availability; there is no guaranteed patch
window.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Prefer a **[private GitHub security advisory](https://github.com/eddiethedean/rowguard/security/advisories/new)**
on this repository. If that is unavailable, contact the repository owner via
the email listed on their [GitHub profile](https://github.com/eddiethedean).

Include:

- RowGuard version
- Python / SQLAlchemy / Pydantic versions
- A minimal reproduction when possible
- Impact assessment (data exposure, DoS, etc.)

## Adopter considerations

RowGuard validates and classifies query rows. It does **not** replace:

- Database authentication / authorization
- Network TLS configuration
- Secrets management
- Application-level access control

**Pushdown is not authz.** SQLRules pushdown is an optimization. Express tenant
and access filters as explicit SQL / `where=` clauses—never rely on Pydantic
constraints alone for isolation.

**Rejection payloads retain data.** Under `on_reject="collect"`, `RejectedRow`
may hold `mapping`, `raw_row`, and validation details (including PII). Prefer
`skip` or `raise` when you must not retain failed row content, or redact before
logging / persisting results. Future quarantine sinks will need the same care.

**Trusted inputs.** Treat `compiled_rules=`, `where=`, and caller-built
`statement=` objects as trusted application code—not untrusted user input.
