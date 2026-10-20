import pytest
from app.services.archive_quality import copy_issue, distinct_traits
from app.services.archive_v8 import _personality_copy


@pytest.mark.parametrize(
    "title", ["提供实际帮助", "协作中注重结构", "文字沟通中注意澄清", "需要被倾听", "拒绝金钱回礼"]
)
def test_actions_and_conditions_are_not_characteristic_labels(title):
    assert copy_issue(title, "表达平和，对自己的选择有清楚的判断。相处时顾及他人，也保留自己的取舍。")


def test_characteristic_explanation_is_detailed_without_an_event_recap():
    assert not copy_issue(
        "温和有主见",
        "表达柔和，但对自己的选择有清楚的判断。相处中愿意顾及别人的感受，也不会轻易为了迎合而放下自己的想法。",
    )
    assert copy_issue("温和有主见", "这次先拒绝买票，后来同意见面。说明做事有主见。")
    assert copy_issue("温和有主见", "表达柔和，同时有自己的想法和明确判断。")


def test_synonyms_merge_for_one_person_but_keep_distinct_and_other_person():
    rows = [{"kind": "trait", "subject": "other", "title": s} for s in ["表达直接", "坦率直爽", "幽默松弛"]]
    rows += [{"kind": "trait", "subject": "self", "title": "坦率直爽"}, {"kind": "topic", "title": "已约定的安排"}]
    result = distinct_traits(rows)
    assert [r["title"] for r in result] == ["表达直接", "幽默松弛", "坦率直爽", "已约定的安排"]


def test_general_explanation_is_not_rejected_by_a_single_introductory_word():
    text = "面对不同意见时，倾向于平和地说清自己的判断，也能听取别人的理由。在听取意见的同时仍保留自己的取舍，不会轻易为了迎合而改变。"
    assert _personality_copy({"title": "温和有主见", "text": text}) == ("温和有主见", text)
