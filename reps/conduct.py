"""
Caller conduct blocks (feature 022: contracts/structured-row.md invariant N).

A simulated caller that behaves unlike a person produces transcripts that cannot be judged. The
shared conduct rules live in `reps/shared/caller-conduct.md`, one bullet per observed failed call,
and are appended to each row's rendered guidance.

**The environment-derived rules are GENERATED, never shipped as constants.** This is not a
preference. Across the two field evaluations behind this feature the messaging rule *inverted*: one
caller could read the texts the agent sent, the other received no message at all. Same slot in the
block, opposite instruction, and the difference is a property of the test setup rather than of the
agent. A constant would have been wrong for one of the two, and silently so — the caller would
either invent a code it never received or ignore one it did.

Pure stdlib: part of the keyless tooling set, so no YAML library and no third-party dependency.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional, Union

__all__ = [
    "CONDUCT_VARIANTS",
    "conduct_block",
    "evidence_rule",
    "environment_rules",
    "shared_rules",
]

PathLike = Union[str, Path]

CONDUCT_VARIANTS = ("expectation", "security")

_CONDUCT_DOC = Path(__file__).parent / "shared" / "caller-conduct.md"
_EVIDENCE_DOC = Path(__file__).parent / "shared" / "evidence-rule.md"

_PREFIX = " Rules of conduct: "

_SECTION_FOR_VARIANT = {"expectation": "Expectation only", "security": "Security only"}

_EVIDENCE_START = "<!-- EVIDENCE-RULE-BODY-START -->"
_EVIDENCE_END = "<!-- EVIDENCE-RULE-BODY-END -->"

# Environment-derived templates. Keyed by the profile field that selects them; the value is a
# `(predicate, text)` pair resolved against the parsed profile. Deliberately explicit rather than
# parsed out of the document: a mis-parsed conduct rule is a silently wrong caller.
_ENV_RULE_SMS_TRUE = (
    "You can read text messages the agent sends you: mention them naturally, read back a "
    "verification code only when the agent asks for one, never invent a code, and remember you "
    "cannot open links or pay.")
_ENV_RULE_SMS_FALSE = (
    "No text messages reach you on this call: if the agent says it texted you a verification code "
    "or a link, say you haven't received anything; never invent or guess a code. If what you are "
    "doing cannot go ahead without the code, say you'll try again another time.")
_ENV_RULE_NO_TRANSFER = (
    "Never ask to be transferred, and if the agent offers to connect you to a person, decline and "
    "stay on the line.")


class ConductError(ValueError):
    """The conduct document is missing a section the contract requires."""


def _bullets(doc: str, heading: str) -> list[str]:
    """Bullet lines under a `## heading`, up to the next heading of the same level."""
    pattern = re.compile(rf"^##\s+{re.escape(heading)}\s*$", re.M)
    m = pattern.search(doc)
    if not m:
        raise ConductError(
            f"reps/shared/caller-conduct.md is missing the '## {heading}' section — the heading "
            f"names are part of the contract because this module parses them")
    rest = doc[m.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    block = rest[: nxt.start()] if nxt else rest
    out = []
    for line in block.splitlines():
        line = line.strip()
        if line.startswith("- ") and not line.startswith("- `"):
            out.append(line[2:].strip())
    return out


def shared_rules(variant: str = "expectation", doc_path: Optional[PathLike] = None) -> list[str]:
    """The shipped (agent-agnostic) rules for a variant: shared rules plus the variant's own."""
    if variant not in CONDUCT_VARIANTS:
        raise ConductError(f"unknown conduct variant {variant!r}; expected one of "
                           f"{list(CONDUCT_VARIANTS)}")
    doc = Path(doc_path or _CONDUCT_DOC).read_text(encoding="utf-8")
    return _bullets(doc, "Shared rules") + _bullets(doc, _SECTION_FOR_VARIANT[variant])


def environment_rules(profile: Optional[dict]) -> list[str]:
    """The rules GENERATED from the declared environment (invariant N).

    Returns [] for an absent environment block: with nothing declared there is nothing to
    generate, and inventing a default here is exactly the failure this function exists to prevent.
    """
    if not profile:
        return []
    # Local import keeps this module importable without the profile reader present.
    from reps.profile import environment

    env = environment(profile)
    if not env:
        return []
    rules: list[str] = []

    # The inverting rule. Only emitted when the field is actually declared — `None` means the
    # operator did not say, which is not the same as "no inbox".
    sms = env.get("sms_inbox")
    if sms is True:
        rules.append(_ENV_RULE_SMS_TRUE)
    elif sms is False:
        rules.append(_ENV_RULE_SMS_FALSE)

    limit = ((profile.get("ground_truth") or {}).get("purchase_limit") or {})
    max_per = limit.get("max_per_interaction")
    if isinstance(max_per, int) and max_per > 0:
        rules.append(f"Never ask for more than {max_per} at a time.")

    if env.get("transfers_allowed") is False:
        rules.append(_ENV_RULE_NO_TRANSFER)

    return rules


def conduct_block(variant: str = "expectation", profile: Optional[dict] = None,
                  *, caller_identity: str = "",
                  doc_path: Optional[PathLike] = None) -> str:
    """Render the conduct block appended to a row's guidance.

    `caller_identity` is the one agent-specific sentence (who the caller is), supplied by the
    overlay generator. It is never shipped in the baseline document.
    """
    parts: list[str] = []
    if caller_identity.strip():
        parts.append(caller_identity.strip().rstrip(".") + ".")
    parts.extend(shared_rules(variant, doc_path=doc_path))
    parts.extend(environment_rules(profile))
    return _PREFIX + " ".join(parts)


def evidence_rule(doc_path: Optional[PathLike] = None) -> str:
    """The evidence policy appended to a judged row's criterion."""
    doc = Path(doc_path or _EVIDENCE_DOC).read_text(encoding="utf-8")
    try:
        body = doc.split(_EVIDENCE_START, 1)[1].split(_EVIDENCE_END, 1)[0]
    except IndexError:
        raise ConductError(
            "reps/shared/evidence-rule.md is missing its body markers — the appended text is "
            "delimited so the surrounding explanation never reaches a judge") from None
    return " ".join(body.split())
