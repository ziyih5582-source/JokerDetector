# -*- coding: utf-8 -*-
"""
Joker Detector Pro v7：小丑类型判断 + 可视化GUI界面
四种小丑类型：殉道型、镜像型、弄臣型、幻恋型

用法：python final_v4.py
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pandas as pd
import re
import os
import threading
import tkinter.font as tkfont
from PIL import Image, ImageTk
from openai import OpenAI
import httpx

# ================== 中文字体自动检测 ==================
def _detect_cn_font():
    """按优先级探测可用的中文字体"""
    candidates = [
        'Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'WenQuanYi Zen Hei',
        'AR PL UKai CN', 'AR PL UMing CN',
        'song ti', 'fangsong ti',
        'Microsoft YaHei', 'PingFang SC', 'Heiti SC', 'SimHei',
    ]
    r = tk.Tk()
    r.withdraw()
    available = set(tkfont.families())
    # 对每个候选字体，无论是否在 families() 中都尝试创建
    for name in candidates:
        try:
            f = tkfont.Font(family=name, size=12)
            w = f.measure('你好世界小丑检测')
            if w > 20:  # 能渲染中文
                r.destroy()
                return name
        except Exception:
            continue
    r.destroy()
    return 'TkDefaultFont'

CN_FONT = _detect_cn_font()
print(f"[字体] 检测到中文字体：{CN_FONT}")

# ================== AI 配置 ==================
API_KEY = os.getenv("", "")
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

# ================== 小丑类型定义 ==================
JOKER_TYPES = {
    "殉道型": {
        "desc": "无条件付出，不期待对方的回报，认为付出本身就是自己的价值所在。",
        "suggestion": "你的价值不取决于你付出了多少。学会在关系中设立边界，真正的爱是双向流动的。",
        "image": "殉道型.jpg",
        "color": "#C46868",
        "keywords": [
            "只要你", "不用管我", "我没事", "为你", "值得", "付出", "应该的",
            "你开心", "我就", "牺牲", "愿意等", "多久都", "没关系", "我不重要",
            "你先", "随便我", "无所谓我", "我怎样都行", "为了你"
        ]
    },
    "镜像型": {
        "desc": "失去自我的感受，只考虑对方的情感和需求，变成了对方的镜子。",
        "suggestion": "你不是别人的影子。重新找回自己的喜好和观点，真实的你才最有吸引力。",
        "image": "镜像型.jpg",
        "color": "#6B8DB5",
        "keywords": [
            "我也是", "都行", "随便", "听你的", "你喜欢", "和你一样",
            "嗯嗯", "对的", "你说得对", "我也觉得", "看你了", "你觉得呢",
            "我都可以", "无所谓", "你定", "我跟着你"
        ]
    },
    "弄臣型": {
        "desc": "靠自我贬低和自我嘲弄来渴求让对方开心，用笑话掩饰内心的不安全感。",
        "suggestion": "幽默是魅力，但自贬不是。你不需要贬低自己来让别人喜欢你——你本来就值得被喜欢。",
        "image": "弄臣型.jpg",
        "color": "#D4A853",
        "keywords": [
            "我不配", "我这种人", "搞笑", "小丑", "废物", "菜鸡",
            "垃圾", "我是个", "我太菜", "别笑我", "丢人", "哈哈哈我",
            "我真服了", "笑死", "救命", "我死了", "呜呜", "我错了",
            "原谅我", "对不起对不起", "哈哈"
        ]
    },
    "幻恋型": {
        "desc": "在大脑中不断幻想和对方的暧昧场景，而在现实中唯唯诺诺。",
        "suggestion": "脑海里的剧本不等于现实。勇敢地走出幻想，哪怕只是多说一句话，也比一万次内心戏更有意义。",
        "image": "幻恋型.jpg",
        "color": "#8B6FAF",
        "keywords": [
            "你是不是", "我在想", "如果", "以后", "会不会", "可能",
            "感觉", "好像", "也许", "万一", "要是", "说不定",
            "有没有可能", "该不会", "我猜", "我总觉得", "你知道吗",
            "我在幻想", "做梦", "梦到"
        ]
    }
}

NOT_JOKER_DESC = "你的聊天模式较为健康，没有明显的小丑行为特征。继续保持！"

# ================== 核心分析引擎 ==================
class JokerAnalyzer:
    def __init__(self):
        self.client = None
        self.ai_model = MODEL
        self._init_ai()

    def _init_ai(self):
        """初始化 AI 客户端"""
        if not API_KEY or API_KEY.startswith("sk-xxx"):
            self.client = None
            return
        try:
            self.client = OpenAI(
                api_key=API_KEY,
                base_url=BASE_URL,
                http_client=httpx.Client(trust_env=False)
            )
        except Exception:
            self.client = None

    def parse_chat(self, file_path):
        """解析 Excel 聊天记录"""
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
        return data

    def get_speakers(self, data):
        """获取对话双方"""
        unique = []
        for speaker, _ in data:
            if speaker not in unique:
                unique.append(speaker)
        return unique

    def compute_statistics(self, data, self_id, other_id):
        """计算所有统计数据"""
        stats = {
            'self_msg_count': 0, 'other_msg_count': 0,
            'self_sticker_count': 0, 'other_sticker_count': 0,
            'self_pic_count': 0, 'other_pic_count': 0,
            'self_total_chars': 0, 'other_total_chars': 0,
            'max_self_cont': 0, 'max_other_cont': 0,
            'self_voice_call': 0, 'other_voice_call': 0,
            'has_voice_or_call': False,
            'self_keyword_matches': {t: 0 for t in JOKER_TYPES},
            'self_question_count': 0,
            'self_exclamation_count': 0,
            'self_laugh_count': 0,
        }

        current_streak = 0
        current_speaker = None

        for speaker, msg in data:
            pics = 0
            stickers = 0
            is_voice_call = False

            if '[图片]' in msg:
                pics = 1
            elif '[语音]' in msg or '语音消息' in msg:
                stats['has_voice_or_call'] = True
                is_voice_call = True
            elif '通话' in msg:
                stats['has_voice_or_call'] = True
                is_voice_call = True
            elif re.search(r'\[.+?\]', msg):
                stickers = 1

            chars = len(msg)

            if speaker == self_id:
                stats['self_msg_count'] += 1
                stats['self_sticker_count'] += stickers
                stats['self_pic_count'] += pics
                stats['self_total_chars'] += chars
                if is_voice_call:
                    stats['self_voice_call'] += 1
                # 关键词检测
                for jtype, info in JOKER_TYPES.items():
                    for kw in info['keywords']:
                        if kw in msg:
                            stats['self_keyword_matches'][jtype] += 1
                # 问号计数（用于幻恋型检测）
                stats['self_question_count'] += msg.count('？') + msg.count('?')
                stats['self_exclamation_count'] += msg.count('！') + msg.count('!')
                stats['self_laugh_count'] += msg.count('哈')
            elif speaker == other_id:
                stats['other_msg_count'] += 1
                stats['other_sticker_count'] += stickers
                stats['other_pic_count'] += pics
                stats['other_total_chars'] += chars
                if is_voice_call:
                    stats['other_voice_call'] += 1

            if speaker == current_speaker:
                current_streak += 1
            else:
                current_streak = 1
                current_speaker = speaker

            if speaker == self_id:
                stats['max_self_cont'] = max(stats['max_self_cont'], current_streak)
            elif speaker == other_id:
                stats['max_other_cont'] = max(stats['max_other_cont'], current_streak)

        # 计算比率
        stats['r1'] = stats['self_msg_count'] / stats['other_msg_count'] if stats['other_msg_count'] > 0 else 0
        stats['r2'] = stats['self_sticker_count'] / stats['other_sticker_count'] if stats['other_sticker_count'] > 0 else 0
        stats['r3'] = stats['max_self_cont'] / stats['max_other_cont'] if stats['max_other_cont'] > 0 else 0
        stats['r4'] = stats['self_total_chars'] / stats['other_total_chars'] if stats['other_total_chars'] > 0 else 0
        stats['r5'] = stats['self_pic_count'] / stats['other_pic_count'] if stats['other_pic_count'] > 0 else 0

        stats['jokernum_alg'] = (stats['r1'] + stats['r2'] + stats['r3'] + stats['r4'] + stats['r5']) / 5
        if stats['has_voice_or_call']:
            stats['jokernum_alg'] *= 0.8

        stats['self_avg_chars'] = stats['self_total_chars'] / stats['self_msg_count'] if stats['self_msg_count'] > 0 else 0
        stats['other_avg_chars'] = stats['other_total_chars'] / stats['other_msg_count'] if stats['other_msg_count'] > 0 else 0
        stats['self_media_rate'] = (stats['self_sticker_count'] + stats['self_pic_count']) / stats['self_msg_count'] if stats['self_msg_count'] > 0 else 0
        stats['other_media_rate'] = (stats['other_sticker_count'] + stats['other_pic_count']) / stats['other_msg_count'] if stats['other_msg_count'] > 0 else 0

        return stats

    def classify_joker_type_algorithmic(self, stats, data, self_id):
        """
        基于算法判断小丑类型。
        返回 (is_joker, joker_type, confidence)

        策略：关键词命中是主信号，行为模式是辅信号。
        关键词信号强 → 直接按关键词密度判定；
        关键词信号弱 → 根据行为指标兜底。
        """
        r1, r2 = stats['r1'], stats['r2']
        keyword_counts = stats['self_keyword_matches']
        total_self_msgs = max(stats['self_msg_count'], 1)

        # 原始 jokernum 判断是否是"小丑"
        is_joker = stats['jokernum_alg'] > 0.35
        if not is_joker:
            return False, None, 0

        # 各类型关键词密度
        densities = {t: keyword_counts[t] / total_self_msgs for t in JOKER_TYPES}
        total_kw = sum(keyword_counts.values())

        # --- 情况 A：关键词信号明显 → 关键词主导分类 ---
        if total_kw >= 2:
            ranked = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
            best_type = ranked[0][0]
            best_kw = ranked[0][1]
            if best_kw >= 2:
                confidence = min(0.5 + best_kw / max(total_kw, 1) * 0.4, 0.9)
                return True, best_type, round(confidence, 2)

        # --- 情况 B：关键词信号弱 → 行为模式兜底 ---
        # 殉道型：消息/字数投入严重失衡（r1 或 r4 显著 > 1）
        if stats['r1'] > 1.5 or stats['r4'] > 1.5:
            return True, "殉道型", 0.55

        # 弄臣型：笑声频繁 + 自贬
        if stats['self_laugh_count'] >= 2 or r2 > 1.5:
            return True, "弄臣型", 0.45

        # 幻恋型：有幻想关键词 + 不敢主动（消息少）或问号多
        if densities["幻恋型"] > 0 or stats['self_question_count'] >= 2:
            return True, "幻恋型", 0.45

        # 镜像型：有附和关键词
        if densities["镜像型"] > 0:
            return True, "镜像型", 0.40

        # 殉道型：次强投入失衡
        if r1 > 1.2:
            return True, "殉道型", 0.40

        # 完全无特征 → 弱镜像型兜底
        return True, "镜像型", 0.35

    def classify_joker_type_ai(self, data, self_id, stats):
        """使用 AI 判断小丑类型及小丑指数（0-100）"""
        if self.client is None:
            return None, None, None

        transcript_lines = []
        for speaker, msg in data:
            tag = "【自己】" if speaker == self_id else "【对方】"
            transcript_lines.append(f"{tag}{speaker}: {msg}")
        transcript = "\n".join(transcript_lines)

        prompt = f"""你是一位情感关系分析师。请阅读以下双人聊天记录，其中标注了【自己】和【对方】。

