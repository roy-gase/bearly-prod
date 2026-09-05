"""The Bearly chat coach.

Streams a reply while running Bearly's own finance functions as tools. The model
chooses which question to ask and how to explain it; every number it quotes came
out of the deterministic engine.

Two runners:
  * `anthropic` — real conversation with tool use and token streaming.
  * `stub`      — no inference. Routes the question to the right tool and writes
                  the answer from a template, so the feature works with no key.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import ChatConversation, ChatMessage, User
from app.services.ai import tools as tool_layer
from app.services.finance.money import money

logger = logging.getLogger("bearly.chat")

MAX_HISTORY_MESSAGES = 20   # what we resend; older turns drop off
MAX_TOOL_ROUNDS = 4         # bounds cost and stops any tool ping-pong
MAX_REPLY_TOKENS = 1200

SYSTEM_PROMPT = """You are Bearly, a personal finance coach for people who are not finance experts.

How you work:
- A CURRENT SITUATION briefing is appended below with the user's real, up-to-date figures. It is authoritative. Answer from it directly rather than calling a tool to re-read the same numbers.
- You have tools that run Bearly's engine for anything the briefing does not already contain: what-if calculations, payoff simulations at a specific payment, growth projections, spending trends, and full specialist analyses.
- NEVER compute a figure yourself, not even approximately. No sums, no percentages, no "roughly", no "about $X". If a number is not in the briefing and no tool returns it, say you would need to work it out rather than estimating. An approximate number in a finance app is a wrong number.
- The next-dollar ordering from get_priorities is decided by Bearly's rules, not by you. Explain it; do not reorder it.
- If a tool returns an error or empty data, say what is missing and what the user should add.

How you talk:
- Plain language, warm, direct. Address the user as "you". Short paragraphs.
- Lead with the answer, then the reasoning. Give concrete dollar amounts and dates.
- Be honest when the news is bad, but never preachy or alarmist. This person is trying.
- Ask a clarifying question when the request is genuinely ambiguous, rather than guessing.

