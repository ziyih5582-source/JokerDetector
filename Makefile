# Joker Detector · 常用命令
# 前后端分离：backend/ 是 FastAPI 服务，frontend/ 是纯静态站点。

PY ?= .venv/bin/python
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: help install run dev test lint fmt clean

help:  ## 显示可用命令
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:  ## 安装后端依赖（含开发用 pytest / ruff）
	$(PY) -m pip install -r backend/requirements.txt
	$(PY) -m pip install pytest ruff httpx

run:  ## 启动后端（生产式，无热重载）
	$(PY) -m uvicorn app.main:app --app-dir backend --host $(HOST) --port $(PORT)

dev:  ## 启动后端（改代码自动重载）
	$(PY) -m uvicorn app.main:app --app-dir backend --host $(HOST) --port $(PORT) --reload

test:  ## 运行后端测试
	cd backend && ../$(PY) -m pytest

lint:  ## 静态检查（ruff）
	$(PY) -m ruff check backend

fmt:  ## 自动格式化（ruff）
	$(PY) -m ruff check --fix backend

clean:  ## 清理缓存
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache backend/.pytest_cache
