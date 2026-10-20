"""Evidence-checked lifecycle links across archive facts, without a new extractor."""

import copy
import re
from datetime import date

from app.services.profiles import now

CHANGE = re.compile(r"改主意|改成|改为|改到|更正|说错|打错|不再|现在|目前|之前|后来|还是|同意|答应|取消|完成|发完|交完")
EXPLICIT_CORRECTION = re.compile(r"改主意|更正|说错|打错|改成|改为|改到|不再")
LIMITED = re.compile(r"这次|仅|只|但不|不过|不去|不包括|不延伸|公共|校内|学校|群里|私下")
RELATIONS = {"replace", "qualify", "conflict"}


def prune(profile):
    """Deleting/correcting a source must remove its copied transition history."""
    bank = {f["id"]: f for f in profile.get("facts", [])}
    for fact in bank.values():
        if "versions" in fact:
            fact["versions"] = [
                v
                for v in fact["versions"]
                if not v.get("source_fact_id")
                or v["source_fact_id"] in bank
                and bank[v["source_fact_id"]]["text"] == v.get("text")
            ]
        if "continuity_from" in fact:
            fact["continuity_from"] = [i for i in fact["continuity_from"] if i in bank]
        pending = fact.get("continuity_pending_from")
        if pending and pending not in bank:
            fact.pop("continuity_pending_from", None)
            fact.update(conflict=False, validity="current")
        removed = any(a.get("linked_fact_id") and a["linked_fact_id"] not in bank for a in fact.get("alternatives", []))
        if removed:
            fact["alternatives"] = [
                a for a in fact["alternatives"] if not a.get("linked_fact_id") or a["linked_fact_id"] in bank
            ]
            if not fact["alternatives"]:
                fact.update(conflict=False, validity="current")


def proposals(rows, facts):
    if not isinstance(rows, list) or len(rows) > 8:
        return []
    bank = {f["id"]: f for f in facts if not f.get("manual")}
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = (row.get("old_id"), row.get("new_id"))
        if key in seen or key[0] == key[1] or not all(i in bank for i in key) or row.get("relation") not in RELATIONS:
            continue
        old, new = (bank[i] for i in key)
        if old["subject"] != new["subject"] and new["subject"] != "relation":
            continue
        seen.add(key)
        result.append({"old_id": key[0], "new_id": key[1], "relation": row["relation"]})
    return result


def _newer(old, new):
    try:
        return date.fromisoformat(new["observed_on"]) > date.fromisoformat(old["observed_on"])
    except (KeyError, TypeError, ValueError):
        return False


def apply(profile, proposed, checked, sources=()):
    """Call inside the portrait transaction; reject any unverified transition."""
    if not isinstance(checked, list) or len(checked) > 8:
        return []
    bank = {f["id"]: f for f in profile.get("facts", [])}
    allowed = {(r["old_id"], r["new_id"], r["relation"]) for r in proposed}
    changed, used = [], set()
    for row in checked:
        if not isinstance(row, dict) or row.get("verdict") != "supported" or not str(row.get("reason", "")).strip():
            continue
        key = (row.get("old_id"), row.get("new_id"), row.get("relation"))
        if key not in allowed or key[0] in used:
            continue
        old, new = bank.get(key[0]), bank.get(key[1])
        if (
            not old
            or not new
            or any(f.get("manual_locked") or not f.get("use_in_ai", True) or f.get("conflict") for f in (old, new))
        ):
            continue
        unknown_conflict = key[2] == "conflict" and not (old.get("observed_on") and new.get("observed_on"))
        if (
            old.get("validity", "current") != "current"
            or new.get("validity", "current") != "current"
            or not (_newer(old, new) or unknown_conflict)
        ):
            continue
        role = old.get("subject")
        evidence = [e for e in new.get("evidence", []) if e.get("role") == role and not e.get("historical")]
        quote = row.get("quote")
        original_context = any(
            new["id"] in s.get("fact_ids", [])
            and any(
                t["role"] == role
                and isinstance(quote, str)
                and quote in t["content"]
                and t.get("chat_date") == new.get("observed_on")
                for t in s["turns"]
            )
            for s in sources
        )
        if (
            not isinstance(quote, str)
            or len(quote) < 4
            or not (any(quote in e["quote"] for e in evidence) or original_context)
        ):
            continue
        if old.get("subject") != new.get("subject") and new.get("subject") != "relation":
            continue
        if old.get("memory_type") == "relationship_position" and new.get("memory_type") != "relationship_position":
            continue  # Accepting an activity does not overturn a friend boundary.
        if old.get("event_identity") and new.get("event_identity") and old["event_identity"] != new["event_identity"]:
            continue
        if re.search(r"单独|两个人|私下", old["text"]) and re.search(r"四个人|多人|大家一起|聚餐|群体", quote):
            continue
        if (
            not CHANGE.search(quote)
            or old.get("memory_type") == "special_date"
            and not EXPLICIT_CORRECTION.search(quote)
        ):
            continue
        # Broader relationship reversals and unresolved contradictions require
        # the existing short confirmation flow. A clearly limited new agreement
        # can qualify an earlier boundary without generalizing its permission.
        review = key[2] == "conflict" or (old.get("memory_type") == "relationship_position")
        if key[2] == "qualify" and not LIMITED.search(quote):
            review = True
        if key[2] == "replace" and not EXPLICIT_CORRECTION.search(quote):
            review = True
        if review:
            old.update(conflict=True, validity="needs_confirmation")
            old["alternatives"] = [
                {
                    "text": new["text"],
                    "observed_on": new.get("observed_on"),
                    "linked_fact_id": new["id"],
                    "evidence_keys": [e.get("key") for e in evidence],
                }
            ]
            new.update(conflict=True, validity="needs_confirmation", continuity_pending_from=old["id"])
            changed.append({"old_id": old["id"], "new_id": new["id"], "relation": "pending"})
        else:
            version = {
                k: copy.deepcopy(old.get(k))
                for k in ("text", "context", "observed_on", "event_date", "event_status", "item_state", "retention")
            }
            new.setdefault("versions", []).append(
                {
                    **version,
                    "source_fact_id": old["id"],
                    "reason": "archive_" + key[2],
                    "validity": "superseded",
                    "at": now(),
                }
            )
            old.update(validity="superseded", superseded_by=new["id"])
            new.setdefault("continuity_from", []).append(old["id"])
            changed.append({"old_id": old["id"], "new_id": new["id"], "relation": key[2]})
        used.add(old["id"])
    return changed
