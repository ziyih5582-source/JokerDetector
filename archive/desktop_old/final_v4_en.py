# -*- coding: utf-8 -*-
"""
Joker Detector Pro v7 (English)：Joker type classification + Visual GUI
Four joker types: Martyr, Mirror, Jester, Dreamer

Usage: python final_v4_en.py
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

# ================== Chinese Font Auto-Detection ==================
def _detect_cn_font():
    """Detect available Chinese font by priority"""
    candidates = [
        'Noto Sans CJK SC', 'WenQuanYi Micro Hei', 'WenQuanYi Zen Hei',
        'AR PL UKai CN', 'AR PL UMing CN',
        'song ti', 'fangsong ti',
        'Microsoft YaHei', 'PingFang SC', 'Heiti SC', 'SimHei',
    ]
    r = tk.Tk()
    r.withdraw()
    available = set(tkfont.families())
    # Try each candidate — some work even if not listed in families()
    for name in candidates:
        try:
            f = tkfont.Font(family=name, size=12)
            w = f.measure('你好世界小丑检测')
            if w > 20:  # can render Chinese
                r.destroy()
                return name
        except Exception:
            continue
    r.destroy()
    return 'TkDefaultFont'

CN_FONT = _detect_cn_font()
print(f"[Font] Detected Chinese font: {CN_FONT}")

# ================== AI Config ==================
API_KEY = os.getenv("OPENAI_API_KEY", "sk-xxxxxxxxxxxxxxxxx")
BASE_URL = "https://models.sjtu.edu.cn/api/v1"
MODEL = "deepseek-chat"

# ================== Joker Type Definitions ==================
JOKER_TYPES = {
    "殉道型": {
        "en_name": "Martyr",
        "desc": "Unconditional giver — expects nothing in return. Believes self-worth equals how much they sacrifice.",
        "suggestion": "Your value is not measured by how much you give. Set boundaries — real love flows both ways.",
        "image": "殉道型.jpg",
        "color": "#C46868",
        "keywords": [
            "只要你", "不用管我", "我没事", "为你", "值得", "付出", "应该的",
            "你开心", "我就", "牺牲", "愿意等", "多久都", "没关系", "我不重要",
            "你先", "随便我", "无所谓我", "我怎样都行", "为了你"
        ]
    },
    "镜像型": {
        "en_name": "Mirror",
        "desc": "Lost sense of self — only considers the other's feelings and needs. Becomes a mirror of the other person.",
        "suggestion": "You are not someone's shadow. Rediscover your own preferences and opinions — the real you is the most attractive.",
        "image": "镜像型.jpg",
        "color": "#6B8DB5",
        "keywords": [
            "我也是", "都行", "随便", "听你的", "你喜欢", "和你一样",
            "嗯嗯", "对的", "你说得对", "我也觉得", "看你了", "你觉得呢",
            "我都可以", "无所谓", "你定", "我跟着你"
        ]
    },
    "弄臣型": {
        "en_name": "Jester",
        "desc": "Self-deprecating entertainer — relies on mocking themselves to make the other person laugh. Uses humor to hide deep insecurity.",
        "suggestion": "Humor is charming, but self-mockery is not. You don't need to put yourself down to be liked — you already deserve to be.",
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
        "en_name": "Dreamer",
        "desc": "Lives in fantasy — endlessly imagines romantic scenarios in their head, but is timid and passive in reality.",
        "suggestion": "The script in your head isn't reality. Step out of the fantasy — even one more word spoken aloud is worth more than ten thousand daydreams.",
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

NOT_JOKER_DESC = "Your chat pattern appears healthy — no obvious joker behavior detected. Keep it up!"

# ================== Core Analysis Engine ==================
class JokerAnalyzer:
    def __init__(self):
        self.client = None
        self.ai_model = MODEL
        self._init_ai()

    def _init_ai(self):
        """Initialize AI client"""
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
        """Parse Excel chat log"""
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
        """Get both conversation participants"""
        unique = []
        for speaker, _ in data:
            if speaker not in unique:
                unique.append(speaker)
        return unique

    def compute_statistics(self, data, self_id, other_id):
        """Compute all statistics"""
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

            if '[图片]' in msg:  # image
                pics = 1
            elif '[语音]' in msg or '语音消息' in msg:  # voice message
                stats['has_voice_or_call'] = True
                is_voice_call = True
            elif '通话' in msg:  # call
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
                # Keyword detection
                for jtype, info in JOKER_TYPES.items():
                    for kw in info['keywords']:
                        if kw in msg:
                            stats['self_keyword_matches'][jtype] += 1
                # Question mark count (for Dreamer type detection)
                stats['self_question_count'] += msg.count('？') + msg.count('?')
                stats['self_exclamation_count'] += msg.count('！') + msg.count('!')
                stats['self_laugh_count'] += msg.count('哈')  # laugh detection
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

        # Compute ratios
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
        Determine joker type algorithmically.
        Returns (is_joker, joker_type, confidence)

        Strategy: keywords are primary signal, behavior patterns secondary.
        Strong keyword signal -> classify by density;
        Weak keyword signal -> fall back to behavioral indicators.
        """
        r1, r2 = stats['r1'], stats['r2']
        keyword_counts = stats['self_keyword_matches']
        total_self_msgs = max(stats['self_msg_count'], 1)

        # Raw jokernum determines "is joker"
        is_joker = stats['jokernum_alg'] > 0.35
        if not is_joker:
            return False, None, 0

        # Keyword density per type
        densities = {t: keyword_counts[t] / total_self_msgs for t in JOKER_TYPES}
        total_kw = sum(keyword_counts.values())

        # --- Case A: Strong keyword signal -> keyword-driven classification ---
        if total_kw >= 2:
            ranked = sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True)
            best_type = ranked[0][0]
            best_kw = ranked[0][1]
            if best_kw >= 2:
                confidence = min(0.5 + best_kw / max(total_kw, 1) * 0.4, 0.9)
                return True, best_type, round(confidence, 2)

        # --- Case B: Weak keyword signal -> behavior pattern fallback ---
        # Martyr: severe message/char investment imbalance (r1 or r4 significantly > 1)
        if stats['r1'] > 1.5 or stats['r4'] > 1.5:
            return True, "殉道型", 0.55

        # Jester: frequent laughter + self-deprecation
        if stats['self_laugh_count'] >= 2 or r2 > 1.5:
            return True, "弄臣型", 0.45

        # Dreamer: fantasy keywords + too shy to initiate (few messages) or many questions
        if densities["幻恋型"] > 0 or stats['self_question_count'] >= 2:
            return True, "幻恋型", 0.45

        # Mirror: echoing keywords present
        if densities["镜像型"] > 0:
            return True, "镜像型", 0.40

        # Martyr: secondary investment imbalance
        if r1 > 1.2:
            return True, "殉道型", 0.40

        # No signal at all -> weak Mirror fallback
        return True, "镜像型", 0.35

    def classify_joker_type_ai(self, data, self_id, stats):
        """Use AI to determine joker type and index (0-100)"""
        if self.client is None:
            return None, None, None

        transcript_lines = []
        for speaker, msg in data:
            tag = "[SELF]" if speaker == self_id else "[OTHER]"
            transcript_lines.append(f"{tag}{speaker}: {msg}")
        transcript = "\n".join(transcript_lines)

        prompt = f"""You are a relationship analyst. Read the following two-person chat log, where [SELF] and [OTHER] are labeled.

First, determine whether [SELF] exhibits joker behavior (grovelling, one-sided effort, excessive people-pleasing, lack of boundaries, etc.).

If [SELF] is NOT a joker, output: NOT_JOKER
If [SELF] IS a joker, output BOTH:
1. Joker type (pick one):
   - 殉道型 (Martyr): Unconditional giver — sacrifices endlessly, expects nothing, believes self-worth = sacrifice
   - 镜像型 (Mirror): Lost sense of self — mirrors the other's feelings and needs, no own identity
   - 弄臣型 (Jester): Self-deprecating entertainer — mocks themselves to make the other laugh
   - 幻恋型 (Dreamer): Fantasy lover — builds romantic scenarios in their head, but timid in reality
2. Joker index (integer 0-100, higher = more severe)

Output STRICTLY in this format (no other text):
TYPE_NAME SCORE

Example outputs:
殉道型 78
NOT_JOKER

Chat log:
{transcript}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {"role": "system", "content": "Output ONLY \"TYPE SCORE\" (e.g. \"殉道型 78\") or \"NOT_JOKER\". No other text. Valid types: 殉道型 镜像型 弄臣型 幻恋型."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=20
            )
            result = response.choices[0].message.content.strip()
            if "NOT_JOKER" in result.upper():
                return False, None, None
            # Parse "殉道型 78" format
            for t in JOKER_TYPES:
                if t in result:
                    # Try to extract score
                    score_match = re.search(r'(\d+)', result)
                    ai_score = int(score_match.group(1)) if score_match else None
                    if ai_score is not None:
                        ai_score = max(0, min(100, ai_score))
                    return True, t, ai_score
            # fallback: type found but no score
            return True, "殉道型", 50
        except Exception:
            return None, None, None

    def ai_guidance(self, data, self_id, joker_type):
        """AI emotional guidance"""
        if self.client is None:
            return None

        transcript_lines = []
        for speaker, msg in data:
            tag = "[SELF]" if speaker == self_id else "[OTHER]"
            transcript_lines.append(f"{tag}{speaker}: {msg}")
        transcript = "\n".join(transcript_lines)

        type_info = JOKER_TYPES.get(joker_type, {})
        en_name = type_info.get('en_name', joker_type)
        type_desc = type_info.get('desc', '')

        prompt = f"""You are a warm, empathetic emotional support coach. The user has been identified as a 「{en_name}」 type joker ({type_desc}).

