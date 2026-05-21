# Security

## Secrets

- Secrets are loaded from Vault when available.
- Local development uses `.env`, and `.env` is ignored by git.
- No raw secret strings should be committed under `app/`.

## Logging

- Request payloads and memory writes are redacted before logging.
- Bearer tokens, API keys, passwords, and similar secret-like values are masked.
- Structured errors include a request ID, but not secret values.

## Auth

- Passwords are hashed.
- JWTs carry a token-version field for revocation.
- Admin-only actions require role checks.

## Widget Boundary

- Widget runtime config is injected from the API at request time.
- Public widget chat is gated by an origin allowlist.
- The widget bundle should never receive raw Vault credentials.

## Long-Term Memory

- Long-term writes are audited.
- Sensitive content is redacted before persistence where appropriate.

