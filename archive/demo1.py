# -*- coding: utf-8 -*-
"""
Created on Fri Apr  3 19:57:03 2026

@author: 31691
"""

import pandas as pd
import re

# ================== 升级版：自动识别双方ID + 图片数量比值 + 语音/通话惩罚 ==================
file_path = input("请输入 Excel 文件路径（例如：chat.xlsx）： ").strip().strip('"\'')
print(f"正在读取文件：{file_path}\n")

# 读取 Excel 文件（假设数据在第一个 Sheet，第一列为聊天记录，无表头）
df = pd.read_excel(file_path, header=None)

# 解析聊天记录
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

# 自动识别对话双方ID（按首次出现顺序）
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

# 让用户选择自己是哪一方
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

# ================== 统计部分（新增图片数量 + 语音/通话检测） ==================
self_msg_count = 0
other_msg_count = 0
self_sticker_count = 0
other_sticker_count = 0
self_pic_count = 0
other_pic_count = 0
self_total_chars = 0
other_total_chars = 0

# 连续消息统计
max_self_cont = 0
max_other_cont = 0
current_streak = 0
current_speaker = None

# 语音/通话/视频通话惩罚标志（只要聊天记录中出现任意一条就触发）
has_voice_or_call = False

# 遍历每条消息进行统计
for speaker, msg in data:
    # ========== 新增：消息类型分类（图片、表情包、语音/通话） ==========
    pics = 0
    stickers = 0
    
    if '[图片]' in msg:
        pics = 1
    elif '[语音]' in msg or '语音消息' in msg:
        has_voice_or_call = True
    elif '通话' in msg:          # 覆盖 [语音通话]、[视频通话]、已取消通话等
        has_voice_or_call = True
    elif re.search(r'\[.+?\]', msg):   # 其余带 [] 的都算表情包（[动画表情]、[发怒] 等）
        stickers = 1
    
    chars = len(msg)
    
    # 统计到对应用户
    if speaker == self_id:
        self_msg_count += 1
        self_sticker_count += stickers
        self_pic_count += pics
        self_total_chars += chars
    elif speaker == other_id:
        other_msg_count += 1
        other_sticker_count += stickers
        other_pic_count += pics
        other_total_chars += chars
    
    # 更新连续发言数（与消息类型无关）
    if speaker == current_speaker:
        current_streak += 1
    else:
        current_streak = 1
        current_speaker = speaker
    
    if speaker == self_id:
        max_self_cont = max(max_self_cont, current_streak)
    elif speaker == other_id:
        max_other_cont = max(max_other_cont, current_streak)

# 计算五个比率（避免除以零）
r1 = self_msg_count / other_msg_count if other_msg_count > 0 else 0
r2 = self_sticker_count / other_sticker_count if other_sticker_count > 0 else 0
r3 = max_self_cont / max_other_cont if max_other_cont > 0 else 0
r4 = self_total_chars / other_total_chars if other_total_chars > 0 else 0
r5 = self_pic_count / other_pic_count if other_pic_count > 0 else 0   # 新增：图片数量比值

# 计算 jokernum（现在是 5 项平均值）
jokernum = (r1 + r2 + r3 + r4 + r5) / 5

# 如果存在语音/通话/视频通话，额外降低 jokernum（算法更复杂）
if has_voice_or_call:
    original = jokernum
    jokernum *= 0.8          # 额外降低 20%
    penalty_note = f"⚠️ 检测到语音消息/语音通话/视频通话，jokernum 已额外降低 20%（从 {original:.4f} → {jokernum:.4f}）"
else:
    penalty_note = "✅ 本次聊天无语音/通话/视频记录"

# 输出结果
print("=== 计算完成 ===")
print(f"{self_id}（自己）消息数: {self_msg_count} | {other_id}（对方）消息数: {other_msg_count}")
print(f"{self_id}（自己）表情包数: {self_sticker_count} | {other_id}（对方）表情包数: {other_sticker_count}")
print(f"{self_id}（自己）图片数: {self_pic_count} | {other_id}（对方）图片数: {other_pic_count}")
print(f"{self_id}（自己）最大连续消息数: {max_self_cont} | {other_id}（对方）最大连续消息数: {max_other_cont}")
print(f"{self_id}（自己）消息总字数: {self_total_chars} | {other_id}（对方）消息总字数: {other_total_chars}")
print(f"\njokernum = {jokernum:.4f}  (消息数、表情包、最大连续、总字数、图片数 五项比率的平均值)")
print(penalty_note)
