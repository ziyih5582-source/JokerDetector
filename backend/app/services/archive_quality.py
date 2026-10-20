"""Presentation and redundancy checks; these are not personality truth scores."""

import re

FACETS = {
    "tone",
    "humor",
    "autonomy",
    "deliberation",
    "emotional_expression",
    "care",
    "reciprocity",
    "openness",
    "initiative",
    "followthrough",
    "other",
}
ACTION_TITLE = re.compile(
    r"(?:回应|相处|谈话|聊天|轻松|协作|沟通|文字|兴趣|对话|分歧).{0,3}中|^提供|^照顾对方|^评价|^拒绝|^需要被|^先|^愿意.{2,}|^对特定|^文字|^直接表达边界"
)
STORY = re.compile(
    r"本次|这次|对方提到|先拒绝|后来同意|从拒绝.{0,18}同意|(?:拒绝|同意).{0,8}(?:单独见面|约会)|例如|比如|周[一二三四五六日天末]|\d|[“”「」]|(?:机票|小册|球赛|海报|摄影|咖啡厅|目录)"
)


def copy_issue(title, text):
    if not isinstance(title, str) or not 2 <= len(title) <= 12 or ACTION_TITLE.search(title):
        return "标题应是简短特点，不能是行为、任务或条件句"
    if not isinstance(text, str) or not 24 <= len(text) <= 140:
        return "解读需要有实质内容，并保持一小段"
    sentences = [s for s in re.split(r"[。！？!?]+", text) if s.strip()]
    complete_compound = len(sentences) == 1 and len(text) >= 36 and len(re.split(r"[，,；;]", text)) >= 3
    if not (2 <= len(sentences) <= 3 or complete_compound) or STORY.search(text):
        return "解读通常为2至3句；完整复句也可保留，具体事情留在依据里"
    return ""


def facet_for(title, proposed=None):
    # Vocabulary here groups similar labels; it never supplies a new trait.
    families = [
        ("tone", r"直率|坦率|直爽|直接|坦诚|简洁|温和|委婉|柔和"),
        ("humor", r"幽默|俏皮|接梗|诙谐|风趣|松弛"),
        ("autonomy", r"边界|界限|主见|自主|独立|不迎合"),
        ("deliberation", r"审慎|谨慎|慎重|理性|讲理|严谨|求证"),
        ("care", r"体贴|体谅|细心|周到|关怀|共情"),
        ("openness", r"开放|包容|不同意见|接纳"),
        ("initiative", r"主动|分享|热情"),
        ("reciprocity", r"互惠|回应|平等|相互|互相"),
        ("followthrough", r"条理|规划|认真|守信|负责"),
    ]
    return next(
        (key for key, pattern in families if re.search(pattern, title)), proposed if proposed in FACETS else "other"
    )


def distinct_traits(rows):
    result, seen = [], set()
    counts = {"self": 0, "other": 0}
    for row in rows:
        if row["kind"] != "trait":
            result.append(row)
            continue
        facet = facet_for(row["title"], row.get("facet"))
        key = (row["subject"], facet if facet != "other" else row["title"])
        if key in seen or counts[row["subject"]] >= 4:
            continue
        seen.add(key)
        counts[row["subject"]] += 1
        row["facet"] = facet
        result.append(row)
    return result
