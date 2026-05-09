# -*- coding: utf-8 -*-
"""
Joker Detector Pro v6：算法 + AI 双重评估，并判定小丑等级 + 情感疏导
修复：httpx proxies 参数兼容性、重复函数定义、use_ai 逻辑覆盖问题
"""
import pandas as pd
import re
import os
from openai import OpenAI
import httpx


# ================== 0. AI 配置 ==================
API_KEY = os.getenv("OPENAI_API_KEY", "sk-xxxxxxxxxxxxxxx")  # 填你的 key
BASE_URL = "xxxxxxxxxxxxxxxxx"
MODEL = "xxxxxxxxxxxxx"


def setup_ai_client():
    if not API_KEY or API_KEY.startswith("sk-xxx"):
        print("⚠️  未配置有效的 API_KEY，跳过 AI 评估")
        return None, None
    try:
        # ✅ 修复：用 trust_env=False 替代已废弃的 proxies=None
        client = OpenAI(
            api_key=API_KEY,
            base_url=BASE_URL,
            http_client=httpx.Client(trust_env=False)
        )
        print(f"✅ AI 客户端初始化成功（模型：{MODEL}）")
        return client, MODEL
    except Exception as e:
        print(f"❌ 客户端初始化失败：{e}")
        return None, None


# ================== 1. 读取与解析 ==================
file_path = input("请输入 Excel 文件路径（例如：chat.xlsx）： ").strip().strip('"\'')
print(f"正在读取文件：{file_path}\n")

df = pd.read_excel(file_path, header=None)

data = []
for _, row in df.iterrows():
    cell = row.iloc[0] if len(row) > 0 else None
    if pd.isna(cell):
        continue
    cell_str = str(cell).strip()
    if not cell_str:
        continue
    parts = cell_str.split(': ', 1)
    if len(parts) < 2:
        continue
    speaker = parts[0].strip()
    msg = parts[1].strip()
    if not speaker or not msg:
        continue
    data.append((speaker, msg))

if not data:
    print("❌ 未检测到任何聊天记录，请检查 Excel 文件格式！")
    exit()

unique_speakers = []
for speaker, _ in data:
    if speaker not in unique_speakers:
        unique_speakers.append(speaker)

if len(unique_speakers) != 2:
    print(f"❌ 检测到 {len(unique_speakers)} 个对话方（{unique_speakers}），当前程序仅支持正好 2 个对话方")
    exit()

print("✅ 检测到对话双方：")
for i, sp in enumerate(unique_speakers):
    print(f"   {i}: {sp}")

while True:
    try:
        choice = int(input("\n请输入你是哪一个（0 或 1）： "))
        if choice in (0, 1):
            break
        else:
            print("请输入 0 或 1")
    except ValueError:
        print("请输入数字 0 或 1")

self_id = unique_speakers[choice]
other_id = unique_speakers[1 - choice]
print(f"\n✅ 你选择自己是：{self_id}，对方是：{other_id}\n")


# ================== 2. 内置算法统计 ==================
self_msg_count = 0
other_msg_count = 0
self_sticker_count = 0
other_sticker_count = 0
self_pic_count = 0
other_pic_count = 0
self_total_chars = 0
other_total_chars = 0

max_self_cont = 0
max_other_cont = 0
current_streak = 0
current_speaker = None

has_voice_or_call = False
self_voice_call = 0
other_voice_call = 0

for speaker, msg in data:
    pics = 0
    stickers = 0
    is_voice_call = False

    if '[图片]' in msg:
        pics = 1
    elif '[语音]' in msg or '语音消息' in msg:
        has_voice_or_call = True
        is_voice_call = True
    elif '通话' in msg:
        has_voice_or_call = True
        is_voice_call = True
    elif re.search(r'\[.+?\]', msg):
        stickers = 1

    chars = len(msg)

    if speaker == self_id:
        self_msg_count += 1
        self_sticker_count += stickers
        self_pic_count += pics
        self_total_chars += chars
        if is_voice_call:
            self_voice_call += 1
    elif speaker == other_id:
        other_msg_count += 1
        other_sticker_count += stickers
        other_pic_count += pics
        other_total_chars += chars
        if is_voice_call:
            other_voice_call += 1

    if speaker == current_speaker:
        current_streak += 1
    else:
        current_streak = 1
        current_speaker = speaker

    if speaker == self_id:
        max_self_cont = max(max_self_cont, current_streak)
    elif speaker == other_id:
        max_other_cont = max(max_other_cont, current_streak)

