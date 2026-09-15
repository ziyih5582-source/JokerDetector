# 旧版前端（方框卡片风）· 归档

这里是重写前的前端：深色渐变 + 纯色卡片 + Chart.js 图表 + 独立的两套页面。项目已改用**水墨风统一工作台**，旧界面整体保留在本目录，没有删除。

| 旧文件 | 作用 | 新位置 |
| --- | --- | --- |
| `index.html` 之外的 `profiles.html` | 独立的「联系人档案」页 | 功能并入 `web/frontend/index.html` 的「名册」视图 |
| `css/style.css` | 深色卡片主题（含大量方框、渐变、发光） | `web/frontend/css/ink.css` |
| `css/profiles.css` | 档案页主题 | 同上 |
| `js/app.js` | 聊天分析主逻辑（含粒子背景、CDN 图表） | `web/frontend/js/ink.js` |
| `js/charts.js` | Chart.js 雷达图 / 柱状图 | 改为手绘 SVG 墨线图，见 `js/ink.js` |
| `js/profiles.js` | 档案 CRUD 逻辑 | 并入 `js/ink.js` |

## 为什么归档

新界面不再使用 Chart.js 与 html2canvas 两个 CDN 依赖，因此页面可以启用严格 CSP（`script-src 'self'`），所有绘制都在本机完成。

旧版依赖的 API 全部保留，未删除：

- `POST /api/analyze/demo/{id}`、`POST /api/analyze/upload`、`GET /api/demos`、`GET /api/joker_types`、`POST /api/config`、`POST /api/config/test`、`GET /api/music`
- `/api/profiles/*` 全部接口

如需回退旧界面：把本目录的文件放回 `web/frontend/`（`profiles.html` 放回 `web/frontend/`），并让 `main.py` 的 `/profiles` 指回 `profiles.html`。
