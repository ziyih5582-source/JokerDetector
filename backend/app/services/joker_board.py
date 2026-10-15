# -*- coding: utf-8 -*-
"""小丑看板（ClownBoard）：把「六征判定」整理成一块挂在页面右上角的看板。

鉴定所回答「是不是小丑」，看板回答另外三件更具体的事：

1. 六个维度各得多少分（0~100）、权重多少、谁在拉高总分；
2. 每一维的**依据**：命中的关键词出自本人哪几句话，或者哪几条连续发送；
3. 下一步可以做点什么（不诊断、不评判，只给能立刻执行的小动作）。

它复用 ``JokerAnalyzer.detect_joker_profile`` 的本地判定：
不新增云端调用、不写数据库、不接受没有的两个发言者。
"""

from __future__ import annotations

from datetime import datetime

from app.services.analyzer import JOKER_TYPES, JokerAnalyzer

# 六征顺序与鉴定所弹窗一致：单向性排第一，其余五项按「自己骗自己」到「事后自嘲」排开
SIGN_ORDER = (
    "one_way",
    "self_moved",
    "fantasy",
    "boundary",
    "no_accept_reject",
    "self_mockery",
)

SIGN_WEIGHT = {
    "one_way": 0.24,          # 单向推进：这段关系是不是只有一个人在用劲
    "self_moved": 0.16,       # 自我感动：付出被自己吞掉
    "fantasy": 0.14,          # 幻想脑补：脑内剧本多过现实对话
    "boundary": 0.14,         # 边界失守：牺牲与托付型表达
    "no_accept_reject": 0.18,  # 不接受拒绝：被拒绝后仍在续命
    "self_mockery": 0.14,     # 事后自嘲：靠贬低自己换对方一笑
}

# 与前端 LEVEL_NAME 一一对应，避免同一个等级在两处叫不同名字
LEVEL_LABEL = {
    "confirmed": "确诊小丑",
    "high_risk": "高度疑似",
    "suspicious": "轻度倾向",
    "mild": "基本对等",
    "healthy": "清醒玩家",
}

# 每一维对应一个可执行的小动作（只给动作，不下诊断）
STEP_BY_SIGN = {
    "one_way": "停三天不主动，看对方会不会来找你：答案比任何自我说服都清楚。",
    "self_moved": "把「我没事」换成「我其实有点在意」，让付出被看见，而不是被自己消化。",
    "fantasy": "把脑内剧本换成一句能发出去的话：比如「周末想约你喝咖啡，你方便吗？」",
    "boundary": "先给自己定一条底线（时间、钱、情绪各一条），越线就停下来。",
    "no_accept_reject": "对方已经给过答案：把等待的时间还给自己，不打扰也是一种体面。",
    "self_mockery": "下次想自嘲时，把那句话改成一句真实的需求，例如「我有点难过，想被安慰一下」。",
}

CLEAR_STEP = "保持现在的节奏：主动与回应大致对等，这是最稳的关系形态，把话说明白就好。"

ENGINE_NOTE = "本地六征 v1 · 不调用云端 AI"

QUOTE_LIMIT = 24  # 引用原句的字数上限，太长会撑破看板


def _keywords_by_sign() -> dict:
    """依据关键词直接取鉴定所的同名分组。

    这样「为什么命中」和「命中在哪一句话」用的永远是同一套词表，
    以后有人改了判定词表，看板里的依据也会跟着变，不会两处对不上。
    """
    return {name: tuple(words) for name, words in JokerAnalyzer._SIGN_KEYWORDS.items()}


def _quote(text: str) -> str:
    """把一条消息裁成可以摆进看板的短引用。"""
    clean = " ".join(str(text or "").split())
    if len(clean) > QUOTE_LIMIT:
        clean = clean[: QUOTE_LIMIT - 1] + "…"
    return "「" + clean + "」"


