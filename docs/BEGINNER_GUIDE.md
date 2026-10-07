# JokerDetector 小白操作手册（Windows + Git Bash）

你已有 Git Bash，不必再安装 GitHub Desktop。本手册从下载完整项目讲到应用朗读更新包、启动、使用、修改和上传。网站当前名称是「交心 · 思源湖研究所」，代码位于 backend/ 与 frontend/。

命令逐行执行，等上一条结束再继续；有报错先停在那一步。以下全部是 Git Bash 命令，路径用正斜杠 /，不要混用 PowerShell 语法。

## 1. 需要什么软件

| 软件或服务 | 用途 | 是否需要 |
| --- | --- | --- |
| Git / Git Bash | 下载仓库、记录修改和上传；Git Bash 是输入命令的窗口 | 已装即可 |
| GitHub 账号 | 上传时登录获授权的账号，先接受协作者邀请 | 需要 |
| VS Code | 打开项目文件夹和编辑代码 | 推荐，也可用其他编辑器 |
| Python 3.10+ | 运行后端 | 需要，推荐 3.12 |
| GitHub Desktop | 用按钮替代部分 Git 命令 | 可选 |
| Node.js 22 | 运行朗读自动测试 | 日常运行不需要 |

公开仓库能下载，不代表当前账号能上传。项目普通运行不需要 npm install。

## 2. 先认识 Git 的动作

| 动作 | 解释 |
| --- | --- |
| Clone / 克隆 | 第一次完整下载代码、版本历史与远程地址 |
| Pull / 拉取 | 将当前分支的远程更新带到本地 |
| Branch / 分支 | 为自己的功能建立一条工作线，方便团队合并 |
| Add / 暂存 | 选定这一次准备提交的文件 |
| Commit / 提交 | 保存一个本地版本，还没有上传 |
| Push / 推送 | 把本地提交上传到 GitHub |
| Pull Request / PR | 请团队审阅并把工作分支合进 main |

保存文件、Commit、Push 是三个动作。PR 合并后代码进入 main；已部署的网站是否同时更新，取决于部署流程。

## 3. 打开 Git Bash，检查软件

开始菜单搜索 Git Bash，普通方式打开，不需要管理员权限。输入：

```bash
git --version
python --version
```