# 计算五个比率
r1 = self_msg_count / other_msg_count if other_msg_count > 0 else 0
r2 = self_sticker_count / other_sticker_count if other_sticker_count > 0 else 0
r3 = max_self_cont / max_other_cont if max_other_cont > 0 else 0
r4 = self_total_chars / other_total_chars if other_total_chars > 0 else 0
r5 = self_pic_count / other_pic_count if other_pic_count > 0 else 0

jokernum_alg = (r1 + r2 + r3 + r4 + r5) / 5

if has_voice_or_call:
    original = jokernum_alg
    jokernum_alg *= 0.8
    penalty_note = f"⚠️  检测到语音/通话记录，算法 jokernum 额外降低 20%（{original:.4f} → {jokernum_alg:.4f}）"
else:
    penalty_note = "✅ 本次聊天无语音/通话记录，算法未施加惩罚"

print(penalty_note)


# ================== 2.5 初始化 AI 客户端 ==================
client, ai_model = setup_ai_client()
# ✅ 修复：移除后面那个 use_ai=True 覆盖，统一由此处决定
use_ai = client is not None


# ================== 3. 辅助函数（只定义一次） ==================
def build_chat_transcript(data, self_id):
    """构建聊天记录文本，标注哪位是'自己'"""
    lines = []
    for speaker, msg in data:
        tag = "【自己】" if speaker == self_id else "【对方】"
        lines.append(f"{tag}{speaker}: {msg}")
    return "\n".join(lines)


