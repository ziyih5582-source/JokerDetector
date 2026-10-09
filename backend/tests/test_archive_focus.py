"""Regressions for long bubbles, dated requests and proposal/acceptance confusion."""
from PIL import Image, ImageDraw

from app.services import communication, ocr
from app.services.profiles import ProfileStore
from app.services.dossier import prepare_import


def text_box(text, left, top, right, bottom):
    return {"text": text, "left": left, "top": top, "right": right, "bottom": bottom,
            "cx": (left+right)/2, "cy": (top+bottom)/2, "h": bottom-top, "score": .99}


def test_long_left_bubble_does_not_change_speaker_between_lines(monkeypatch):
    image = Image.new("RGB", (600, 850), (237, 237, 237))
    draw = ImageDraw.Draw(image)
    draw.rectangle((90, 190, 535, 275), fill="white")
    draw.rectangle((190, 320, 530, 385), fill=(149, 236, 101))
    boxes = [text_box("我提前准备了", 105, 205, 520, 229),
             text_box("半个月的物料", 105, 240, 260, 264),
             text_box("听起来很期待", 210, 337, 515, 362)]
    monkeypatch.setattr(ocr, "detect_nontext_bubbles", lambda *args: [])
    rows = ocr.build_messages(image, boxes)
    assert rows[0]["speaker"] == "对方"
    assert rows[0]["content"] == "我提前准备了半个月的物料"
    assert rows[1]["speaker"] == "我"


def test_calendar_marker_is_not_a_speaker_message():
    assert ocr.is_time_marker("8/18/2610:29PM")
    assert ocr.is_time_marker("8/16/26 8:12 PM8/16/268:12 PM")
    assert not ocr.is_time_marker("我8/18/26回来")


def test_no_calendar_date_is_guessed_before_first_separator():
    rows = ocr.assemble_messages([text_box("先聊几句", 75, 100, 160, 120),
                                 text_box("8/18/2610:29PM", 210, 160, 390, 180),
                                 text_box("我去看现场", 75, 200, 210, 220)], 600)
    assert rows[0]["time"] is None
    assert rows[1]["time"] == "8/18/2610:29PM"


def test_confirmed_screenshot_dates_survive_archive_preparation():
    rows, _, _ = prepare_import({"messages": [{"speaker":"我", "content":"你什么时候方便", "time":"8/18/2610:29PM"},
                                             {"speaker":"TA", "content":"今天先休息", "time":"8/18/2610:29PM"}],
                                "self_speaker":"我", "other_speaker":"TA", "scene":"",
                                "source_kind":"ocr", "time_reliability":"confirmed"})
    assert communication.message_source_date(rows[1]) == "2026-08-18"
    rows[1]["time_confirmed"] = False
    assert communication.message_source_date(rows[1]) is None


def test_proposal_and_refusal_cannot_prove_mutual_agreement():
    rows = [{"id":0,"role":"self","content":"明天我来找你，就这么定了"},
            {"id":1,"role":"other","content":"不要呀，明天我想休息"}]
    accepted, rejected = communication.validate_items([{
        "memory_type":"interaction_signal", "subject":"relation", "topic":"见面提议",
        "fact":"双方最终约定明天见面", "scope":"这次见面讨论", "retention":"episode",
        "evidence":[{"message_id":0,"quote":rows[0]["content"]}, {"message_id":1,"quote":rows[1]["content"]}]}], rows, semantic_checked=True)
    assert not accepted
    assert any("接受" in reason for reason in rejected)


def test_recipients_plain_good_with_followup_is_not_dropped():
    rows = [{"id":0,"role":"other","content":"周五我整理图，八点前发给你"},
            {"id":1,"role":"self","content":"好，我收到后统一排版"}]
    accepted, rejected = communication.validate_items([{
        "memory_type":"interaction_signal", "subject":"relation", "topic":"展示图分工",
        "fact":"双方约定由对方整理图片，用户收到后统一排版", "scope":"这次小组作业", "retention":"episode",
        "evidence":[{"message_id":0,"quote":rows[0]["content"]}, {"message_id":1,"quote":rows[1]["content"]}]}], rows, semantic_checked=True)
    assert accepted
    assert not rejected


def test_past_call_refusal_does_not_become_tonight_instruction():
    fact = {"id":"past", "memory_version":3, "memory_type":"communication_request", "topic":"当次通话",
            "text":"那次不想通话", "context":"当晚", "retention":"episode", "observed_on":"2020-08-16",
            "validity":"current", "conflict":False, "use_in_ai":True, "method":"暂不拨打", "evidence":[]}
    assert communication.cards_for({"facts":[fact]}) == []
    assert communication.relevant_facts({"facts":[fact]}, "今晚能给TA打电话吗") == []
    assert communication.relevant_facts({"facts":[fact]}, "当时为什么不想通话") == [fact]


def test_old_airport_concern_does_not_generate_arrival_reminder():
    fact = {"id":"past", "memory_version":3, "memory_type":"personal_view", "topic":"当次旅程的担忧",
            "text":"那次担心夜间出机场", "scene":"everyday", "context":"当次旅程",
            "retention":"episode", "observed_on":"2020-08-18", "validity":"current", "conflict":False,
            "method":"到了机场说一声", "evidence":[]}
    assert communication.cards_for({"facts":[fact]}) == []


def test_engine_upgrade_can_add_previously_missed_statement_without_recounting_source(tmp_path, monkeypatch):
    store = ProfileStore(tmp_path)
    p = store.create("虚构联系人")
    rows = [{"id":0,"role":"self","content":"刚才是说台词吗"},
            {"id":1,"role":"other","content":"我喜欢这部动画OP，前面是在念台词，咱们还是普通同学。"}]
    def candidate(kind, topic, fact, quote):
        accepted, rejected = communication.validate_items([{"memory_type":kind,"subject":"other","topic":topic,
            "fact":fact,"scope":"这次私聊","retention":"conditional","evidence":[{"message_id":1,"quote":quote}]}],rows,semantic_checked=True)
        assert not rejected
        return accepted
    original_prompt, original_policy = communication.PROMPT_VERSION, communication.POLICY_VERSION
    monkeypatch.setattr(communication,"PROMPT_VERSION","older-prompt")
    monkeypatch.setattr(communication,"POLICY_VERSION","older-policy")
    old = communication.preview(store,p,rows,candidate("personal_view","动画OP","对方喜欢动画OP","我喜欢这部动画OP"),"2026-10-09","","ai")
    p = communication.commit(store,p["id"],old["token"])
    monkeypatch.setattr(communication,"PROMPT_VERSION",original_prompt)
    monkeypatch.setattr(communication,"POLICY_VERSION",original_policy)
    new = communication.preview(store,p,rows,candidate("relationship_position","本人的关系澄清","对方明确表示还是普通同学","咱们还是普通同学"),"2026-10-09","","ai")
    assert not new["duplicate"] and new["changes"]
    p = communication.commit(store,p["id"],new["token"])
    again = communication.preview(store,p,rows,candidate("relationship_position","本人的关系澄清","对方明确表示还是普通同学","咱们还是普通同学"),"2026-10-09","","ai")
    assert again["duplicate"]
    assert len(p["facts"]) == 2
    assert all(len(f["evidence"]) == 1 for f in p["facts"])
