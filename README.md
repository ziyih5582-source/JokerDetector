# 🃏 Joker Detector Pro · 交心 · 思源湖研究所

> 上海交通大学工程学导论课程项目 | 把一段聊天投进湖里，量一量、记下来、说出口

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Fun%20%26%20WIP-orange.svg)

---

## 本次更新：前端改名与思源湖主题重做

**1. 站点改名换主题。**
界面不再叫「观心潭」，改为**「交心 · 思源湖研究所」**（副标题：上海交通大学 · 把一段聊天投进湖里，量一量、记下来、说出口）。整套前端按校园「谈心 + 自查」小机制的口径重写，三件事一次做完：**① 量一量**（谈心分析）、**② 记下来**（人物档案）、**③ 说出口**（找钓翁聊聊）。首页显眼处写明它**不是心理测量、不是诊断，也不能替代心理咨询或医疗**，并把校内心理健康教育与咨询中心、全国统一心理援助热线 **12356**、**120 / 110** 这些真实求助入口放在顺手的地方。

**2. 页面与按钮全部改成大白话。**
导航共七个去处：**首页 · 谈心分析 · 找钓翁聊聊 · 人物档案 · 心理学依据 · 使用说明 · 设置**，另有一个不在导航里的结果页**「分析结果」**（保留「水纹」这个别称）。按钮顺势改名：「投食 → 洒入水中」变「谈心分析 → 开始分析」，「择卷 → 录名 → 抹去此人」变「导入 Excel → 新建档案 → 删除此人」，「拓一张纸」变「导出为图片」，「再投一次」变「再分析一段」，「静水」变「暂停湖面动画」，「配乐」变「背景音乐」，「示例 · 初 / 示例 · 变」变「填入示例一 / 填入示例二」。钓翁这个人设保留，只是从「潭边」挪到了「思源湖畔垂钓多年的老者」。

**3. 思源湖主题。**
首页最前面是一张思源湖水彩画：原图 `assets/pictures/交大思源湖.png` 不入库，网页用的是由它导出的 `frontend/img/siyuan-lake.jpg`，另有一张模糊压暗的 `frontend/img/siyuan-lake-soft.jpg` 作为整站的远景水色；首页中段还有一条用它做的「卷中题记」水色横带。湖面 canvas（`#pond-canvas`）只在首页之外的页面可见，点纸面空白处即可撒一把食喂鱼，首页放的是画卷、不放鱼。设计上仍然只有细墨线 + 浓淡墨色 + 文字，没有任何方框按钮。

**4. 后端文案随之对齐。**
未配置云端 AI 时的提示现在指向「设置」页（不再叫「墨设」），`backend/tests/test_fisherman.py` 的断言也一并改成「设置」；测试仍是 **77 项**，全部通过。

### 上一次更新：目录按前后端分离重组

**1. 前后端彻底分开。**
后端在 `backend/`（FastAPI，可单独部署），前端在 `frontend/`（纯静态 HTML/CSS/JS，也可单独部署），两边只通过 `/api/*` 通信。开发时后端顺手把前端和 `/music` 一起挂载，所以体验上仍是打开一个网址就能用。

**2. 后端按分层组织，不再是平铺的几个脚本。**
`core/` 放配置、中间件与错误映射，`schemas/` 放请求模型，`services/` 放分析引擎、档案库与融合流程，`api/` 只负责把 service 暴露成 HTTP。所有路径只在 `backend/app/core/config.py` 里解析一次，不再散落各处。

**3. 单片机（Arduino）相关代码与全部早期版本已删除。**
`archive/` 整目录清空——Arduino 固件、串口联动代码、旧版前端与各代桌面脚本都不再保留。桌面版 Tkinter 程序作为历史版本挪到 `legacy/desktop/`，已不再维护。

**4. 工程化补齐。**
`backend/pyproject.toml`（pytest / ruff 配置）、根目录 `Makefile`、`scripts/start.sh` 与 `scripts/start.bat`、`.github/workflows/ci.yml`（自动跑 ruff + 77 项测试）。测试里不再需要 `sys.path` 小动作。

---

## 📖 项目简介

你是不是在感情中付出太多却得不到回应？你是不是那个永远在主动的"小丑"？

**Joker Detector Pro** 是一款专为工程学导论课程设计的聊天记录分析工具，界面上的名字是**「交心 · 思源湖研究所」**。它能够：

- 📊 从微信聊天记录 Excel 文件中提取数据（也支持直接粘贴 `发言者：内容`）
- 🧮 使用多维度算法量化你的"小丑指数"
- 🤖 结合 AI 大模型进行情感关系深度分析
- 💌 生成个性化情感疏导建议，并维护一份本机加密的"人物档案"
- 🎣 「找钓翁聊聊」：把档案作为背景，和 AI 聊具体这段关系

