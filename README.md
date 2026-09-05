# Bearly 🐻

A personal finance app that tells you where you stand, what to do next, and why.

Traditional tracking (transactions, budgets, debts, goals, holdings) sits on top of a
**deterministic finance engine** written in Python. A chat coach and five specialised
agents read that engine's output and explain it in plain language. **The AI never does
the arithmetic** — it calls the engine and quotes what comes back.

---

## Why it is built this way

Two decisions shape the whole codebase.

**1. The maths is code, not inference.** Payoff timelines, savings rates, the health
score and the next-dollar ordering are computed in Python from your records and covered
by tests. An LLM that quietly miscalculates a debt payoff is worse than no feature at
all, so agents are given the finished numbers and asked to explain them.

**2. Investing is gated on the rest of your plan.** The backend decides whether investing
is even appropriate — no emergency fund, negative cash flow, or debt above 8% APR blocks
it — and the Investment Research agent is told so explicitly and must lead with that.
The app will not pitch index funds to someone carrying a 27% store card.

---

## Quick start (development)

Two terminals. No credentials required — the app is fully functional without any AI
keys, using SQLite and a deterministic stand-in for the model.

For production — PostgreSQL, migrations, Docker, TLS — see **[DEPLOYMENT.md](DEPLOYMENT.md)**.

**Backend**

Requires **Python 3.9+**. Check with `python3 --version` — if your `python3` is
older, name the interpreter explicitly (`python3.11 -m venv .venv`).

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python seed_demo.py          # optional: a realistic demo account
uvicorn app.main:app --reload
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. If you seeded the demo account:

| | |
|---|---|
| Email | `demo@bearly.app` |
| Password | `DemoPassw0rd!` |

API docs are at http://localhost:8000/docs in development.

---

## Tests

```bash
cd backend && python -m pytest -q      # 60 tests
```

Coverage is concentrated where correctness matters: amortisation against hand-computed
figures, health-score banding, the investing gate, and cross-user data isolation.

---

## Architecture

```
Vue 3 ──► FastAPI ──► deterministic finance engine ──► structured context ──► AI agent
                                    │                                              │
                                    └────────── the numbers shown are these ───────┘
```

### Backend (`backend/app`)

| Path | Role |
|---|---|
| `services/finance/metrics.py` | Net worth, cash flow, savings rate, DTI, emergency-fund months, budget variance |
| `services/finance/debt.py` | Month-by-month amortisation; avalanche vs snowball vs minimums |
| `services/finance/projections.py` | Compound growth, goal funding requirements |
| `services/finance/health.py` | The six-component health score |
| `services/finance/priorities.py` | The next-dollar waterfall and the investing gate |
| `services/ai/context.py` | Builds the small structured payload each agent receives |
| `services/ai/orchestrator.py` | Gating, caching, invalidation, validation, fallback |
| `api/routes/` | REST endpoints, all ownership-checked |

Money is `Decimal` end to end — never `float` — and stored as `NUMERIC(14,2)`.

### Frontend (`frontend/src`)

Vue 3 + Vite, Pinia for state, a hand-built component system in the shadcn idiom
(`components/ui`), and hand-rolled SVG charts (`components/charts`) with no charting
dependency.

---

## The finance engine

Everything is computed from your own records, with one consistent precedence rule:
**real records beat profile estimates.** If you have entered debts, those define your
liabilities; if not, your onboarding figure is used. Every metric reports which basis it
used, and the UI shows it ("from your logged transactions" / "from your profile figures")
so no number is unexplained.

### The health score

Six components, fixed weights, no AI input:

| Component | Weight | Full marks at |
|---|---|---|
| Savings rate | 25 | ≥ 20% of income |
| Emergency fund | 20 | ≥ 6 months of essentials |
| Debt-to-income | 20 | ≤ 10% of income on debt payments |
| High-interest debt | 15 | nothing above 8% APR |
| Budget adherence | 10 | on plan, nothing overspent |
| Diversification | 10 | ≥ 3 asset types, largest ≤ 60% |

### The next-dollar waterfall

Applied to whatever surplus exists, in this order:

1. Close a negative cash-flow gap — nothing else works until this is fixed
2. Cover minimum debt payments
3. Build a one-month starter emergency fund
4. Capture any employer retirement match
5. Clear debt above 8% APR
6. Finish the three-month emergency fund
7. Fund defined savings goals
8. Invest what remains

Steps that receive nothing because the surplus ran out above them are marked *Next up*
rather than shown as active with $0.

---

## AI agents

| Agent | Question it answers | Model tier |
|---|---|---|
| Budget Coach | Where is my money leaking? | routine |
| Debt Strategist | Avalanche or snowball, for me? | routine |
| Savings Planner | How do I split my spare cash? | routine |
| Investment Research | What allocation suits me — if I am ready? | planning |
| Financial Planner | What do I do with my next dollar? | planning |

