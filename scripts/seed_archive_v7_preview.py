"""Create explicitly fictional UI examples in a supplied, isolated directory.

This is a deterministic replay of hand-written candidates, NOT an AI benchmark.
No cloud API, screenshots or real chats are read. Existing contacts are retained.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services import communication as cm
from app.services.dossier import save
from app.services.profiles import ProfileStore


def batch(store, p, day, entries):
    messages = [{"id": 0, "role": "self", "content": "继续聊聊上次的事吧"}]
    raw = []
    for role, kind, topic, text, extras in entries:
        i = len(messages)
        messages.append({"id": i, "role": role, "content": text})
        item = {"memory_type": kind, "subject": role, "topic": topic, "fact": text,
                "scope": extras.get("scope", "这段交流中本人所述的情境"),
                "retention": "temporary" if kind in {"open_loop", "commitment", "stage_context", "support_need"} else "conditional",
                "evidence": [{"message_id": i, "quote": text}]}
        item.update(extras)
        if kind in cm.TIMED_TYPES:
            item.setdefault("event_identity", topic)
        raw.append(item)
    valid, rejected = cm.validate_items(raw, messages, semantic_checked=True)
    if rejected:
        raise ValueError(rejected)
    preview = cm.preview(store, p, messages, valid, day, "预置虚构示例", "local")
    return cm.commit(store, p["id"], preview["token"]) if preview["token"] else p


def create(store, name, steps):
    found = next((c for c in store.list() if c["name"] == name), None)
    if found:
        return store.get(found["id"])
    p = store.create(name)
    for day, entries in steps:
        p = batch(store, p, day, entries)
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        p["preview_fictional"] = True
        return save(store, db, p)


def seed(directory):
    store = ProfileStore(directory)
    short = create(store, "示例·两段短聊", [
        ("2026-10-15", [
            ("other", "situated_trait", "熟悉程度与表达", "我刚认识人话比较少，聊熟悉的话题会放开些。", {"scope": "刚认识或谈熟悉话题时"}),
            ("other", "special_date", "生日", "我的生日是11月18日，过公历。", {}),
            ("self", "situated_trait", "不确定时的表达", "我拿不准意思时会多确认。", {"scope": "意思不确定时"}),
        ]),
        ("2026-10-16", [
            ("other", "useful_preference", "星露谷与慢节奏游戏", "我更喜欢星露谷里慢慢经营农场，不太想把游戏玩成每天必须打卡。", {}),
            ("other", "boundary", "游戏交流的频率", "可以聊农场的进展，但别每天追问我玩到哪了。", {"scope": "游戏进度交流"}),
        ]),
    ])
    rich = create(store, "示例·持续了解小林", [
        ("2026-10-15", [
            ("other", "situated_trait", "熟悉话题与分享", "我刚认识时话少，碰到熟悉的同人话题会讲得多一些。", {"scope": "熟悉程度与同人话题"}),
            ("self", "situated_trait", "确认安排的方式", "我约时间喜欢先给两个选择，再一起确认。", {"scope": "共同安排"}),
            ("other", "special_date", "生日", "我11月18日生日，过公历。", {}),
            ("self", "open_loop", "咖啡邀约", "我们周六要不要喝咖啡？这次只是提议，还没确定。", {"item_state": "proposed"}),
        ]),
        ("2026-10-16", [
            ("other", "useful_preference", "星桥A/B与线下同好", "我最喜欢《星桥》A/B的角色关系，也喜欢去线下和同好聊剧情，不是追演员恋情。", {}),
            ("other", "personal_view", "角色关系的理解", "我在意A和B怎样互相理解，最打动我的是他们愿意认真听彼此说话。", {}),
            ("other", "boundary", "角色与演员话题", "聊角色可以，但别拿演员私生活开玩笑。", {"scope": "同人兴趣交流"}),
            ("other", "support_need", "这次课程吐槽", "今天我先吐槽一会儿，你先听我讲就好，暂时不用急着给建议。", {"scope": "这次课程吐槽"}),
            ("self", "commitment", "复习资料", "我答应周五把复习资料发给你。", {"item_state": "agreed"}),
            ("other", "personal_goal", "考研准备", "我这学期想先把专业基础补起来，再决定考研方向。", {}),
            ("other", "open_loop", "社团面试结果", "社团面试的结果还没出来，我也在等通知。", {"item_state": "pending"}),
        ]),
        ("2026-10-17", [
            ("other", "special_date", "生日", "生日我之前打错了，是11月19日。", {"operation": "change"}),
            ("self", "commitment", "复习资料", "现在复习资料已经发完，对方说收到啦。", {"item_state": "completed", "operation": "end"}),
            ("other", "relationship_position", "继续了解与公开范围", "我愿意慢慢了解你，但先别公开我们的事。", {"scope": "这段关系的当前态度与公开范围"}),
        ]),
    ])
    uncertainty = create(store, "示例·待定不等于答应", [
        ("2026-10-18", [
            ("other", "stage_context", "本周课程压力", "这周实验报告比较多，晚上不一定有空。", {}),
            ("self", "open_loop", "周末电影", "周末一起看电影吗？还没收到答复。", {"item_state": "proposed"}),
            ("other", "special_date", "生日", "我的生日是2月29日，过公历。", {}),
            ("other", "communication_request", "安排用文字", "重要安排写成文字发我，免得我漏听。", {"scope": "重要安排"}),
        ]),
    ])
    return {"mode": "handwritten_fictional_replay", "contacts": [{"id": p["id"], "name": p["name"]} for p in (rich, short, uncertainty)]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", required=True, help="Use a separate preview directory, not your real archive.")
    args = parser.parse_args()
    print(json.dumps(seed(Path(args.directory)), ensure_ascii=False))
