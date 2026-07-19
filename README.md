# My Deep Work

**Kanban Trello-like com autenticação segura**

Stack: Python · FastAPI · PostgreSQL · Redis · Jinja2 · Docker Compose

---

## Quick Start

```bash
git clone https://github.com/bbarbosa-lab/my-deep-work.git
cd my-deep-work
cp .env.example .env
docker compose up --build
```

Abra: **http://localhost:8000**

| Rota | Função |
|------|--------|
| `/register` | Criar conta |
| `/login` | Entrar |
| `/boards` | Seus boards |
| `/boards/{id}` | Board Kanban (drag-and-drop) |
| `/settings` | Trocar senha |
| `/forgot-password` | Recuperar senha |
| `/docs` | API Swagger (dev) |

---

## Funcionalidades

### Autenticação (segura)
- Registro e login com argon2id
- Sessões server-side (Redis) com regeneração anti-fixation
- Rate limiting + account lockout
- Recuperação de senha (token de uso único)
- Troca de senha com revogação das outras sessões
- Cookies HttpOnly + SameSite + security headers
- Logs de eventos de autenticação
- Anti-enumeração em login e reset

### Kanban (estilo Trello)
- Workspaces (criado automaticamente)
- Boards (criar, favoritar, arquivar, cor de fundo)
- Listas (criar, renomear, reordenar)
- Cards com drag-and-drop entre listas
- Labels por board
- Checklists e itens
- Due date
- Comentários
- Activity log
- Permissões owner/member

---

## Arquitetura

```
app/
  core/          # config, database, security, deps
  models/        # SQLAlchemy domain models
  schemas/       # Pydantic
  services/      # regras de negócio (boards)
  routers/       # API + pages
  templates/     # Jinja2
  static/        # CSS + JS (SortableJS para DnD)
```

Separação deliberada:
- **PostgreSQL** → identidade e dados do Kanban (fonte da verdade)
- **Redis** → sessões, rate limit, tokens de reset, event log efêmero

---

## Segurança

Ver `docs/threat-model.md`.

Controles principais:
- argon2id (64 MiB, t=3, p=4)
- Session regeneration no login
- Rate limit IP + conta
- Account lockout
- Respostas uniformes (anti-enumeração)
- Logout invalida sessão no servidor
- Troca/reset de senha revoga sessões
- CSP, X-Frame-Options, etc.

**Fora do escopo desta versão:** MFA, verificação de e-mail obrigatória, WebAuthn, OAuth.

---

## Licença / Intent

Aplicação particular / portfólio. Não é um clone comercial do Trello.
