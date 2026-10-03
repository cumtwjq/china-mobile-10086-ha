"""Run a short, local proxy session and copy the verified request templates."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import time
import uuid

from export_capture import main as copy_request
from local_capture import READY_MARKER
from vault import VAULT


ROOT = Path(__file__).resolve().parent
PORT = 8082
MITMDUMP = ROOT / "bin" / "mitmdump.exe"


def _port_in_use() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.5)
        return connection.connect_ex(("127.0.0.1", PORT)) == 0


def _show_ipv4_addresses() -> None:
    command = (
        "Get-NetIPAddress -AddressFamily IPv4 | "
        "Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | "
        "Select-Object -ExpandProperty IPAddress"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    addresses = sorted(set(result.stdout.split()))
    if addresses:
        print("本机 IPv4 地址：" + "、".join(addresses))


def main() -> int:
    if os.name != "nt" or not MITMDUMP.is_file():
        print("缺少 Windows 版 mitmdump.exe。")
        return 1
    if _port_in_use():
        print(f"端口 {PORT} 已被占用，请关闭上一次的抓包窗口。")
        return 1
    READY_MARKER.unlink(missing_ok=True)
    session_id = uuid.uuid4().hex
    environment = {**os.environ, "CHINA_MOBILE_CAPTURE_SESSION": session_id}
    _show_ipv4_addresses()
    print(f"1. iPhone 连接电脑热点，在当前 Wi-Fi 的手动代理中填电脑热点地址，端口 {PORT}。")
    print("2. 首次使用：代理启动后用 Safari 打开 http://mitm.it，选择 iOS 下载描述文件。")
    print("   到 iPhone“设置 → 通用 → VPN 与设备管理”安装描述文件。")
    print("   再到“设置 → 通用 → 关于本机 → 证书信任设置”，开启 mitmproxy 证书的完全信任。")
    print("   若此前已安装并信任同一台电脑的证书，可跳过安装，无需删除旧证书。")
    print("   若 mitm.it 打不开，请确认输入的是 http://、代理地址和端口正确，并稍等代理启动。")
    print("3. 打开中国移动10086服务号主页并刷新，等待话费、流量、通话三个请求。")
    print("只读请求会在本机加密保存；按 Ctrl+C 可取消，最长等待 15 分钟。")
    process = subprocess.Popen(
        [str(MITMDUMP), "-q", "-s", str(ROOT / "local_capture.py"), "--listen-host", "0.0.0.0", "--listen-port", str(PORT)],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        deadline = time.monotonic() + 15 * 60
        while time.monotonic() < deadline:
            if READY_MARKER.is_file():
                marker = json.loads(READY_MARKER.read_text(encoding="utf-8"))
                if (
                    marker.get("session") != session_id
                    or VAULT.stat().st_mtime_ns != marker.get("capture_file_modified_ns")
                ):
                    print("抓取标记与本次加密文件不一致，本次没有复制旧请求。")
                    return 1
                print("已抓齐三个只读请求并加密保存。")
                copy_request()
                print("到 HA 的中国移动10086集成配置页粘贴剪贴板内容。")
                print("完成后把 iPhone Wi-Fi 代理改回关闭，并复制普通文字覆盖剪贴板。")
                return 0
            if process.poll() is not None:
                print("代理启动失败，请检查端口或工具文件。")
                return 1
            time.sleep(0.5)
        print("等待超时，请确认主页已刷新且三个数据卡片均加载。")
        return 1
    except KeyboardInterrupt:
        print("已取消抓取。")
        return 1
    finally:
        if process.poll() is None:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