首先判断【自己】是否表现出小丑行为（卑微、单向付出、过度讨好、缺乏自我边界等）。

如果【自己】不是小丑，请输出：NOT_JOKER
如果【自己】是小丑，请同时给出：
1. 小丑类型（四选一）：
   - 殉道型：无条件付出，不期待对方的回报，只知道付出，认为这是自己的价值
   - 镜像型：失去自我的感受，只考虑对方的情感和需求，变成对方的镜子
   - 弄臣型：靠自我贬低和自我嘲弄渴求让对方开心的小丑
   - 幻恋型：在大脑中不断幻想自己和对方的暧昧场景，而在现实中唯唯诺诺
2. 小丑指数（0-100整数，越高越严重）

请严格按以下格式输出，不要其他文字：
类型名称 指数数字

示例输出：
殉道型 78
NOT_JOKER

聊天记录：
{transcript}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {"role": "system", "content": "你只输出\"类型 数字\"（如\"殉道型 78\"）或\"NOT_JOKER\"，不要其他文字。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=20
            )
            result = response.choices[0].message.content.strip()
            if "NOT_JOKER" in result.upper():
                return False, None, None
            # 解析 "殉道型 78" 格式
            for t in JOKER_TYPES:
                if t in result:
                    # 尝试提取分数
                    score_match = re.search(r'(\d+)', result)
                    ai_score = int(score_match.group(1)) if score_match else None
                    if ai_score is not None:
                        ai_score = max(0, min(100, ai_score))
                    return True, t, ai_score
            # fallback：有类型但没分数
            return True, "殉道型", 50
        except Exception:
            return None, None, None

    def ai_guidance(self, data, self_id, joker_type):
        """AI 情感疏导"""
        if self.client is None:
            return None

        transcript_lines = []
        for speaker, msg in data:
            tag = "【自己】" if speaker == self_id else "【对方】"
            transcript_lines.append(f"{tag}{speaker}: {msg}")
        transcript = "\n".join(transcript_lines)

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
{transcript}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {"role": "system", "content": "你是富有同理心的情感导师，输出温柔具体的疏导文本，2000字左右。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4096
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return None

    def full_analysis(self, file_path, self_index):
        """
        完整分析流程。
        返回 dict 包含所有结果。
        """
        data = self.parse_chat(file_path)
        if not data:
            raise ValueError("未检测到任何聊天记录")

        speakers = self.get_speakers(data)
        if len(speakers) != 2:
            raise ValueError(f"检测到 {len(speakers)} 个对话方，需要恰好 2 个")

        self_id = speakers[self_index]
        other_id = speakers[1 - self_index]

        # 计算统计
        stats = self.compute_statistics(data, self_id, other_id)

        # 算法判断：是否是小丑 + 类型（灵敏度由算法阈值控制）
        is_joker_alg, joker_type_alg, confidence_alg = self.classify_joker_type_algorithmic(stats, data, self_id)

        # AI 判断类型 + 小丑指数（AI 用于类型细分和打分）
        is_joker_ai, joker_type_ai, ai_score = self.classify_joker_type_ai(data, self_id, stats)

        # 综合判断：算法决定"是不是小丑"（灵敏度高），AI 提供类型和分数
        is_joker = is_joker_alg
        ai_available = is_joker_ai is not None

        if ai_available and is_joker_ai and joker_type_ai:
            # AI 也认为是小丑 → AI 类型优先
            joker_type = joker_type_ai
        elif is_joker:
            # 算法认为是小丑但 AI 不认为 → 用算法类型
            joker_type = joker_type_alg
        else:
            joker_type = None
            ai_score = None

        # AI 情感疏导
        guidance = None
        if is_joker and joker_type and self.client:
            guidance = self.ai_guidance(data, self_id, joker_type)

        return {
            'data': data,
            'speakers': speakers,
            'self_id': self_id,
            'other_id': other_id,
            'self_index': self_index,
            'stats': stats,
            'is_joker': is_joker,
            'joker_type': joker_type,
            'joker_type_alg': (is_joker_alg, joker_type_alg, confidence_alg),
            'joker_type_ai': (is_joker_ai, joker_type_ai),
            'ai_score': ai_score,
            'ai_available': ai_available,
            'guidance': guidance,
        }


# ================== GUI ==================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PICTURES_DIR = os.path.join(BASE_DIR, "pictures")

def _load_text(filename):
    """Load text file content, return empty string if not found"""
    path = os.path.join(BASE_DIR, filename)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

class JokerDetectorGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🃏 Joker Detector - 小丑检测器")
        self.root.geometry("960x760")
        self.root.minsize(800, 600)
        self.root.configure(bg="#FBF5DD")

        # Warm light color palette
        self.colors = {
            'bg_cream': '#FBF5DD',       # Main background (warm cream)
            'bg_card': '#FFFFFF',         # Card background (white)
            'bg_alt': '#F5F5F5',          # Alternate background (light gray)
            'accent': '#99AD7A',          # Primary accent (sage green)
            'accent_dark': '#7D9460',     # Darker accent
            'text_primary': '#2D2D2D',    # Primary text (dark gray)
            'text_secondary': '#7A7A7A',  # Secondary text
            'text_muted': '#AAAAAA',      # Muted text
            'success': '#6BAF7B',         # Success green
            'warning': '#D4A853',         # Warning amber
            'danger': '#C46868',          # Error red
            'info': '#6B8DB5',            # Info blue
            'border': '#E8E0D0',          # Subtle border
        }

        self.analyzer = JokerAnalyzer()
        self.result = None
        self.photo_image = None  # 保持引用防止GC

        # Load text resources
        self.text_theory = _load_text("theroy.txt")
        self.text_emotion = _load_text("somewords.txt")

        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        # Configure styles for warm light theme
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

        style.configure('Cream.Horizontal.TScale', background=self.colors['bg_cream'])

    def _build_ui(self):
        # --- 顶部标题栏 ---
        header = ttk.Frame(self.root, style='Cream.TFrame')
        header.pack(fill='x', padx=20, pady=(20, 0))

        ttk.Label(header, text="🃏 Joker Detector", style='Title.TLabel').pack(anchor='w')
        ttk.Label(header, text="输入聊天记录，检测你的小丑指数 & 小丑类型", style='Subtitle.TLabel').pack(anchor='w', pady=(4, 0))

        # --- 主内容区域 ---
        main = ttk.Frame(self.root, style='Cream.TFrame')
        main.pack(fill='both', expand=True, padx=20, pady=15)

        # 左侧 - 控制面板
        left = ttk.Frame(main, style='Card.TFrame')
        left.pack(side='left', fill='both', expand=True, padx=(0, 8))

        self._build_left_panel(left)

        # 右侧 - 结果显示
        right = ttk.Frame(main, style='Cream.TFrame')
        right.pack(side='right', fill='both', expand=True, padx=(8, 0))
        self._build_right_panel(right)

    def _build_left_panel(self, parent):
        # 文件选择区域
        file_frame = ttk.Frame(parent, style='Card.TFrame')
        file_frame.pack(fill='x', padx=15, pady=(15, 10))

        ttk.Label(file_frame, text="📂 选择聊天记录文件", style='Accent.TLabel').pack(anchor='w', pady=(0, 10))

        btn_frame = ttk.Frame(file_frame, style='Card.TFrame')
        btn_frame.pack(fill='x')

        self.file_btn = ttk.Button(btn_frame, text="浏览选择 Excel 文件...", command=self._select_file, style='Cream.TButton')
        self.file_btn.pack(side='left', padx=(0, 10))

        self.file_label = ttk.Label(btn_frame, text="未选择文件", style='Card.TLabel', foreground=self.colors['text_secondary'])
        self.file_label.pack(side='left')

        # 分隔线
        ttk.Separator(parent, orient='horizontal').pack(fill='x', padx=15, pady=10)

        # 对话方选择
        speaker_frame = ttk.Frame(parent, style='Card.TFrame')
        speaker_frame.pack(fill='x', padx=15, pady=5)

        ttk.Label(speaker_frame, text="👤 选择你自己", style='Accent.TLabel').pack(anchor='w', pady=(0, 10))

        self.speaker_var = tk.IntVar(value=0)

        # 用户0 和 用户1 的按钮框架
        self.speaker_btn_frame = ttk.Frame(speaker_frame, style='Card.TFrame')
        self.speaker_btn_frame.pack(fill='x', pady=5)

        self.speaker_btn0 = ttk.Radiobutton(
            self.speaker_btn_frame, text="用户 0", variable=self.speaker_var, value=0,
            style='Cream.TRadiobutton'
        )
        self.speaker_btn0.pack(side='left', padx=(0, 20))

        self.speaker_btn1 = ttk.Radiobutton(
            self.speaker_btn_frame, text="用户 1", variable=self.speaker_var, value=1,
            style='Cream.TRadiobutton'
        )
        self.speaker_btn1.pack(side='left')

        # 自定义 radiobutton 外观
        for rb in [self.speaker_btn0, self.speaker_btn1]:
            rb.configure(style='Cream.TRadiobutton')

        # 分析按钮
        self.analyze_btn = ttk.Button(parent, text="🔍 开始分析",
                                       command=self._start_analysis,
                                       style='Accent.TButton',
                                       state='disabled')
        self.analyze_btn.pack(fill='x', padx=15, pady=15)

        # 进度条
        self.progress = ttk.Progressbar(parent, mode='indeterminate', style='Cream.Horizontal.TProgressbar')
        self.progress.pack(fill='x', padx=15, pady=(0, 5))

        # 状态标签
        self.status_label = ttk.Label(parent, text="就绪 —— 请选择文件后开始", style='Card.TLabel',
                                       foreground=self.colors['text_secondary'])
        self.status_label.pack(anchor='w', padx=15, pady=(0, 10))

        # 小丑类型说明卡片
        info_frame = ttk.Frame(parent, style='Card.TFrame')
        info_frame.pack(fill='both', expand=True, padx=15, pady=(5, 15))

        ttk.Label(info_frame, text="🎭 四种小丑类型", style='Accent.TLabel').pack(anchor='w', pady=(10, 5))

        type_info_text = (
            "🔴 殉道型：无条件付出，不期待回报\n"
            "🔵 镜像型：失去自我，变成对方的镜子\n"
            "🟡 弄臣型：自我贬低，用笑话掩饰不安\n"
            "🟣 幻恋型：脑中幻想千遍，现实唯唯诺诺"
        )
        ttk.Label(info_frame, text=type_info_text, style='Card.TLabel',
                  foreground=self.colors['text_secondary'], font=(CN_FONT, 10)).pack(anchor='w', pady=(0, 10))

        # AI 状态
        ai_status = "✅ AI 已连接" if self.analyzer.client else "⚠️ AI 未连接（仅算法模式）"
        ai_color = self.colors['success'] if self.analyzer.client else self.colors['warning']
        ttk.Label(info_frame, text=ai_status, style='Card.TLabel',
                  foreground=ai_color, font=(CN_FONT, 10)).pack(anchor='w', pady=(5, 10))

        # 知识库按钮
        ttk.Separator(info_frame, orient='horizontal').pack(fill='x', pady=(5, 0))
        ttk.Label(info_frame, text="📖 知识库", style='Accent.TLabel').pack(anchor='w', pady=(10, 5))
        btn_frame = ttk.Frame(info_frame, style='Card.TFrame')
        btn_frame.pack(fill='x', pady=(0, 5))
        ttk.Button(btn_frame, text="📚 恋爱理论",
                   command=lambda: self._show_popup("📚 恋爱心理学理论", self.text_theory),
                   style='Small.TButton').pack(side='left', padx=(0, 8))
        ttk.Button(btn_frame, text="💬 情感话语",
                   command=lambda: self._show_popup("💬 情感话语", self.text_emotion),
                   style='Small.TButton').pack(side='left')

    def _show_popup(self, title, text):
        """Show a popup window with the given text"""
        if not text:
            messagebox.showinfo("提示", "文本内容未加载，请检查文件是否存在。")
            return
        popup = tk.Toplevel(self.root)
        popup.title(title)
        popup.geometry("600x500")
        popup.minsize(400, 300)
        popup.configure(bg=self.colors['bg_card'])
        popup.transient(self.root)

        st = scrolledtext.ScrolledText(popup, wrap=tk.WORD, font=(CN_FONT, 11),
                                        bg=self.colors['bg_card'],
                                        fg=self.colors['text_primary'],
                                        relief='flat', borderwidth=0,
                                        padx=20, pady=15)
        st.pack(fill='both', expand=True)
        st.insert('1.0', text)
        st.configure(state='disabled')

    def _build_right_panel(self, parent):
        # --- 可滚动的右侧面板：Canvas + Scrollbar ---
        self.right_canvas = tk.Canvas(parent, bg=self.colors['bg_card'],
                                       highlightthickness=0, relief='flat')
        self.right_scrollbar = ttk.Scrollbar(parent, orient='vertical',
                                              command=self.right_canvas.yview)
        self.right_canvas.configure(yscrollcommand=self.right_scrollbar.set)

        self.right_scrollbar.pack(side='right', fill='y')
        self.right_canvas.pack(side='left', fill='both', expand=True)

        # 结果区域（作为 Canvas 内部窗口，内容从这里开始）
        self.result_frame = ttk.Frame(self.right_canvas, style='Card.TFrame')
        self._canvas_window_id = self.right_canvas.create_window(
            (0, 0), window=self.result_frame, anchor='nw')

        # --- 占位欢迎界面 ---
        self.placeholder = ttk.Frame(self.result_frame, style='Card.TFrame')
        self.placeholder.pack(fill='x', padx=20, pady=20)

        ttk.Label(self.placeholder, text="🃏", font=(CN_FONT, 64),
                  background=self.colors['bg_card']).pack(pady=(60, 15))
        ttk.Label(self.placeholder, text="等待分析...", style='TypeTitle.TLabel').pack(pady=5)
        ttk.Label(self.placeholder,
                  text="选择你的聊天记录文件\n选择你在对话中的身份\n然后点击「开始分析」",
                  style='TypeDesc.TLabel', font=(CN_FONT, 11)).pack(pady=10)

        # 结果内容（初始隐藏）
        self.result_content = ttk.Frame(self.result_frame, style='Card.TFrame')

        # --- 绑定 Canvas 滚动事件 ---
        self.right_canvas.bind('<Configure>', self._on_right_canvas_configure)
        self.result_frame.bind('<Configure>', self._on_result_frame_configure)
        self.right_canvas.bind('<Enter>', self._bind_mousewheel)
        self.right_canvas.bind('<Leave>', self._unbind_mousewheel)

    # --------------- Canvas 滚动支持 ---------------
    def _on_right_canvas_configure(self, event):
        """Canvas 大小变化时：让内部 frame 宽度与 Canvas 同步"""
        self.right_canvas.itemconfig(self._canvas_window_id, width=event.width)

    def _on_result_frame_configure(self, event):
        """内部 frame 大小变化时：更新 Canvas 的滚动区域"""
        self.right_canvas.configure(scrollregion=self.right_canvas.bbox('all'))

    def _bind_mousewheel(self, event):
        """鼠标进入 Canvas 时绑定滚轮事件"""
        # Linux: Button-4 / Button-5
        self.right_canvas.bind_all('<Button-4>', self._on_mousewheel)
        self.right_canvas.bind_all('<Button-5>', self._on_mousewheel)
        # Windows / macOS: MouseWheel
        self.right_canvas.bind_all('<MouseWheel>', self._on_mousewheel)

    def _unbind_mousewheel(self, event):
        """鼠标离开 Canvas 时解绑滚轮事件"""
        self.right_canvas.unbind_all('<Button-4>')
        self.right_canvas.unbind_all('<Button-5>')
        self.right_canvas.unbind_all('<MouseWheel>')

    def _on_mousewheel(self, event):
        """处理鼠标滚轮事件（跨平台）"""
        if event.num == 4:
            self.right_canvas.yview_scroll(-1, 'units')
        elif event.num == 5:
            self.right_canvas.yview_scroll(1, 'units')
        else:
            # MouseWheel: delta 正=上滚，负=下滚（//120 标准化）
            self.right_canvas.yview_scroll(-1 * (event.delta // 120), 'units')

    # --------------------------------------------------

    def _select_file(self):
        """选择文件回调"""
        file_path = filedialog.askopenfilename(
            title="选择聊天记录文件",
            filetypes=[("Excel 文件", "*.xlsx *.xls"), ("所有文件", "*.*")]
        )
        if file_path:
            self.selected_file = file_path
            self.file_label.configure(text=os.path.basename(file_path))

            # 快速解析以显示说话人
            try:
                data = self.analyzer.parse_chat(file_path)
                speakers = self.analyzer.get_speakers(data)
                if len(speakers) == 2:
                    self.speaker_btn0.configure(text=speakers[0])
                    self.speaker_btn1.configure(text=speakers[1])
                    self.analyze_btn.configure(state='normal')
                    self.status_label.configure(text=f"✅ 已加载文件，检测到 {len(data)} 条消息", foreground=self.colors['success'])
                else:
                    self.analyze_btn.configure(state='disabled')
                    self.status_label.configure(text=f"❌ 检测到 {len(speakers)} 个对话方，需要恰好 2 个", foreground=self.colors['danger'])
            except Exception as e:
                self.analyze_btn.configure(state='disabled')
                self.status_label.configure(text=f"❌ 文件解析失败：{str(e)[:50]}", foreground=self.colors['danger'])

    def _start_analysis(self):
        """开始分析"""
        if not hasattr(self, 'selected_file'):
            return

        self.analyze_btn.configure(state='disabled', text="⏳ 分析中...")
        self.progress.start(10)
        self.status_label.configure(text="正在分析聊天记录...", foreground=self.colors['text_secondary'])

        def run():
            try:
                result = self.analyzer.full_analysis(self.selected_file, self.speaker_var.get())
                self.result = result
                self.root.after(0, self._display_result)
            except Exception as e:
                self.root.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _on_error(self, msg):
        self.progress.stop()
        self.analyze_btn.configure(state='normal', text="🔍 开始分析")
        self.status_label.configure(text=f"❌ 错误：{msg[:80]}", foreground=self.colors['danger'])
        messagebox.showerror("分析失败", msg)

    def _display_result(self):
        self.progress.stop()
        self.analyze_btn.configure(state='normal', text="🔍 重新分析")

        # 清除占位和旧结果
        self.placeholder.pack_forget()
        for widget in self.result_content.winfo_children():
            widget.destroy()
        self.result_content.pack(fill='x')

        r = self.result
        is_joker = r['is_joker']
        joker_type = r['joker_type']
        stats = r['stats']

        # ===== 判断结果头部 =====
        header_frame = ttk.Frame(self.result_content, style='Card.TFrame')
        header_frame.pack(fill='x', padx=15, pady=(15, 5))

        if is_joker and joker_type:
            type_info = JOKER_TYPES[joker_type]
            verdict = f"🤡 确诊小丑 —— {joker_type}"
            verdict_color = type_info['color']
        else:
            verdict = "✅ 恭喜！你不是小丑"
            verdict_color = self.colors['success']

        verdict_label = tk.Label(header_frame, text=verdict, fg=verdict_color,
                                  bg=self.colors['bg_card'], font=(CN_FONT, 20, 'bold'))
        verdict_label.pack(anchor='w')

        # 综合评分
        jn = stats['jokernum_alg']
        ai_score = r.get('ai_score')
        score_text = f"算法指数：{jn:.2f}"
        if ai_score is not None:
            score_text += f"  |  🤖 AI 小丑指数：{ai_score}/100"
        if is_joker and joker_type:
            ai_hint = ""
            if r.get('ai_available') and r['joker_type_ai']:
                ai_t = r['joker_type_ai'][1]
                ai_hint = f"  (AI 判定：{ai_t if r['joker_type_ai'][0] else '非小丑'})"
            score_text += f"\n类型：{joker_type}{ai_hint}"
        ttk.Label(header_frame, text=score_text, style='Card.TLabel',
                  foreground=self.colors['text_secondary'], font=(CN_FONT, 11)).pack(anchor='w', pady=(5, 0))

        ttk.Separator(self.result_content, orient='horizontal').pack(fill='x', padx=15, pady=8)

        # ===== 如果是小丑，展示图片和详细描述 =====
        if is_joker and joker_type:
            type_info = JOKER_TYPES[joker_type]
            img_desc_frame = ttk.Frame(self.result_content, style='Card.TFrame')
            img_desc_frame.pack(fill='x', padx=15, pady=8)

            # 图片展示
            img_path = os.path.join(PICTURES_DIR, type_info['image'])
            img_frame = ttk.Frame(img_desc_frame, style='Card.TFrame')
            img_frame.pack(side='left', padx=(0, 15))

            if os.path.exists(img_path):
                try:
                    pil_img = Image.open(img_path)
                    pil_img = pil_img.resize((200, 200), Image.LANCZOS)
                    self.photo_image = ImageTk.PhotoImage(pil_img)
                    img_label = tk.Label(img_frame, image=self.photo_image, bg=self.colors['bg_card'])
                    img_label.pack()
                except Exception as e:
                    err_label = tk.Label(img_frame, text=f"[图片加载失败]\n{type_info['image']}",
                                         bg=self.colors['bg_card'], fg=self.colors['text_secondary'],
                                         font=(CN_FONT, 10), width=25, height=10)
                    err_label.pack()
            else:
                missing = tk.Label(img_frame, text=f"[图片不存在]\n{type_info['image']}",
                                   bg=self.colors['bg_card'], fg=self.colors['text_secondary'],
                                   font=(CN_FONT, 10), width=25, height=10)
                missing.pack()

            # 类型描述
            desc_frame = ttk.Frame(img_desc_frame, style='Card.TFrame')
            desc_frame.pack(side='left', fill='both', expand=True)

            type_label = tk.Label(desc_frame, text=f"「{joker_type}」", fg=type_info['color'],
                                  bg=self.colors['bg_card'], font=(CN_FONT, 16, 'bold'))
            type_label.pack(anchor='w')

            type_desc_label = tk.Label(desc_frame, text=type_info['desc'],
                                       bg=self.colors['bg_card'], fg=self.colors['text_primary'],
                                       font=(CN_FONT, 12), wraplength=420, justify='left')
            type_desc_label.pack(anchor='w', pady=(6, 10))

            suggestion_label = tk.Label(desc_frame, text=f"💡 {type_info['suggestion']}",
                                        bg=self.colors['bg_card'], fg=self.colors['success'],
                                        font=(CN_FONT, 11, 'italic'), wraplength=420, justify='left')
            suggestion_label.pack(anchor='w')
        else:
            # 不是小丑的展示
            not_joker_frame = ttk.Frame(self.result_content, style='Card.TFrame')
            not_joker_frame.pack(fill='x', padx=15, pady=15)
            ttk.Label(not_joker_frame, text=NOT_JOKER_DESC, style='Card.TLabel',
                      font=(CN_FONT, 12), wraplength=500).pack(anchor='w')

        ttk.Separator(self.result_content, orient='horizontal').pack(fill='x', padx=15, pady=8)

        # ===== 统计数据 =====
        stats_frame = ttk.Frame(self.result_content, style='Card.TFrame')
        stats_frame.pack(fill='x', padx=15, pady=5)

        ttk.Label(stats_frame, text="📊 聊天统计", style='Accent.TLabel').pack(anchor='w', pady=(0, 8))

        stat_grid = ttk.Frame(stats_frame, style='Card.TFrame')
        stat_grid.pack(fill='x')

        left_stats = [
            f"消息数：自己 {stats['self_msg_count']} 条 / 对方 {stats['other_msg_count']} 条",
            f"表情包：自己 {stats['self_sticker_count']} 个 / 对方 {stats['other_sticker_count']} 个",
            f"图片数：自己 {stats['self_pic_count']} 张 / 对方 {stats['other_pic_count']} 张",
            f"总字数：自己 {stats['self_total_chars']} 字 / 对方 {stats['other_total_chars']} 字",
        ]

        right_stats = [
            f"最大连续：自己 {stats['max_self_cont']} 条 / 对方 {stats['max_other_cont']} 条",
            f"语音/通话：自己 {stats['self_voice_call']} 次 / 对方 {stats['other_voice_call']} 次",
            f"平均字数：自己 {stats['self_avg_chars']:.1f} 字 / 对方 {stats['other_avg_chars']:.1f} 字",
        ]

        # 各项比率
        ratio_items = [
            (f"消息比：{stats['r1']:.2f}", stats['r1']),
            (f"表情比：{stats['r2']:.2f}", stats['r2']),
            (f"连续比：{stats['r3']:.2f}", stats['r3']),
            (f"字数比：{stats['r4']:.2f}", stats['r4']),
            (f"图片比：{stats['r5']:.2f}", stats['r5']),
        ]

        for i, (text, val) in enumerate(ratio_items):
            color = self.colors['danger'] if val > 1.5 else (self.colors['success'] if val < 0.67 else self.colors['text_secondary'])
            ttk.Label(stat_grid, text=text, style='Stat.TLabel',
                      foreground=color, font=(CN_FONT, 10)).grid(row=i, column=0, sticky='w', pady=2, padx=(0, 20))
            if i < len(right_stats):
                ttk.Label(stat_grid, text=right_stats[i], style='Stat.TLabel',
                          foreground=self.colors['text_secondary'], font=(CN_FONT, 10)).grid(row=i, column=1, sticky='w', pady=2)

        # 关键词命中
        if is_joker and joker_type and stats['self_keyword_matches'].get(joker_type, 0) > 0:
            kw_count = stats['self_keyword_matches'][joker_type]
            ttk.Label(stats_frame, text=f"🔑 类型关键词命中：{kw_count} 次",
                      style='Stat.TLabel', foreground=self.colors['text_secondary']).pack(anchor='w', pady=(5, 0))

        ttk.Separator(self.result_content, orient='horizontal').pack(fill='x', padx=15, pady=8)

        # ===== AI 情感疏导 =====
        if r.get('guidance'):
            guidance_frame = ttk.Frame(self.result_content, style='Card.TFrame')
            guidance_frame.pack(fill='x', padx=15, pady=5)

            ttk.Label(guidance_frame, text="💌 AI 情感疏导", style='Accent.TLabel').pack(anchor='w', pady=(0, 8))
            ttk.Label(guidance_frame, text=r['guidance'], style='TypeDesc.TLabel',
                      font=(CN_FONT, 11), wraplength=550).pack(anchor='w')

        # 底部间距
        ttk.Frame(self.result_content, style='Card.TFrame', height=10).pack()

        self.status_label.configure(text="✅ 分析完成！", foreground=self.colors['success'])

    def run(self):
        """启动 GUI"""
        self.root.mainloop()


# ================== 入口 ==================
if __name__ == "__main__":
    app = JokerDetectorGUI()
    app.run()
