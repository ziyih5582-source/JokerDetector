"""Prevent the relation alias from merging separate people's personal facts."""

import pytest

from app.services import archive_v8 as av, communication as cm
from app.services.archive_personality import STYLE
from app.services.profiles import ProfileStore, public_profile
from app.schemas.communication import Candidate


def topic(subject, ids):
    return {
        "title": "兴趣记录",
        "text": "记录双方各自提到的具体作品。",
        "subject": subject,
        "fact_ids": ids,
        "priority": "core",
    }


def test_relation_label_cannot_bypass_separate_person_ownership():
    facts = [{"id": "mine", "subject": "self"}, {"id": "theirs", "subject": "other"}]
    output = {"portraits": [], "topics": [topic("relation", ["mine", "theirs"])], "suggestions": []}
    accepted, rejected = av._candidates(output, [], facts, personality_style=True)
    assert not accepted and rejected


def test_verified_shared_fact_can_support_a_relation_topic():
    facts = [{"id": "shared", "subject": "relation"}]
    output = {"portraits": [], "topics": [topic("relation", ["shared"])], "suggestions": []}
    accepted, rejected = av._candidates(output, [], facts, personality_style=True)
    assert not rejected and accepted[0]["subject"] == "relation"


@pytest.mark.parametrize("retention,priority", [("conditional", "useful"), ("episode", "minor")])
def test_cached_mixed_topic_is_split_without_losing_enduring_interests(tmp_path, retention, priority):
    store = ProfileStore(tmp_path)
    p = store.create("虚构核验")
    for subject, title in [("self", "桥上行人"), ("other", "潮间记")]:
        p["facts"].append(
            cm.new_fact(
                store,
                Candidate.model_validate(
                    {
                        "memory_type": "useful_preference",
                        "subject": subject,
                        "topic": title,
                        "fact": "喜欢并持续讨论《" + title + "》。",
                        "scope": "作品兴趣",
                        "retention": retention,
                        "evidence": [{"message_id": 0, "quote": "喜欢这部作品。"}],
                    }
                ).model_dump(),
                "2026-10-16",
            )
        )
    row = {"kind": "topic", "id": 0, **topic("relation", [f["id"] for f in p["facts"]])}
    p["archive_v8"] = {
        "version": av.VERSION,
        "sources": [],
        "dismissed": [],
        "analysis": {"rows": [row], "mode": "excerpts", "portrait_style": STYLE},
    }
    p["archive_v8"]["signature"] = av.signature(p)
    result = public_profile(p)["archive"]
    assert len(result["topics"]) == 2
    assert {t["subject"] for t in result["topics"]} == {"self", "other"}
    assert all(t["priority"] == priority for t in result["topics"])
