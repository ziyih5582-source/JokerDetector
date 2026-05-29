# -*- coding: utf-8 -*-
"""
本次更新总结 (v4.8 版 + 严苛判定版)
算法内核重构 (零和博弈)：彻底摒弃了之前的线性平均逻辑，采用了基于“权力的不对等性”的微分数学模型。
高敏动态平衡：Sigmoid 函数偏置项调整为 0.05，斜率提升至 5.0。对微小的权力倾斜（如追求期）极其敏感，分数拉升极快。
严苛决策树：≥60分算法直接强杀确诊；45-60分交由AI死磕细节；<45分才算真正势均力敌。
AI 标尺收紧：明确规定“害怕冷场、过度解释、单向输出”即为小丑，打破“对方有回复就不算”的假阳性豁免。
"""

import sys
import subprocess
import importlib
import os
import math
import serial

# ================== 自动化依赖安装 ==================
REQUIRED_PACKAGES = {
    'pandas': 'pandas',
    'openpyxl': 'openpyxl',
    'xlrd': 'xlrd',
    'openai': 'openai',
    'httpx': 'httpx',
    'pygame': 'pygame',
    'PIL': 'Pillow',
    'serial': 'pyserial'
}

def auto_install_packages():
    print("🔍 正在检查运行环境...")
    for import_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            importlib.import_module(import_name)
        except ImportError:
            print(f"📦 发现缺失库，正在自动安装：{pip_name}，请稍候...")
            try:
                subprocess.check_call(
                    [sys.executable, "-m", "pip", "install", pip_name, "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]
                )
                print(f"✅ {pip_name} 安装成功！")
            except Exception as e:
                print(f"❌ 安装 {pip_name} 失败，请检查网络: {e}")
                sys.exit(1)

auto_install_packages()

# ================== 正常导入 ==================
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pandas as pd
import re
import threading
import tkinter.font as tkfont
from PIL import Image, ImageTk
from openai import OpenAI
import httpx
import pygame

# ================== 中文字体自动检测 ==================
def _detect_cn_font():
    candidates = [
        'Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'WenQuanYi Zen Hei',
        'AR PL UKai CN', 'AR PL UMing CN',
        'song ti', 'fangsong ti',
        'Microsoft YaHei', 'PingFang SC', 'Heiti SC', 'SimHei',
    ]
    r = tk.Tk()
    r.withdraw()
    for name in candidates:
        try:
            f = tkfont.Font(family=name, size=12)
            w = f.measure('测试')
            if w > 20: 
                r.destroy()
                return name
        except Exception:
            continue
    r.destroy()
    return 'TkDefaultFont'

CN_FONT = _detect_cn_font()

# ================== AI 配置 ==================
API_KEY = os.getenv("", "") # 请替换为你的真实 Key
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

# ================== 串口配置（连接 Arduino UNO） ==================
SERIAL_PORT = "COM3"
SERIAL_BAUD = 9600

def send_jokernum_to_arduino(jokernum):
    """将 jokernum (0~100) 通过串口发送给 Arduino UNO"""
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        # 将浮点数转为整数发送，Arduino 端使用 Serial.parseInt() 接收
        ser.write(f"{int(jokernum)}\n".encode('utf-8'))
        ser.close()
        print(f"[串口] 已发送 jokernum={int(jokernum)} → {SERIAL_PORT}")
    except Exception as e:
        print(f"[串口] 发送失败（Arduino 可能未连接）: {e}")

# ================== 小丑类型定义 ==================
JOKER_TYPES = {
    "殉道型": {
        "desc": "无条件付出，不期待对方的回报，认为付出本身就是自己的价值所在。",
        "suggestion": "你的价值不取决于你付出了多少。学会在关系中设立边界，真正的爱是双向流动的。",
        "image": "殉道型.jpg",
        "music": "过火.mp3",
        "color": "#C46868",
        "keywords": ["只要你", "不用管我", "我没事", "为你", "值得", "付出", "应该的", "你开心", "我就", "牺牲", "愿意等", "多久都", "没关系", "我不重要", "你先", "随便我", "无所谓我", "我怎样都行", "为了你"]
    },
    "镜像型": {
        "desc": "失去自我的感受，只考虑对方的情感和需求，变成了对方的镜子。",
        "suggestion": "你不是别人的影子。重新找回自己的喜好和观点，真实的你才最有吸引力。",
        "image": "镜像型.jpg",
        "music": "一直很安静.mp3",
        "color": "#6B8DB5",
        "keywords": ["我也是", "都行", "随便", "听你的", "你喜欢", "和你一样", "嗯嗯", "对的", "你说得对", "我也觉得", "看你了", "你觉得呢", "我都可以", "无所谓", "你定", "我跟着你"]
    },
    "弄臣型": {
        "desc": "靠自我贬低和自我嘲弄来渴求让对方开心，用笑话掩饰内心的不安全感。",
        "suggestion": "幽默是魅力，但自贬不是。你不需要贬低自己来让别人喜欢你——你本来就值得被喜欢。",
        "image": "弄臣型.jpg",
        "music": "怪咖.mp3",
        "color": "#D4A853",
        "keywords": ["我不配", "我这种人", "搞笑", "小丑", "废物", "菜鸡", "垃圾", "我是个", "我太菜", "别笑我", "丢人", "哈哈哈我", "我真服了", "笑死", "救命", "我死了", "呜呜", "我错了", "原谅我", "对不起对不起", "哈哈"]
    },
    "幻恋型": {
        "desc": "在大脑中不断幻想和对方的暧昧场景，而在现实中唯唯诺诺。",
        "suggestion": "脑海里的剧本不等于现实。勇敢地走出幻想，哪怕只是多说一句话，也比一万次内心戏更有意义。",
        "image": "幻恋型.jpg",
        "music": "水星记.mp3",
        "color": "#8B6FAF",
        "keywords": ["你是不是", "我在想", "如果", "以后", "会不会", "可能", "感觉", "好像", "也许", "万一", "要是", "说不定", "有没有可能", "该不会", "我猜", "我总觉得", "你知道吗", "我在幻想", "做梦", "梦到"]
    }
}

NOT_JOKER_DESC = "🎉 恭喜！你击败了全国 99% 的纯爱战神！\n在你们的聊天中，你保持了极高的人格独立与边界感，没有出现明显的妥协与卑微。但记住，爱情是一场势均力敌的博弈，继续保持你的清醒，享受关系本身吧！"

# ================== 核心分析引擎 ==================
class JokerAnalyzer:
    def __init__(self):
        self.client = None
        self.ai_model = MODEL
        self._init_ai()

    def _init_ai(self):
        if not API_KEY or API_KEY.startswith("sk-xxx"):
            self.client = None
            return
        try:
            self.client = OpenAI(api_key=API_KEY, base_url=BASE_URL, http_client=httpx.Client(trust_env=False))
        except Exception:
            self.client = None

    def parse_chat(self, file_path):
        try:
            if file_path.lower().endswith('.xls'):
                df = pd.read_excel(file_path, header=None, engine='xlrd')
            else:
                df = pd.read_excel(file_path, header=None, engine='openpyxl')
        except Exception as e:
            raise ValueError(f"读取 Excel 文件失败: {str(e)}")

        data = []
        current_speaker = None

        for _, row in df.iterrows():
            valid_cells = [str(x).strip() for x in row if pd.notna(x) and str(x).strip() != '']
            if not valid_cells: continue

            lines = []
            for cell in valid_cells: lines.extend(cell.split('\n'))
            lines = [line.strip() for line in lines if line.strip()]
            if not lines: continue

            if len(valid_cells) >= 2 and len(lines) == len(valid_cells):
                speaker = lines[-2].strip()
                msg = lines[-1].strip()
                speaker = re.sub(r'^(\d{2,4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s+)?', '', speaker).strip()
                if speaker and msg: data.append((speaker, msg))
                continue

            for line in lines:
                match_single = re.search(r'^([^:：]+)[:：]\s*(.+)$', line)
                if match_single:
                    speaker = match_single.group(1).strip()
                    speaker = re.sub(r'^(\d{2,4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s+)?(\d{1,2}:\d{1,2}(:\d{1,2})?\s+)?', '', speaker).strip()
                    msg = match_single.group(2).strip()
                    if len(speaker) <= 25: 
                        data.append((speaker, msg))
                        current_speaker = None
                    continue
                    
                match_speaker = re.search(r'^([^:：]+)[:：]$', line)
                if match_speaker and len(match_speaker.group(1)) <= 25:
                    raw_speaker = match_speaker.group(1).strip()
                    current_speaker = re.sub(r'^(\d{2,4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s+)?(\d{1,2}:\d{1,2}(:\d{1,2})?\s+)?', '', raw_speaker).strip()
                elif current_speaker:
                    data.append((current_speaker, line))
                    current_speaker = None 
                    
        return data

    def get_speakers(self, data):
        speaker_counts = {}
        for speaker, _ in data:
            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
        sorted_speakers = sorted(speaker_counts.items(), key=lambda x: x[1], reverse=True)
        return [s[0] for s in sorted_speakers[:2]]

    def compute_statistics(self, data, self_id, other_id):
        stats = {
            'self_msg_count': 0, 'other_msg_count': 0,
            'self_sticker_count': 0, 'other_sticker_count': 0,
            'self_pic_count': 0, 'other_pic_count': 0,
            'self_total_chars': 0, 'other_total_chars': 0,
            'max_self_cont': 0, 'max_other_cont': 0,
            'self_voice_call': 0, 'other_voice_call': 0,
            'has_voice_or_call': False,
            'self_keyword_matches': {t: 0 for t in JOKER_TYPES}
        }

        current_streak = 0
        current_speaker = None

        for speaker, msg in data:
            pics, stickers, is_voice_call = 0, 0, False

            if '[图片]' in msg: pics = 1
            elif '[语音]' in msg or '语音消息' in msg:
                stats['has_voice_or_call'] = True
                is_voice_call = True
            elif '通话' in msg:
                stats['has_voice_or_call'] = True
                is_voice_call = True
            elif re.search(r'\[.+?\]', msg): stickers = 1

            chars = len(msg)

            if speaker == self_id:
                stats['self_msg_count'] += 1
                stats['self_sticker_count'] += stickers
                stats['self_pic_count'] += pics
                stats['self_total_chars'] += chars
                if is_voice_call: stats['self_voice_call'] += 1
                for jtype, info in JOKER_TYPES.items():
                    for kw in info['keywords']:
                        if kw in msg: stats['self_keyword_matches'][jtype] += 1
            elif speaker == other_id:
                stats['other_msg_count'] += 1
                stats['other_sticker_count'] += stickers
                stats['other_pic_count'] += pics
                stats['other_total_chars'] += chars
                if is_voice_call: stats['other_voice_call'] += 1

            if speaker == current_speaker: current_streak += 1
            else:
                current_streak = 1
                current_speaker = speaker

            if speaker == self_id: stats['max_self_cont'] = max(stats['max_self_cont'], current_streak)
            elif speaker == other_id: stats['max_other_cont'] = max(stats['max_other_cont'], current_streak)

        stats['r1'] = stats['self_msg_count'] / stats['other_msg_count'] if stats['other_msg_count'] > 0 else 0
        stats['r2'] = stats['self_sticker_count'] / stats['other_sticker_count'] if stats['other_sticker_count'] > 0 else 0
        stats['r3'] = stats['max_self_cont'] / stats['max_other_cont'] if stats['max_other_cont'] > 0 else 0
        stats['r4'] = stats['self_total_chars'] / stats['other_total_chars'] if stats['other_total_chars'] > 0 else 0
        stats['r5'] = stats['self_pic_count'] / stats['other_pic_count'] if stats['other_pic_count'] > 0 else 0
        stats['self_avg_chars'] = stats['self_total_chars'] / stats['self_msg_count'] if stats['self_msg_count'] > 0 else 0
        stats['other_avg_chars'] = stats['other_total_chars'] / stats['other_msg_count'] if stats['other_msg_count'] > 0 else 0

        DA = sum(1 for i in range(1, len(data)) if data[i][0] == self_id and data[i-1][0] == self_id)
        DB = sum(1 for i in range(1, len(data)) if data[i][0] == other_id and data[i-1][0] == other_id)
        Z_SSDT = (DA - DB) / (DA + DB + 1e-6)

        I_A = sum(msg.count(w) for w in ['我', '俺', '自己'] for sp, msg in data if sp == self_id)
        We_A = sum(msg.count(w) for w in ['我们', '咱们'] for sp, msg in data if sp == self_id)
        I_B = sum(msg.count(w) for w in ['我', '俺', '自己'] for sp, msg in data if sp == other_id)
        We_B = sum(msg.count(w) for w in ['我们', '咱们'] for sp, msg in data if sp == other_id)
        PFI_A = math.log(I_A + 1) / (math.log(We_A + 1) + 1e-6)
        PFI_B = math.log(I_B + 1) / (math.log(We_B + 1) + 1e-6)
        Z_PFI = (PFI_A - PFI_B) / (PFI_A + PFI_B + 1e-6) 

        Hedges = ['可能', '有点', '似乎', '也许', '嗯', '那个', '对吧', '好吗', '对不起', '抱歉', '不好意思', '哈哈', '？', '?']
        Hedge_A = sum(msg.count(w) for w in Hedges for sp, msg in data if sp == self_id)
        Hedge_B = sum(msg.count(w) for w in Hedges for sp, msg in data if sp == other_id)
        PLD_A = Hedge_A / (stats['self_total_chars'] + 1)
        PLD_B = Hedge_B / (stats['other_total_chars'] + 1)
        Z_PLD = (PLD_A - PLD_B) / (PLD_A + PLD_B + 1e-6)

        Emotions = ['开心', '喜欢', '爱', '讨厌', '生气', '郁闷', '绝望', '崩溃', '高兴', '烦', '累', '痛', '死', '哭', '笑', '！', '!']
        E_A = sum(msg.count(w) for w in Emotions for sp, msg in data if sp == self_id)
        E_B = sum(msg.count(w) for w in Emotions for sp, msg in data if sp == other_id)
        EPEG = math.log(E_A + 1) - math.log(E_B + 1)
        Z_EPEG = max(min(EPEG / 2.0, 1.0), -1.0) 

        FuncWords = ['因为', '所以', '并且', '但是', '是', '有', '能够', '可以', '很', '非常', '其实', '只', '就']
        conv_ab, base_ab, conv_ba, base_ba = 0, 0, 0, 0
        for i in range(1, len(data)):
            prev_sp, prev_msg = data[i-1]
            curr_sp, curr_msg = data[i]
            if curr_sp == self_id and prev_sp == other_id:
                if any(w in prev_msg and w in curr_msg for w in FuncWords): conv_ab += 1
                base_ab += 1
            elif curr_sp == other_id and prev_sp == self_id:
                if any(w in prev_msg and w in curr_msg for w in FuncWords): conv_ba += 1
                base_ba += 1
        Conv_AB = conv_ab / (base_ab + 1e-6)
        Conv_BA = conv_ba / (base_ba + 1e-6)
        Z_CONV = Conv_AB - Conv_BA

        # ⚠️绝对严苛优化：左移偏置到 0.05，增大斜率到 5.0。只要有轻微势能差，分数立刻拉升
        Z_Total = 0.25 * Z_SSDT + 0.2 * Z_PFI + 0.2 * Z_PLD + 0.15 * Z_EPEG + 0.2 * Z_CONV
        score = 100 / (1 + math.exp(-5.0 * (Z_Total - 0.05)))
        
        # 语音通话的扣分力度减弱，避免追人的时候打了几个电话就被洗白
        if stats['has_voice_or_call']: score *= 0.95

        stats['jokernum_alg'] = score
        stats['z_metrics'] = {'SSDT': Z_SSDT, 'PFI': Z_PFI, 'PLD': Z_PLD, 'EPEG': Z_EPEG, 'CONV': Z_CONV}
        return stats

    def classify_joker_type_algorithmic(self, stats, data, self_id):
        score = stats['jokernum_alg']
        
        # 这个只是基础门槛，用于生成类型。真实的是否小丑取决于 full_analysis 的交叉验证
        is_joker = score > 45.0

        z_metrics = stats['z_metrics']
        highest_metric = max(z_metrics, key=z_metrics.get)

        if highest_metric == 'SSDT': joker_type = "幻恋型"      
        elif highest_metric == 'CONV': joker_type = "镜像型"     
        elif highest_metric == 'PLD': joker_type = "弄臣型"      
        else: joker_type = "殉道型"                              

        return is_joker, joker_type, score

    def classify_joker_type_ai(self, data, self_id, stats):
        if self.client is None: return None, None, None
        transcript_lines = [f"{'【自己】' if speaker == self_id else '【对方】'}{speaker}: {msg}" for speaker, msg in data]
        transcript = "\n".join(transcript_lines[-300:]) 

        # ⚠️严苛标尺：不再因为“对方有回复”就放过，严查害怕冷场和情绪单向输出
        prompt = f"""你是一位极其敏锐的情感博弈分析师。阅读聊天记录，判断【自己】在关系中是否处于低位（小丑）。

【严苛判定标尺】：
1. 只要【自己】表现出以下任何一点：害怕冷场而连续找话题、过度解释自己的行为、字数和热情明显多于对方、单向提供情绪价值（即使对方有回复）。只要满足其一，【必须】判定为小丑。
2. 只有当双方完全势均力敌，互相推拉，不惧怕冷场，谁也不怕失去谁时，才能输出：NOT_JOKER

如果属于小丑行为，输出：类型名称（殉道型/镜像型/弄臣型/幻恋型） 小丑指数（60-100整数）
如果不属于，输出：NOT_JOKER

聊天记录：\n{transcript}"""

        try:
            response = self.client.chat.completions.create(
                model=self.ai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2, max_tokens=20
            )
            res = response.choices[0].message.content.strip()
            if "NOT_JOKER" in res.upper(): return False, None, None
            for t in JOKER_TYPES:
                if t in res:
                    m = re.search(r'(\d+)', res)
                    return True, t, int(m.group(1)) if m else 65
            return True, "殉道型", 65
        except:
            return None, None, None

    def ai_guidance(self, data, self_id, is_joker, joker_type):
        if self.client is None: return None
        
        transcript_lines = [f"{'【自己】' if speaker == self_id else '【对方】'}{speaker}: {msg}" for speaker, msg in data]
        transcript = "\n".join(transcript_lines[-500:])
        
        if is_joker:
            type_info = JOKER_TYPES.get(joker_type, {})
            type_desc = type_info.get('desc', '')
            
            prompt = f"""你是一位理性客观的情感支持导师。用户被分析为「{joker_type}」小丑（{type_desc}）。

请阅读聊天记录，从【自己】的视角出发，写一段情感疏导（2000字左右）：
1. 先安抚情绪
2. 结合他的具体聊天内容具体分析，点出问题。结合著名的人际交往和爱情理论（如依恋理论、亲密关系的五大需求等）进行分析，帮助他理解自己的行为模式和背后的心理机制
3. 针对具体的聊天内容给出具体的建议
4. 语气温柔
5. 如果你没有拿到具体的聊天记录就老实说没拿到聊天记录，方便开发者调试

聊天记录：
{transcript}"""

        else:
            prompt = f"""你是一位理性客观的情感支持导师。用户在聊天中表现出了极高的人格独立和边界感，没有陷入卑微讨好的境地，属于势均力敌的「清醒玩家」。

请阅读聊天记录，写一段情感复盘与鼓励（1000字左右）：
1. 肯定并夸奖ta在聊天中不卑不亢的具体表现（请引用聊天记录中的具体细节）。
2. 结合著名的人际交往和爱情理论，分析目前这段关系中的权力流动状态，告诉ta为什么这种保持自我的方式是健康的。
3. 给出一条进阶建议，指导ta如何继续保持这种健康博弈关系。
4. 语气温柔、真诚且带有欣赏。
5. 如果你没有拿到具体的聊天记录就老实说没拿到聊天记录，方便开发者调试。

聊天记录：
{transcript}"""

        try:
            response = self.client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {"role": "system", "content": "你是一位富有同理心且专业的情感导师。你的回答需要娓娓道来，充满温度，像一封写给朋友的信。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7, 
                max_tokens=2000
            )
            return response.choices[0].message.content.strip()
        except:
            return None

    def full_analysis(self, file_path, self_index):
        data = self.parse_chat(file_path)
        if not data: raise ValueError("未能提取到有效聊天内容，请检查表格格式")
        speakers = self.get_speakers(data)
        if len(speakers) < 2: raise ValueError("必须包含至少2个人的对话数据！")

        self_id, other_id = speakers[self_index], speakers[1 - self_index]
        stats = self.compute_statistics(data, self_id, other_id)
        
        is_joker_alg, joker_type_alg, _ = self.classify_joker_type_algorithmic(stats, data, self_id)
        is_joker_ai, joker_type_ai, ai_score = self.classify_joker_type_ai(data, self_id, stats)

        ai_available = is_joker_ai is not None
        alg_score = stats['jokernum_alg']
        
        # ⚠️核弹级收严：降低确诊门槛
        if ai_available:
            if alg_score >= 60.0:
                # 算出来超过 60 分（追求期），立刻盖章确诊，不听 AI 辩解
                is_joker = True
            elif alg_score >= 45.0:
                # 45-60分的微小倾斜，让 AI 决定
                is_joker = is_joker_ai
            else:
                is_joker = False
        else:
            # 断网状态下，算法过 50 即确诊
            is_joker = alg_score > 50.0

        if is_joker and ai_available and joker_type_ai: 
            joker_type = joker_type_ai
        elif is_joker: 
            joker_type = joker_type_alg
        else: 
            joker_type, ai_score = None, None

        guidance = self.ai_guidance(data, self_id, is_joker, joker_type) if self.client else None

        return {
            'data': data, 'speakers': speakers, 'self_id': self_id, 'other_id': other_id,
            'stats': stats, 'is_joker': is_joker, 'joker_type': joker_type,
            'joker_type_ai': (is_joker_ai, joker_type_ai), 'ai_score': ai_score,
            'ai_available': ai_available, 'guidance': guidance
        }

# ================== GUI ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PICTURES_DIR = os.path.join(BASE_DIR, "pictures")
MUSIC_DIR = os.path.join(BASE_DIR, "music")

def _load_text(filename):
    path = os.path.join(BASE_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f: return f.read()
    return ""

class JokerDetectorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🃏 Joker Detector - 小丑检测器")
        self.root.geometry("960x760")
        self.root.minsize(800, 600)
        self.root.configure(bg="#FBF5DD")

        try:
            pygame.mixer.init()
            self.music_enabled = True
            self.is_paused = False
        except Exception:
            self.music_enabled = False
            self.is_paused = False

        self.colors = {
            'bg_cream': '#FBF5DD', 'bg_card': '#FFFFFF', 'bg_alt': '#F5F5F5',
            'accent': '#99AD7A', 'accent_dark': '#7D9460', 'text_primary': '#2D2D2D',
            'text_secondary': '#7A7A7A', 'text_muted': '#AAAAAA', 'success': '#6BAF7B',
            'warning': '#D4A853', 'danger': '#C46868', 'info': '#6B8DB5', 'border': '#E8E0D0'
        }

        self.analyzer = JokerAnalyzer()
        self.result = None
        self.photo_image = None  

        self.text_theory = _load_text("theroy.txt")
        self.text_emotion = _load_text("somewords.txt")

        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Cream.TFrame', background=self.colors['bg_cream'])
        style.configure('Card.TFrame', background=self.colors['bg_card'])
        style.configure('Cream.TLabel', background=self.colors['bg_cream'], foreground=self.colors['text_primary'], font=(CN_FONT, 11))
        style.configure('Card.TLabel', background=self.colors['bg_card'], foreground=self.colors['text_primary'], font=(CN_FONT, 11))
        style.configure('Title.TLabel', background=self.colors['bg_cream'], foreground=self.colors['text_primary'], font=(CN_FONT, 22, 'bold'))
        style.configure('Subtitle.TLabel', background=self.colors['bg_cream'], foreground=self.colors['text_secondary'], font=(CN_FONT, 11))
        style.configure('Accent.TLabel', background=self.colors['bg_card'], foreground=self.colors['accent'], font=(CN_FONT, 14, 'bold'))
        style.configure('TypeTitle.TLabel', background=self.colors['bg_card'], foreground=self.colors['text_primary'], font=(CN_FONT, 18, 'bold'))
        style.configure('TypeDesc.TLabel', background=self.colors['bg_card'], foreground=self.colors['text_secondary'], font=(CN_FONT, 12), wraplength=400)
        style.configure('Stat.TLabel', background=self.colors['bg_card'], foreground=self.colors['text_primary'], font=(CN_FONT, 10))
        style.configure('Cream.TButton', font=(CN_FONT, 11), padding=(20, 8))
        style.configure('Accent.TButton', font=(CN_FONT, 12, 'bold'), padding=(30, 10))
        style.configure('Small.TButton', font=(CN_FONT, 10), padding=(10, 4))

    def _build_ui(self):
        header = ttk.Frame(self.root, style='Cream.TFrame')
        header.pack(fill='x', padx=20, pady=(20, 0))
        ttk.Label(header, text="🃏 Joker Detector", style='Title.TLabel').pack(anchor='w')
        ttk.Label(header, text="输入聊天记录，检测你的小丑指数 & 小丑类型", style='Subtitle.TLabel').pack(anchor='w', pady=(4, 0))

        main = ttk.Frame(self.root, style='Cream.TFrame')
        main.pack(fill='both', expand=True, padx=20, pady=15)

        left = ttk.Frame(main, style='Card.TFrame')
        left.pack(side='left', fill='both', expand=False, padx=(0, 8), ipadx=5)
        self._build_left_panel(left)

        right = ttk.Frame(main, style='Cream.TFrame')
        right.pack(side='right', fill='both', expand=True, padx=(8, 0))
        self._build_right_panel(right)

    def _build_left_panel(self, parent):
        file_frame = ttk.Frame(parent, style='Card.TFrame')
        file_frame.pack(fill='x', padx=15, pady=(15, 10))
        ttk.Label(file_frame, text="📂 选择聊天记录文件", style='Accent.TLabel').pack(anchor='w', pady=(0, 10))
        btn_frame = ttk.Frame(file_frame, style='Card.TFrame')
        btn_frame.pack(fill='x')
        self.file_btn = ttk.Button(btn_frame, text="浏览选择 Excel...", command=self._select_file, style='Cream.TButton')
        self.file_btn.pack(side='left', padx=(0, 10))
        self.file_label = ttk.Label(btn_frame, text="未选择文件", style='Card.TLabel', foreground=self.colors['text_secondary'])
        self.file_label.pack(side='left')

        ttk.Separator(parent, orient='horizontal').pack(fill='x', padx=15, pady=10)

        speaker_frame = ttk.Frame(parent, style='Card.TFrame')
        speaker_frame.pack(fill='x', padx=15, pady=5)
        ttk.Label(speaker_frame, text="👤 选择你自己", style='Accent.TLabel').pack(anchor='w', pady=(0, 10))
        self.speaker_var = tk.IntVar(value=0)
        self.speaker_btn_frame = ttk.Frame(speaker_frame, style='Card.TFrame')
        self.speaker_btn_frame.pack(fill='x', pady=5)
        self.speaker_btn0 = ttk.Radiobutton(self.speaker_btn_frame, text="用户 0", variable=self.speaker_var, value=0)
        self.speaker_btn0.pack(side='left', padx=(0, 20))
        self.speaker_btn1 = ttk.Radiobutton(self.speaker_btn_frame, text="用户 1", variable=self.speaker_var, value=1)
        self.speaker_btn1.pack(side='left')

        self.analyze_btn = ttk.Button(parent, text="🔍 开始分析", command=self._start_analysis, style='Accent.TButton', state='disabled')
        self.analyze_btn.pack(fill='x', padx=15, pady=15)

        self.progress = ttk.Progressbar(parent, mode='indeterminate')
        self.progress.pack(fill='x', padx=15, pady=(0, 5))

        self.status_label = ttk.Label(parent, text="就绪 —— 请选择文件后开始", style='Card.TLabel', foreground=self.colors['text_secondary'])
        self.status_label.pack(anchor='w', padx=15, pady=(0, 10))

        info_frame = ttk.Frame(parent, style='Card.TFrame')
        info_frame.pack(fill='both', expand=True, padx=15, pady=(5, 15))
        ttk.Label(info_frame, text="🎭 四种小丑类型", style='Accent.TLabel').pack(anchor='w', pady=(10, 5))
        type_info_text = (
            "🔴 殉道型：无条件付出，不期待回报\n"
            "🔵 镜像型：失去自我，变成对方的镜子\n"
            "🟡 弄臣型：自我贬低，用笑话掩饰不安\n"
            "🟣 幻恋型：脑中幻想千遍，现实唯唯诺诺"
        )
        ttk.Label(info_frame, text=type_info_text, style='Card.TLabel', foreground=self.colors['text_secondary'], font=(CN_FONT, 10)).pack(anchor='w', pady=(0, 10))

        ai_status = "✅ AI 已连接" if self.analyzer.client else "⚠️ AI 未连接（仅算法模式）"
        ai_color = self.colors['success'] if self.analyzer.client else self.colors['warning']
        ttk.Label(info_frame, text=ai_status, style='Card.TLabel', foreground=ai_color, font=(CN_FONT, 10)).pack(anchor='w', pady=(5, 10))

        ttk.Separator(info_frame, orient='horizontal').pack(fill='x', pady=(5, 0))
        ttk.Label(info_frame, text="📖 知识库与控制", style='Accent.TLabel').pack(anchor='w', pady=(10, 5))
        btn_frame = ttk.Frame(info_frame, style='Card.TFrame')
        btn_frame.pack(fill='x', pady=(0, 5))
        ttk.Button(btn_frame, text="📚 恋爱理论", command=lambda: self._show_popup("📚 恋爱心理学理论", self.text_theory), style='Small.TButton').pack(side='left', padx=(0, 8))
        ttk.Button(btn_frame, text="💬 情感话语", command=lambda: self._show_popup("💬 情感话语", self.text_emotion), style='Small.TButton').pack(side='left')
        self.toggle_music_btn = ttk.Button(btn_frame, text="⏸ 暂停音乐", command=self._toggle_music, style='Small.TButton')
        self.toggle_music_btn.pack(side='left', padx=(8, 0))

    def _show_popup(self, title, text):
        if not text:
            messagebox.showinfo("提示", "文本内容未加载，请检查文件是否存在。")
            return
        popup = tk.Toplevel(self.root)
        popup.title(title)
        popup.geometry("600x500")
        popup.configure(bg=self.colors['bg_card'])
        st = scrolledtext.ScrolledText(popup, wrap=tk.WORD, font=(CN_FONT, 11), bg=self.colors['bg_card'], fg=self.colors['text_primary'], relief='flat', padx=20, pady=15)
        st.pack(fill='both', expand=True)
        st.insert('1.0', text)
        st.configure(state='disabled')

    def _toggle_music(self):
        if not getattr(self, 'music_enabled', False): return
        if getattr(self, 'is_paused', False):
            pygame.mixer.music.unpause()
            self.is_paused = False
            self.toggle_music_btn.configure(text="⏸ 暂停音乐")
        else:
            pygame.mixer.music.pause()
            self.is_paused = True
            self.toggle_music_btn.configure(text="▶ 继续播放")

    def _export_report(self):
        if not self.result: return
        file_path = filedialog.asksaveasfilename(title="保存诊断报告", defaultextension=".txt", initialfile="Joker_Report.txt")
        if not file_path: return
        r = self.result
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(f"诊断对象：{r['self_id']} \n诊断得分：{r['stats']['jokernum_alg']:.1f}/100\n类型：{r['joker_type'] if r['is_joker'] else '清醒非小丑'}")
                if r.get('guidance'):
                    f.write(f"\n\n========================\n\n{r['guidance']}")
            messagebox.showinfo("导出成功", f"报告已保存至：\n{file_path}")
        except Exception as e:
            messagebox.showerror("导出失败", f"保存错误：\n{e}")

    def _build_right_panel(self, parent):
        self.result_frame = ttk.Frame(parent, style='Card.TFrame')
        self.result_frame.pack(fill='both', expand=True)
        
        self.placeholder = ttk.Frame(self.result_frame, style='Card.TFrame')
        self.placeholder.pack(fill='both', expand=True, padx=20, pady=20)
        ttk.Label(self.placeholder, text="🃏", font=(CN_FONT, 64), background=self.colors['bg_card']).pack(pady=(60, 15))
        ttk.Label(self.placeholder, text="等待分析...", style='TypeTitle.TLabel').pack(pady=5)
        
        self.scroll_container = ttk.Frame(self.result_frame, style='Card.TFrame')
        self.scrollbar = ttk.Scrollbar(self.scroll_container, orient="vertical")
        self.scrollbar.pack(side="right", fill="y")
        self.canvas = tk.Canvas(self.scroll_container, bg=self.colors['bg_card'], highlightthickness=0, yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.config(command=self.canvas.yview)
        
        self.result_content = ttk.Frame(self.canvas, style='Card.TFrame')
        self.canvas_window = self.canvas.create_window((0, 0), window=self.result_content, anchor="nw")
        
        self.result_content.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfig(self.canvas_window, width=e.width))

        self.root.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units") if self.scroll_container.winfo_ismapped() else None)

    def _select_file(self):
        file_path = filedialog.askopenfilename(title="选择聊天记录", filetypes=[("Excel 文件", "*.xlsx *.xls *.csv")])
        if file_path:
            self.selected_file = file_path
            self.file_label.configure(text=os.path.basename(file_path))
            try:
                data = self.analyzer.parse_chat(file_path)
                speakers = self.analyzer.get_speakers(data)
                if len(speakers) >= 2:
                    self.speaker_btn0.configure(text=speakers[0])
                    self.speaker_btn1.configure(text=speakers[1])
                    self.analyze_btn.configure(state='normal')
                    self.status_label.configure(text=f"✅ 检测到 {len(data)} 条消息", foreground=self.colors['success'])
                else:
                    self.analyze_btn.configure(state='disabled')
            except Exception as e:
                pass

    def _start_analysis(self):
        if not hasattr(self, 'selected_file'): return
        if getattr(self, 'music_enabled', False): pygame.mixer.music.stop()
        self.analyze_btn.configure(state='disabled', text="⏳ 分析中...")
        self.progress.start(10)

        def run():
            try:
                self.result = self.analyzer.full_analysis(self.selected_file, self.speaker_var.get())
                # 将 jokernum 通过串口发送给 Arduino UNO
                jokernum = self.result['stats']['jokernum_alg']
                send_jokernum_to_arduino(jokernum)
                self.root.after(0, self._display_result)
            except Exception as e:
                self.root.after(0, lambda: self._on_error(str(e)))
        threading.Thread(target=run, daemon=True).start()

    def _on_error(self, msg):
        self.progress.stop()
        self.analyze_btn.configure(state='normal', text="🔍 开始分析")
        messagebox.showerror("分析失败", msg)

    def _display_result(self):
        self.progress.stop()
        self.analyze_btn.configure(state='normal', text="🔍 重新分析")
        self.placeholder.pack_forget()
        for widget in self.result_content.winfo_children(): widget.destroy()
        self.scroll_container.pack(fill='both', expand=True)
        self.canvas.yview_moveto(0)

        r = self.result
        is_joker, joker_type, stats = r['is_joker'], r['joker_type'], r['stats']

        header_frame = ttk.Frame(self.result_content, style='Card.TFrame')
        header_frame.pack(fill='x', padx=15, pady=(15, 5))

        if is_joker and joker_type:
            type_info = JOKER_TYPES[joker_type]
            verdict = f"🤡 确诊小丑 —— {joker_type}"
            if getattr(self, 'music_enabled', False):
                music_file = os.path.join(MUSIC_DIR, type_info['music'])
                if os.path.exists(music_file):
                    try: pygame.mixer.music.load(music_file); pygame.mixer.music.play(-1); self.is_paused = False; self.toggle_music_btn.configure(text="⏸ 暂停音乐")
                    except: pass
        else:
            verdict, type_info = "👑 恭喜！你不是小丑", None

        tk.Label(header_frame, text=verdict, fg=type_info['color'] if type_info else self.colors['success'], bg=self.colors['bg_card'], font=(CN_FONT, 20, 'bold')).pack(anchor='w')

        score_text = f"📊 算法综合得分：{stats['jokernum_alg']:.1f}/100"
        if r.get('ai_score') is not None: score_text += f"  |  🤖 AI 情感判定分：{r['ai_score']}/100"
        ttk.Label(header_frame, text=score_text, style='Card.TLabel', foreground=self.colors['text_secondary']).pack(anchor='w', pady=(5, 0))

        ttk.Separator(self.result_content, orient='horizontal').pack(fill='x', padx=15, pady=8)

        if is_joker and type_info:
            img_desc_frame = ttk.Frame(self.result_content, style='Card.TFrame')
            img_desc_frame.pack(fill='x', padx=15, pady=8)
            img_path = os.path.join(PICTURES_DIR, type_info['image'])
            img_frame = ttk.Frame(img_desc_frame, style='Card.TFrame')
            img_frame.pack(side='left', padx=(0, 15))
            if os.path.exists(img_path):
                try:
                    pil_img = Image.open(img_path).resize((200, 200), Image.LANCZOS)
                    self.photo_image = ImageTk.PhotoImage(pil_img)
                    tk.Label(img_frame, image=self.photo_image, bg=self.colors['bg_card']).pack()
                except: tk.Label(img_frame, text=f"[图片加载失败]", bg=self.colors['bg_card'], width=25, height=10).pack()

            desc_frame = ttk.Frame(img_desc_frame, style='Card.TFrame')
            desc_frame.pack(side='left', fill='both', expand=True)
            tk.Label(desc_frame, text=type_info['desc'], bg=self.colors['bg_card'], font=(CN_FONT, 12), wraplength=420, justify='left').pack(anchor='w', pady=(6, 10))
            tk.Label(desc_frame, text=f"💡 {type_info['suggestion']}", bg=self.colors['bg_card'], fg=self.colors['success'], font=(CN_FONT, 11, 'italic'), wraplength=420, justify='left').pack(anchor='w')
        else:
            ttk.Label(self.result_content, text=NOT_JOKER_DESC, style='Card.TLabel', font=(CN_FONT, 12), wraplength=550).pack(anchor='w', padx=15, pady=15)

        ttk.Separator(self.result_content, orient='horizontal').pack(fill='x', padx=15, pady=8)

        stats_frame = ttk.Frame(self.result_content, style='Card.TFrame')
        stats_frame.pack(fill='x', padx=15, pady=5)
        ttk.Label(stats_frame, text="📊 基础聊天行为统计", style='Accent.TLabel').pack(anchor='w', pady=(0, 8))
        
        stat_grid = ttk.Frame(stats_frame, style='Card.TFrame')
        stat_grid.pack(fill='x')
        left_stats = [f"消息数：自己 {stats['self_msg_count']} / 对方 {stats['other_msg_count']}", f"表情包：自己 {stats['self_sticker_count']} / 对方 {stats['other_sticker_count']}", f"图片数：自己 {stats['self_pic_count']} / 对方 {stats['other_pic_count']}"]
        right_stats = [f"总字数：自己 {stats['self_total_chars']} / 对方 {stats['other_total_chars']}", f"最大连发：自己 {stats['max_self_cont']} / 对方 {stats['max_other_cont']}", f"平均字数：自己 {stats['self_avg_chars']:.1f} / 对方 {stats['other_avg_chars']:.1f}"]
        
        for i in range(len(left_stats)):
            ttk.Label(stat_grid, text=left_stats[i], style='Stat.TLabel', foreground=self.colors['text_secondary']).grid(row=i, column=0, sticky='w', pady=2, padx=(0, 30))
            ttk.Label(stat_grid, text=right_stats[i], style='Stat.TLabel', foreground=self.colors['text_secondary']).grid(row=i, column=1, sticky='w', pady=2)

        if r.get('guidance'):
            ttk.Separator(self.result_content, orient='horizontal').pack(fill='x', padx=15, pady=8)
            g_frame = ttk.Frame(self.result_content, style='Card.TFrame')
            g_frame.pack(fill='x', padx=15, pady=5)
            ai_title = "💌 AI 深度情感诊断报告" if is_joker else "👑 AI 高阶博弈复盘报告"
            ttk.Label(g_frame, text=ai_title, style='Accent.TLabel').pack(anchor='w', pady=(0, 8))
            ttk.Label(g_frame, text=r['guidance'], style='TypeDesc.TLabel', wraplength=550).pack(anchor='w')

        b_frame = ttk.Frame(self.result_content, style='Card.TFrame')
        b_frame.pack(fill='x', padx=15, pady=20)
        ttk.Button(b_frame, text="📄 导出简单报告", command=self._export_report, style='Cream.TButton').pack(side='right')

        self.status_label.configure(text="✅ 分析完成！", foreground=self.colors['success'])

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = JokerDetectorGUI()
    app.run()