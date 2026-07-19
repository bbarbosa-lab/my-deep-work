# Threat Model — My Deep Work

**Version:** 1.0  
**Scope:** Authentication + Kanban application

## Assets
- User credentials (argon2id hashes)
- Active sessions (Redis)
- Password reset tokens
- Board/card data (business content)
- Auth event logs

## Actors
- External unauthenticated attacker
- Authenticated member (low privilege on foreign boards)
- Network MITM (TLS assumed in production)
- Insider with Redis/DB access

## Surfaces
- `/api/auth/*` (register, login, reset, change-password)
- `/api/boards/*`, `/api/cards/*`, lists, comments
- Session cookie
- Server-rendered pages + JS
- Redis and PostgreSQL (internal network only)

## Key controls
| Threat | Control |
|--------|----------|
| Credential stuffing | Rate limit IP+account, lockout, uniform errors |
| Session fixation | Regenerate session ID on login |
| Session theft | HttpOnly, SameSite, short TTL, server invalidation |
| Account enumeration | Uniform messages on login/reset/register |
| Weak passwords | argon2id strong params |
| CSRF | SameSite + same-origin fetch; tokens recommended next |
| IDOR on boards | Membership check on every board/card operation |
| XSS | Jinja2 auto-escape, CSP |

## Explicit non-goals (this version)
- MFA / WebAuthn
- Mandatory email verification
- Real email delivery (dev shows reset token)
- Full realtime collaboration

## Residual risks
- No MFA → password compromise = full account access
- Reset token shown in dev response (must not happen in production)
- CSP allows unsafe-inline for form handlers
- Distributed botnets can still low-and-slow
- Host compromise bypasses app controls