> ⚠️ 本项目仅供课程学习和娱乐目的，请勿用于实际情感决策。
>
> 它**不是心理测量工具，也不做诊断**，更不能替代心理咨询或医疗；如果你正处在持续的痛苦里，首页最下面列着校内心理健康教育与咨询中心、全国统一心理援助热线 12356 与 120 / 110。

---

## 🚀 快速开始

### 环境要求

- Python 3.10+（推荐 3.12）
- 无 Node.js 依赖：前端是纯静态页面，不需要构建

### 安装依赖

```bash
python -m venv .venv
# Windows: .venv\Scripts\python -m pip install -r backend/requirements.txt
.venv/bin/python -m pip install -r backend/requirements.txt
```

想跑测试再加：`.venv/bin/python -m pip install pytest ruff`（或直接 `make install`）。

### 启动

```bash
# 方式一：Makefile（推荐）
make run          # 生产式启动
make dev          # 改代码自动重载

# 方式二：直接命令（在项目根目录）
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# 方式三：双击脚本
scripts/start.sh            # macOS / Linux
scripts\start.bat           # Windows
```

浏览器访问 <http://127.0.0.1:8000/> 。也可以在 `backend/` 目录下 `python -m app.main`。

> 后端与前端是两份独立的东西：如果只想动后端，`cd backend && python -m app.main` 即可；如果要把前端放到 Nginx 或对象存储，直接把 `frontend/` 整个目录传上去，再把 `/api` 反代到后端就行。

### 使用流程

点「谈心分析」→ 粘贴或导入聊天 → 「辨认说话的人」→ 核对「我（自己） / 对方」→（可选）在右侧「这段聊天记在谁名下」里选一个档案条目，决定是否写入档案 → 「开始分析」。

一次提交同时得到分析结果（情感分析）与人物档案变动（喜好、依据、冲突）。不选档案条目就是纯分析，不写档案库。

想聊感情问题：点「找钓翁聊聊」，选好「这次想聊谁」（可以不选人），把想说的写下来发送。这个功能需要先配置云端 AI。

想看鱼：切到首页之外的任意页面，点纸面空白处就能撒食；首页放的是思源湖画卷，没有鱼，点空白处也没有任何副作用。

### 配置云端 AI（可选）

Web 版采用**统一配置**，使用者无需在网页里填 Key。把 `.env.example` 复制成项目根目录的 `.env`：

```env
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com   # 任意 OpenAI 兼容服务
DEEPSEEK_MODEL=deepseek-chat
```

读取顺序：**真实进程环境变量优先，其次 `.env`**。改完 `.env` 后在「设置」页点「重新加载配置」即可生效，不必重启（后端会撤掉上一次由 `.env` 注入的变量再重读）。然后在「设置」页点「验证调用」确认真能跑通，再在「谈心分析」里勾选云端选项。未配置时后端的提示也会把你引到「设置」页。

没有 Key 时本地统计与喜好提取照常工作，只是没有云端长文。

---

## 📁 项目结构

