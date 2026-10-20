"""Lifecycle behavior, provenance, privacy and confirmation regressions."""

import copy
import pytest

from app.schemas.communication import Candidate
from app.services import archive_continuity as ac, communication as cm
from app.services.profiles import ProfileStore, public_profile


def pair(
    store,
    *,
    old_type="boundary",
    new_type="interaction_signal",
    old_text="目前不愿单独见面，先聊天。",
    new_text="我改主意了，只同意这次在学校公共咖啡厅见面，但不去校外。",
):
    rows = []
    for index, (kind, text, day) in enumerate([(old_type, old_text, "2026-10-11"), (new_type, new_text, "2026-10-16")]):
        c = Candidate(
            memory_type=kind,
            topic="见面意愿" if index == 0 else "见面安排",
            fact=text,
            scope="当前关系",
            retention="conditional",
            subject="other",
            evidence=[{"message_id": index, "quote": text}],
        ).model_dump()
        f = cm.new_fact(store, c, day)
        f["evidence"] = [
            {
                "quote": text,
                "role": "other",
                "message_number": index + 1,
                "chat_date": day,
                "key": str(index),
                "historical": False,
            }
        ]
        rows.append(f)
    return rows


def transition(rows, relation="qualify"):
    p = {"old_id": rows[0]["id"], "new_id": rows[1]["id"], "relation": relation}
    return [p], [{**p, "verdict": "supported", "quote": rows[1]["text"], "reason": "明确的较新限定同意"}]


def test_limited_new_consent_retires_old_current_fact_but_preserves_history(tmp_path):
    rows = pair(ProfileStore(tmp_path))
    profile = {"facts": rows}
    original = rows[0]["text"]
    p, a = transition(rows)
    assert ac.apply(profile, p, a)[0]["relation"] == "qualify"
    assert rows[0]["validity"] == "superseded" and rows[0]["text"] == original
    assert rows[1]["validity"] == "current" and "不去校外" in rows[1]["text"]
    assert rows[1]["versions"][0]["text"] == original
    assert not ac.apply(profile, p, a), "Rebuilding twice must not duplicate a transition"


@pytest.mark.parametrize(
    "change",
    ["manual", "no_ai", "unknown_order", "older", "wrong_owner", "invented_quote", "unsupported", "unproposed"],
)
def test_no_transition_without_provenance_and_chronology(tmp_path, change):
    rows = pair(ProfileStore(tmp_path))
    p, a = transition(rows)
    if change == "manual":
        rows[0]["manual_locked"] = True
    if change == "no_ai":
        rows[1]["use_in_ai"] = False
    if change == "unknown_order":
        rows[1]["observed_on"] = None
    if change == "older":
        rows[1]["observed_on"] = "2026-10-01"
    if change == "wrong_owner":
        rows[1]["evidence"][0]["role"] = "self"
    if change == "invented_quote":
        a[0]["quote"] = "我肯定愿意以后都单独见面"
    if change == "unsupported":
        a[0]["verdict"] = "unsupported"
    if change == "unproposed":
        p = []
    before = copy.deepcopy(rows)
    assert not ac.apply({"facts": rows}, p, a)
    assert rows == before


def test_group_agreement_does_not_cancel_private_boundary(tmp_path):
    rows = pair(ProfileStore(tmp_path), new_text="四个人聚餐我现在同意，单独的还是不想。")
    p, a = transition(rows)
    assert not ac.apply({"facts": rows}, p, a)


def test_accepting_activity_does_not_overturn_friends_only(tmp_path):
    rows = pair(ProfileStore(tmp_path), old_type="relationship_position", old_text="目前只想做朋友。")
    p, a = transition(rows)
    assert not ac.apply({"facts": rows}, p, a)


