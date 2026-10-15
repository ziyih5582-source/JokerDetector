# 局域网共享模式启动器（手动触发，端口固定 8000）。

"""局域网共享模式启动器（手动触发，端口固定 8000）。

默认的 start.bat 只监听 127.0.0.1，仅本机可访问。
本脚本把服务绑到 0.0.0.0，并把本机局域网 IP 加进 Host 白名单，
让同一个热点/路由器下的同学用 http://<本机IP>:8000/ 访问。

用法：
    python scripts/start_lan.py            # 自动探测本机局域网 IP
    python scripts/start_lan.py 10.0.0.5   # 手动指定要放行的 IP
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
PORT = 8000

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def detect_lan_ip() -> str:
    """探测本机在局域网中的 IPv4 地址（不会真的发包）。"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        finally:
            s.close()
    except OSError:
        pass
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return ""


def firewall_rule_exists() -> bool:
    try:
        out = subprocess.run(
            ["netsh", "advfirewall", "firewall", "show", "rule",
             "name=JokerDetector 8000"],
            capture_output=True, text=True,
            check=False,
        )
        return out.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def main(argv):
    lan_ip = (argv[0].strip() if argv else "") or detect_lan_ip()

    print("=" * 56)
    print("  交心 · 思源湖研究所  —— 局域网共享模式")
    print("=" * 56)
    print(f"  监听：0.0.0.0:{PORT}（同网段的设备都能连）")
    if lan_ip:
        print(f"  同学请用浏览器打开：http://{lan_ip}:{PORT}/")
    else:
        print("  未能自动探测本机 IP，请用 ipconfig 查到 IPv4 地址后手动访问。")
    print(f"  本机自己仍可用：http://127.0.0.1:{PORT}/")
    print()
    print("  提示：需要同学与你连同一个热点 / 路由器。")
    if not firewall_rule_exists():
        print("  若同学连不上，多半是防火墙拦截，请用【管理员】PowerShell 执行一次：")
        print('    netsh advfirewall firewall add rule name="JokerDetector 8000" '
              'dir=in action=allow protocol=TCP localport=8000')
    print("  按 Ctrl+C 停止服务")
    print("=" * 56, flush=True)

    env = dict(os.environ)
    env["PYTHONPATH"] = str(BACKEND)
    env["JOKER_HOST"] = "0.0.0.0"
    env["JOKER_PORT"] = str(PORT)
    # 放开 Host 校验：本机地址 + 探测到的局域网 IP（探测失败就放开全部）
    env["JOKER_ALLOWED_HOSTS"] = lan_ip if lan_ip else "*"
    env.setdefault("PYTHONIOENCODING", "utf-8")

    os.chdir(BACKEND)
    try:
        subprocess.run(
            [sys.executable, "-m", "uvicorn", "app.main:app",
             "--host", "0.0.0.0", "--port", str(PORT)],
            env=env,
            check=False,
        )
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main(sys.argv[1:])
