# 后端 · Joker Detector API

FastAPI 服务：聊天记录分析与联系人档案。可以独立部署，不依赖仓库里其它目录（前端只是静态文件，由 `main.py` 顺手挂载）。

## 运行

```bash
# 在 backend/ 目录下
python -m app.main
# 或在项目根目录
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

依赖：`pip install -r requirements.txt`（Python 3.10+）。

## 分层

| 目录 | 职责 | 不该做的事 |
| --- | --- | --- |
| `app/core/` | 配置、路径、中间件、错误映射 | 不写业务逻辑 |
| `app/schemas/` | 请求 / 响应模型 | 不访问数据库 |
| `app/services/` | 分析引擎、档案库、格式化、融合流程 | 不出现 `APIRouter` / 装饰器 |
| `app/api/` | 路由与进程级单例 | 不自己实现业务规则 |

路径、版本与各项上限只在 `app/core/config.py` 里定义一次；`/api/guide` 的 `limits` 与各接口的校验读的是同一份常量。

## 接口一览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查、AI 与音乐是否可用 |
| GET | `/api/config` | 统一 AI 配置状态（不回传密钥） |
| POST | `/api/config/reload` | 重新读取 `.env` / 环境变量 |
| POST | `/api/config/test` | 用固定虚构样本验证调用 |
| GET | `/api/demos` | 内置示例列表 |
| POST | `/api/analyze/demo/{id}` | 用示例走统一流程 |
| POST | `/api/analyze/upload` | 上传 Excel 分析 |
| POST | `/api/analyze/unified` | 融合入口：情感分析 + 档案更新 |
| GET | `/api/guide` | 解说页数据源：阈值、权重、指标、上限 |
| GET | `/api/joker_types` | 类型定义 |
| GET/POST | `/api/profiles/contacts` | 名册查询与新建 |
| GET/DELETE | `/api/profiles/contacts/{id}` | 单个档案 |
| PATCH | `/api/profiles/contacts/{id}/facts/{fact_id}` | 条目的确认 / 修正 / 删除 |
| POST | `/api/profiles/preview` | 脱敏与角色归一化预览 |
| POST | `/api/profiles/parse` | 解析 Excel 为消息数组 |
| POST | `/api/profiles/contacts/{id}/analyze` | 保留的旧路径，内部走统一流程 |
| GET | `/api/fisherman/status` | 问钓翁的 AI 状态 |
| POST | `/api/fisherman/context` | 预览将发送的档案背景（所见即所发） |
| POST | `/api/fisherman/chat` | SSE 流式对话 |

## 数据与隐私

- 聊天原文只在请求内使用，不落盘；只有勾选云端选项时才发送脱敏片段。
- 联系人档案存在项目根的 `data/private/`（可用环境变量 `JOKER_PROFILE_DIR` 覆盖），脱敏后加密；密钥与数据库要一起备份。
- 服务假定只在本机运行：只接受本机 Host，拒绝跨站写请求，页面走严格 CSP。

## 测试

```bash
pytest            # 在 backend/ 下运行；pythonpath 已在 pyproject.toml 配好
ruff check .      # 静态检查
```