@pytest.mark.parametrize("decision", ["accept", "keep"])
def test_major_attitude_change_uses_existing_confirmation_and_preserves_fact_types(tmp_path, decision):
    store = ProfileStore(tmp_path)
    p = store.create("虚构")
    rows = pair(
        store,
        old_type="relationship_position",
        new_type="relationship_position",
        old_text="目前只想做朋友。",
        new_text="我改主意了，现在想试着和你以恋爱的方向了解。",
    )
    p["facts"] = rows
    proposed, audit = transition(rows, "replace")
    assert ac.apply(p, proposed, audit)[0]["relation"] == "pending"
    with store.connection() as db:
        store._write(db, p)
    current = store.get(p["id"])
    view = public_profile(current)
    assert len(view["campus_board"]["reviews"]) == 1
    assert not view["archive"]["topics"], "Unconfirmed alternatives must not become current advice"
    result = cm.resolve(store, p["id"], rows[0]["id"], current["revision"], decision)
    facts = {f["id"]: f for f in result["facts"]}
    kept = rows[1]["id"] if decision == "accept" else rows[0]["id"]
    old = rows[0]["id"] if decision == "accept" else rows[1]["id"]
    assert facts[kept]["validity"] == "current" and facts[old]["validity"] == "superseded"
    assert facts[kept]["memory_type"] == "relationship_position"
    assert not any(f["conflict"] for f in facts.values())


def test_different_event_identity_never_merges_tasks(tmp_path):
    rows = pair(ProfileStore(tmp_path), old_type="commitment", new_type="commitment")
    rows[0]["event_identity"] = "班会海报"
    rows[1]["event_identity"] = "问卷封面"
    p, a = transition(rows)
    assert not ac.apply({"facts": rows}, p, a)


def test_full_original_clause_can_verify_change_when_saved_excerpt_is_shorter(tmp_path):
    rows = pair(ProfileStore(tmp_path))
    p, a = transition(rows)
    whole = "关于见面，" + rows[1]["text"]
    a[0]["quote"] = whole
    sources = [
        {
            "fact_ids": [rows[1]["id"]],
            "turns": [{"role": "other", "content": whole, "chat_date": rows[1]["observed_on"]}],
        }
    ]
    assert ac.apply({"facts": rows}, p, a, sources)


def test_unrelated_original_context_cannot_repair_a_missing_change_quote(tmp_path):
    rows = pair(ProfileStore(tmp_path))
    p, a = transition(rows)
    a[0]["quote"] = "我现在同意其他所有安排"
    sources = [
        {
            "fact_ids": ["unrelated"],
            "turns": [{"role": "other", "content": a[0]["quote"], "chat_date": rows[1]["observed_on"]}],
        }
    ]
    assert not ac.apply({"facts": rows}, p, a, sources)


def test_unknown_time_conflict_asks_instead_of_silently_replacing(tmp_path):
    rows = pair(ProfileStore(tmp_path))
    rows[1]["observed_on"] = None
    p, a = transition(rows, "conflict")
    assert ac.apply({"facts": rows}, p, a)[0]["relation"] == "pending"
    assert rows[0]["text"] == "目前不愿单独见面，先聊天。"


def test_legacy_fact_cleanup_does_not_change_existing_cache_signature():
    profile = {"facts": [{"id": "legacy", "text": "原有记录", "versions": []}]}
    before = copy.deepcopy(profile)
    ac.prune(profile)
    assert profile == before


@pytest.mark.parametrize("change", ["delete", "correct"])
def test_removed_or_corrected_original_does_not_survive_in_copied_history(tmp_path, change):
    rows = pair(ProfileStore(tmp_path))
    p, a = transition(rows)
    profile = {"facts": rows}
    ac.apply(profile, p, a)
    if change == "delete":
        profile["facts"] = [rows[1]]
    else:
        rows[0]["text"] = "用户纠正的原信息"
    ac.prune(profile)
    assert not rows[1]["versions"]
    if change == "delete":
        assert not rows[1]["continuity_from"]


@pytest.mark.parametrize("removed_index", [0, 1])
def test_removing_pending_conflict_releases_surviving_record(tmp_path, removed_index):
    rows = pair(ProfileStore(tmp_path))
    p, a = transition(rows, "conflict")
    profile = {"facts": rows}
    ac.apply(profile, p, a)
    remaining = rows[1 - removed_index]
    profile["facts"] = [remaining]
    ac.prune(profile)
    assert not remaining["conflict"] and remaining["validity"] == "current"
    assert not remaining.get("alternatives") and not remaining.get("continuity_pending_from")
