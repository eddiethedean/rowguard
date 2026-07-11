# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.5.x | Yes |
| 0.4.x | Best-effort only |
| < 0.4 | Best-effort only |

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

We aim to acknowledge reports within a few business days.

## Scope notes

RowGuard validates and classifies query rows. It does not replace:

- Database authentication / authorization
- Network TLS configuration
- Secrets management
- Application-level access control

SQLRules pushdown is an optimization, not an authorization boundary. Express
tenant and access filters as explicit SQL / `where=` clauses.

Rejection payloads may contain row data. Treat `collect` / future quarantine
sinks as sensitive and apply redaction policies appropriate to your environment.