Read the chat log and write a brief emotional guidance note (120-180 words) from the perspective of [SELF]:
1. Start by validating their feelings
2. Gently point out the pattern
3. Give 1-2 concrete, actionable suggestions
4. Keep the tone warm and non-judgmental

IMPORTANT: Write your ENTIRE response in English.

Chat log:
{transcript}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.ai_model,
                messages=[
                    {"role": "system", "content": "You are an empathetic emotional coach. Output a warm, specific guidance note in English, 120-180 words."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=400
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return None

    def full_analysis(self, file_path, self_index):
        """
        Full analysis pipeline.
        Returns dict with all results.
        """
        data = self.parse_chat(file_path)
        if not data:
            raise ValueError("No chat messages detected")

        speakers = self.get_speakers(data)
        if len(speakers) != 2:
            raise ValueError(f"Detected {len(speakers)} participants — exactly 2 required")

        self_id = speakers[self_index]
        other_id = speakers[1 - self_index]

        # Compute statistics
        stats = self.compute_statistics(data, self_id, other_id)

        # Algorithm: determines "is joker" + type (sensitivity controlled by algorithm threshold)
        is_joker_alg, joker_type_alg, confidence_alg = self.classify_joker_type_algorithmic(stats, data, self_id)

        # AI: type classification + joker score (AI used for type refinement and scoring)
        is_joker_ai, joker_type_ai, ai_score = self.classify_joker_type_ai(data, self_id, stats)

        # Hybrid: algorithm decides "is joker" (high sensitivity), AI provides type and score
        is_joker = is_joker_alg
        ai_available = is_joker_ai is not None

        if ai_available and is_joker_ai and joker_type_ai:
            # AI also thinks it is a joker -> use AI type
            joker_type = joker_type_ai
        elif is_joker:
            # Algorithm says joker but AI disagrees -> use algorithm type
            joker_type = joker_type_alg
        else:
            joker_type = None
            ai_score = None

        # AI emotional guidance
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
        self.root.title("🃏 Joker Detector")
        self.root.geometry("960x760")
        self.root.minsize(800, 600)
        self.root.configure(bg="#FBF5DD")

        # Color scheme
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
        self.photo_image = None  # Keep reference to prevent GC

        # Load text resources
        self.text_theory = _load_text("theroy.txt")
        self.text_emotion = _load_text("somewords.txt")

        self._setup_styles()
        self._build_ui()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        # Configure styles
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
        # --- Header ---
        header = ttk.Frame(self.root, style='Cream.TFrame')
        header.pack(fill='x', padx=20, pady=(20, 0))

        ttk.Label(header, text="🃏 Joker Detector", style='Title.TLabel').pack(anchor='w')
        ttk.Label(header, text="Upload your chat log to detect your joker index & type", style='Subtitle.TLabel').pack(anchor='w', pady=(4, 0))

        # --- Main content area ---
        main = ttk.Frame(self.root, style='Cream.TFrame')
        main.pack(fill='both', expand=True, padx=20, pady=15)

        # Left - control panel
        left = ttk.Frame(main, style='Card.TFrame')
        left.pack(side='left', fill='both', expand=True, padx=(0, 8))

        self._build_left_panel(left)

        # Right - results display
        right = ttk.Frame(main, style='Cream.TFrame')
        right.pack(side='right', fill='both', expand=True, padx=(8, 0))
        self._build_right_panel(right)

    def _build_left_panel(self, parent):
        # File selection area
        file_frame = ttk.Frame(parent, style='Card.TFrame')
        file_frame.pack(fill='x', padx=15, pady=(15, 10))

        ttk.Label(file_frame, text="📂 Select Chat Log File", style='Accent.TLabel').pack(anchor='w', pady=(0, 10))

        btn_frame = ttk.Frame(file_frame, style='Card.TFrame')
        btn_frame.pack(fill='x')

        self.file_btn = ttk.Button(btn_frame, text="Browse Excel File...", command=self._select_file, style='Cream.TButton')
        self.file_btn.pack(side='left', padx=(0, 10))

        self.file_label = ttk.Label(btn_frame, text="No file selected", style='Card.TLabel', foreground=self.colors['text_secondary'])
        self.file_label.pack(side='left')

        # Separator
        ttk.Separator(parent, orient='horizontal').pack(fill='x', padx=15, pady=10)

        # Speaker selection
        speaker_frame = ttk.Frame(parent, style='Card.TFrame')
        speaker_frame.pack(fill='x', padx=15, pady=5)

        ttk.Label(speaker_frame, text="👤 Select Yourself", style='Accent.TLabel').pack(anchor='w', pady=(0, 10))

        self.speaker_var = tk.IntVar(value=0)

        # User 0 & User 1 radio button frame
        self.speaker_btn_frame = ttk.Frame(speaker_frame, style='Card.TFrame')
        self.speaker_btn_frame.pack(fill='x', pady=5)

        self.speaker_btn0 = ttk.Radiobutton(
            self.speaker_btn_frame, text="User 0", variable=self.speaker_var, value=0,
            style='Cream.TRadiobutton'
        )
        self.speaker_btn0.pack(side='left', padx=(0, 20))

        self.speaker_btn1 = ttk.Radiobutton(
            self.speaker_btn_frame, text="User 1", variable=self.speaker_var, value=1,
            style='Cream.TRadiobutton'
        )
        self.speaker_btn1.pack(side='left')

        # Customize radio button appearance
        for rb in [self.speaker_btn0, self.speaker_btn1]:
            rb.configure(style='Cream.TRadiobutton')

        # Analyze button
        self.analyze_btn = ttk.Button(parent, text="🔍 Analyze",
                                       command=self._start_analysis,
                                       style='Accent.TButton',
                                       state='disabled')
        self.analyze_btn.pack(fill='x', padx=15, pady=15)

        # Progress bar
        self.progress = ttk.Progressbar(parent, mode='indeterminate', style='Cream.Horizontal.TProgressbar')
        self.progress.pack(fill='x', padx=15, pady=(0, 5))

        # Status label
        self.status_label = ttk.Label(parent, text="Ready — select a file to begin", style='Card.TLabel',
                                       foreground=self.colors['text_secondary'])
        self.status_label.pack(anchor='w', padx=15, pady=(0, 10))

        # Type legend card
        info_frame = ttk.Frame(parent, style='Card.TFrame')
        info_frame.pack(fill='both', expand=True, padx=15, pady=(5, 15))

        ttk.Label(info_frame, text="🎭 Four Joker Types", style='Accent.TLabel').pack(anchor='w', pady=(10, 5))

        type_info_text = (
            "🔴 Martyr: Unconditional giver, expects nothing\n"
            "🔵 Mirror: Loses self, becomes the other's reflection\n"
            "🟡 Jester: Self-deprecation, hides insecurity behind jokes\n"
            "🟣 Dreamer: Fantasizes endlessly, timid in reality"
        )
        ttk.Label(info_frame, text=type_info_text, style='Card.TLabel',
                  foreground=self.colors['text_secondary'], font=(CN_FONT, 10)).pack(anchor='w', pady=(0, 10))

        # AI status
        ai_status = "✅ AI Connected" if self.analyzer.client else "⚠️ AI Disconnected (algorithm-only mode)"
        ai_color = self.colors['success'] if self.analyzer.client else self.colors['warning']
        ttk.Label(info_frame, text=ai_status, style='Card.TLabel',
                  foreground=ai_color, font=(CN_FONT, 10)).pack(anchor='w', pady=(5, 10))

        # Knowledge base buttons
        ttk.Separator(info_frame, orient='horizontal').pack(fill='x', pady=(5, 0))
        ttk.Label(info_frame, text="📖 Knowledge Base", style='Accent.TLabel').pack(anchor='w', pady=(10, 5))
        btn_frame = ttk.Frame(info_frame, style='Card.TFrame')
        btn_frame.pack(fill='x', pady=(0, 5))
        ttk.Button(btn_frame, text="📚 Love Theories",
                   command=lambda: self._show_popup("📚 Love Theories", self.text_theory),
                   style='Small.TButton').pack(side='left', padx=(0, 8))
        ttk.Button(btn_frame, text="💬 Gentle Words",
                   command=lambda: self._show_popup("💬 Gentle Words", self.text_emotion),
                   style='Small.TButton').pack(side='left')

    def _show_popup(self, title, text):
        """Show a popup window with the given text"""
        if not text:
            messagebox.showinfo("Notice", "Text not loaded. Please check if the file exists.")
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
        # Results area - initially shows welcome
        self.result_frame = ttk.Frame(parent, style='Card.TFrame')
        self.result_frame.pack(fill='both', expand=True)

        # Placeholder welcome screen
        self.placeholder = ttk.Frame(self.result_frame, style='Card.TFrame')
        self.placeholder.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(self.placeholder, text="🃏", font=(CN_FONT, 64),
                  background=self.colors['bg_card']).pack(pady=(60, 15))
        ttk.Label(self.placeholder, text="Waiting for analysis...", style='TypeTitle.TLabel').pack(pady=5)
        ttk.Label(self.placeholder,
                  text="Select your chat log file\nChoose your identity in the conversation\nThen click 'Analyze'",
                  style='TypeDesc.TLabel', font=(CN_FONT, 11)).pack(pady=10)

        # Results content (initially hidden)
        self.result_content = ttk.Frame(self.result_frame, style='Card.TFrame')

    def _select_file(self):
        """File selection callback"""
        file_path = filedialog.askopenfilename(
            title="Select Chat Log File",
            filetypes=[("Excel Files", "*.xlsx *.xls"), ("All Files", "*.*")]
        )
        if file_path:
            self.selected_file = file_path
            self.file_label.configure(text=os.path.basename(file_path))

            # Quick parse to show speakers
            try:
                data = self.analyzer.parse_chat(file_path)
                speakers = self.analyzer.get_speakers(data)
                if len(speakers) == 2:
                    self.speaker_btn0.configure(text=speakers[0])
                    self.speaker_btn1.configure(text=speakers[1])
                    self.analyze_btn.configure(state='normal')
                    self.status_label.configure(text=f"✅ File loaded — {len(data)} messages detected", foreground=self.colors['success'])
                else:
                    self.analyze_btn.configure(state='disabled')
                    self.status_label.configure(text=f"❌ Detected {len(speakers)} participants — exactly 2 required", foreground=self.colors['danger'])
            except Exception as e:
                self.analyze_btn.configure(state='disabled')
                self.status_label.configure(text=f"❌ Failed to parse file: {str(e)[:50]}", foreground=self.colors['danger'])

    def _start_analysis(self):
        """Start analysis"""
        if not hasattr(self, 'selected_file'):
            return

        self.analyze_btn.configure(state='disabled', text="⏳ Analyzing...")
        self.progress.start(10)
        self.status_label.configure(text="Analyzing chat log...", foreground=self.colors['text_secondary'])

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
        self.analyze_btn.configure(state='normal', text="🔍 Analyze")
        self.status_label.configure(text=f"❌ Error: {msg[:80]}", foreground=self.colors['danger'])
        messagebox.showerror("Analysis Failed", msg)

    def _display_result(self):
        self.progress.stop()
        self.analyze_btn.configure(state='normal', text="🔍 Re-analyze")

        # Clear placeholder and old results
        self.placeholder.pack_forget()
        for widget in self.result_content.winfo_children():
            widget.destroy()
        self.result_content.pack(fill='both', expand=True)

        r = self.result
        is_joker = r['is_joker']
        joker_type = r['joker_type']
        stats = r['stats']

        # ===== Verdict Header =====
        header_frame = ttk.Frame(self.result_content, style='Card.TFrame')
        header_frame.pack(fill='x', padx=15, pady=(15, 5))

        if is_joker and joker_type:
            type_info = JOKER_TYPES[joker_type]
            verdict = f"🤡 Joker Confirmed — {joker_type}"
            verdict_color = type_info['color']
        else:
            verdict = "✅ Congrats! You are NOT a joker"
            verdict_color = self.colors['success']

        verdict_label = tk.Label(header_frame, text=verdict, fg=verdict_color,
                                  bg=self.colors['bg_card'], font=(CN_FONT, 20, 'bold'))
        verdict_label.pack(anchor='w')

        # Score display
        jn = stats['jokernum_alg']
        ai_score = r.get('ai_score')
        score_text = f"Algo Index: {jn:.2f}"
        if ai_score is not None:
            score_text += f"  |  🤖 AI Joker Index: {ai_score}/100"
        if is_joker and joker_type:
            ai_hint = ""
            if r.get('ai_available') and r['joker_type_ai']:
                ai_t = r['joker_type_ai'][1]
                ai_hint = f"  (AI says: {ai_t if r['joker_type_ai'][0] else 'Not Joker'})"
            score_text += f"\nType: {joker_type}{ai_hint}"
        ttk.Label(header_frame, text=score_text, style='Card.TLabel',
                  foreground=self.colors['text_secondary'], font=(CN_FONT, 11)).pack(anchor='w', pady=(5, 0))

        ttk.Separator(self.result_content, orient='horizontal').pack(fill='x', padx=15, pady=8)

        # ===== If joker, show image and detailed description =====
        if is_joker and joker_type:
            type_info = JOKER_TYPES[joker_type]
            img_desc_frame = ttk.Frame(self.result_content, style='Card.TFrame')
            img_desc_frame.pack(fill='x', padx=15, pady=8)

            # Display image
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
                    err_label = tk.Label(img_frame, text=f"[Image load failed]\n{type_info['image']}",
                                         bg=self.colors['bg_card'], fg=self.colors['text_secondary'],
                                         font=(CN_FONT, 10), width=25, height=10)
                    err_label.pack()
            else:
                missing = tk.Label(img_frame, text=f"[Image not found]\n{type_info['image']}",
                                   bg=self.colors['bg_card'], fg=self.colors['text_secondary'],
                                   font=(CN_FONT, 10), width=25, height=10)
                missing.pack()

            # Type description
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
            # Not joker display
            not_joker_frame = ttk.Frame(self.result_content, style='Card.TFrame')
            not_joker_frame.pack(fill='x', padx=15, pady=15)
            ttk.Label(not_joker_frame, text=NOT_JOKER_DESC, style='Card.TLabel',
                      font=(CN_FONT, 12), wraplength=500).pack(anchor='w')

        ttk.Separator(self.result_content, orient='horizontal').pack(fill='x', padx=15, pady=8)

        # ===== Statistics =====
        stats_frame = ttk.Frame(self.result_content, style='Card.TFrame')
        stats_frame.pack(fill='x', padx=15, pady=5)

        ttk.Label(stats_frame, text="📊 Chat Statistics", style='Accent.TLabel').pack(anchor='w', pady=(0, 8))

        stat_grid = ttk.Frame(stats_frame, style='Card.TFrame')
        stat_grid.pack(fill='x')

        left_stats = [
            f"Messages: Self {stats['self_msg_count']} / Other {stats['other_msg_count']}",
            f"Stickers: Self {stats['self_sticker_count']} / Other {stats['other_sticker_count']}",
            f"Images: Self {stats['self_pic_count']} / Other {stats['other_pic_count']}",
            f"Total chars: Self {stats['self_total_chars']} / Other {stats['other_total_chars']}",
        ]

        right_stats = [
            f"Max streak: Self {stats['max_self_cont']} / Other {stats['max_other_cont']}",
            f"Voice/Call: Self {stats['self_voice_call']} / Other {stats['other_voice_call']}",
            f"Avg chars: Self {stats['self_avg_chars']:.1f} / Other {stats['other_avg_chars']:.1f}",
        ]

        # Ratio items
        ratio_items = [
            (f"Msg ratio: {stats['r1']:.2f}", stats['r1']),
            (f"Sticker ratio: {stats['r2']:.2f}", stats['r2']),
            (f"Streak ratio: {stats['r3']:.2f}", stats['r3']),
            (f"Char ratio: {stats['r4']:.2f}", stats['r4']),
            (f"Image ratio: {stats['r5']:.2f}", stats['r5']),
        ]

        for i, (text, val) in enumerate(ratio_items):
            color = self.colors['danger'] if val > 1.5 else (self.colors['success'] if val < 0.67 else self.colors['text_secondary'])
            ttk.Label(stat_grid, text=text, style='Stat.TLabel',
                      foreground=color, font=(CN_FONT, 10)).grid(row=i, column=0, sticky='w', pady=2, padx=(0, 20))
            if i < len(right_stats):
                ttk.Label(stat_grid, text=right_stats[i], style='Stat.TLabel',
                          foreground=self.colors['text_secondary'], font=(CN_FONT, 10)).grid(row=i, column=1, sticky='w', pady=2)

        # Keyword hits
        if is_joker and joker_type and stats['self_keyword_matches'].get(joker_type, 0) > 0:
            kw_count = stats['self_keyword_matches'][joker_type]
            ttk.Label(stats_frame, text=f"🔑 Type keyword hits: {kw_count}",
                      style='Stat.TLabel', foreground=self.colors['text_secondary']).pack(anchor='w', pady=(5, 0))

        ttk.Separator(self.result_content, orient='horizontal').pack(fill='x', padx=15, pady=8)

        # ===== AI emotional guidance =====
        if r.get('guidance'):
            guidance_frame = ttk.Frame(self.result_content, style='Card.TFrame')
            guidance_frame.pack(fill='x', padx=15, pady=5)

            ttk.Label(guidance_frame, text="💌 AI emotional guidance", style='Accent.TLabel').pack(anchor='w', pady=(0, 8))
            ttk.Label(guidance_frame, text=r['guidance'], style='TypeDesc.TLabel',
                      font=(CN_FONT, 11), wraplength=550).pack(anchor='w')

        # Bottom spacer
        ttk.Frame(self.result_content, style='Card.TFrame', height=10).pack()

        self.status_label.configure(text="✅ Analysis complete!", foreground=self.colors['success'])

    def run(self):
        """Launch GUI"""
        self.root.mainloop()


# ================== Entry Point ==================
if __name__ == "__main__":
    app = JokerDetectorGUI()
    app.run()
