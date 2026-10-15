# 小丑看板 · 说明（右上角小丑 + 小丑值 + 六维依据）

> 一句话：**鉴定所回答「是不是小丑」，看板回答「这个分是怎么来的」。**
> 判定仍然只跑本地六征，不调用云端 AI；看板不做诊断，也不替你决定任何事。

## 1. 它长什么样

- 整站右上角一个**小丑头像**（纯 SVG，不需要任何图片资源，会轻轻晃、会眨眼）。
- 头像**上面是「小丑值」小牌**：分数 + 等级（确诊小丑 / 高度疑似 / 轻度倾向 / 基本对等 / 清醒玩家），颜色随等级变化。
- 点一下头像展开**面板**：六维分数条、权重与本项贡献、每维的统计口径、命中维度的**依据原句**、一句总评、下一步两件事，以及「直接在这里粘一段聊天，立刻量一量」。
- 宽屏贴右上角；窄屏自动顺到页眉下方；手机上收成底部抽屉；右上角箭头可**收起**（状态记在本机）。

## 2. 数据从哪来

```
导入聊天记录（Excel / 长截图 OCR / 粘贴「发言人：内容」）
        │  统一成 [{speaker, content}, ...]（与鉴定所同一份规范化格式）
        ▼
POST /api/joker/board  →  backend/app/services/joker_board.py
        │  · 复用 JokerAnalyzer.detect_joker_profile（本地六征，纯规则，不联网）
        │  · 每维补上：0~100 分、权重、本项贡献、依据原句
        ▼
看板渲染（localStorage 缓存，跨视图常驻，开鉴后实时更新）
```

两条入口：

1. **小丑鉴定所开鉴** → `frontend/js/ink.js` 在 `renderJokerDialog()` 里调 `window.ClownBoard.publish(result, {messages, self, other})`：先用返回值即时更新分数，再向 `/api/joker/board` 补齐依据原句。
2. **看板面板速测** → 粘一段 `我：在忙吗` 形式的文本，前端用 `parseChatText()` 校验成两个人，再打同一个接口。

## 3. 六个维度与权重

权重写在 `backend/app/services/joker_board.py` 的 `SIGN_WEIGHT`，与前端 `clown-board.js` 的兜底表一致；**六个值相加为 1**。

| 维度 | 键 | 权重 | 判定依据（与鉴定所同一套关键词） |
| --- | --- | --- | --- |
| 单向推进 | `one_way` | 0.24 | 双方消息条数比 + 最长连发比 |
| 自我感动 | `self_moved` | 0.16 | 「我都可以 / 听你的 / 我没事 / 为了你…」+ 低姿态语言密度 |
| 幻想脑补 | `fantasy` | 0.14 | 「我在想 / 如果 / 会不会 / 梦到…」+ 连续发送倾向 |
| 边界失守 | `boundary` | 0.14 | 「只要你 / 不用管我 / 我可以等…」 |
| 不接受拒绝 | `no_accept_reject` | 0.18 | 「再等等 / 万一 / 我等你 / 我不会放弃…」+ 拒绝后继续发送比例 |
| 事后自嘲 | `self_mockery` | 0.14 | 「我不配 / 小丑 / 废物 / 丢人…」 |

- **综合小丑值** `score`：与鉴定所弹窗里的分**同一个数**（同一个引擎的返回值），保证两处不打架。
- **六征加权分** `weighted_score`：六维加权求和，用来看「问题集中在哪几维」，不替代综合小丑值。
- 权重与关键词不在看板里另写一份：关键词直接读鉴定所的 `JokerAnalyzer._SIGN_KEYWORDS`，以后有人改词表，看板的依据会跟着变。

## 4. 依据（这是本轮的重点）

