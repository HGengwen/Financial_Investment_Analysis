"""pytest 全局配置：网络不可用环境下防止测试无限挂起。

本仓库测试依赖的 akshare 等数据源在发起 requests 请求时未显式设置 timeout。
在此环境下存在两条导致无限阻塞的路径（TLS 握手阶段）：

1. ``requests`` 未传 ``timeout`` 时，urllib3 使用连接池默认 timeout（None），
   底层 ``socket.create_connection(..., None)`` 会显式执行 ``sock.settimeout(None)``，
   覆盖 ``socket.setdefaulttimeout`` 设置的默认值；
2. urllib3 仅在 TLS 握手完成、发送请求之前才把请求级 timeout 写到 socket 上，
   因此“新建连接 + 握手被网络截断”时，即使显式传入 ``requests.get(timeout=...)``
   也无法让握手超时，会无限阻塞在 ``ssl.do_handshake``。
   （pytest-timeout 的 ``--timeout-method=thread`` 无法打断 C 层阻塞调用。）

解决方式：monkeypatch ``socket.socket.settimeout``，**拒绝将超时清零**。
任何库试图 ``settimeout(None)`` 都会被强制替换为固定兜底超时，
使 TLS 握手/读操作在超时后抛出 ``TimeoutError/SSLError``，
由各测试文件已有的 ``except Exception -> skipTest`` 逻辑捕获并跳过。
"""

import os
import socket

# 兜底超时（秒）：任何被清零的 socket 超时都会退化为该值。
_DEFAULT_SOCKET_TIMEOUT = 20.0

_ORIG_SETTIMEOUT = socket.socket.settimeout


def _guarded_settimeout(sock, value):
    """拦截将 socket 超时清零的调用，替换为固定兜底超时。"""
    if value is None:
        value = _DEFAULT_SOCKET_TIMEOUT
    return _ORIG_SETTIMEOUT(sock, value)


socket.socket.settimeout = _guarded_settimeout

# 将本目录注入 PYTHONPATH：子进程（CLI 测试经 subprocess 启动）继承环境变量后，
# 会通过 sitecustomize.py 获得同样的 socket 超时兜底，避免子进程无限挂起。
_tests_dir = os.path.dirname(os.path.abspath(__file__))
_env_paths = os.environ.get("PYTHONPATH", "").split(os.pathsep)
if _tests_dir not in _env_paths:
    os.environ["PYTHONPATH"] = os.pathsep.join([_tests_dir] + [p for p in _env_paths if p])