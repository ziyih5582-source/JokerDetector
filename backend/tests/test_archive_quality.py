"""Audit-contract tests, not a claim that a personality adjective is true."""

import copy
import pytest
from app.services import archive_v8 as av
from app.services.profiles import AIResultError


def proposed(
    text="表达柔和，同时保留自己的判断和决定。相处时顾及对方心意，也会清楚说明自己的取舍。", title="温和有主见"
):
    messages = [
        {"id": 0, "role": "self", "content": "我替你安排吧。"},
        {"id": 1, "role": "other", "content": "谢谢心意，不过我想自己决定，可以和你讨论理由。"},
    ]
    sources = av.interaction_sources(messages, None, [])
    sid = sources[0]["id"]
    output = {
        "portraits": [
            {
                "subject": "other",
                "traits": [
                    {
                        "title": title,
                        "text": text,
                        "scope": "目前的互动",
                        "alternative": "也可能与本次安排有关",
                        "source_ids": [sid],
                        "evidence": [{"source_id": sid, "number": 2, "quote": messages[1]["content"]}],
                        "counter_source_ids": [],
                        "counter_evidence": [],
                    }
                ],
            }
        ],
        "topics": [],
        "suggestions": [],
    }
    return sources, output


def test_event_quotation_is_not_enough_to_make_a_personality():
    sources, output = proposed(title="拒绝回礼")
    candidates, _ = av._candidates(output, sources, [], personality_style=True)
    audit = {"checks": [{"id": 0, "verdict": "supported", "abstraction": "event", "reason": "仅能说明拒绝了一个提议"}]}
    assert not av._verify(audit, candidates, personality_style=True)


def test_presentational_error_reaches_existing_audit_for_a_grounded_rewrite():
    sources, output = proposed(text="提到这次拒绝代为安排，显示其有个人判断。")
    candidates, drops = av._candidates(output, sources, [], personality_style=True)
    assert not drops and candidates[0]["presentation_issue"]
    evidence = copy.deepcopy(candidates[0]["evidence"])
    audit = {
        "checks": [
            {
                "id": 0,
                "verdict": "narrow",
                "abstraction": "interpersonal_style",
                "reason": "可总结缓和而清楚的表达方式",
                "title": "温和有主见",
                "text": "表达较柔和，也愿意清楚说明自己的判断。交流中顾及对方的心意，同时保留作决定的自主性。",
            }
        ]
    }
    accepted = av._verify(audit, candidates, personality_style=True)
    assert len(accepted) == 1 and accepted[0]["evidence"] == evidence and "presentation_issue" not in accepted[0]


def test_rewriting_never_repairs_invented_evidence():
    sources, output = proposed(text="提到自己有主见。")
    output["portraits"][0]["traits"][0]["evidence"][0]["quote"] = "我是一个非常有主见的人"
    candidates, drops = av._candidates(output, sources, [], personality_style=True)
    assert not candidates and drops


def test_supported_compound_explanation_is_not_discarded_for_punctuation():
    sources, output = proposed()
    candidates, _ = av._candidates(output, sources, [], personality_style=True)
    text = "表达观点时不绕弯，会直接指出问题所在，并主动澄清自己的表达方式，避免对方误解。"
    audit = {
        "checks": [
            {
                "id": 0,
                "verdict": "supported",
                "abstraction": "interpersonal_style",
                "reason": "表达方式有原始语言支持",
                "title": "直接坦率",
                "text": text,
            }
        ]
    }
    accepted = av._verify(audit, candidates, personality_style=True)
    assert len(accepted) == 1 and accepted[0]["text"] == text
    assert accepted[0]["evidence"] == candidates[0]["evidence"]


def test_copied_candidates_without_a_verdict_are_not_assumed_supported():
    sources, output = proposed()
    candidates, _ = av._candidates(output, sources, [], personality_style=True)
    with pytest.raises(AIResultError, match="核查"):
        av._verify({"checks": candidates}, candidates, personality_style=True)


def test_duplicate_titles_are_not_displayed_twice_for_one_person():
    sources, output = proposed()
    candidates, _ = av._candidates(output, sources, [], personality_style=True)
    candidates.append({**copy.deepcopy(candidates[0]), "id": 1})
    audit = {
        "checks": [
            {"id": i, "verdict": "supported", "abstraction": "interpersonal_style", "reason": "表达与引用相符"}
            for i in range(2)
        ]
    }
    assert len(av._verify(audit, candidates, personality_style=True)) == 1


