"""One read-only view of cumulative archive evidence for a person.

Consumes stored memory only. No scores, transcript analysis or extra model calls.
"""
from datetime import date
import re

from app.services.communication import today


def topic_grams(text):
    text = re.sub(r"\s+", "", text)
    return {text[i:i+2] for i in range(len(text)-1)} - {"喜欢", "喜好", "习惯", "兴趣", "偏好", "沟通"}

CONTEXT_TYPES = {"emotional_state", "stage_context", "event"}


def view_item(f):
    evidence = [e for e in f.get("evidence", []) if not e.get("historical")]
    dates = sorted({e["chat_date"] for e in evidence if e.get("chat_date") and not e.get("context_only")})
    manual = f.get("manual_locked") or f.get("source_level") == "user_note"
    if manual:
        evidence = []  # Original quotes are not evidence for a human's replacement text.
    source = "我的补充 / 修正" if manual else "双方互动" if f.get("source_level") == "interaction" else "本人表达"
    if not manual and f.get("claim_basis") in {"observed", "inferred"}:
        source = "观察到的表现" if f["claim_basis"] == "observed" else "有限推断"
    when = f.get("observed_on")
    age = (date.fromisoformat(today()) - date.fromisoformat(when)).days if when else None
    temporary = f.get("retention") == "temporary"
    return {"id": f["id"], "topic": f["topic"], "text": f["text"], "scope": f.get("context", ""),
            "scene": f.get("scene", "everyday"), "memory_type": f.get("memory_type"),
            "subject": f.get("subject", "other"), "source": source, "observed_on": when,
            "dated_observations": len(dates), "temporary": temporary,
            "historical": f.get("validity") == "ended" or (temporary and (age is None or age > 7)),
            "interpretation": f.get("interpretation", ""), "limitation": f.get("limitation", ""),
            "claim_basis": f.get("claim_basis", "stated"), "alternative": f.get("alternative", ""),
            "event_date": f.get("event_date"), "date_text": f.get("date_text", ""),
            "event_status": f.get("event_status", "unknown"), "evidence": evidence,
            "branches": f.get("branches", []), "versions": f.get("versions", [])}


