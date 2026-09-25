# -*- coding: utf-8 -*-
"""结果格式化：把内部分析结果翻成前端友好的 JSON。

判定阈值与五维说明都只有这一份，`/api/guide` 的解说页读的也是它，
所以文档不会和判定逻辑脱节。
"""

from __future__ import annotations

from app.services.analyzer import JOKER_TYPES, METRIC_WEIGHTS, NOT_JOKER_DESC

# 判定阈值：(下限分数, 档位 key)
LEVEL_THRESHOLDS = [
    (75, "confirmed"),
    (60, "high_risk"),
    (45, "suspicious"),
    (30, "mild"),
    (0, "healthy"),
]

# 五个维度的说明：结果页与解说页共用
METRIC_DOCS = {
    "SSDT": {
        "label": "连续发送倾向",
        "desc": "你是否连续发消息不给对方插话机会",
        "how": "统计一方连续发言的最长段数，取你与对方的相对差",
    },
    "PFI": {
        "label": "自我中心指数",
        "desc": "你对话中「我」的使用密度对比",
        "how": "比较「我 / 俺」与「我们 / 咱们」的出现比例，再看双方的相对差",
    },
    "PLD": {
        "label": "低姿态语言密度",
        "desc": "道歉、语气词、犹豫词的使用频率",
        "how": "统计「可能 / 有点 / 对不起 / 好吗 / ？」这类词在总字数里的占比",
    },
    "EPEG": {
        "label": "情感表达差",
        "desc": "你与对方的情绪表达强度差异",
        "how": "统计情绪词与感叹号数量，取双方对数差（相差约 2 倍即达到满值）",
    },
    "CONV": {
        "label": "对话衔接度",
        "desc": "双方回应对方话题的投入程度",
        "how": "看接话时是否复用对方上一句里的连接词，比较两个方向的接话率",
    },
}


def level_for(score: float) -> str:
    """分数 → 档位 key。阈值处归入较高的一档。"""
    for minimum, key in LEVEL_THRESHOLDS:
        if score >= minimum:
            return key
    return "healthy"


def safe_ratio(a, b) -> float:
    if b == 0:
        return 99.0 if a > 0 else 0.0
    return round(a / b, 2)


def build_report(result: dict, source_name: str) -> dict:
    """将内部分析结果转换为前端友好的 JSON（不回传聊天原文，只给统计）。"""
    stats = result["stats"]
    z = stats["z_metrics"]

    if result["is_joker"] and result["joker_type"]:
        verdict = {
            "is_joker": True,
            "level": level_for(stats["jokernum_alg"]),
            "type": result["joker_type"],
            "type_info": JOKER_TYPES.get(result["joker_type"], {}),
            "score": stats["jokernum_alg"],
            "label": "🤡 确诊小丑",
        }
    else:
        verdict = {
            "is_joker": False,
            "level": "healthy",
            "type": None,
            "type_info": None,
            "score": stats["jokernum_alg"],
            "label": "👑 清醒玩家",
            "desc": NOT_JOKER_DESC,
        }

    return {
        "source": source_name,
        "verdict": verdict,
        "speakers": {"self": result["self_id"], "other": result["other_id"]},
        "statistics": {
            "message_count": {"self": stats["self_msg_count"], "other": stats["other_msg_count"]},
            "sticker_count": {"self": stats["self_sticker_count"], "other": stats["other_sticker_count"]},
            "picture_count": {"self": stats["self_pic_count"], "other": stats["other_pic_count"]},
            "total_chars": {"self": stats["self_total_chars"], "other": stats["other_total_chars"]},
            "max_streak": {"self": stats["max_self_cont"], "other": stats["max_other_cont"]},
            "avg_chars": {
                "self": round(stats["self_avg_chars"], 1),
                "other": round(stats["other_avg_chars"], 1),
            },
            "has_voice_or_call": stats["has_voice_or_call"],
            "ratios": {
                "message": safe_ratio(stats["self_msg_count"], stats["other_msg_count"]),
                "sticker": safe_ratio(stats["self_sticker_count"], stats["other_sticker_count"]),
                "picture": safe_ratio(stats["self_pic_count"], stats["other_pic_count"]),
                "chars": safe_ratio(stats["self_total_chars"], stats["other_total_chars"]),
                "streak": safe_ratio(stats["max_self_cont"], stats["max_other_cont"]),
            },
        },
        "z_metrics": {
            key: {
                "value": z[key],
                "label": METRIC_DOCS[key]["label"],
                "desc": METRIC_DOCS[key]["desc"],
                "weight": METRIC_WEIGHTS[key],
            }
            for key in METRIC_DOCS
        },
        "guidance": result.get("guidance"),
        "guidance_error": result.get("guidance_error"),
        "keyword_matches": stats.get("self_keyword_matches", {}),
    }
