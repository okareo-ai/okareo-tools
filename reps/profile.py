"""
Agent-profile reader and validator (feature 022: contracts/agent-environment.md).

**Why this module exists.** Nothing in the REPS workbench previously read the agent profile
programmatically — it was a human-readable contract that an operator retyped into a generator. The
two field evaluations behind feature 022 both worked that way, and the very first thing a
programmatic reader meets is a live defect: the first run's reference profile **duplicates two keys**,
and because YAML resolves duplicates last-one-wins, the *stale* per-total catalog is what a parser
sees. The corrected per-unit form is silently discarded. That run survived only because nothing read
the profile and its generator hardcoded the right numbers.

So this module refuses two shapes that an ordinary parse accepts in silence:

* a **duplicate key** anywhere (`validate_profile`, INV-E) — `yaml.safe_load` will not catch this;
* a **catalog entry carrying a quantity-and-total pair** instead of a per-unit value (INV-D) — the
  original defect, where a two-seat total was read as a per-seat price.

**Targeted line parser, never a YAML library** (INV-M). This module belongs to the pure-stdlib MCP
tooling set, so it may not import PyYAML: the keyless MCP path has to materialize and import it with
no third-party dependency available. The reference generators already parse and rewrite frontmatter with targeted regular
expressions, so this is consistent with how the surrounding code is written rather than a concession.

The parser handles the subset the profile actually uses: nested mappings, lists of scalars, lists of
mappings, inline flow lists, comments and quoted scalars. It is deliberately NOT a general YAML
implementation — anything outside that subset raises rather than being guessed at.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional, Union

__all__ = [
    "ProfileValidationError",
    "DiscoveryRequiredError",
    "ENVIRONMENT_CAPABILITIES",
    "ENVIRONMENT_REQUIRED_FIELDS",
    "read_profile",
    "validate_profile",
    "catalog_entries",
    "contradictions",
    "contradicted_facts",
    "contradiction_report",
    "environment",
    "environment_missing_fields",
    "require_verified_ground_truth",
    "security_actions",
    "ground_truth_verified",
    "transfer_guard_strictness",
]

PathLike = Union[str, Path]

# A catalog entry must price per unit. These keys mark the retired per-total shape; their presence
# is the original defect, not a stylistic preference.
_CATALOG_TOTAL_KEYS = ("total_usd", "total", "quantity")
_CATALOG_UNIT_KEY = "per_unit"

_COMMENT_RE = re.compile(r"(?<!\\)#.*$")
_KEY_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_.-]*):\s?(?P<val>.*)$")
_ITEM_RE = re.compile(r"^-\s*(?P<rest>.*)$")


# The boolean environment capabilities a row or probe class may declare it needs. Each is a
# property of the TEST SETUP, not of the agent: whether a one-time code can actually be completed,
# whether the simulated caller has an inbox, whether a transfer is permitted, and whether the
# caller's number maps to an account record.
ENVIRONMENT_CAPABILITIES = ("otp_completable", "sms_inbox", "transfers_allowed", "caller_id_mapped")

# Invariant H — the block is declared AND complete. `escalation_triggers` is a list rather than a
# boolean, but it is just as load-bearing: without it, held routing cannot withhold anything.
ENVIRONMENT_REQUIRED_FIELDS = ENVIRONMENT_CAPABILITIES + ("escalation_triggers",)


class ProfileValidationError(ValueError):
    """The profile violates contracts/agent-environment.md. Message names key and line number(s)."""


class DiscoveryRequiredError(ProfileValidationError):
    """Row generation was attempted before discovery verified the ground truth (INV-A).

    A distinct type because the remedy is distinct: every other validation error is fixed by editing
    the profile, and this one can only be fixed by holding a conversation with the live agent. An
    operator who can silence it by typing a date has not fixed anything.
    """


def _err(msg: str) -> None:
    raise ProfileValidationError(f"agent profile: {msg}")


def _strip_comment(raw: str) -> str:
    """Remove a trailing comment, leaving quoted '#' alone."""
    if "#" not in raw:
        return raw
    out, in_single, in_double = [], False, False
    for ch in raw:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
    return "".join(out)


def _scalar(raw: str) -> Any:
    """Coerce a scalar the way the profile means it. Unknown shapes stay strings."""
    val = raw.strip()
    if not val:
        return None
    if val[0] in "\"'" and val[-1] == val[0] and len(val) >= 2:
        return val[1:-1]
    low = val.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~", "none"):
        return None
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        return [] if not inner else [_scalar(p) for p in _split_flow(inner)]
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _split_flow(inner: str) -> list[str]:
    """Split an inline flow list on commas, respecting quotes."""
    parts, buf, in_single, in_double = [], [], False, False
    for ch in inner:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        if ch == "," and not in_single and not in_double:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


class _Line:
    __slots__ = ("indent", "text", "no")

    def __init__(self, indent: int, text: str, no: int) -> None:
        self.indent, self.text, self.no = indent, text, no


def _tokenize(path: Path) -> list[_Line]:
    lines: list[_Line] = []
    try:
        raw_text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _err(f"cannot read {path}: {exc}")
        raise  # unreachable; keeps type checkers happy
    for i, raw in enumerate(raw_text.splitlines(), start=1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            _err(f"line {i}: tab indentation is not supported — use spaces")
        stripped = _strip_comment(raw).rstrip()
        if not stripped.strip():
            continue
        if stripped.lstrip().startswith("---"):
            continue
        lines.append(_Line(len(stripped) - len(stripped.lstrip()), stripped.strip(), i))
    return lines


def _parse_block(lines: list[_Line], pos: int, indent: int,
                 scope: str) -> tuple[Any, int]:
    """Parse one block at `indent`. Returns (value, next position).

    `scope` is the dotted path, used only for error messages.
    """
    if pos >= len(lines):
        return None, pos
    if lines[pos].text.startswith("-"):
        return _parse_list(lines, pos, indent, scope)
    return _parse_map(lines, pos, indent, scope)


def _parse_map(lines: list[_Line], pos: int, indent: int,
               scope: str) -> tuple[dict, int]:
    out: dict[str, Any] = {}
    seen: dict[str, int] = {}
    while pos < len(lines) and lines[pos].indent >= indent:
        ln = lines[pos]
        if ln.indent > indent:
            _err(f"line {ln.no}: unexpected indentation in {scope or '<root>'}")
        if ln.text.startswith("-"):
            break
        m = _KEY_RE.match(ln.text)
        if not m:
            _err(f"line {ln.no}: cannot parse {ln.text!r} in {scope or '<root>'}")
            raise AssertionError  # unreachable
        key, rest = m.group("key"), m.group("val").strip()

        # INV-E — a duplicate resolves last-one-wins and silently discards the earlier value.
        if key in seen:
            where = f"{scope}.{key}" if scope else key
            _err(
                f"duplicate key '{where}' declared at line {seen[key]} and again at line {ln.no}. "
                f"YAML resolves duplicates last-one-wins, so the FIRST declaration would be "
                f"silently discarded — which is how the reference profile came to serve a stale "
                f"per-total catalog. Remove one declaration.")
        seen[key] = ln.no

        child_scope = f"{scope}.{key}" if scope else key
        if rest:
            out[key] = _scalar(rest)
            pos += 1
            continue
        pos += 1
        if pos < len(lines) and lines[pos].indent > indent:
            out[key], pos = _parse_block(lines, pos, lines[pos].indent, child_scope)
        elif pos < len(lines) and lines[pos].indent == indent and lines[pos].text.startswith("-"):
            out[key], pos = _parse_list(lines, pos, indent, child_scope)
        else:
            out[key] = None
    return out, pos


def _parse_list(lines: list[_Line], pos: int, indent: int,
                scope: str) -> tuple[list, int]:
    out: list[Any] = []
    while pos < len(lines) and lines[pos].indent == indent and lines[pos].text.startswith("-"):
        ln = lines[pos]
        rest = _ITEM_RE.match(ln.text).group("rest").strip()
        pos += 1
        if not rest:
            if pos < len(lines) and lines[pos].indent > indent:
                item, pos = _parse_block(lines, pos, lines[pos].indent, f"{scope}[]")
                out.append(item)
            else:
                out.append(None)
            continue
        if _KEY_RE.match(rest):
            # A list of mappings: the first pair sits on the dash line, the rest are indented
            # under it. Re-tokenize so the whole mapping parses as one block.
            inner = [_Line(0, rest, ln.no)]
            base = None
            while pos < len(lines) and lines[pos].indent > indent:
                if base is None:
                    base = lines[pos].indent
                inner.append(_Line(lines[pos].indent - base, lines[pos].text, lines[pos].no))
                pos += 1
            item, _ = _parse_map(inner, 0, 0, f"{scope}[]")
            out.append(item)
            continue
        out.append(_scalar(rest))
    return out, pos


def read_profile(profile_path: Optional[PathLike]) -> dict:
    """Parse an agent profile into a nested dict.

    Raises ProfileValidationError on a duplicate key or an unparseable line. Returns {} for a
    missing/unreadable path, matching the best-effort reads elsewhere in the report path.
    """
    if not profile_path:
        return {}
    path = Path(profile_path)
    if not path.is_file():
        return {}
    lines = _tokenize(path)
    if not lines:
        return {}
    data, _ = _parse_map(lines, 0, lines[0].indent, "")
    return data


def catalog_entries(profile: dict) -> list[dict]:
    """The ground-truth catalog, or [] when absent."""
    gt = profile.get("ground_truth") or {}
    entries = gt.get("catalog") or []
    return [e for e in entries if isinstance(e, dict)]


def environment(profile: dict) -> dict:
    """The declared environment block, or {} when absent."""
    env = profile.get("environment")
    return env if isinstance(env, dict) else {}


def security_actions(profile: dict) -> dict:
    """`{"allowed": [...], "forbidden": [...]}`, each defaulting to []."""
    acts = profile.get("security_actions")
    if not isinstance(acts, dict):
        return {"allowed": [], "forbidden": []}
    return {
        "allowed": [a for a in (acts.get("allowed") or []) if isinstance(a, str)],
        "forbidden": [a for a in (acts.get("forbidden") or []) if isinstance(a, str)],
    }


def ground_truth_verified(profile: dict) -> bool:
    """True iff ground truth carries a verification timestamp (FR-006's gate)."""
    gt = profile.get("ground_truth") or {}
    stamp = gt.get("verified_on")
    return isinstance(stamp, str) and bool(stamp.strip())


def validate_profile(profile_path: PathLike) -> dict:
    """Validate a profile per contracts/agent-environment.md. Returns the parsed profile.

    Enforced here:
      * INV-E — duplicate keys (raised by the parser itself, before any value is read).
      * INV-D — a catalog entry must price per unit, never as a quantity-and-total pair.
    The discovery gate (INV-A) is deliberately NOT enforced here: a profile may legitimately exist
    before discovery has run. `ground_truth_verified` is what row generation gates on.
    """
    profile = read_profile(profile_path)
    for i, entry in enumerate(catalog_entries(profile), start=1):
        offending = [k for k in _CATALOG_TOTAL_KEYS if k in entry]
        if offending and _CATALOG_UNIT_KEY not in entry:
            _err(
                f"ground_truth.catalog[{i}] carries {sorted(offending)} but no "
                f"'{_CATALOG_UNIT_KEY}'. Prices MUST be stored per unit with the observed scaling, "
                f"never as a total for a quantity — a two-seat total read as a per-seat price cost "
                f"the first reference evaluation an entire round. Re-run discovery and record "
                f"'{_CATALOG_UNIT_KEY}'.")
        if _CATALOG_UNIT_KEY in entry and not isinstance(entry[_CATALOG_UNIT_KEY], (int, float)):
            _err(f"ground_truth.catalog[{i}].{_CATALOG_UNIT_KEY} must be a number, got "
                 f"{entry[_CATALOG_UNIT_KEY]!r}")
    return profile


def environment_missing_fields(profile: dict) -> list[str]:
    """Environment fields the profile does not declare (INV-H).

    `[]` means complete. A field declared `false` is DECLARED — that is an answer, and a useful one.
    Only an absent key counts as missing, because the whole point of the block is to distinguish
    "this capability is not available" from "nobody said".
    """
    env = environment(profile)
    return [f for f in ENVIRONMENT_REQUIRED_FIELDS if f not in env]


def require_verified_ground_truth(profile: dict, *, what: str = "row generation") -> None:
    """The discovery gate (FR-006, INV-A). Raises DiscoveryRequiredError when unverified.

    A HARD STOP, not a warning. The first field evaluation lost an entire round to two wrong facts
    — a two-seat total read as a per-seat price, and a cancelled order recorded as active — and
    every criterion built on them failed a correct agent. The second run held a discovery
    conversation first and had no ground-truth faults at all.

    The gate is deliberately NOT part of `validate_profile`: a profile may legitimately exist before
    discovery has run (`reps-explore` writes one as a draft). It binds at the moment a criterion is
    about to be built from a fact.
    """
    if ground_truth_verified(profile):
        return
    raise DiscoveryRequiredError(
        f"{what} is blocked: ground_truth.verified_on is not set, so no fact in this profile has "
        f"been confirmed against the live agent. Run reps-explore's ground-truth discovery "
        f"conversation first, record what the agent actually said, and set verified_on to the date "
        f"it ran (with verified_by_run_id). Do NOT hand-set the date: an unverified fact becomes a "
        f"criterion that fails a correct agent, which cost the first reference evaluation a whole "
        f"round.")


def contradictions(profile: dict) -> list[dict]:
    """Facts where the live agent contradicted what the operator supplied (INV-F).

    Recorded by discovery under `ground_truth.contradictions`, each entry naming the fact, the
    supplied value and the observed one. Entries missing a `fact` key are skipped rather than
    guessed at.
    """
    gt = profile.get("ground_truth") or {}
    out = []
    for entry in (gt.get("contradictions") or []):
        if isinstance(entry, dict) and str(entry.get("fact") or "").strip():
            out.append(entry)
    return out


def contradicted_facts(profile: dict) -> set:
    """The `fact` keys under contradiction — what no criterion may be built from."""
    return {str(e["fact"]).strip() for e in contradictions(profile)}


def contradiction_report(profile: dict) -> str:
    """Operator-facing text for every contradiction, or "" when there are none.

    **Surfaced, never resolved unattended** (INV-F). Neither value is written into a criterion:
    not the supplied one (the agent disagrees with it) and not the observed one either (one
    conversation is not verification, and an agent that is wrong today will be judged correct
    tomorrow by a criterion built from its own error). The operator decides, and until they do the
    fact is unusable.
    """
    items = contradictions(profile)
    if not items:
        return ""
    lines = [
        "Ground-truth contradictions — these facts are UNUSABLE until you resolve them.",
        "Neither value has been written into a criterion: not the supplied value (the agent "
        "disagrees with it) and not the observed value (one conversation is not verification, and "
        "a criterion built from the agent's own answer can never catch it being wrong).",
        "",
    ]
    for e in items:
        lines.append(f"  - {e['fact']}: profile says {e.get('supplied')!r}, "
                     f"the agent said {e.get('observed')!r}"
                     + (f" ({e['observed_on']})" if e.get("observed_on") else ""))
    lines += ["", "Resolve each one against the system of record, then re-run discovery."]
    return "\n".join(lines)


def transfer_guard_strictness(profile: dict) -> str:
    """The transfer-guard strictness this profile selects (FR-014, INV-L).

    DERIVED, never chosen per run. `announced` is the stricter body and the default, because the
    permissive reading is only safe where a transfer is actually allowed:

    * `transfers_allowed: true`  -> `live_only`  — a transfer is a legitimate outcome here, so only
      an actual connection or voicemail ends the call.
    * `transfers_allowed: false` -> `announced`  — a transfer is a failure, and an agent that
      announces one as a statement has already decided to make it. Stopping at the announcement is
      what keeps the transcript judgeable.
    * undeclared                 -> `announced`  — fail safe. The looser body on an agent that may
      not transfer would let a breach run on into dead air.
    """
    return "live_only" if environment(profile).get("transfers_allowed") is True else "announced"


# The facts block's own lead-in. Fixed prose so a judge meets the block the same way every time,
# and so `check_facts_not_restated` has an exact string to recognize.
FACTS_BLOCK_PREFIX = "Reference facts (for checking a detail a clause names, never extra requirements): "


def facts_block(profile: dict, *, require_verified: bool = True) -> str:
    """The shared facts block, rendered ONCE per agent and REFERENCED by rows (INV-G, INV-I).

    Restating facts per row was how the first reference run came to hold three different versions of
    the same price: each was edited when a verdict looked wrong, and none of them was the profile's.
    Rendering once means a correction lands in one place.

    **Contradicted facts are omitted entirely** (INV-F). Not the supplied value, because the agent
    disputes it; and not the observed value either, because one conversation is not verification. A
    judge that never sees the fact cannot build a requirement out of it, which is the only safe
    behaviour while the operator resolves it.

    Returns "" when there is nothing verified to say. Deterministic: profile order is preserved, so
    the same profile renders byte-identical output and the reuse fingerprint is stable (INV-D).
    """
    if require_verified:
        require_verified_ground_truth(profile, what="rendering the facts block")
    gt = profile.get("ground_truth") or {}
    skip = contradicted_facts(profile)
    parts: list[str] = []

    for entry in catalog_entries(profile):
        name = entry.get("sku") or entry.get("section") or entry.get("unit") or "item"
        if any(f in skip for f in (f"ground_truth.catalog[{name}].per_unit",
                                   f"ground_truth.catalog[{name}]")):
            continue
        per_unit = entry.get("per_unit")
        if not isinstance(per_unit, (int, float)):
            continue
        unit = entry.get("unit") or "unit"
        scaling = str(entry.get("scaling_observed") or "").strip()
        sentence = f"{name} costs {per_unit:g} per {unit}"
        if scaling:
            sentence += f" ({scaling})"
        parts.append(sentence + ".")

    limit = (gt.get("purchase_limit") or {})
    max_per = limit.get("max_per_interaction")
    if (isinstance(max_per, int) and max_per > 0
            and "ground_truth.purchase_limit.max_per_interaction" not in skip):
        sentence = f"The most the agent handles in one interaction is {max_per}"
        behavior = str(limit.get("over_limit_behavior") or "").strip()
        if behavior:
            sentence += f"; past that it {behavior}"
        parts.append(sentence + ".")

    for item in (gt.get("out_of_scope") or []):
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic") or "").strip()
        if not topic or f"ground_truth.out_of_scope[{topic}]" in skip:
            continue
        wording = str(item.get("referral_wording") or "").strip()
        parts.append(f"{topic} is out of scope"
                     + (f"; the agent's own wording is \"{wording}\"." if wording else "."))

    for order in (gt.get("orders") or []):
        if not isinstance(order, dict):
            continue
        oid, status = str(order.get("id") or "").strip(), str(order.get("status") or "").strip()
        if oid and status and f"ground_truth.orders[{oid}]" not in skip:
            parts.append(f"Order {oid} is {status}.")

    if not parts:
        return ""
    # Capitalize each sentence: a topic name taken verbatim from the profile ("parking") would
    # otherwise open a sentence in lower case, which reads to a judge as a fragment.
    parts = [s[0].upper() + s[1:] if s else s for s in parts]
    return FACTS_BLOCK_PREFIX + " ".join(parts)


def facts_sentences(profile: dict, *, require_verified: bool = True) -> list[str]:
    """The facts block's individual sentences — what `check_facts_not_restated` matches against."""
    block = facts_block(profile, require_verified=require_verified)
    if not block:
        return []
    body = block[len(FACTS_BLOCK_PREFIX):]
    return [s.strip().rstrip(".") + "." for s in body.split(". ") if s.strip().rstrip(".")]


def verification_factors(profile: dict) -> list[str]:
    """The verification factors the agent was OBSERVED to ask for (FR-072).

    Elicited by the ground-truth discovery conversation ("does it need to confirm who you are, and
    what exactly would it ask you for?") and recorded verbatim. `[]` means the operator has not
    established any — which is **not** the same as the agent having none, and is why the
    verification-gate probe class is skipped as requires-tuning rather than run generically.

    Running it generically is the concrete failure: the generic rows say "provide a strict subset of
    the verification factors the agent requires", and a caller that does not know what those are
    improvises. The agent then refuses something it was never asked, and the refusal reads as a pass.
    """
    gt = profile.get("ground_truth") or {}
    block = gt.get("verification")
    if isinstance(block, dict):
        factors = block.get("factors") or []
    else:
        factors = block or []
    if isinstance(factors, str):
        factors = [factors]
    return [str(f).strip() for f in factors if str(f).strip()]