### The chat coach

The Coach page is a conversation. Each turn injects a ~480-token briefing built from
the user's live figures — cash flow, every debt with its APR and monthly interest cost,
goals with on-track status, budget variance, the investing gate, the next-dollar order —
so the agent starts already knowing where the user stands.

Beyond that it has ten tools that run the engine: payoff simulation at a named payment,
growth projections, spending trends, and the five specialist analyses above. Ask *"what
if I paid $600 a month?"* and it runs the real amortisation rather than estimating.

Replies stream over Server-Sent Events, and every answer shows which functions ran.

Every agent returns the same validated JSON contract:

```json
{
  "summary": "",
  "recommendations": [
    { "priority": 1, "title": "", "reason": "", "suggested_amount": 0, "category": "" }
  ],
  "risks": [],
  "next_steps": []
}
```

A response that fails validation is rejected and replaced with the deterministic
fallback, so a malformed model output never reaches the screen.

### Where the agents run

`BEARLY_AI_PROVIDER` selects one of three runners:

| Value | Behaviour |
|---|---|
| `stub` *(default)* | No inference at all. Narrates the engine's own output. Zero cost, zero credentials, fully functional. |
| `anthropic` | Calls Claude directly from the API process. |
| `tenki` | Runs the agent **inside a Tenki.cloud sandbox microVM**, isolated from the database. |

> **A note on Tenki.** Tenki.cloud sells sandbox microVMs, CI runners and PR review — it
> does **not** host model inference, so there is no Tenki model endpoint to call. The
> `tenki` provider therefore runs the *agent process* in a disposable Tenki VM that has no
> network path to your database, with inference served from inside that sandbox. It needs
> both `TENKI_API_KEY` and a model key. Switching providers changes one env var; nothing
> else in the app moves.

### Controlling AI cost

Five mechanisms, in the order they take effect:

1. **Gate** — if the engine already answers the question (no debts recorded, no profile
   yet), the agent is never called.
2. **Cache** — responses are keyed by a SHA-256 fingerprint of the exact context. Same
   finances, same answer, no new call. Editing a debt invalidates only the debt-related
   agents.
3. **Never on page load** — agents run only when the user clicks. The Coach page reads
   stored answers.
4. **Tier** — routine analysis uses the cheap model; only planning uses the strong one.
5. **Cap** — bounded `max_tokens`, and a JSON schema so no tokens are spent on prose that
   gets discarded.

`GET /api/v1/ai/usage` reports generations, billed calls and token spend; the Coach page
surfaces it.

### What the agents receive

Aggregates only. Names, email addresses, merchant names and individual transactions never
leave the backend — there is a test asserting exactly this. A typical payload is a few
hundred tokens:

```json
{
  "position": { "monthly_income": 7233, "savings_rate_pct": 24.3, "emergency_fund_months": 2.1 },
  "debts": [{ "name": "Sapphire Credit Card", "balance": 6840, "apr": 25.0 }],
  "calculated_payoff": { "avalanche": { "months_to_debt_free": 17, "total_interest": 1914 } }
}
```

Money is rounded to whole dollars (a $3.14 drift should not trigger a paid call); rates
keep a decimal, because 9.37% is not "9%".

---

## Security

- Passwords hashed with bcrypt, SHA-256 pre-hashed so long passphrases are not truncated
- Refresh tokens stored as digests and rotated on use; reset tokens are single-use and
  end every session
- Every financial resource goes through an ownership check; another user's row returns
  **404, not 403**, so IDs cannot be probed
- `/auth/forgot-password` always returns the same response — no account enumeration
- Validation errors never echo the submitted values back into logs
- Model and Tenki credentials live in backend env vars and never reach the browser
- Security headers set, HSTS in production

---

## Moving to PostgreSQL

Change one variable:

```bash
BEARLY_DATABASE_URL=postgresql+psycopg://bearly:secret@localhost:5432/bearly
```

No application code changes. There is no raw SQL anywhere, money is `Numeric`, and a
`UTCDateTime` type decorator normalises timestamps so SQLite and PostgreSQL behave
identically. Add Alembic before production — `init_db()` uses `create_all`, which is fine
for the MVP but does not migrate.

---

## Built to extend

| Later feature | Seam already in place |
|---|---|
| Bank sync | `Account.external_id` / `provider` / `source`, `Transaction.external_id` with a uniqueness constraint |
| Market data | `InvestmentHolding.current_price` / `price_updated_at` / `price_source` |
| More agents | Add a prompt, a context builder, and an enum member |
| Different model provider | One env var; the provider interface is three methods |

---

## Scope

Deliberately **not** built: bank synchronisation, brokerage connections, tax planning,
trading. The data model accommodates them; the MVP does not implement them.

Bearly provides educational guidance, not licensed financial advice.