Hard rules:
- Check whether investing is appropriate before discussing it. If get_priorities says it is not, explain why the money is better used elsewhere and do not give allocation ideas.
- Never recommend a specific stock, ticker, or market timing. Asset classes and diversification only.
- Never promise a return. Say "historically" or "typically". Note that investments can lose value.
- You are not a licensed financial advisor and this is not personalised financial advice.
- Keep replies under 250 words unless the user asks for detail."""


STARTERS = [
    {"label": "Where do I stand?", "prompt": "Give me an honest summary of where I stand financially right now."},
    {"label": "What should I do next?", "prompt": "What should I do with my next available dollar, and why that order?"},
    {"label": "Review my budget", "prompt": "Review my budget this month and tell me where my money is leaking."},
    {"label": "Debt payoff plan", "prompt": "What is the fastest realistic way for me to get out of debt?"},
    {"label": "Am I ready to invest?", "prompt": "Am I in a position to start investing yet? Be honest."},
    {"label": "Can I afford this?", "prompt": "How much could I realistically save each month without it hurting?"},
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def build_briefing(db: Session, user: User) -> str:
    """A compact, current picture of the user's whole financial position.

    Injected on every turn so the agent starts each reply already knowing where
    the user stands, instead of spending a round trip asking. Tools stay for
    what-if calculations and anything not summarised here.

    Aggregates only — no names, emails, merchants or individual transactions.
    """
    from sqlalchemy import select

    from app.models import Debt, SavingsGoal
    from app.services.finance.health import compute_health_score
    from app.services.finance.metrics import build_overview
    from app.services.finance.priorities import build_priorities
    from app.services.finance.projections import goal_requirement

    ov = build_overview(db, user)
    if not ov.has_profile:
        return (
            "CURRENT SITUATION: this user has not completed their financial profile yet, "
            "so almost no figures are available. Encourage them to fill it in from Settings, "
            "and answer general questions only."
        )

    health = compute_health_score(ov)
    prio = build_priorities(ov)
    money_fmt = lambda v: "$%s" % format(float(v), ",.0f")

    lines = [
        "CURRENT SITUATION — calculated by Bearly's engine, accurate as of this message.",
        "Use these figures directly; do not call a tool just to re-read them.",
        "",
        "Cash flow: %s in, %s out, %s left over each month (savings rate %.1f%%)."
        % (money_fmt(ov.monthly_income), money_fmt(ov.monthly_expenses),
           money_fmt(ov.monthly_cash_flow), float(ov.savings_rate_pct)),
        "Sources: income figures %s, expense figures %s."
        % (ov.income_basis, ov.expense_basis),
        "Net worth: %s (assets %s, liabilities %s)."
        % (money_fmt(ov.net_worth), money_fmt(ov.total_assets), money_fmt(ov.total_liabilities)),
        "Emergency fund: %s = %.1f months of %s essential expenses (3-month target %s)."
        % (money_fmt(ov.emergency_fund), float(ov.emergency_fund_months),
           money_fmt(ov.essential_expenses or ov.monthly_expenses), money_fmt(ov.emergency_fund_target)),
        "Health score: %d/100 (%s). Weakest area: %s."
        % (health["score"], health["grade"], health["weakest_label"]),
    ]

    debts = db.scalars(
        select(Debt).where(Debt.user_id == user.id, Debt.is_active.is_(True))
    ).all()
    if debts:
        from decimal import Decimal

        monthly_interest = sum(
            (Decimal(str(d.current_balance)) * Decimal(str(d.apr)) / Decimal(1200)) for d in debts
        )
        lines.append(
            "Debt: %s total at %.1f%% weighted average, %s/mo in minimums, %s of it above 8%% APR."
            % (money_fmt(ov.total_debt), float(ov.weighted_avg_apr),
               money_fmt(ov.monthly_minimum_payments), money_fmt(ov.high_interest_debt))
        )
        lines.append(
            "  Interest accruing right now: %s/mo across all debts." % money_fmt(monthly_interest)
        )
        for d in sorted(debts, key=lambda x: -float(x.apr)):
            per_debt_interest = (
                Decimal(str(d.current_balance)) * Decimal(str(d.apr)) / Decimal(1200)
            )
            lines.append(
                "  - %s: %s at %.2f%% APR, minimum %s/mo, costing %s/mo in interest"
                % (d.name, money_fmt(d.current_balance), float(d.apr),
                   money_fmt(d.minimum_payment), money_fmt(per_debt_interest))
            )
    else:
        lines.append("Debt: none recorded.")

    goals = db.scalars(
        select(SavingsGoal).where(SavingsGoal.user_id == user.id, SavingsGoal.is_active.is_(True))
    ).all()
    if goals:
        lines.append("Savings goals (%d):" % len(goals))
        for g in goals:
            req = goal_requirement(
                g.target_amount, g.current_amount, g.target_date, g.monthly_contribution
            )
            status = "on track" if req["on_track"] else ("behind" if req["on_track"] is False else "no target date")
            lines.append(
                "  - %s: %s of %s (%.0f%%), contributing %s/mo, needs %s/mo — %s"
                % (g.name, money_fmt(req["current_amount"]), money_fmt(req["target_amount"]),
                   req["progress_pct"], money_fmt(req["current_monthly"]),
                   money_fmt(req["required_monthly"]) if req["required_monthly"] else "n/a", status)
            )
    else:
        lines.append("Savings goals: none set.")

    if ov.budget_total > 0:
        over = [c for c in ov.categories if c.is_over and abs(c.remaining) >= 1]
        lines.append(
            "Budget this month: %s spent of %s planned (%.0f%% used)%s."
            % (money_fmt(ov.budget_spent), money_fmt(ov.budget_total),
               float(ov.budget_utilization_pct),
               (", over on " + ", ".join(c.name for c in over[:4])) if over else ", nothing over plan")
        )
        top = sorted(ov.categories, key=lambda c: c.actual, reverse=True)[:5]
        lines.append(
            "  Biggest categories: %s."
            % ", ".join("%s %s" % (c.name, money_fmt(c.actual)) for c in top)
        )
    else:
        lines.append("Budget: none set for this month.")

    if ov.holding_count:
        alloc = ", ".join(
            "%s %.0f%%" % (k, v["pct"]) for k, v in list(ov.allocation_by_asset_type.items())[:5]
        )
        lines.append(
            "Investments: %s across %d holdings (%s)."
            % (money_fmt(ov.holdings_value), ov.holding_count, alloc)
        )
    else:
        lines.append("Investments: %s recorded, no individual holdings." % money_fmt(ov.investment_assets))

    lines.append(
        "Investor profile: %s risk tolerance, %d-year horizon."
        % (ov.risk_tolerance, ov.investment_horizon_years)
    )
    lines.append("")
    lines.append(
        "INVESTING GATE: %s"
        % ("appropriate — foundations are covered."
           if prio["investing_appropriate"]
           else "NOT appropriate yet. " + (prio["investing_blocked_reason"] or ""))
    )
    # Spelled out, because a terse status code invites misreading: an agent read
    # "[check]" as "done" and told the user they had already captured their match.
    STATUS_WORDS = {
        "urgent": "URGENT, must be dealt with before anything else",
        "not_started": "not started yet",
        "in_progress": "the current focus",
        "queued": "queued, no money spare for it until the steps above are funded",
        "ready": "ready to act on",
        "blocked": "not appropriate yet",
        "check": "NOT verified — Bearly cannot see workplace retirement plans, so the "
                 "user must check with their employer whether they are getting the full match",
    }
    lines.append("NEXT-DOLLAR ORDER (decided by Bearly's rules — explain it, never reorder it):")
    for step in prio["steps"]:
        lines.append(
            "  %d. %s — %s%s"
            % (step["rank"], step["title"],
               STATUS_WORDS.get(step["status"], step["status"]),
               (", suggested %s/mo" % money_fmt(step["suggested_monthly"])) if step["suggested_monthly"] > 0 else "")
        )
    return "\n".join(lines)


def build_history(conversation: ChatConversation) -> List[dict]:
    """Recent turns, in the wire format. Older turns are dropped to cap cost."""
    recent = conversation.messages[-MAX_HISTORY_MESSAGES:]
    return [{"role": m.role, "content": m.content} for m in recent if m.content.strip()]


def title_from(text: str) -> str:
    cleaned = " ".join(text.split())
    return (cleaned[:57] + "…") if len(cleaned) > 58 else cleaned or "New conversation"


# ---------------------------------------------------------------------------
# Anthropic runner
# ---------------------------------------------------------------------------


def _stream_anthropic(
    db: Session, user: User, history: List[dict], briefing: str
) -> Iterator[dict]:
    import anthropic

    client = anthropic.Anthropic(
        api_key=settings.anthropic_api_key, timeout=settings.ai_timeout_seconds
    )
    messages: List[dict] = list(history)
    tools_used: List[dict] = []
    usage = {"input": 0, "output": 0}
    model = settings.ai_chat_model

    for _round in range(MAX_TOOL_ROUNDS):
        with client.messages.stream(
            model=model,
            max_tokens=MAX_REPLY_TOKENS,
            # The rules never change, so they carry the cache breakpoint and are
            # billed at the cached rate. The briefing changes whenever the user's
            # finances do, so it sits after the breakpoint.
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                },
                {"type": "text", "text": briefing},
            ],
            tools=tool_layer.TOOL_SCHEMAS,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield {"type": "text", "delta": text}
            final = stream.get_final_message()

        if getattr(final, "usage", None):
            usage["input"] += getattr(final.usage, "input_tokens", 0) or 0
            usage["output"] += getattr(final.usage, "output_tokens", 0) or 0

        if final.stop_reason != "tool_use":
            break

        # Run every requested tool, then hand the results back in one message.
        messages.append({"role": "assistant", "content": final.content})
        results = []
        for block in final.content:
            if block.type != "tool_use":
                continue
            args = block.input if isinstance(block.input, dict) else {}
            label = tool_layer.TOOL_LABELS.get(block.name, block.name)
            yield {"type": "tool", "name": block.name, "label": label, "input": args}
            tools_used.append({"name": block.name, "label": label, "input": args})
            output = tool_layer.execute(db, user, block.name, args)
            results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(output, default=str),
                }
            )
        messages.append({"role": "user", "content": results})
    else:
        yield {
            "type": "text",
            "delta": "\n\n(I stopped after several lookups — ask me something narrower and I'll go deeper.)",
        }

    yield {
        "type": "meta",
        "tools_used": tools_used,
        "provider": "anthropic",
        "model": model,
        "input_tokens": usage["input"],
        "output_tokens": usage["output"],
    }


# ---------------------------------------------------------------------------
# Stub runner — no inference, still useful
# ---------------------------------------------------------------------------

_INTENTS = [
    ("debt", r"\b(debts?|pay ?off|credit cards?|avalanche|snowball|aprs?|interest|loans?|owe|balances?)\w*"),
    ("invest", r"\b(invest|portfolio|stock|etf|index fund|market|allocat|retire|brokerage)\w*"),
    ("budget", r"\b(budget|spend|expens|groceries|categor|cut ?back|leak|overspend|afford)\w*"),
    ("savings", r"\b(sav|emergency fund|goals?|vacation|deposit|rainy day)\w*"),
    ("plan", r"\b(next dollar|priorit|what should i|where do i stand|focus|plan|score|health)\w*"),
]


_AMOUNT = re.compile(
    r"\$\s*([\d,]+(?:\.\d{1,2})?)"
    r"|([\d,]{2,}(?:\.\d{1,2})?)\s*(?:dollars?|bucks?)?\s*(?:a|per|/|each)\s*(?:month|mo\b)",
    re.IGNORECASE,
)


def _extract_amount(text: str) -> Optional[float]:
    """Pull a dollar figure out of the question.

    "can I afford $600 a month" must be answered about $600, not about whatever
    surplus the engine computed.
    """
    match = _AMOUNT.search(text or "")
    if not match:
        return None
    raw = match.group(1) or match.group(2) or ""
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return None
    return value if 0 < value < 1_000_000 else None


def _detect_intent(text: str) -> str:
    lowered = text.lower()
    for intent, pattern in _INTENTS:
        if re.search(pattern, lowered):
            return intent
    return "plan"


def _fmt(value) -> str:
    try:
        return "$%s" % format(float(value), ",.0f")
    except (TypeError, ValueError):
        return "$0"


def _stub_reply(db: Session, user: User, question: str) -> tuple:
    """Return (text, tools_used). Real numbers, templated prose."""
    intent = _detect_intent(question)
    used: List[dict] = []

    def run(name: str, args: Optional[dict] = None) -> dict:
        used.append(
            {"name": name, "label": tool_layer.TOOL_LABELS.get(name, name), "input": args or {}}
        )
        return tool_layer.execute(db, user, name, args)

    snap = run("get_financial_snapshot")

    if intent == "debt":
        if snap["total_debt"] <= 0:
            return ("You have no debt recorded, so there is nothing to pay off. "
                    "If you do carry a balance somewhere, add it on the Debt page and ask me again.", used)
        asked = _extract_amount(question)
        cmp_ = run("compare_debt_strategies", {"extra_monthly": asked or 0})
        if "error" in cmp_:
            return (cmp_["error"], used)
        av, sn = cmp_["avalanche"], cmp_["snowball"]
        used_extra = cmp_["extra_monthly_used"]

        opening = (
            "Yes — %s a month is affordable: you have about %s spare after expenses.\n\n"
            % (_fmt(asked), _fmt(snap["monthly_surplus"]))
            if asked is not None and asked <= snap["monthly_surplus"]
            else "That would stretch you — %s a month is more than the %s you have spare, so it "
            "would have to come out of something else.\n\n" % (_fmt(asked), _fmt(snap["monthly_surplus"]))
            if asked is not None
            else ""
        )

        text = opening + (
            "You owe %s at a weighted average rate of %.1f%%.\n\n"
            "Putting %s a month towards them on top of your minimums, the avalanche method "
            "(highest rate first) clears everything in %s months and costs %s in interest. "
            "Snowball (smallest balance first) takes %s months and costs %s.\n\n"
            % (
                _fmt(snap["total_debt"]), snap["weighted_average_apr"], _fmt(used_extra),
                av["months_to_debt_free"], _fmt(av["total_interest"]),
                sn["months_to_debt_free"], _fmt(sn["total_interest"]),
            )
        )

        saved = cmp_["interest_saved_avalanche_vs_snowball"]
        if av["payoff_order"] == sn["payoff_order"]:
            text += (
                "Both methods clear your debts in the same order here — your smallest balance "
                "is also one of your priciest — so they cost the same. Pick either and stay with it."
            )
        elif saved > 0:
            text += (
                "Avalanche saves you %s in interest. It starts with %s; snowball would clear %s "
                "first instead. Snowball costs more, but the quick win keeps some people going — "
                "that difference is what the motivation is worth."
                % (_fmt(saved), av["payoff_order"][0], sn["payoff_order"][0])
            )
        else:
            text += (
                "They cost within a few dollars of each other, so choose on temperament: "
                "%s first for the fastest visible win, or %s first to kill the priciest rate."
                % (sn["payoff_order"][0], av["payoff_order"][0])
            )
        return (text, used)

    if intent == "invest":
        prio = run("get_priorities")
        if not prio["investing_appropriate"]:
            return (
                "Not yet — and that is a good thing to know before you put money in.\n\n%s\n\n"
                "Clear that first. Money used there earns you a guaranteed return, which investing "
                "cannot promise. Ask me about your payoff plan and I will show you the numbers."
                % prio["investing_blocked_reason"],
                used,
            )
        proj = run(
            "project_investment_growth",
            {"monthly_contribution": max(0.0, prio["monthly_surplus"] * 0.5),
             "annual_return_pct": 7, "years": snap["investment_horizon_years"] or 20},
        )
        return (
            "Your foundations are in place, so investing is a reasonable next step. About %s a "
            "month is genuinely spare.\n\nIf you put %s a month in at a %s%% assumed annual return "
            "over %s years, that projects to %s, of which %s is growth. That is a fixed-rate "
            "projection, not a forecast — real returns vary year to year and can be negative.\n\n"
            "With a %s risk tolerance, the usual shape is broad, low-cost diversification across "
            "asset classes rather than individual picks. Investments can lose value."
            % (
                _fmt(prio["monthly_surplus"]), _fmt(proj["total_contributed"] / max(proj["years"] * 12, 1)),
                proj["annual_return_pct"], proj["years"],
                _fmt(proj["future_value"]), _fmt(proj["growth"]), snap["risk_tolerance"],
            ),
            used,
        )

    if intent == "budget":
        budget = run("get_budget_breakdown")
        if budget["total_budgeted"] <= 0:
            return (
                "You have not set a budget for this month yet, so I cannot compare plan against "
                "actual. You are spending about %s a month against %s of income. Set a budget and "
                "I will tell you exactly where it is slipping." % (_fmt(snap["monthly_expenses"]), _fmt(snap["monthly_income"])),
                used,
            )
        # A one-cent overage is noise, not a leak — reporting "over by $0" is worse
        # than not mentioning it.
        over = [c for c in budget["categories"] if c["is_over"] and abs(c["remaining"]) >= 1]
        top = budget["categories"][:3]
        text = (
            "You have used %.0f%% of your budget this month — %s of %s planned.\n\n"
            "Your biggest categories are %s.\n\n"
            % (
                budget["utilization_pct"], _fmt(budget["total_spent"]), _fmt(budget["total_budgeted"]),
                ", ".join("%s at %s" % (c["name"], _fmt(c["actual"])) for c in top) or "not recorded yet",
            )
        )
        if over:
            text += "Over plan: %s. That is where to look first." % ", ".join(
                "%s by %s" % (c["name"], _fmt(abs(c["remaining"]))) for c in over[:4]
            )
        else:
            text += "Nothing is over plan, so the question is allocation rather than discipline — could any of that surplus be doing more elsewhere?"
        return (text, used)

    if intent == "savings":
        goals = run("get_savings_goals")
        text = (
            "Your emergency fund covers %.1f months of essentials, and you have about %s a month "
            "spare.\n\n" % (snap["emergency_fund_months"], _fmt(snap["monthly_surplus"]))
        )
        if snap["emergency_fund_months"] < 3:
            text += ("Getting that to three months is the highest-value thing you can do with "
                     "savings right now — it is what stops a surprise bill becoming new debt.\n\n")
        if goals["goals"]:
            behind = [g for g in goals["goals"] if g.get("on_track") is False]
            text += "You are tracking %d goal(s). " % len(goals["goals"])
            if behind:
                g = behind[0]
                text += ("%s is behind: it needs %s a month to hit its date and you are putting in %s. "
                         "Either raise the contribution or move the target date — both are honest choices."
                         % (g["name"], _fmt(g.get("required_monthly")), _fmt(g.get("current_monthly"))))
            else:
                text += "All of them are on track at your current contributions."
        else:
            text += "You have not set any savings goals yet. Naming what you are saving for makes it far more likely to happen."
        return (text, used)

    prio = run("get_priorities")
    health = run("get_health_score")
    steps = prio["steps"][:3]
    text = (
        "Your financial health score is %d out of 100 (%s). The weakest area is %s.\n\n"
        "You bring in %s a month and spend %s, leaving %s.\n\n"
        % (
            health["score"], health["grade"], health["weakest_component"],
            _fmt(snap["monthly_income"]), _fmt(snap["monthly_expenses"]), _fmt(snap["monthly_surplus"]),
        )
    )
    if prio["blocking_issue"] == "negative_cash_flow":
        text += ("You are spending more than you earn, so that is the only thing worth working on "
                 "right now. Every other goal is being funded by borrowing until it is closed.")
    else:
        text += "Here is where your next dollar should go:\n\n" + "\n".join(
            "%d. %s%s" % (s["rank"], s["title"],
                          (" — %s/mo" % _fmt(s["suggested_monthly"])) if s["suggested_monthly"] > 0 else "")
            for s in steps
        )
    return (text, used)


def _stream_stub(db: Session, user: User, history: List[dict]) -> Iterator[dict]:
    question = history[-1]["content"] if history else ""
    text, used = _stub_reply(db, user, question)

    for tool in used:
        yield {"type": "tool", **tool}

    # Emit in chunks so the UI streams identically on both runners.
    for i in range(0, len(text), 90):
        yield {"type": "text", "delta": text[i : i + 90]}

    yield {
        "type": "meta",
        "tools_used": used,
        "provider": "stub",
        "model": "deterministic",
        "input_tokens": 0,
        "output_tokens": 0,
    }


def stream_reply(db: Session, user: User, history: List[dict]) -> Iterator[dict]:
    """Yield events for one assistant turn, falling back to the stub on failure."""
    if settings.ai_provider == "anthropic" and settings.anthropic_api_key:
        try:
            for event in _stream_anthropic(db, user, history, build_briefing(db, user)):
                yield event
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("Chat failed on anthropic: %s", type(exc).__name__)
            yield {
                "type": "notice",
                "message": "The AI service was unavailable, so this answer comes from Bearly's own calculations.",
            }
    for event in _stream_stub(db, user, history):
        yield event