```
📦 JokerDetector
├── 📁 backend/                     # 后端服务（FastAPI，可独立部署）
│   ├── 📁 app/
│   │   ├── 📄 main.py              # 装配应用：中间件、静态挂载、路由聚合、启动入口
│   │   ├── 📁 core/                # 不含业务逻辑的公共设施
│   │   │   ├── 📄 config.py        # 路径、版本、各项上限、.env 加载（唯一解析路径的地方）
│   │   │   ├── 📄 middleware.py    # 只信任本机 Host、拒绝跨站写请求、严格 CSP
│   │   │   └── 📄 errors.py        # 领域异常 → HTTP 状态码
│   │   ├── 📁 schemas/             # Pydantic 请求模型（base / profiles / fisherman / system）
│   │   ├── 📁 services/            # 业务能力，不依赖 FastAPI 装饰器
│   │   │   ├── 📄 analyzer.py      # 核心分析引擎（统计、五维、类型判定）
│   │   │   ├── 📄 profiles.py      # 脱敏、加密存储、合并、冲突、人工修正
│   │   │   ├── 📄 unified.py       # run_unified()：分析与建档的唯一融合入口
│   │   │   ├── 📄 report.py        # 结果格式化、判定阈值、五维说明
│   │   │   └── 📄 demo_data.py     # 内置示例案例
│   │   └── 📁 api/
│   │       ├── 📄 deps.py          # analyzer 单例与本机档案库
│   │       └── 📁 routes/          # system / analysis / profiles / fisherman，由 api_router 聚合
│   ├── 📁 tests/                   # 77 项自动化测试
│   ├── 📄 pyproject.toml           # pytest 与 ruff 配置
│   └── 📄 requirements.txt
│
├── 📁 frontend/                    # 前端（纯静态，可单独部署）
│   ├── 📄 index.html               # 单页工作台：首页 / 谈心分析 / 分析结果 / 找钓翁聊聊 / 人物档案 / 心理学依据 / 使用说明 / 设置
│   ├── 📁 css/ink.css              # 水墨样式：只有细墨线与湖色，没有方框
│   ├── 📁 img/                     # 首页画卷 siyuan-lake.jpg 与整站远景水色 siyuan-lake-soft.jpg
│   └── 📁 js/                      # pond.js 湖面画布、ink.js 主逻辑、theory.js 心理学依据页
│
├── 📁 data/
│   ├── 📁 samples/                 # 虚构聊天样例（test1.xls 为本地真实记录，不入库）
│   └── 📁 private/                 # 加密档案库与密钥（不入库，备份要一起带走）
│
├── 📁 assets/                      # 本地媒体资源（不入库，见 assets/README.md）
│   ├── 📁 music/
│   └── 📁 pictures/                # 含首页画卷原图 交大思源湖.png（网页用的是 frontend/img/ 里的成品）
│
├── 📁 docs/                        # PROFILES.md 使用教程、TECHNICAL.md 技术文档、reference 素材
├── 📁 legacy/desktop/              # 早期 Tkinter 桌面版，仅作历史保留
├── 📁 scripts/                     # start.sh / start.bat
├── 📁 .github/workflows/ci.yml     # CI：ruff + pytest
├── 📄 Makefile                     # make install / run / dev / test / lint / fmt / clean
├── 📄 .env.example                 # 统一 AI 配置模板（复制为 .env）
└── 📄 README.md / LICENSE
```

### 一次请求怎么走

```
浏览器 frontend/ ──► /api/analyze/unified ──► api/routes/analysis.py
                                                │
                                                ├─► services/unified.py  （融合流程：建档 + 情感分析）
                                                │      ├─► services/profiles.py  脱敏 / 加密档案库
                                                │      └─► services/analyzer.py  统计与五维打分
                                                └─► services/report.py  （翻成前端 JSON）
```

约定：`services/` 不认识 HTTP；`api/` 不写业务；`core/config.py` 是路径与上限的唯一来源（`/api/guide` 解说页读的就是它，所以文档不会和代码脱节）。

---

## ✨ 核心功能

### 1. 数据解析与统计

| 统计维度 | 说明 |
|---------|------|
| 消息数量 | 统计双方消息总数，计算发送比例 |
| 表情包数量 | 检测 `[emoji]` 格式表情 |
| 图片数量 | 检测 `[图片]` 标记 |
| 连续消息数 | 分析消息连续发送的最大 streak |
| 语音/通话记录 | 检测通话行为并施加惩罚系数 |

### 2. 算法评估系统

五个维度各自先换算成 **−1 ~ +1 的相对值**（这一项你比对方重多少），加权求和后过 logistic 曲线映射到 0–100 分：

```
Z_Total = 0.25·SSDT + 0.20·PFI + 0.20·PLD + 0.15·EPEG + 0.20·CONV
score   = 100 / (1 + e^(−5.0 × (Z_Total − 0.05)))      # 出现语音/通话记录再 ×0.95
```

| 维度 | 含义 |
| --- | --- |
| SSDT | 连续发送倾向：你有没有连着发消息不给对方插话机会 |
| PFI | 自我中心指数：「我 / 俺」相对「我们 / 咱们」的使用密度 |
| PLD | 低姿态语言密度：道歉、语气词、犹豫词与问号的占比 |
| EPEG | 情感表达差：情绪词与感叹号数量的双方对数差 |
| CONV | 对话衔接度：接话时是否复用对方上一句里的连接词 |

结果页上还会列出五项原始比率（消息数 / 表情 / 图片 / 字数 / 连发），它们**只作展示，不参与评分**。

### 3. AI 与算法怎么结合

勾选云端后，大模型会读其中一段对话，给出「是否处于低位 + 类型 + 0–1 指数」，然后按判决树与算法分结合：

- 算法分 **≥ 60** → 直接判小丑（不必等 AI）
- **45 – 60** → 由 AI 的意见决定
- **< 45** → 判为清醒

不勾选云端时退化为纯算法（`score > 50` 判小丑）。两者是**判决树**关系，不是早期版本那种「算法分 × AI 分」的乘积。

### 4. 情感类型

四种类型，取自五维里数值最高的那一项：连续发送→**幻恋型**，衔接度→**镜像型**，低姿态→**弄臣型**，其余→**殉道型**。每种类型带一段释义、建议与关键信号词，勾选云端时可改由 AI 判定。