def _keyword_evidence(messages, self_id: str, keywords, limit: int = 2) -> list:
    """找出本人真正说出过关键词的原句，作为这一维的依据。"""
    found = []
    for speaker, text in messages:
        if speaker != self_id:
            continue
        if any(word in text for word in keywords):
            found.append(_quote(text))
            if len(found) >= limit:
                break
    return found


def _streak_evidence(messages, self_id: str, limit: int = 3) -> list:
    """单向推进的依据：本人最长的一段连续发送。"""
    best, current = [], []
    for speaker, text in messages:
        if speaker == self_id:
            current.append(text)
            if len(current) > len(best):
                best = list(current)
        else:
            current = []
    return [_quote(text) for text in best[:limit]]


def _counter(messages) -> dict:
    counts = {}
    for speaker, _text in messages:
        counts[speaker] = counts.get(speaker, 0) + 1
    return counts


def build_board(analyzer: JokerAnalyzer, messages, self_id: str, other_id: str) -> dict:
    """把一次六征判定整理成看板 JSON（每个维度都带分值、权重与依据）。

    ``messages`` 与鉴定所一样，是 ``[(speaker, content), ...]`` 的纯文本序列。
    """
    base = analyzer.detect_joker_profile(messages, self_id, other_id)
    signs = base.get("signs") or {}
    keywords = _keywords_by_sign()

    dimensions = []
    weighted_total = 0.0
    for key in SIGN_ORDER:
        sign = signs.get(key) or {}
        score = float(sign.get("score") or 0.0)
        weight = SIGN_WEIGHT[key]
        contribution = score * weight * 100
        weighted_total += contribution
        if not sign.get("hit"):
            # 没命中的维度不引用原句：依据留在 detail 的统计口径里，看板才不会到处是「证据」
            evidence = []
        elif key == "one_way":
            evidence = _streak_evidence(messages, self_id)
        else:
            evidence = _keyword_evidence(messages, self_id, keywords.get(key, ()))
        dimensions.append({
            "key": key,
            "label": sign.get("label", key),
            "hit": bool(sign.get("hit")),
            "score": round(score, 2),          # 原始 0~1 分，与鉴定所口径一致
            "points": round(score * 100, 1),    # 换算成看板上的 0~100 分
            "weight": weight,
            "contribution": round(contribution, 1),
            "detail": sign.get("detail", ""),
            "evidence": evidence,
        })

    hits = [item for item in dimensions if item["hit"]]
    top = sorted(hits, key=lambda item: item["points"], reverse=True)[:3]

    if top:
        summary = "六征里命中 {count} 项：{names} 最突出。".format(
            count=len(hits),
            names="、".join("{0} {1}".format(item["label"], item["points"]) for item in top),
        )
    else:
        summary = "六征一项都没命中：主动、表达与回应大致对等，这段关系现在还是清醒的。"

    steps = [STEP_BY_SIGN[item["key"]] for item in top[:2]]
    if not steps:
        steps = [CLEAR_STEP]
    elif base.get("type") and JOKER_TYPES.get(base["type"], {}).get("suggestion"):
        steps.append(JOKER_TYPES[base["type"]]["suggestion"])

    counts = _counter(messages)
    return {
        "engine": ENGINE_NOTE,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "score": base.get("score", 0.0),              # 综合小丑值，与鉴定所弹窗同一个数
        "weighted_score": round(min(100.0, weighted_total), 1),  # 六征加权分，用来看结构
        "level": base.get("level", "healthy"),
        "level_label": LEVEL_LABEL.get(base.get("level", "healthy"), "清醒玩家"),
        "is_joker": bool(base.get("is_joker")),
        "type": base.get("type"),
        "type_info": base.get("type_info"),
        "hit_count": len(hits),
        "dimensions": dimensions,
        "radar": [
            {"key": item["key"], "label": item["label"], "value": item["points"]}
            for item in dimensions
        ],
        "summary": summary,
        "next_steps": steps,
        "message_counts": {
            "self": counts.get(self_id, 0),
            "other": counts.get(other_id, 0),
            "total": len(messages),
        },
        "self_speaker": self_id,
        "other_speaker": other_id,
    }
