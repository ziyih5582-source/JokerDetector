# -*- coding: utf-8 -*-
"""
本次更新总结 (COM10 专属联动版)
1. 端口配置：已在底层 send_to_arduino 方法中将端口硬编码为 COM10。
2. 界面完整：完美保留所有 UI 模块（图片展示、数据网格、三个控制按钮、导出报告功能）。
3. 纯净架构：无虚拟环境套娃，直接运行即可触发硬件联动。
"""

import os
import sys
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
import serial
import math

# ================== 基础路径配置 ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PICTURES_DIR = os.path.join(BASE_DIR, "pictures")
MUSIC_DIR = os.path.join(BASE_DIR, "music")

def _load_text(filename):
    path = os.path.join(BASE_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f: return f.read()
    return ""

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
API_KEY = os.getenv("loneranger1118", "sk-bd9dc29e52f94d76b42990a0592d6c37") # 请替换为你的真实 Key
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

# ================== 小丑类型定义 ==================
JOKER_TYPES = {
    "殉道型": {
        "desc": "无条件付出，不期待对方的回报，认为付出本身就是自己的价值所在。",
        "suggestion": "你的价值不取决于你付出了多少。学会在关系中设立边界，真正的爱是双向流动的。",
        "image": "殉道型.jpg", "music": "过火.mp3", "color": "#C46868",
        "keywords": ["只要你", "不用管我", "我没事", "为你", "值得", "付出", "应该的", "随便我", "为了你"]
    },
    "镜像型": {
        "desc": "失去自我的感受，只考虑对方的情感和需求，变成了对方的镜子。",
        "suggestion": "你不是别人的影子。重新找回自己的喜好和观点，真实的你才最有吸引力。",
        "image": "镜像型.jpg", "music": "一直很安静.mp3", "color": "#6B8DB5",
        "keywords": ["我也是", "都行", "随便", "听你的", "你喜欢", "和你一样", "我也觉得", "看你了", "你定"]
    },
    "弄臣型": {
        "desc": "靠自我贬低和自我嘲弄来渴求让对方开心，用笑话掩饰内心的不安全感。",
        "suggestion": "幽默是魅力，但自贬不是。你不需要贬低自己来让别人喜欢你——你本来就值得被喜欢。",
        "image": "弄臣型.jpg", "music": "怪咖.mp3", "color": "#D4A853",
        "keywords": ["我不配", "我这种人", "搞笑", "小丑", "废物", "我太菜", "丢人", "救命", "我错了", "对不起对不起"]
    },
    "幻恋型": {
        "desc": "在大脑中不断幻想和对方的暧昧场景，而在现实中唯唯诺诺。",
        "suggestion": "脑海里的剧本不等于现实。勇敢地走出幻想，哪怕只是多说一句话，也比一万次内心戏更有意义。",
        "image": "幻恋型.jpg", "music": "水星记.mp3", "color": "#8B6FAF",
        "keywords": ["你是不是", "我在想", "如果", "以后", "会不会", "可能", "感觉", "有没有可能", "做梦", "梦到"]
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
        if not API_KEY or API_KEY.startswith("sk-xxx"): return
        try:
            self.client = OpenAI(api_key=API_KEY, base_url=BASE_URL, http_client=httpx.Client(trust_env=False))
        except: pass

    def parse_chat(self, file_path):
        try:
            if file_path.lower().endswith('.xls'): df = pd.read_excel(file_path, header=None, engine='xlrd')
            else: df = pd.read_excel(file_path, header=None, engine='openpyxl')
        except Exception as e: raise ValueError(f"读取文件失败: {str(e)}")

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
                speaker = re.sub(r'^(\d{2,4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s+)?', '', lines[-2].strip()).strip()
                if speaker and lines[-1]: data.append((speaker, lines[-1].strip()))
                continue

            for line in lines:
                match_single = re.search(r'^([^:：]+)[:：]\s*(.+)$', line)
                if match_single:
                    speaker = re.sub(r'^(\d{2,4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s+)?(\d{1,2}:\d{1,2}(:\d{1,2})?\s+)?', '', match_single.group(1).strip()).strip()
                    if len(speaker) <= 25: 
                        data.append((speaker, match_single.group(2).strip()))
                        current_speaker = None
                    continue
                    
                match_speaker = re.search(r'^([^:：]+)[:：]$', line)
                if match_speaker and len(match_speaker.group(1)) <= 25:
                    current_speaker = re.sub(r'^(\d{2,4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s+)?(\d{1,2}:\d{1,2}(:\d{1,2})?\s+)?', '', match_speaker.group(1).strip()).strip()
                elif current_speaker:
                    data.append((current_speaker, line))
                    current_speaker = None 
        return data

    def get_speakers(self, data):
        counts = {}
        for sp, _ in data: counts[sp] = counts.get(sp, 0) + 1
        return [s[0] for s in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:2]]

    def compute_statistics(self, data, self_id, other_id):
        stats = {'self_msg_count': 0, 'other_msg_count': 0, 'self_sticker_count': 0, 'other_sticker_count': 0,
                 'self_pic_count': 0, 'other_pic_count': 0, 'self_total_chars': 0, 'other_total_chars': 0,
                 'max_self_cont': 0, 'max_other_cont': 0, 'has_voice_or_call': False, 'self_keyword_matches': {t: 0 for t in JOKER_TYPES}}
        curr_streak, curr_sp = 0, None
        for sp, msg in data:
            pics = 1 if '[图片]' in msg else 0
            stickers = 1 if re.search(r'\[.+?\]', msg) and not pics else 0
            if '[语音]' in msg or '语音消息' in msg or '通话' in msg: stats['has_voice_or_call'] = True
            
            chars = len(msg)
            if sp == self_id:
                stats['self_msg_count'] += 1; stats['self_sticker_count'] += stickers; stats['self_pic_count'] += pics; stats['self_total_chars'] += chars
                for jtype, info in JOKER_TYPES.items():
                    for kw in info['keywords']:
                        if kw in msg: stats['self_keyword_matches'][jtype] += 1
            elif sp == other_id:
                stats['other_msg_count'] += 1; stats['other_sticker_count'] += stickers; stats['other_pic_count'] += pics; stats['other_total_chars'] += chars

            if sp == curr_sp: curr_streak += 1
            else: curr_streak, curr_sp = 1, sp

            if sp == self_id: stats['max_self_cont'] = max(stats['max_self_cont'], curr_streak)
            elif sp == other_id: stats['max_other_cont'] = max(stats['max_other_cont'], curr_streak)

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
            p_sp, p_msg = data[i-1]
            c_sp, c_msg = data[i]
            if c_sp == self_id and p_sp == other_id:
                if any(w in p_msg and w in c_msg for w in FuncWords): conv_ab += 1
                base_ab += 1
            elif c_sp == other_id and p_sp == self_id:
                if any(w in p_msg and w in c_msg for w in FuncWords): conv_ba += 1
                base_ba += 1
        Z_CONV = (conv_ab / (base_ab + 1e-6)) - (conv_ba / (base_ba + 1e-6))

        # 算法模型 (严苛标尺)
        Z_Total = 0.25 * Z_SSDT + 0.2 * Z_PFI + 0.2 * Z_PLD + 0.15 * Z_EPEG + 0.2 * Z_CONV
        score = 100 / (1 + math.exp(-5.0 * (Z_Total - 0.05)))
        if stats['has_voice_or_call']: score *= 0.95

        stats['jokernum_alg'] = score
        stats['z_metrics'] = {'SSDT': Z_SSDT, 'PFI': Z_PFI, 'PLD': Z_PLD, 'EPEG': Z_EPEG, 'CONV': Z_CONV}
        return stats

    def classify_joker_type_algorithmic(self, stats):
        hm = max(stats['z_metrics'], key=stats['z_metrics'].get)
        if hm == 'SSDT': return "幻恋型"      
        elif hm == 'CONV': return "镜像型"     
        elif hm == 'PLD': return "弄臣型"      
        return "殉道型"

    def classify_joker_type_ai(self, data, self_id):
        if self.client is None: return None, None
        transcript = "\n".join([f"{'【自己】' if sp == self_id else '【对方】'}{sp}: {m}" for sp, m in data[-300:]]) 
        prompt = f"""你是一位极其敏锐的情感博弈分析师。阅读聊天记录，判断【自己】在关系中是否处于低位（小丑）。
【严苛判定标尺】：
1. 只要表现出：害怕冷场连续找话题、过度解释、单向提供情绪价值（即使对方有回复），必须判定为小丑。
2. 只有双方完全势均力敌，互相推拉不惧冷场，才能输出：NOT_JOKER
如果是小丑行为，输出：类型名称（殉道型/镜像型/弄臣型/幻恋型） 小丑指数（60-100）
如果不属于，输出：NOT_JOKER\n\n聊天记录：\n{transcript}"""
        try:
            res = self.client.chat.completions.create(model=self.ai_model, messages=[{"role": "user", "content": prompt}], temperature=0.2, max_tokens=20).choices[0].message.content.strip()
            if "NOT_JOKER" in res.upper(): return False, None
            for t in JOKER_TYPES:
                if t in res:
                    m = re.search(r'(\d+)', res)
                    return True, t
            return True, "殉道型"
        except: return None, None

    def ai_guidance(self, data, self_id, is_joker, joker_type):
        if self.client is None: return None
        transcript = "\n".join([f"{'【自己】' if sp == self_id else '【对方】'}{sp}: {m}" for sp, m in data[-500:]]) 
        if is_joker:
            t_desc = JOKER_TYPES.get(joker_type, {}).get('desc', '')
            prompt = f"""你是一位理性客观的情感支持导师。用户被分析为「{joker_type}」小丑（{t_desc}）。\n请从【自己】视角写一段情感疏导（2000字）：安抚情绪、结合聊天内容引用原话、利用心理学分析核心问题、给出实操建议。语气温柔。\n\n聊天记录：\n{transcript}"""
        else:
            prompt = f"""你是一位情感导师。用户展现出极高独立性和边界感（清醒玩家）。\n写一段复盘鼓励（1000字）：夸奖其具体表现（引用原话）、分析权力流动、给出保持框架的进阶建议。语气温柔欣赏。\n\n聊天记录：\n{transcript}"""
        try:
            return self.client.chat.completions.create(model=self.ai_model, messages=[{"role": "system", "content": "你是一位富有同理心且专业的情感导师。"}, {"role": "user", "content": prompt}], temperature=0.7, max_tokens=2000).choices[0].message.content.strip()
        except: return None

    def full_analysis(self, file_path, self_index):
        data = self.parse_chat(file_path)
        if not data: raise ValueError("未能提取到有效聊天内容")
        speakers = self.get_speakers(data)
        if len(speakers) < 2: raise ValueError("必须包含至少2个人的对话！")

        self_id, other_id = speakers[self_index], speakers[1 - self_index]
        stats = self.compute_statistics(data, self_id, other_id)
        
        alg_type = self.classify_joker_type_algorithmic(stats)
        ai_is_joker, ai_type = self.classify_joker_type_ai(data, self_id)

        alg_score = stats['jokernum_alg']
        if ai_is_joker is not None:
            if alg_score >= 60.0: is_joker = True
            elif alg_score >= 45.0: is_joker = ai_is_joker
            else: is_joker = False
        else: is_joker = alg_score > 50.0

        joker_type = ai_type if (is_joker and ai_is_joker and ai_type) else (alg_type if is_joker else None)
        guidance = self.ai_guidance(data, self_id, is_joker, joker_type) if self.client else None

        return {'data': data, 'speakers': speakers, 'self_id': self_id, 'stats': stats, 'is_joker': is_joker, 'joker_type': joker_type, 'guidance': guidance}

# ================== GUI ==================
class JokerDetectorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🃏 Joker Detector - 智能串口联动版")
        self.root.geometry("960x760")
        self.root.configure(bg="#FBF5DD")

        try: pygame.mixer.init(); self.music_enabled = True; self.is_paused = False
        except: self.music_enabled = False; self.is_paused = False

        self.colors = {'bg_cream': '#FBF5DD', 'bg_card': '#FFFFFF', 'accent': '#99AD7A', 'text_primary': '#2D2D2D', 'text_secondary': '#7A7A7A', 'success': '#6BAF7B', 'warning': '#D4A853'}
        self.analyzer = JokerAnalyzer()
        self.result = None
        self.photo_image = None
        
        # 加载本地知识库文件
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
        style.configure('Accent.TButton', font=(CN_FONT, 12, 'bold'), padding=(30, 10))
        style.configure('Small.TButton', font=(CN_FONT, 10), padding=(10, 4))
        style.configure('Cream.TButton', font=(CN_FONT, 11), padding=(20, 8))

    def _build_ui(self):
        header = ttk.Frame(self.root, style='Cream.TFrame')
        header.pack(fill='x', padx=20, pady=(20, 0))
        ttk.Label(header, text="🃏 Joker Detector", style='Title.TLabel').pack(anchor='w')
        ttk.Label(header, text="智能情感分析与 Arduino 硬件联动终端", style='Subtitle.TLabel').pack(anchor='w', pady=(4, 0))

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
        ttk.Button(file_frame, text="📂 浏览选择 Excel...", command=self._select_file).pack(side='left')
        self.file_label = ttk.Label(file_frame, text="未选择文件", style='Card.TLabel', foreground=self.colors['text_secondary'])
        self.file_label.pack(side='left', padx=10)

        speaker_frame = ttk.Frame(parent, style='Card.TFrame')
        speaker_frame.pack(fill='x', padx=15, pady=5)
        ttk.Label(speaker_frame, text="👤 选择你自己", style='Accent.TLabel').pack(anchor='w', pady=(0, 10))
        self.speaker_var = tk.IntVar(value=0)
        self.speaker_btn0 = ttk.Radiobutton(speaker_frame, text="用户 0", variable=self.speaker_var, value=0)
        self.speaker_btn0.pack(side='left', padx=(0, 20))
        self.speaker_btn1 = ttk.Radiobutton(speaker_frame, text="用户 1", variable=self.speaker_var, value=1)
        self.speaker_btn1.pack(side='left')

        self.analyze_btn = ttk.Button(parent, text="🔍 开始分析", command=self._start_analysis, style='Accent.TButton', state='disabled')
        self.analyze_btn.pack(fill='x', padx=15, pady=15)
        self.progress = ttk.Progressbar(parent, mode='indeterminate'); self.progress.pack(fill='x', padx=15)
        
        self.status_label = ttk.Label(parent, text="就绪 —— 请选择文件后开始", style='Card.TLabel', foreground=self.colors['text_secondary'])
        self.status_label.pack(anchor='w', padx=15, pady=(10, 10))

        # ====== 信息区与三个控制按钮 ======
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

    def _build_right_panel(self, parent):
        self.result_frame = ttk.Frame(parent, style='Card.TFrame')
        self.result_frame.pack(fill='both', expand=True)
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
        self.scroll_container.pack(fill='both', expand=True)

    # ====== 弹窗与音乐控制 ======
    def _show_popup(self, title, text):
        if not text:
            messagebox.showinfo("提示", "文本内容未加载，请检查目录下是否存在对应的 txt 文件。")
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

    def _select_file(self):
        fp = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xls *.csv")])
        if fp:
            self.selected_file = fp
            self.file_label.configure(text=os.path.basename(fp))
            try:
                sp = self.analyzer.get_speakers(self.analyzer.parse_chat(fp))
                if len(sp) >= 2:
                    self.speaker_btn0.configure(text=sp[0]); self.speaker_btn1.configure(text=sp[1])
                    self.analyze_btn.configure(state='normal')
            except: pass

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

   
   # ====== 核心：硬编码 COM10 通信 ======
    def send_to_arduino(self, score):
        port = "COM10" 
        try:
            ser = serial.Serial(port, 9600, timeout=1)
            
            # 👇 --- 新增这两行代码（极其重要！）--- 👇
            import time
            time.sleep(2)  # 等待2秒，让 Arduino 重启并准备好接收
            # 👆 ----------------------------------- 👆

            msg = f"{int(score)}\n"
            ser.write(msg.encode('utf-8'))
            ser.close()
            print(f"✅ 成功发送分数 {int(score)} 到 {port}")
        except Exception as e:
            print(f"⚠️ 硬件未联动: 串口 {port} 发送失败。原因：{e}")
    def _start_analysis(self):
        if not hasattr(self, 'selected_file'): return
        self.analyze_btn.configure(state='disabled'); self.progress.start(10)
        self.status_label.configure(text="⏳ 正在深度分析中...", foreground=self.colors['text_primary'])
        def run():
            try:
                self.result = self.analyzer.full_analysis(self.selected_file, self.speaker_var.get())
                self.root.after(0, self._display_result)
            except Exception as e:
                self.root.after(0, lambda: [self.progress.stop(), self.analyze_btn.configure(state='normal'), messagebox.showerror("错误", str(e))])
        threading.Thread(target=run, daemon=True).start()

    def _display_result(self):
        self.progress.stop(); self.analyze_btn.configure(state='normal')
        self.status_label.configure(text="✅ 分析完成！", foreground=self.colors['success'])
        for w in self.result_content.winfo_children(): w.destroy()
        self.canvas.yview_moveto(0)

        r = self.result; is_joker, joker_type, stats = r['is_joker'], r['joker_type'], r['stats']
        
        # 🌟 算完分瞬间，触发 Arduino 物理硬件！
        self.send_to_arduino(stats['jokernum_alg'])

        # --- 模块 1：头部标题与分数 ---
        hf = ttk.Frame(self.result_content, style='Card.TFrame'); hf.pack(fill='x', padx=15, pady=(15, 5))
        if is_joker and joker_type:
            ti = JOKER_TYPES[joker_type]
            tk.Label(hf, text=f"🤡 确诊小丑 —— {joker_type}", fg=ti['color'], bg=self.colors['bg_card'], font=(CN_FONT, 20, 'bold')).pack(anchor='w')
            tk.Label(hf, text=f"算法得分: {stats['jokernum_alg']:.1f}/100", bg=self.colors['bg_card'], fg=self.colors['text_secondary']).pack(anchor='w', pady=(5, 0))
            
            ttk.Separator(self.result_content, orient='horizontal').pack(fill='x', padx=15, pady=8)
            
            # --- 模块 2：小丑配图与描述 ---
            img_desc_frame = ttk.Frame(self.result_content, style='Card.TFrame')
            img_desc_frame.pack(fill='x', padx=15, pady=8)
            
            img_path = os.path.join(PICTURES_DIR, ti['image'])
            img_frame = ttk.Frame(img_desc_frame, style='Card.TFrame')
            img_frame.pack(side='left', padx=(0, 15))
            if os.path.exists(img_path):
                try:
                    pil_img = Image.open(img_path).resize((200, 200), Image.LANCZOS)
                    self.photo_image = ImageTk.PhotoImage(pil_img) 
                    tk.Label(img_frame, image=self.photo_image, bg=self.colors['bg_card']).pack()
                except Exception:
                    tk.Label(img_frame, text=f"[图片加载失败]", bg=self.colors['bg_card'], width=25, height=10).pack()
            
            desc_frame = ttk.Frame(img_desc_frame, style='Card.TFrame')
            desc_frame.pack(side='left', fill='both', expand=True)
            tk.Label(desc_frame, text=ti['desc'], bg=self.colors['bg_card'], font=(CN_FONT, 12), wraplength=420, justify='left').pack(anchor='w', pady=(6, 10))
            tk.Label(desc_frame, text=f"💡 {ti['suggestion']}", bg=self.colors['bg_card'], fg=self.colors['success'], font=(CN_FONT, 11, 'italic'), wraplength=420, justify='left').pack(anchor='w')
            
            # 播放音乐
            if getattr(self, 'music_enabled', False):
                try: 
                    pygame.mixer.music.load(os.path.join(MUSIC_DIR, ti['music']))
                    pygame.mixer.music.play(-1)
                except: pass

        else:
            tk.Label(hf, text="👑 恭喜！你不是小丑", fg=self.colors['success'], bg=self.colors['bg_card'], font=(CN_FONT, 20, 'bold')).pack(anchor='w')
            tk.Label(hf, text=f"算法得分: {stats['jokernum_alg']:.1f}/100", bg=self.colors['bg_card'], fg=self.colors['text_secondary']).pack(anchor='w', pady=(5, 0))
            ttk.Separator(self.result_content, orient='horizontal').pack(fill='x', padx=15, pady=8)
            ttk.Label(self.result_content, text=NOT_JOKER_DESC, style='Card.TLabel', font=(CN_FONT, 12), wraplength=550).pack(anchor='w', padx=15, pady=15)

        ttk.Separator(self.result_content, orient='horizontal').pack(fill='x', padx=15, pady=8)

        # --- 模块 3：基础聊天行为统计网格 ---
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

        # --- 模块 4：AI 报告 ---
        if r.get('guidance'):
            ttk.Separator(self.result_content, orient='horizontal').pack(fill='x', padx=15, pady=8)
            gf = ttk.Frame(self.result_content, style='Card.TFrame'); gf.pack(fill='x', padx=15, pady=5)
            ai_title = "💌 AI 深度情感诊断报告" if is_joker else "👑 AI 高阶博弈复盘"
            ttk.Label(gf, text=ai_title, style='Accent.TLabel').pack(anchor='w', pady=(0, 8))
            ttk.Label(gf, text=r['guidance'], style='TypeDesc.TLabel', wraplength=550).pack(anchor='w')

        # --- 模块 5：导出报告按钮 ---
        b_frame = ttk.Frame(self.result_content, style='Card.TFrame')
        b_frame.pack(fill='x', padx=15, pady=20)
        ttk.Button(b_frame, text="📄 导出简单报告", command=self._export_report, style='Cream.TButton').pack(side='right')

    def run(self): self.root.mainloop()

if __name__ == "__main__":
    app = JokerDetectorGUI()
    app.run()