@pytest.mark.parametrize("level", ["temporary_need", "topic_view", "insufficient"])
def test_momentary_needs_and_fictional_values_stay_outside_personality(level):
    sources, output = proposed()
    candidates, _ = av._candidates(output, sources, [], personality_style=True)
    audit = {"checks": [{"id": 0, "verdict": "supported", "abstraction": level, "reason": "只支持对应类型的内容"}]}
    assert not av._verify(audit, candidates, personality_style=True)


def test_modest_topic_overflow_does_not_erase_portraits_and_prioritizes_core():
    sources, output = proposed()
    facts = [{"id": "f", "subject": "other"}]
    output["topics"] = [
        {
            "title": f"话题{i}",
            "text": "有原始事实支持的信息。",
            "subject": "other",
            "fact_ids": ["f"],
            "priority": "core" if i == 12 else "minor",
        }
        for i in range(13)
    ]
    candidates, _ = av._candidates(output, sources, facts, personality_style=True)
    assert len(candidates) == 14
    audit = {
        "checks": [
            {
                "id": i,
                "verdict": "supported",
                "reason": "信息有依据",
                "abstraction": "interpersonal_style" if i == 0 else "not_applicable",
            }
            for i in range(14)
        ]
    }
    accepted = av._verify(audit, candidates, personality_style=True)
    assert len([r for r in accepted if r["kind"] == "trait"]) == 1
    assert len([r for r in accepted if r["kind"] == "topic"]) == 8
    assert any(r["title"] == "话题12" for r in accepted)


def test_excessive_topic_output_still_fails_bounded_contract():
    sources, output = proposed()
    output["topics"] = [{} for _ in range(25)]
    with pytest.raises(AIResultError, match="结构"):
        av._candidates(output, sources, [], personality_style=True)


def test_long_turn_overlap_preserves_every_original_without_large_duplication():
    messages = [
        {"id": i, "role": "self" if i % 2 else "other", "content": str(i) + ("不同话题原文。" * 65)} for i in range(30)
    ]
    sources = av.interaction_sources(messages, "2026-10-16", [])
    original = {i + 1: m["content"] for i, m in enumerate(messages)}
    seen = {t["number"]: t["content"] for s in sources for t in s["turns"]}
    assert seen == original
    assert sum(len(t["content"]) for s in sources for t in s["turns"]) < 1.5 * sum(map(len, original.values()))


def test_fact_namespace_alias_is_repaired_only_through_exact_own_original():
    sources, output = proposed()
    sid = sources[0]["id"]
    sources[0]["fact_ids"] = ["f"]
    trait = output["portraits"][0]["traits"][0]
    trait["source_ids"] = ["f"]
    trait["evidence"][0]["source_id"] = "f"
    candidates, drops = av._candidates(output, sources, [{"id": "f", "subject": "other"}], personality_style=True)
    assert not drops and candidates[0]["source_ids"] == [sid]
    trait["evidence"][0]["quote"] = "这句原文不存在"
    assert not av._candidates(output, sources, [{"id": "f", "subject": "other"}], personality_style=True)[0]


@pytest.mark.parametrize(
    "quote,fact,expected",
    [
        ("我查查，好像是12月15号。", "阳历生日是12月15日。", False),
        ("我查查，好像是12月15号。", "阳历生日可能是12月15日，待确认。", True),
        ("我生日是12月15号，聚餐可能去不了。", "阳历生日是12月15日。", True),
    ],
)
def test_model_verification_cannot_erase_an_uncertain_birthdate(monkeypatch, quote, fact, expected):
    from app.services import archive_extraction as ax, communication as cm

    messages = [
        {"id": 0, "role": "self", "content": "你阳历生日是哪天？"},
        {"id": 1, "role": "other", "content": quote},
    ]

    def request(client, model, prompt, payload, **kwargs):
        if payload["stage"] == "extract":
            return {
                "items": [
                    {
                        "memory_type": "special_date",
                        "subject": "other",
                        "topic": "生日",
                        "fact": fact,
                        "scope": "本人生日",
                        "retention": "conditional",
                        "evidence": [{"message_id": 1, "quote": quote}],
                    }
                ]
            }
        return {"checks": [{"candidate_id": 0, "verdict": "supported", "reason": "已经核查", "operation": "add"}]}

    monkeypatch.setattr(ax, "request", request)
    accepted, _ = ax.extract(
        messages, {"facts": []}, object(), "test", "2026-10-16", "", cm.validate_items, cm.existing_context
    )
    assert bool(accepted) == expected
