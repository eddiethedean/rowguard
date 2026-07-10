# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 0.4.x | Yes |
| < 0.4 | Best-effort only |

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Email the maintainers via the contact listed on the
[GitHub repository](https://github.com/eddiethedean/rowguard) (or open a
**private** security advisory on GitHub if enabled for the repo).

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

Rejection payloads may contain row data. Treat `collect` / future quarantine
sinks as sensitive and apply redaction policies appropriate to your environment.