# ================== 3.1 AI 小丑指数评估 ==================
jokernum_ai = None
if use_ai:
    transcript = build_chat_transcript(data, self_id)
    prompt = (
        "你是一位情感关系分析师。请阅读以下双人聊天记录，其中标注了【自己】和【对方】。\n"
        "请分析【自己】在对话中表现出的小丑程度（卑微、单向付出、过度讨好、缺乏自我边界等），\n"
        "并严格以一个 0 到 1 之间的小数给出评分，数字越小表示越正常，越大表示越小丑。\n"
        "直接输出一个数字（如 0.65），不要添加其他文字。\n\n"
        f"{transcript}"
    )
    try:
        response = client.chat.completions.create(
            model=ai_model,
            messages=[
                {"role": "system", "content": "你只输出一个0到1之间的数字，代表小丑指数。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=20
        )
        ai_text = response.choices[0].message.content.strip()
        match = re.search(r"(\d+\.?\d*|\.\d+)", ai_text)
        if match:
            jokernum_ai = float(match.group(1))
            jokernum_ai = max(0.0, min(1.0, jokernum_ai))
            print(f"🤖 AI 评估完成，原始返回：{ai_text} → 提取数值：{jokernum_ai:.4f}")
        else:
            print(f"⚠️  AI 返回内容无法解析为数字：{ai_text}")
    except Exception as e:
        print(f"❌ AI 调用失败：{e}")

# 计算最终 jokernum
if jokernum_ai is not None:
    final_jokernum = jokernum_alg * jokernum_ai
    ai_note = f"🤖 AI 评分：{jokernum_ai:.4f}"
else:
    final_jokernum = jokernum_alg
    ai_note = "⚠️  未采用 AI 评分（仅算法值）"


# ================== 3.2 情感疏导 AI 调用 ==================
ai_guidance = None
if use_ai:
    # transcript 在上方 use_ai 块中已定义，若 API_KEY 无效则不会到此
    guidance_prompt = (
        "你是一位温暖、有同理心的情感支持导师。请阅读以下双人聊天记录，其中标注了【自己】和【对方】。\n"
        "请从【自己】的视角出发，提供一段 200～300 字的情感疏导，要求：\n"
        "1. 先安抚情绪，认可对方的正常情感需求；\n"
        "2. 再客观指出这段关系中可能存在的自我感动、边界模糊等问题；\n"
        "3. 给出 2~3 条具体、可执行的心理调节或行为改变建议；\n"
        "4. 语气温柔、不带评判，像朋友聊天一样。\n\n"
        f"{transcript}"
    )
    try:
        guidance_response = client.chat.completions.create(
            model=ai_model,
            messages=[
                {"role": "system", "content": "你是一位富有同理心的情感导师，输出温柔、具体的疏导文本，字数200-300。"},
                {"role": "user", "content": guidance_prompt}
            ],
            temperature=0.7,
            max_tokens=500
        )
        ai_guidance = guidance_response.choices[0].message.content.strip()
        print("💌 情感疏导 AI 已生成")
    except Exception as e:
        print(f"❌ 情感疏导 AI 调用失败：{e}")


# ================== 4. 小丑人格维度（MBTI风格）==================
if r1 > 1.2:
    dim1, dim1_desc = 'I', '主动发起型'
elif r1 < 0.8:
    dim1, dim1_desc = 'P', '被动回应型'
else:
    dim1, dim1_desc = ('I', '主动倾向型') if r1 >= 1.0 else ('P', '被动倾向型')

self_media_rate = (self_sticker_count + self_pic_count) / self_msg_count if self_msg_count > 0 else 0
other_media_rate = (other_sticker_count + other_pic_count) / other_msg_count if other_msg_count > 0 else 0
if self_media_rate > other_media_rate * 1.5:
    dim2, dim2_desc = 'E', '表达丰富型（爱发表情/图片）'
elif self_media_rate < other_media_rate * 0.67:
    dim2, dim2_desc = 'R', '含蓄克制型'
else:
    dim2, dim2_desc = ('E', '偏表达型') if self_media_rate > 0.1 else ('R', '偏含蓄型')

self_avg_chars = self_total_chars / self_msg_count if self_msg_count > 0 else 0
other_avg_chars = other_total_chars / other_msg_count if other_msg_count > 0 else 0
if self_avg_chars > other_avg_chars * 1.5:
    dim3, dim3_desc = 'D', '深度表达型（话多且长）'
elif self_avg_chars < other_avg_chars * 0.67:
    dim3, dim3_desc = 'S', '浅层交流型'
else:
    dim3, dim3_desc = ('D', '偏深度型') if self_avg_chars >= other_avg_chars else ('S', '偏浅层型')

tenacity_score = 0
if r3 > 1.5:
    tenacity_score += 1
if self_voice_call > other_voice_call * 1.5:
    tenacity_score += 1
if has_voice_or_call and self_voice_call > 0 and other_voice_call == 0:
    tenacity_score += 1
if tenacity_score >= 2:
    dim4, dim4_desc = 'T', '执着纠缠型'
elif tenacity_score == 1:
    dim4, dim4_desc = 'T', '偏执着型'
else:
    dim4, dim4_desc = 'F', '随性洒脱型'

personality_type = dim1 + dim2 + dim3 + dim4


# ================== 5. 输出结果 ==================
print("\n" + "=" * 60)
print("                     📊 聊天统计结果")
print("=" * 60)
print(f"{self_id}（自己）消息数: {self_msg_count} | {other_id}（对方）消息数: {other_msg_count}")
print(f"{self_id}（自己）表情包数: {self_sticker_count} | {other_id}（对方）表情包数: {other_sticker_count}")
print(f"{self_id}（自己）图片数: {self_pic_count} | {other_id}（对方）图片数: {other_pic_count}")
print(f"{self_id}（自己）最大连续消息: {max_self_cont} | {other_id}（对方）最大连续消息: {max_other_cont}")
print(f"{self_id}（自己）总字数: {self_total_chars} | {other_id}（对方）总字数: {other_total_chars}")
print(f"语音/通话: 自己 {self_voice_call} 次, 对方 {other_voice_call} 次")
print(f"\n🧮 算法评分 (jokernum_alg): {jokernum_alg:.4f}")
print(ai_note)
print(f"🌟 最终 jokernum (算法 × AI): {final_jokernum:.4f}")

# 小丑判定
if final_jokernum > 2.0:
    verdict = "🤡 确诊纯小丑 —— 你的情感投入严重失衡，请立即清醒！"
elif final_jokernum > 1.0:
    verdict = "😬 高度疑似小丑 —— 你比对方主动太多，存在自我感动风险。"
elif final_jokernum > 0.5:
    verdict = "😐 轻度小丑倾向 —— 偶尔失衡，但总体可控。"
elif final_jokernum > 0.2:
    verdict = "🙂 健康社交模式 —— 关系基本对等，继续保持。"
else:
    verdict = "😎 绝对理性人（or 对方太主动） —— 你可能是这段关系里的冰冷主宰。"

print(f"\n🔍 小丑判定结果：{verdict}")

print("\n" + "=" * 60)
print("              🃏 你的情感人格类型：", personality_type)
print("=" * 60)
print(f"💬 {dim1_desc} | 🎨 {dim2_desc} | 📝 {dim3_desc} | 🔗 {dim4_desc}\n")

# 人格维度解读
analysis = []
suggestions = []
if dim1 == 'I':
    analysis.append("你在对话中属于主动发起方，掌握话语权但也容易过度投入。")
    suggestions.append("偶尔把话题抛给对方，观察 Ta 的反应，避免独角戏。")
else:
    analysis.append("你比较被动，较少主动开启话题。")
    suggestions.append("适当增加主动分享能平衡关系温度。")

if dim2 == 'E':
    analysis.append("你热衷发表情/图片，情感外放。")
    suggestions.append("注意对方是否同频，避免热情泼在冰面上。")
else:
    analysis.append("表达含蓄，少用多媒体。")
    suggestions.append("可以试着用一两个表情传递情绪，增加亲和力。")

if dim3 == 'D':
    analysis.append("你习惯于长篇大论，追求深度沟通。")
    suggestions.append("把长文拆成短句，给对方插话的空间。")
else:
    analysis.append("交流浅显轻松，很少深入。")
    suggestions.append("偶尔展开一个认真话题，让关系不止步于表面。")

if dim4 == 'T':
    analysis.append("你有执着纠缠的倾向，容易忽略对方边界。")
    suggestions.append("紧追不舍不如以退为进，神秘感也是一种吸引。")
else:
    analysis.append("你随性洒脱，不执着，这是很舒服的状态。")
    suggestions.append("保持这样松弛的节奏，是长久关系的良药。")

print("📌 情感投入核心问题：")
for line in analysis:
    print(f"  • {line}")
print("\n✨ 针对性建议：")
for line in suggestions:
    print(f"  ▶ {line}")

# 情感疏导输出（紧跟在建议之后）
if ai_guidance:
    print("\n" + "=" * 60)
    print("                   💌 AI 情感疏导")
    print("=" * 60)
    print(ai_guidance)
    print("=" * 60)
else:
    print("\n⚠️  AI 情感疏导未生成（API 不可用或调用失败）")

# 经典组合彩蛋
if personality_type in ['IEDT', 'IEDF']:
    print("\n🎭 典型画像：『深情表演家』—— 用尽全力展示爱，小心只是感动了自己。")
elif personality_type in ['IRDT', 'IRDF']:
    print("\n🎭 典型画像：『沉默的守望者』—— 内心戏丰富，可对方只看到沉默。")
elif personality_type in ['PEST', 'PESF']:
    print("\n🎭 典型画像：『气氛组选手』—— 热闹的表象下，可能缺少真正的连接。")
elif personality_type == 'PRSF':
    print("\n🎭 典型画像：『理性旁观者』—— 冷静观察，却容易错过火花。")
else:
    print("\n🎭 你的混合型人格独一无二，上面的分析已经足够揭示你的情感模式。")

input("\n按回车键退出...")