- **命中的维度**才引用原句：从**你自己**发过的消息里挑出真正含关键词的那两句（`_keyword_evidence`）。
- **单向推进**引用你最长的一段连续发送（`_streak_evidence`），例如「忙完了吗 / 在吗 / 我就是个小丑，我太菜了」。
- **未命中的维度**不引用原句，只留 `detail` 里的统计口径（例如 `低姿态语言密度 PLD=+0.31`），免得看板上到处是「证据」。
- 命中了但确实没有可引用原句时（例如命中来自节奏或字数的整体统计），面板会直接写明这一点，不编造。
- 引用超过 24 个字会截断并加省略号。

## 5. 接口

`POST /api/joker/board`

```jsonc
// 请求：与 /api/analyze/joker/detect 完全一致（复用 JokerDetectInput）
{ "messages": [{ "speaker": "我", "content": "在忙吗" }], "self_speaker": "我", "other_speaker": "对方" }
```

```jsonc
// 响应（节选）
{
  "score": 68.4, "weighted_score": 46.6, "level": "high_risk", "level_label": "高度疑似",
  "is_joker": true, "type": "单向型", "hit_count": 3,
  "dimensions": [
    { "key": "one_way", "label": "单向推进", "hit": true, "score": 0.9, "points": 90,
      "weight": 0.24, "contribution": 21.6,
      "detail": "你发了 7 条，对方 2 条；最长连发 4 vs 1",
      "evidence": ["「忙完了吗」", "「在吗」"] }
  ],
  "radar": [{ "key": "one_way", "label": "单向推进", "value": 90 }],
  "summary": "六征里命中 3 项：单向推进 90、事后自嘲 80、不接受拒绝 62 最突出。",
  "next_steps": ["停三天不主动，看对方会不会来找你…"],
  "message_counts": { "self": 7, "other": 2, "total": 9 },
  "engine": "本地六征 v1 · 不调用云端 AI", "generated_at": "2026-10-15T22:34:00+08:00"
}
```

校验与鉴定所一致：两个发言者必须不同、只能是文件里实际的两个人、单次文本不超过 12 万字，否则 400。

## 6. 前端接入（两行 + 一个调用点）

```html
<link rel="stylesheet" href="/static/css/clown-board.css?v=joker-board-1.0">
<script src="/static/js/clown-board.js?v=joker-board-1.0"></script>
```

`clown-board.js` 自己会在 `DOMContentLoaded` 时把看板挂到 `<body>` 上，不需要额外容器，也不改任何现有结构；唯一需要联动的地方是 `ink.js` 的 `renderJokerDialog()` 里那一句 `window.ClownBoard.publish(result, {...})`。

对外 API：`publish(payload, context)`、`open()`、`close()`、`toggle()`、`refresh()`、`clear()`、`setCollapsed(bool)`，以及可单测的纯函数 `parseChatText` / `normalize` / `summarize` / `levelMeta` / `formatScore`。

## 7. 边界与隐私

- 判定与依据**全部在本机**完成，不调用云端 AI、不写数据库、不入档案库。
- 分数只存在浏览器 `localStorage`（键 `joker.board.v1`），换台电脑就看不见；面板里可以「清掉这块看板」。
- 看板不是心理测量、不做诊断，也不能替代心理咨询或医疗；面板底部保留了这句话。

## 8. 怎么自测

```bash
# 前端纯逻辑（不需要 npm）
node --test frontend/tests/clown-board.test.cjs

# 后端（在 backend/ 目录）
pytest tests/test_joker_board.py -q

# 装不上依赖也能跑引擎自检（用占位模块顶住 httpx / openai / cryptography）
python 交付说明/tools/verify_joker_board.py
```

浏览器里看效果：启动服务后打开 <http://127.0.0.1:8000/>，首页即应出现右上角小丑；去「小丑鉴定所」粘示例开一次鉴，右上角分数与面板会立刻更新。

## 9. 之后可以接着做

- 把 `radar` 画成六边形雷达图（数据接口已经给出）。
- 在 `localStorage` 里存历史分数，做「小丑值曲线」。
- 面板里的速测支持直接拖入 Excel / 长截图（复用鉴定所的 OCR 与解析）。