def board_for(public):
    """Use the already scrubbed public profile so internal hashes never leak."""
    usable = [f for f in public["facts"] if f.get("memory_version") == 3
              and f.get("retention") != "pending" and not f.get("conflict")
              and f.get("validity") in {"current", "ended"}]
    usable.sort(key=lambda f: (f.get("observed_on") or "", f.get("last_seen", "")), reverse=True)
    rows = [view_item(f) for f in usable]
    stance_rows = [r for r in rows if r["memory_type"] == "relationship_position" and r["source"] == "本人表达"]
    stances = []
    for subject in ("other", "self"):
        owned = [r for r in stance_rows if r["subject"] == subject]
        recent = [r for r in owned if not r["historical"]]
        stances.extend(recent or owned[:1])  # An old explicit stance stays inspectable, clearly dated.
    interactions = [r for r in rows if r["memory_type"] == "interaction_signal"]
    # Scenes remain compatible stored context, never a navigation/filter choice.
    # Manual corrections are retained in the main view without becoming partner stances.
    knowledge = [r for r in rows if r["memory_type"] not in CONTEXT_TYPES
                 and r not in stances and r not in interactions and not r["historical"]]
    # Put distinctive knowledge before constraints already shown in method cards.
    priority = {"situated_trait":0,"useful_preference":1,"personal_view":2}
    knowledge.sort(key=lambda r: (0 if r["source"]=="我的补充 / 修正" else 1,
                                 priority.get(r["memory_type"],3)))
    context = [r for r in rows if r["memory_type"] in CONTEXT_TYPES and not r["historical"]]
    sections = [{"title": "对 TA 的了解", "items": knowledge[:8]},
                {"title": "最近提到的事", "items": context[:6]}]
    sections = [s for s in sections if s["items"]]
    interests = [r for r in knowledge if r["memory_type"] in {"useful_preference", "personal_view"} and r["subject"] == "other"]
    by_id = {f["id"]: f for f in public["facts"]}
    prior_topics = [topic_grams(f["topic"]) for f in public["facts"]
                    if f.get("kind") == "preference" and f.get("status") in {"confirmed", "corrected"}]
    # Continuity only ranks presentation; it does not validate or strengthen a claim.
    interests.sort(key=lambda r: (any(topic_grams(r["topic"]) & old for old in prior_topics),
                                 by_id[r["id"]].get("retention") == "conditional",
                                 r.get("observed_on") or "",
                                 min(len({e["quote"] for e in r["evidence"]}), 4)), reverse=True)
    legacy = []
    for f in public["facts"]:
        if (f.get("memory_version") == 3 or f.get("validity") != "current" or f.get("conflict")
                or f.get("status") not in {"confirmed", "corrected"}):
            continue
        if f.get("category") not in {"preference", "style", "trait", "boundary"}:
            continue
        legacy.append({"id": f["id"], "topic": f["topic"], "text": f["text"], "scope": f.get("context", ""),
                       "source": "旧版摘录，待复核", "subject": "other", "memory_type": "legacy",
                       "evidence": f.get("evidence", []), "observed_on": f.get("observed_on")})
    interests.extend(r for r in legacy if by_id[r["id"]].get("category") == "preference"
                     and not any(r["topic"] == current["topic"] for current in interests))
    characteristics = [r for r in knowledge if r["memory_type"] in {"situated_trait", "shared_understanding", "user_note"}]
    characteristics.extend(r for r in legacy if by_id[r["id"]].get("category") in {"style", "trait"})
    boundaries = [r for r in knowledge if r["memory_type"] in {"boundary", "communication_request"}
                  and by_id[r["id"]].get("retention") == "conditional"]
    portrait = [{"title": "兴趣与关注", "items": interests[:4]},
                {"title": "沟通特点", "items": characteristics[:4]},
                {"title": "关系与边界", "items": (stances + boundaries)[:4]}]
    portrait = [group for group in portrait if group["items"]]
    methods = [c for c in public["method_cards"]
               if c.get("memory_type") not in CONTEXT_TYPES | {"relationship_position"}]
    methods.sort(key=lambda c: (c.get("memory_type") == "boundary", c.get("observed_on") or ""), reverse=True)
    interest_order = {r["id"]: i for i, r in enumerate(interests)}
    methods.sort(key=lambda c: (c.get("memory_type") == "boundary",
                               -interest_order.get(c["fact_id"], 100), c.get("observed_on") or ""), reverse=True)
    visible_methods=[]
    # Include one boundary, one response habit and one constructive topic where present.
    for kinds in ({"boundary"},{"communication_request","support_need","situated_trait"},{"useful_preference","personal_view"}):
        picked=next((c for c in methods if c.get("memory_type") in kinds),None)
        if picked:
            visible_methods.append(picked)
    for c in methods:
        if len(visible_methods)>=3:
            break
        if c not in visible_methods:
            visible_methods.append(c)
    visible_methods.sort(key=lambda c: (c.get("memory_type") != "boundary", interest_order.get(c["fact_id"], 100)))
    timeline = []
    for f in usable:
        if f.get("versions"):
            chain = f["versions"][-3:] + [f]
            for v, following in zip(chain, chain[1:], strict=False):
                following_text = following.get("text", "")
                if v.get("text") and v["text"] != following_text:
                    timeline.append({"fact_id": f["id"], "topic": f["topic"], "before": v["text"],
                                     "after": following_text, "date": following.get("observed_on"),
                                     "scene": f.get("scene", "everyday"), "manual": bool(f.get("manual_locked"))})
    timeline.sort(key=lambda r: r["date"] or "", reverse=True)
    return {"sections": sections, "portrait": portrait, "methods": visible_methods, "stances": stances[:6], "interactions": interactions[:6],
            "reviews": [{"id": f["id"], "topic": f["topic"], "before": f["text"], "after": f["alternatives"][-1]["text"]}
                        for f in public["facts"] if f.get("conflict") and f.get("alternatives") and not f.get("manual_locked")],
            "timeline": timeline[:12], "pending": sum(bool(f.get("conflict") or f.get("retention") == "pending") for f in public["facts"]),
            "unknowns": (["只有过去的表达，不能据此确定对方现在的态度。"] if stances and all(r["historical"] for r in stances) else
                         ["还没有对方明确表达的关系态度；友好互动不能代替这个答案。"]
                         if not any(r["subject"] == "other" and any(re.search(r"你|我们|咱们|做朋友|当朋友", e["quote"]) for e in r["evidence"] if e["role"] == "other") for r in stances) else []),
            "version": "archive-v6.0"}
