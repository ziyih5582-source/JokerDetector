# -*- coding: utf-8 -*-
"""局域网共享模式的回归测试。

覆盖：
- config.host() / port() / allowed_hosts() 会读取 JOKER_* 环境变量；
- TrustedHost 中间件按 config.allowed_hosts() 放行，默认只允许本机，
  设置了 JOKER_ALLOWED_HOSTS 后能放行局域网 IP。
"""

import pytest
from fastapi.testclient import TestClient

from app.core import config
from app.main import create_app


LAN_IP = "10.181.32.168"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """每个用例前后清掉 JOKER_* 环境变量，避免互相污染。"""
    for key in ("JOKER_HOST", "JOKER_PORT", "JOKER_ALLOWED_HOSTS"):
        monkeypatch.delenv(key, raising=False)
    yield


# ------------------------------------------------------------ config 读取

def test_default_host_and_port(monkeypatch):
    assert config.host() == "127.0.0.1"
    assert config.port() == 8000


def test_host_and_port_from_env(monkeypatch):
    monkeypatch.setenv("JOKER_HOST", "0.0.0.0")
    monkeypatch.setenv("JOKER_PORT", "9001")
    assert config.host() == "0.0.0.0"
    assert config.port() == 9001


def test_invalid_port_falls_back(monkeypatch):
    monkeypatch.setenv("JOKER_PORT", "not-a-number")
    assert config.port() == 8000


def test_allowed_hosts_default_local_only(monkeypatch):
    hosts = config.allowed_hosts()
    assert hosts == ["localhost", "127.0.0.1", "[::1]", "testserver"]
    assert LAN_IP not in hosts


def test_allowed_hosts_appends_lan_ip(monkeypatch):
    monkeypatch.setenv("JOKER_ALLOWED_HOSTS", LAN_IP)
    hosts = config.allowed_hosts()
    assert LAN_IP in hosts
    # 仍然保留本机白名单
    assert "127.0.0.1" in hosts


def test_allowed_hosts_supports_multiple(monkeypatch):
    monkeypatch.setenv("JOKER_ALLOWED_HOSTS", f"{LAN_IP}, 192.168.1.20 ,")
    hosts = config.allowed_hosts()
    assert LAN_IP in hosts
    assert "192.168.1.20" in hosts


# ------------------------------------------------------------ 中间件实际放行

def test_lan_host_rejected_by_default(monkeypatch, tmp_path):
    """默认（未开局域网）时，局域网 Host 应被 TrustedHost 拒绝 400。"""
    monkeypatch.setenv("JOKER_PROFILE_DIR", str(tmp_path))
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/health", headers={"Host": f"{LAN_IP}:8000"}).status_code == 400
        assert client.get("/api/health", headers={"Host": "127.0.0.1:8000"}).status_code == 200


def test_lan_host_allowed_when_configured(monkeypatch, tmp_path):
    """设置 JOKER_ALLOWED_HOSTS 后，局域网 Host 应能正常访问。"""
    monkeypatch.setenv("JOKER_PROFILE_DIR", str(tmp_path))
    monkeypatch.setenv("JOKER_ALLOWED_HOSTS", LAN_IP)
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/health", headers={"Host": f"{LAN_IP}:8000"}).status_code == 200
        # 首页在本机 Host 下也照常
        assert client.get("/", headers={"Host": "127.0.0.1:8000"}).status_code == 200
        # 其它未授权 Host 仍被拒
        assert client.get("/api/health", headers={"Host": "evil.invalid"}).status_code == 400
