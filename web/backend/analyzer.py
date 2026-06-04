# -*- coding: utf-8 -*-
"""
小丑监测器 - 核心分析引擎
从 v5.py 提取，去除 GUI / Arduino 耦合，纯后端可调用
"""

import os
import re
import math
import pandas as pd
from openai import OpenAI
import httpx

# ================== AI 配置 ==================
API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
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

NOT_JOKER_DESC = (
    "🎉 恭喜！你击败了全国 99% 的纯爱战神！\n"
    "在你们的聊天中，你保持了极高的人格独立与边界感，没有出现明显的妥协与卑微。\n"
    "但记住，爱情是一场势均力敌的博弈，继续保持你的清醒，享受关系本身吧！"
)

# ================== 核心分析引擎 ==================
class JokerAnalyzer:
    def __init__(self):
        self.client = None
        self.ai_model = MODEL
        self._init_ai()

    def _init_ai(self):
        if not API_KEY or API_KEY.startswith("sk-xxx"):
            return
        try:
            self.client = OpenAI(
                api_key=API_KEY,
                base_url=BASE_URL,
                http_client=httpx.Client(trust_env=False)
            )
        except Exception:
            pass

    @property
    def ai_available(self) -> bool:
        return self.client is not None

    def update_ai_config(self, api_key: str, model: str = "deepseek-chat", base_url: str = None):
        """运行时更新 AI 配置，重新初始化客户端"""
        if not api_key or len(api_key.strip()) < 10:
            self.client = None
            return False
        self.ai_model = model
        url = base_url or BASE_URL
        try:
            self.client = OpenAI(
                api_key=api_key.strip(),
                base_url=url,
                http_client=httpx.Client(trust_env=False)
            )
            return True
        except Exception:
            self.client = None
            return False

    # ---------- 聊天记录解析 ----------
    def parse_chat(self, file_path):
        """解析微信导出的 Excel 聊天记录"""
        try:
            if file_path.lower().endswith('.xls'):
                df = pd.read_excel(file_path, header=None, engine='xlrd')
            else:
                df = pd.read_excel(file_path, header=None, engine='openpyxl')
        except Exception as e:
            raise ValueError(f"读取文件失败: {str(e)}")

        data = []
        current_speaker = None
        for _, row in df.iterrows():
            valid_cells = [str(x).strip() for x in row if pd.notna(x) and str(x).strip() != '']
            if not valid_cells:
                continue

            lines = []
            for cell in valid_cells:
                lines.extend(cell.split('\n'))
            lines = [line.strip() for line in lines if line.strip()]
            if not lines:
                continue

            if len(valid_cells) >= 2 and len(lines) == len(valid_cells):
                speaker = re.sub(
                    r'^(\d{2,4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s+)?', '',
                    lines[-2].strip()
                ).strip()
                if speaker and lines[-1]:
                    data.append((speaker, lines[-1].strip()))
                continue

            for line in lines:
                match_single = re.search(r'^([^:：]+)[:：]\s*(.+)$', line)
                if match_single:
                    speaker = re.sub(
                        r'^(\d{2,4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s+)?(\d{1,2}:\d{1,2}(:\d{1,2})?\s+)?',
                        '', match_single.group(1).strip()
                    ).strip()
                    if len(speaker) <= 25:
                        data.append((speaker, match_single.group(2).strip()))
                        current_speaker = None
                    continue

                match_speaker = re.search(r'^([^:：]+)[:：]$', line)
                if match_speaker and len(match_speaker.group(1)) <= 25:
                    current_speaker = re.sub(
                        r'^(\d{2,4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?\s+)?(\d{1,2}:\d{1,2}(:\d{1,2})?\s+)?',
                        '', match_speaker.group(1).strip()
                    ).strip()
                elif current_speaker:
                    data.append((current_speaker, line))
                    current_speaker = None
        return data

    def get_speakers(self, data):
        """获取前两名发言者"""
        counts = {}
        for sp, _ in data:
            counts[sp] = counts.get(sp, 0) + 1
        return [s[0] for s in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:2]]

    # ---------- 统计计算 ----------
    def compute_statistics(self, data, self_id, other_id):
        """计算多维统计指标"""
        stats = {
            'self_msg_count': 0, 'other_msg_count': 0,
            'self_sticker_count': 0, 'other_sticker_count': 0,
            'self_pic_count': 0, 'other_pic_count': 0,
            'self_total_chars': 0, 'other_total_chars': 0,
            'max_self_cont': 0, 'max_other_cont': 0,
            'has_voice_or_call': False,
            'self_keyword_matches': {t: 0 for t in JOKER_TYPES}
        }

        curr_streak, curr_sp = 0, None
        for sp, msg in data:
            pics = 1 if '[图片]' in msg else 0
            stickers = 1 if re.search(r'\[.+?\]', msg) and not pics else 0
            if '[语音]' in msg or '语音消息' in msg or '通话' in msg:
                stats['has_voice_or_call'] = True

            chars = len(msg)
            if sp == self_id:
                stats['self_msg_count'] += 1
                stats['self_sticker_count'] += stickers
                stats['self_pic_count'] += pics
                stats['self_total_chars'] += chars
                for jtype, info in JOKER_TYPES.items():
                    for kw in info['keywords']:
                        if kw in msg:
                            stats['self_keyword_matches'][jtype] += 1
            elif sp == other_id:
                stats['other_msg_count'] += 1
                stats['other_sticker_count'] += stickers
                stats['other_pic_count'] += pics
                stats['other_total_chars'] += chars

            # 连续消息追踪
            if sp == curr_sp:
                curr_streak += 1
            else:
                curr_streak, curr_sp = 1, sp

            if sp == self_id:
                stats['max_self_cont'] = max(stats['max_self_cont'], curr_streak)
            elif sp == other_id:
                stats['max_other_cont'] = max(stats['max_other_cont'], curr_streak)

        stats['self_avg_chars'] = (
            stats['self_total_chars'] / stats['self_msg_count']
            if stats['self_msg_count'] > 0 else 0
        )
        stats['other_avg_chars'] = (
            stats['other_total_chars'] / stats['other_msg_count']
            if stats['other_msg_count'] > 0 else 0
        )

        # ---- Z-score 指标体系 ----
        # Z1: 自我连续发送倾向 (SSDT)
        DA = sum(1 for i in range(1, len(data)) if data[i][0] == self_id and data[i-1][0] == self_id)
        DB = sum(1 for i in range(1, len(data)) if data[i][0] == other_id and data[i-1][0] == other_id)
        Z_SSDT = (DA - DB) / (DA + DB + 1e-6)

        # Z2: 自我中心化指数 (PFI)
        I_A = sum(msg.count(w) for w in ['我', '俺', '自己'] for sp, msg in data if sp == self_id)
        We_A = sum(msg.count(w) for w in ['我们', '咱们'] for sp, msg in data if sp == self_id)
        I_B = sum(msg.count(w) for w in ['我', '俺', '自己'] for sp, msg in data if sp == other_id)
        We_B = sum(msg.count(w) for w in ['我们', '咱们'] for sp, msg in data if sp == other_id)
        PFI_A = math.log(I_A + 1) / (math.log(We_A + 1) + 1e-6)
        PFI_B = math.log(I_B + 1) / (math.log(We_B + 1) + 1e-6)
        Z_PFI = (PFI_A - PFI_B) / (PFI_A + PFI_B + 1e-6)

        # Z3: 低姿态语言密度 (PLD)
        Hedges = ['可能', '有点', '似乎', '也许', '嗯', '那个', '对吧', '好吗',
                   '对不起', '抱歉', '不好意思', '哈哈', '？', '?']
        Hedge_A = sum(msg.count(w) for w in Hedges for sp, msg in data if sp == self_id)
        Hedge_B = sum(msg.count(w) for w in Hedges for sp, msg in data if sp == other_id)
        PLD_A = Hedge_A / (stats['self_total_chars'] + 1)
        PLD_B = Hedge_B / (stats['other_total_chars'] + 1)
        Z_PLD = (PLD_A - PLD_B) / (PLD_A + PLD_B + 1e-6)

        # Z4: 情感表达差 (EPEG)
        Emotions = ['开心', '喜欢', '爱', '讨厌', '生气', '郁闷', '绝望', '崩溃',
                     '高兴', '烦', '累', '痛', '死', '哭', '笑', '！', '!']
        E_A = sum(msg.count(w) for w in Emotions for sp, msg in data if sp == self_id)
        E_B = sum(msg.count(w) for w in Emotions for sp, msg in data if sp == other_id)
        EPEG = math.log(E_A + 1) - math.log(E_B + 1)
        Z_EPEG = max(min(EPEG / 2.0, 1.0), -1.0)

        # Z5: 功能词桥接 (CONV)
        FuncWords = ['因为', '所以', '并且', '但是', '是', '有', '能够',
                      '可以', '很', '非常', '其实', '只', '就']
        conv_ab, base_ab, conv_ba, base_ba = 0, 0, 0, 0
        for i in range(1, len(data)):
            p_sp, p_msg = data[i-1]
            c_sp, c_msg = data[i]
            if c_sp == self_id and p_sp == other_id:
                if any(w in p_msg and w in c_msg for w in FuncWords):
                    conv_ab += 1
                base_ab += 1
            elif c_sp == other_id and p_sp == self_id:
                if any(w in p_msg and w in c_msg for w in FuncWords):
                    conv_ba += 1
                base_ba += 1
        Z_CONV = (conv_ab / (base_ab + 1e-6)) - (conv_ba / (base_ba + 1e-6))

        # 综合评分
        Z_Total = 0.25 * Z_SSDT + 0.2 * Z_PFI + 0.2 * Z_PLD + 0.15 * Z_EPEG + 0.2 * Z_CONV
        score = 100 / (1 + math.exp(-5.0 * (Z_Total - 0.05)))
        if stats['has_voice_or_call']:
            score *= 0.95

        stats['jokernum_alg'] = round(score, 2)
        stats['z_metrics'] = {
            'SSDT': round(Z_SSDT, 4),
            'PFI': round(Z_PFI, 4),
            'PLD': round(Z_PLD, 4),
            'EPEG': round(Z_EPEG, 4),
            'CONV': round(Z_CONV, 4)
        }
        return stats

    # ---------- 小丑分类 ----------
    def classify_joker_type_algorithmic(self, stats):
        """算法层小丑分类"""
        hm = max(stats['z_metrics'], key=stats['z_metrics'].get)
        mapping = {'SSDT': '幻恋型', 'CONV': '镜像型', 'PLD': '弄臣型'}
        return mapping.get(hm, '殉道型')

    def classify_joker_type_ai(self, data, self_id):
        """AI 层小丑分类"""
        if self.client is None:
            return None, None
        transcript = "\n".join(
            [f"{'【自己】' if sp == self_id else '【对方】'}{sp}: {m}"
             for sp, m in data[-300:]]
        )
        prompt = f"""你是一位极其敏锐的情感博弈分析师。阅读聊天记录，判断【自己】在关系中是否处于低位（小丑）。
【严苛判定标尺】：
1. 只要表现出：害怕冷场连续找话题、过度解释、单向提供情绪价值（即使对方有回复），必须判定为小丑。
2. 只有双方完全势均力敌，互相推拉不惧冷场，才能输出：NOT_JOKER
如果是小丑行为，输出：类型名称（殉道型/镜像型/弄臣型/幻恋型） 小丑指数（60-100）
如果不属于，输出：NOT_JOKER

聊天记录：
{transcript}"""
        try:
            res = self.client.chat.completions.create(
                model=self.ai_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=20
            ).choices[0].message.content.strip()
            if "NOT_JOKER" in res.upper():
                return False, None
            for t in JOKER_TYPES:
                if t in res:
                    m = re.search(r'(\d+)', res)
                    return True, t
            return True, "殉道型"
        except Exception:
            return None, None

    def ai_guidance(self, data, self_id, is_joker, joker_type):
        """AI 情感疏导"""
        if self.client is None:
            return None
        transcript = "\n".join(
            [f"{'【自己】' if sp == self_id else '【对方】'}{sp}: {m}"
             for sp, m in data[-500:]]
        )
        if is_joker:
            t_desc = JOKER_TYPES.get(joker_type, {}).get('desc', '')
            prompt = f"""你是一位理性客观的情感支持导师。用户被分析为「{joker_type}」小丑（{t_desc}）。
请从【自己】视角写一段情感疏导（2000字）：安抚情绪、结合聊天内容引用原话、利用心理学分析核心问题、给出实操建议。语气温柔。

聊天记录：
{transcript}"""
        else:
            prompt = f"""你是一位情感导师。用户展现出极高独立性和边界感（清醒玩家）。
写一段复盘鼓励（1000字）：夸奖其具体表现（引用原话）、分析权力流动、给出保持框架的进阶建议。语气温柔欣赏。

聊天记录：
{transcript}"""
        try:
            return self.client.chat.completions.create(
                model=self.ai_model,
                messages=[{"role": "system", "content": "你是一位富有同理心且专业的情感导师。"},
                          {"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=2000
            ).choices[0].message.content.strip()
        except Exception:
            return None

    # ---------- 完整分析流程 ----------
    def full_analysis(self, file_path, self_index=0):
        """完整分析流程：解析 → 统计 → AI 判定 → 疏导"""
        data = self.parse_chat(file_path)
        if not data:
            raise ValueError("未能提取到有效聊天内容")
        speakers = self.get_speakers(data)
        if len(speakers) < 2:
            raise ValueError("必须包含至少2个人的对话！")

        self_id, other_id = speakers[self_index], speakers[1 - self_index]
        stats = self.compute_statistics(data, self_id, other_id)

        alg_type = self.classify_joker_type_algorithmic(stats)
        ai_is_joker, ai_type = self.classify_joker_type_ai(data, self_id)

        alg_score = stats['jokernum_alg']
        if ai_is_joker is not None:
            if alg_score >= 60.0:
                is_joker = True
            elif alg_score >= 45.0:
                is_joker = ai_is_joker
            else:
                is_joker = False
        else:
            is_joker = alg_score > 50.0

        joker_type = (
            ai_type if (is_joker and ai_is_joker and ai_type)
            else (alg_type if is_joker else None)
        )
        guidance = self.ai_guidance(data, self_id, is_joker, joker_type) if self.client else None

        return {
            'data': data,
            'speakers': speakers,
            'self_id': self_id,
            'other_id': other_id,
            'stats': stats,
            'is_joker': is_joker,
            'joker_type': joker_type,
            'guidance': guidance
        }

    def analyze_demo(self, demo_messages, self_name, other_name):
        """Demo 模式：直接传入消息列表分析（无需文件）"""
        data = []
        for msg in demo_messages:
            data.append((msg['speaker'], msg['content']))

        self_id, other_id = self_name, other_name
        stats = self.compute_statistics(data, self_id, other_id)
        alg_type = self.classify_joker_type_algorithmic(stats)
        ai_is_joker, ai_type = self.classify_joker_type_ai(data, self_id)

        alg_score = stats['jokernum_alg']
        if ai_is_joker is not None:
            if alg_score >= 60.0:
                is_joker = True
            elif alg_score >= 45.0:
                is_joker = ai_is_joker
            else:
                is_joker = False
        else:
            is_joker = alg_score > 50.0

        joker_type = (
            ai_type if (is_joker and ai_is_joker and ai_type)
            else (alg_type if is_joker else None)
        )
        guidance = self.ai_guidance(data, self_id, is_joker, joker_type) if self.client else None

        return {
            'data': data,
            'speakers': [self_name, other_name],
            'self_id': self_id,
            'other_id': other_id,
            'stats': stats,
            'is_joker': is_joker,
            'joker_type': joker_type,
            'guidance': guidance
        }