### 5. 情感疏导 AI

基于聊天记录生成 200-300 字的温柔情感疏导，包含：情绪安抚与认可、问题分析与指出、2-3 条可执行建议。

---

## 🎯 判定标准

**网页版（0–100 分）** —— 五维相对值加权后过 logistic 曲线，阈值取自 `backend/app/services/report.py` 的 `LEVEL_THRESHOLDS`：

| 分数 | 判定 |
| --- | --- |
| 75 分以上 | 确诊小丑倾向 |
| 60 – 75 分 | 高度疑似 |
| 45 – 60 分 | 轻度倾向 |
| 30 – 45 分 | 基本对等 |
| 低于 30 分 | 清醒玩家 |

**桌面版 `legacy/desktop/v5.py`** —— 和网页版是**同一套**口径（同样的五维 Z 指标、中点 0.05、斜率 5.0 与权重，分数同为 0–100 分），只有判决树的写法略有差别：桌面版直接输出「小丑 / 清醒」，网页版额外把分数分成下面五档。真正过时的「比率制」属于更早的 `v1.py` / `v3.py` / `v4.x`，那些代码已随 `archive/` 一并删除，仓库里再也找不到。

网页版判定区间与五维权重的唯一来源是代码本身（`backend/app/services/analyzer.py` 的 `METRIC_WEIGHTS`、`backend/app/services/report.py` 的 `LEVEL_THRESHOLDS`），「使用说明」页读的也是这份数据。

---

## 🧪 测试与检查

```bash
make test                 # 等价于 cd backend && ../.venv/bin/python -m pytest
make lint                 # ruff check backend
```

测试全部走 `TestClient`，档案库指向临时目录，不会碰你本机的真实档案。`pytest` 的 `pythonpath` 在 `backend/pyproject.toml` 里配好，测试文件直接 `from app.main import app`。

---

## 🎓 课程学习收获

通过本项目，我们学习并实践了：

- ✅ **数据结构**：列表、元组、字典的操作
- ✅ **文件 I/O**：Excel 文件读取 (pandas)
- ✅ **网络请求**：HTTP 客户端调用 AI API
- ✅ **接口设计**：REST 路由、请求校验、SSE 流式响应
- ✅ **工程分层**：前后端分离、服务分层、配置集中、CI 自动化
- ✅ **算法设计**：多维度评分体系构建

---

## 🔐 提交前检查（安全）

本仓库公开，请勿把下面这些东西提交上来：

- **API Key**：统一配置只从 `.env` 或进程环境变量读取。`.env` 本身已被忽略，但仍要确认它没有被 `git add -f` 强制加进来；也绝不要写进 `analyzer.py` 或用 `os.getenv("X", "sk-真实Key")` 这种带默认值的写法——它看起来像占位符，其实是把密钥提交了。分发打包时若把 `.env` 一起给出，请走私下渠道，不要附在公开压缩包里。
- **真实聊天记录**：`data/samples/test1.xls` 是真实私人对话，已在 `.gitignore` 中排除，只在本地保留。要演示请用仓库里的虚构样例或内置 Demo。
- **联系人档案**：`data/private/` 存的是加密档案库与密钥，已排除。备份时两个文件要一起带走。
- **商业音乐与配图**：`assets/music/` 与 `assets/pictures/` 里的内容不入库，克隆后请自备同名文件；缺少时程序照常运行，只是没有配乐与配图。（首页那张思源湖画卷用的是 `frontend/img/` 里的成品图，`assets/pictures/交大思源湖.png` 只是它的原图，缺了不影响网页显示。）

改完这类内容记得检查一下：

```bash
git diff --cached | grep -nE "sk-[A-Za-z0-9_-]{10,}"   # 只看有没有提交密钥
git status --ignored --short | head                     # 看有没有该忽略却被跟踪的文件
```

更稳妥的做法是装一个 `gitleaks` 或 `detect-secrets` 的 pre-commit 钩子，并打开 GitHub 仓库的 push protection。

> 如果密钥曾经被提交过，**吊销并重新生成**才是真正的止损；删文件、改历史都只是补救。

---

## 📚 更多文档

- [联系人档案使用教程与实验限制](docs/PROFILES.md)
- [技术文档：实现细节、隐私边界与已知限制](docs/TECHNICAL.md)

---

## 🤝 贡献与反馈

欢迎提交 Issue 或 Pull Request！

---

## 📜 许可证

本项目仅用于课程学习交流，如有不妥请联系删除。

仓库不包含第三方音乐与图片文件；若你自行加入受版权保护的内容，请自行确认使用许可。

---

<div align="center">

**Made with ❤️ for Engineering 101 Course**

*小丑指数仅供参考，感情问题还需真诚沟通*

</div>