应分别显示 Git 和 Python 版本。python 不可用时尝试 `py -3.12 --version`。都不可用则从 [Python 官网](https://www.python.org/downloads/windows/) 安装，勾选加入 PATH，随后重新打开 Git Bash。

常用命令：

```bash
pwd
ls
cd ..
```

pwd 显示当前位置，ls 查看文件，cd .. 返回上一级。Git Bash 中 D:\Projects 写成 /d/Projects，C:\Users\30125\Downloads 写成 /c/Users/30125/Downloads。路径有空格时加双引号。粘贴可用右键 Paste 或 Shift+Insert，不要把提示符 $ 一起复制进去。

## 4. 第一次下载完整项目

推荐放到用户目录，不需要 D 盘。逐行执行：

```bash
mkdir -p ~/Projects
cd ~/Projects
git clone https://github.com/ziyih5582-source/JokerDetector.git
cd JokerDetector
git status
git remote -v
```

成功后一般位于 C:\Users\你的用户名\Projects\JokerDetector。clone 会自己创建 JokerDetector 文件夹。git status 应显示 main 分支和干净工作目录，git remote -v 应指向团队仓库。

想放 D 盘：先在资源管理器新建 D:\Projects，再 `cd /d/Projects`，然后执行 clone。也可在目标文件夹右键 → 显示更多选项 → Open Git Bash here。

已经通过 clone 下载的人，直接在原项目根目录打开 Git Bash，不用再 clone。根目录应同时包含 backend、frontend、README.md。

如果此前用的是 GitHub 的 Download ZIP，那不是 Git 克隆。保留原文件夹的个人改动，另找新位置 clone，再逐项迁移；不要直接在 ZIP 文件夹 git init 上传到团队仓库。

## 5. 设置提交作者（通常只需一次）

将下面的占位内容换为自己的信息：

```bash
git config --global user.name "你的名字或GitHub用户名"
git config --global user.email "你的GitHub邮箱或noreply邮箱"
```

不想公开真实邮箱时，在 [GitHub 邮箱设置](https://github.com/settings/emails) 复制自己的 noreply 邮箱。作者设置不会替你登录，也不会赋予仓库权限。共享电脑可去掉 --global，只设置当前仓库。不要填写密码或 API Key。

## 6. 本次更新包是什么，怎么摆放

文件名：JokerDetector-speech-20261005.zip。**它包含 10 个新增/修改文件，不是完整项目，不能独立运行。** 基线为 main 提交 484877edabeb1c27cdaf52c72b998661094c56bd。

下载后在资源管理器右键「全部解压」，包内有：

```text
JokerDetector-speech-20261005.patch  ← 推荐使用的补丁
APPLY_CHANGES.md                    ← 应用与上传说明
changes/                           ← 修改后的 10 个文件
```

在本地项目旁边新建 JokerDetector-update 文件夹，将解压的 .patch 文件放进去，形成：

```text
Projects/
├── JokerDetector/                         ← clone 得到的完整项目
│   ├── backend/
│   ├── frontend/
│   └── README.md
└── JokerDetector-update/
    └── JokerDetector-speech-20261005.patch
```

不要把 changes 文件夹整体放进项目，否则会多出 JokerDetector/changes/frontend/...，网站不会使用它。也不要把 ZIP 当作代码上传到仓库。changes/ 用于查看修改后的文件或人工对照冲突。

## 7. 更新 main、创建分支、应用补丁

在完整项目根目录运行 `git status`。若有之前未提交的个人改动，先在对应工作分支整理并提交，再回来处理本次更新；不要随意删除不明文件。

工作目录干净后，逐行执行：

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/ai-report-read-aloud
git apply --check ../JokerDetector-update/JokerDetector-speech-20261005.patch
```

--check 只检查，不修改文件。没有报错并回到提示符才继续：

```bash
git apply ../JokerDetector-update/JokerDetector-speech-20261005.patch
git status
git diff --stat
```

git status 应看到 10 个新增/修改文件；git diff --stat 不包括尚未跟踪的新文件，这属正常。

如果提示 patch does not apply 或新文件已存在，先停下，检查团队版本或是否已应用，勿直接覆盖。如果分支已存在，用 git branch 核对；确认是自己上次的分支才 git switch feature/ai-report-read-aloud，不要盲目使用他人的分支。

## 8. 打开编辑器和安装依赖

VS Code → File → Open Folder → 选择整个 JokerDetector 文件夹。也可在根目录运行 `code .`；若找不到 code，用界面打开即可。改完按 Ctrl+S 保存。VS Code 底部终端若是 PowerShell，可改选 Git Bash，或继续使用外部 Git Bash。

第一次安装，仍在根目录执行：

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
```

如果只有 py 可用，将第一行改为：

```bash
py -3.12 -m venv .venv
```

.venv 是本项目的 Python 环境。直接调用其中的 Python，不需要激活环境，也不需要 Activate.ps1。等安装成功后再启动。前端无构建步骤，不用 npm install。

需要截图识别时，再装可选 OCR 依赖：

```bash
.venv/Scripts/python.exe -m pip install -r backend/requirements-ocr.txt
```

## 9. 启动、访问、停止

```bash
.venv/Scripts/python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

保持窗口开着，在浏览器打开 http://127.0.0.1:8000/。服务占着终端并不断显示日志是正常的。要输入 Git 命令，可在根目录另开一个 Git Bash 窗口；停止网站回到服务窗口按 Ctrl+C。

前端保存后刷新，缓存未更新按 Ctrl+F5；Python 修改由 --reload 自动重启。不要双击 frontend/index.html，它需要后端的 /api 和 /static 路径。

下次运行不必重新创建环境，进入项目后执行同一条 uvicorn 命令。团队更新 requirements.txt 时，再安装依赖。也可双击 scripts\start.bat，但它不带自动重载。

127.0.0.1 是本机地址，启动成功不等于公开发布。手机也不能把这个地址当作电脑地址访问；手机访问与公开部署需要另外配置。

## 10. 基础使用：先用虚构示例

**谈心分析：** 顶部进入「谈心分析」，先试「填入示例一 / 填入示例二」。自己粘贴文本时每行使用「发言者：内容」，例如：

```text
我：周末要一起去图书馆吗？
演示同学：可以，周六下午有空。
我：那两点门口见。
演示同学：好，我喜欢先在一楼找座位。
```

点「辨认说话的人」，核对我与对方的归属及处理预览。需要记档案时选择对象并确认保存；只做分析可不选档案。没配 AI 时先使用本地模式；有配置时可勾选「本次使用云端 AI」与「同时生成 AI 情感分析长文」，再点「开始分析」。长文等待较久时看页面状态，失败时看具体原因。

**人物档案：** 新建虚构联系人「演示同学」，在谈心分析里选定该档案并确认写入，导入不同示例，然后返回档案查看喜好、原文依据、冲突、确认与修正。提交前核对当前对象。时间线、阶段报告、建议跟进是 docs/PROFILE_ROADMAP.md 的后续提案，目前没有实现。

**找钓翁聊聊：** 需有效云端配置；选对象、输入问题，只有勾选档案背景时才附带档案。当前钓翁对话保存在标签页内存，刷新即消失，不是长期对话存档。

**小丑鉴定所与截图：** 鉴定所是本地娱乐分析，不使用本次长文朗读。截图需要可选 OCR 依赖，识别后先校对再分析。项目输出不等同于对真实关系或心理状态的诊断。

## 11. 配置 AI

已有 .env 时直接编辑，不要覆盖；没有时才运行：

```bash
cp .env.example .env
```

用编辑器填写服务端配置：

```env
DEEPSEEK_API_KEY=填写你有权使用的密钥
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```

地址和模型以自己的服务商实际配置为准。保存后在网页「设置」点「重新加载配置」与「测试连接」。测试会向配置平台发送固定虚构示例，产生少量用量。

GitHub 登录凭据负责上传代码，API Key 负责 AI 调用，是两种凭据。.env 只在服务端本地保留，不放进 ZIP、GitHub 或前端 JS。无 Key 时本地分析可体验，但不能生成验证朗读所需的云端长文。

## 12. 使用和检查朗读

1. 成功生成 AI 情感分析长文，结果页正文下方出现「播放朗读」。
2. 点击后听一段，再点「停止朗读」；重新播放应从头开始。
3. 长文分段连续播放，不自动播放。播放中切页、新报告、网页退到后台或关闭时应停止。
4. 手机宽度下检查按钮和状态文字；失败或无长文时不应有有效播放入口。

使用浏览器/设备 SpeechSynthesis，不新增项目 TTS API 费用，也不消耗 DeepSeek 的朗读调用。音色随设备变化，部分语音可能联网；不支持时显示说明。播放会暂停背景音乐，不生成可下载 MP3。

已通过 10 项模拟语音状态测试和桌面/手机宽度页面检查；音质需实际试听。安装 Node.js 22 后可选运行：

```bash
node --test frontend/tests/speech.test.cjs
```

后端代码未改，本次交付环境没有重跑后端全套测试；成功上传后由 GitHub Actions 执行仓库检查。

## 13. 上传本次修改：Add、Commit、Push

确认当前是自己的工作分支并看差异：

```bash
git branch --show-current
git status
git diff
```

git diff 进入长页面时按 q 退出。确认本次修改后，选择 10 个文件：

```bash
git add .github/workflows/ci.yml README.md frontend/README.md frontend/index.html frontend/css/ink.css frontend/js/ink.js frontend/js/speech.js frontend/tests/speech.test.cjs docs/BEGINNER_GUIDE.md docs/PROFILE_ROADMAP.md
git diff --cached --stat
git diff --cached
```

第一行是一条完整命令。--cached 查看真正准备提交的内容，包括新文件。确认后：

```bash
git commit -m "增加 AI 长文语音朗读及 Git Bash 上手文档"
git push -u origin feature/ai-report-read-aloud
```

第一次 push 可能打开 Git 凭据管理器/浏览器，登录获授权的 GitHub 账号。GitHub 普通密码不能直接作 Git HTTPS 密码；使用受支持的凭据管理器或令牌方式，不要把凭据发到聊天里。

成功后运行 git status、git log -1 --oneline，再在仓库网页切换到 feature/ai-report-read-aloud，确认 frontend/js/speech.js 存在。这时 main 尚未合并。

不要提交 .env、.venv/、data/private/、真实聊天和截图。补丁和 ZIP 放在项目旁边，源代码仓库里无需上传它们。

## 14. 创建 PR 与合并

打开 [团队仓库](https://github.com/ziyih5582-source/JokerDetector)，点 Compare & pull request；没有横幅时进 Pull requests → New pull request。检查 base: main，compare: feature/ai-report-read-aloud。

标题可填「增加 AI 长文语音朗读」，正文可以写：

```text
AI 情感分析长文原先只能阅读，现在正文下方增加播放/停止朗读。
使用浏览器语音，长文分段播放；换报告、切页和页面退到后台停止。
新增 Git Bash 上手手册与档案功能后续提案。

验证：10 项朗读状态测试通过；桌面与手机宽度页面检查通过。
请在实际设备试听中文语音。后端代码未修改，本地未重跑后端全套测试。
```

点 Create pull request，等 Actions 与队友审阅。评审要求修改时，继续在同一分支编辑、Commit、Push，原 PR 会自动更新。合并由团队按权限规则决定。合并后本机还要拉取 main；线上更新取决于部署。

## 15. 以后开发与接收队友更新

工作目录干净后，为下一项功能更新 main 并开分支：

```bash
git switch main
git pull --ff-only origin main
git switch -c feature/profile-timeline
```

分支名只是下一项档案时间线工作示例，每项功能取清楚的名字。编辑、验证后，仅添加实际修改的相关文件，例如：

```bash
git status
git diff
git add backend/app/services/profiles.py backend/tests/test_profiles.py
git diff --cached
git commit -m "完善人物档案时间线"
git push -u origin feature/profile-timeline
```

同一分支第一次 push 后，以后可直接 git push。没有修改示例文件时，不要照抄 add。推送后创建 PR，合并后回 main 拉取。

正在功能分支上开发但 main 已更新时，先提交当前工作，再：

```bash
git fetch origin
git merge origin/main
```

合并后验证，再 push。出现冲突时与相应负责人确认最终内容，不要全部保留自己、强推或清空工作目录。pull --ff-only 停止是提醒历史分歧，不是让你加 --force。

## 16. 档案负责人看哪些文件

| 路径 | 用途 |
| --- | --- |
| backend/app/services/profiles.py | 提取、加密存储、追加合并、冲突、修正 |
| backend/app/services/unified.py | 分析与档案更新协调 |
| backend/app/api/routes/profiles.py | 档案 HTTP 接口 |
| backend/app/schemas/profiles.py | 输入结构和校验 |
| backend/app/api/routes/fisherman.py | 给钓翁选档案背景 |
| frontend/js/ink.js | 档案页面交互，目前与其他页面共用 |
| frontend/index.html、frontend/css/ink.css | 页面结构和样式 |
| backend/tests/test_profiles.py、test_unified.py | 档案与融合测试 |
| frontend/js/speech.js | 本次独立朗读模块 |
| docs/PROFILE_ROADMAP.md | 档案升级提案 |

多人改 ink.js 容易冲突，先确认负责区域；后续可拆成档案模块。后端修改时检查：

```bash
.venv/Scripts/python.exe -m pip install pytest ruff
.venv/Scripts/python.exe -m pytest -c backend/pyproject.toml backend/tests
.venv/Scripts/python.exe -m ruff check --config backend/pyproject.toml backend
```

可选依赖未装时，部分测试跳过与失败不同。测试之外仍要走一遍实际网页流程。

## 17. 常见问题

| 现象 | 处理 |
| --- | --- |
| not a git repository | 位置不对或是 ZIP；pwd、ls，进入真正 clone 的根目录 |
| destination path already exists | 已有同名文件夹；若是真克隆就进入，若是个人文件夹则换新位置，勿随意删除 |
| No such file or directory | 检查当前位置/文件名；路径用 /c/、/d/，有空格加引号 |
| python 找不到 | 检查安装/PATH，重新开窗口，或用 py -3.12 |
| .venv/Scripts/python.exe 找不到 | 确认在根目录，且环境已创建成功 |
| app.main 导入失败 | 回根目录，用带 --app-dir backend 的启动命令 |
| 浏览器连接失败 | 服务还开着吗？地址是 http://127.0.0.1:8000/ 吗？ |
| 8000 被占用 | 停止自己旧服务，或改 --port 8001 并访问 8001 |
| patch does not apply | 停止应用，检查版本或重复应用，不直接覆盖 |
| Author identity unknown | 设置 user.name、user.email |
| nothing to commit | 检查文件是否保存，git status、git log -1 查看 |
| 403 / Permission denied / authentication failed | 核对登录账号、邀请、写入权限和分支规则，不代表代码错 |
| non-fast-forward / rejected | 远程已有新提交，先核对并合并，不强推 |
| 页面是旧的 | Ctrl+F5，核对运行的是哪份项目，是否多套了 changes 目录 |
| 没有朗读按钮 | 补丁已应用吗？长文成功生成了吗？浏览器支持语音吗？ |
| 朗读无声 | 检查系统音量、中文语音，保持前台并手动点播放 |

档案位于 data/private/。备份前停止服务，同时备份 profiles.sqlite3 与 profile.key，二者不上传到团队仓库。当前仍是单人实验版，公开多人部署需要另外完成账号和用户隔离。

## 18. 不要混淆三个位置和两种包

GitHub 仓库是共享代码；clone 的本地 JokerDetector 是你编辑运行的副本；服务器上的项目才对外提供网站。本次朗读 ZIP 只是更新包，完整项目必须先 clone。

操作顺序：clone → main 拉取 → 功能分支 → 检查并应用补丁 → 安装/启动 → 验证 → add → commit → push → PR → 团队合并。

## 官方参考

- [GitHub：克隆仓库](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository)
- [GitHub：推送提交](https://docs.github.com/en/get-started/using-git/pushing-commits-to-a-remote-repository)
- [GitHub：创建 PR](https://docs.github.com/en/pull-requests/how-tos/create-pull-requests/creating-a-pull-request)
- [GitHub：凭据缓存](https://docs.github.com/en/get-started/git-basics/caching-your-github-credentials-in-git)
- [MDN：SpeechSynthesis](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis)
