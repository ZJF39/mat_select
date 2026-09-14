"""MatSelect 桌面启动器（同时是 PyInstaller 打包入口）。

职责：在本机起一个 HTTP 服务（FastAPI + SQLite），并自动打开浏览器。
双击 exe 即为「本机使用」，无需手工敲命令。

用法：
    源码运行：python launcher.py [--port 8100] [--no-browser]
    打包运行：MatSelect.exe       [--port 8100] [--no-browser]

停止：在本控制台窗口按 Ctrl+C，或直接关闭窗口。
"""
from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import webbrowser

BANNER = r"""
  __  __      _   ___           _
 |  \/  |__ _| |_/ __| ___ ___| |_
 | |\/| / _` |  _\__ \/ -_) -_)  _|
 |_|  |_\__,_|\__|___/\___\___|\__|   v1.0.0
 汽车材料选型知识库 · 本机运行
"""


def _free_port(preferred: int) -> int:
    """从 preferred 起找一个可用端口（避免与已占用端口冲突）。"""
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise SystemExit(f"端口 {preferred}~{preferred + 19} 均被占用，请用 --port 指定其它端口。")


def _open_browser_when_ready(url: str) -> None:
    """轮询健康检查，服务就绪后再打开浏览器（避免打开到 404 白页）。"""
    import urllib.request

    for _ in range(80):
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1) as resp:
                if resp.status == 200:
                    webbrowser.open(url)
                    return
        except Exception:  # noqa: BLE001 - 未就绪时继续轮询
            time.sleep(0.5)
    print(f"[launcher] 服务未在预期时间内就绪，请手动在浏览器打开 {url}")


def main() -> None:
    parser = argparse.ArgumentParser(description="MatSelect 本机启动器")
    parser.add_argument("--port", type=int, default=int(os.environ.get("API_PORT", "8100")),
                        help="监听端口（默认 8100，被占用时自动顺延）")
    parser.add_argument("--no-browser", action="store_true", help="启动后不自动打开浏览器")
    args = parser.parse_args()

    if os.name == "nt":
        try:
            os.system("title MatSelect 汽车材料选型知识库")
        except Exception:  # noqa: BLE001
            pass

    from app.core.config import APP_VERSION, DATA_DIR, DB_PATH, FROZEN

    port = _free_port(args.port)
    host = "127.0.0.1"
    url = f"http://{host}:{port}"

    print(BANNER)
    print(f"  版本      : {APP_VERSION}")
    print(f"  运行模式  : {'打包运行（exe）' if FROZEN else '源码运行'}")
    print(f"  数据目录  : {DATA_DIR}")
    print(f"  数据库    : {DB_PATH}")
    print(f"  访问地址  : {url}")
    print("  停止服务  : 本窗口按 Ctrl+C，或直接关闭窗口")
    print()

    if not args.no_browser:
        threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()

    import uvicorn

    from app.main import app

    try:
        uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)
    except KeyboardInterrupt:
        print("\n[launcher] 已停止。")
    except Exception as exc:  # noqa: BLE001
        print(f"\n[launcher] 启动失败：{type(exc).__name__}: {exc}")
        print("[launcher] 若为端口占用，请用 --port 换一个端口重试。")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
