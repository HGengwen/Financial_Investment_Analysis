"""Python 站点自定义初始化：网络不可用环境下防止 socket 无限阻塞。

本文件会被 Python 解释器任意进程（含 pytest 主进程与 CLI 子进程）自动加载，
前提是 ``tests/`` 目录位于 ``sys.path``（通过 conftest 将本目录注入
``PYTHONPATH`` 环境变量，子进程继承后自动生效）。

背景：akshare 等数据源的 HTTP 调用未显式设置 timeout，urllib3 使用池级
默认 timeout（None），底层 ``socket.create_connection(..., None)`` 会显式
执行 ``sock.settimeout(None)``，覆盖 ``socket.setdefaulttimeout``；
且 urllib3 仅在 TLS 握手完成、发送请求前才把请求级 timeout 写到 socket，
因此“新建连接 + 握手被网络截断”时请求级 timeout 无效，``ssl.do_handshake``
会无限阻塞。

解决方式：monkeypatch ``socket.socket.settimeout``，拒绝将超时清零，
任何 ``settimeout(None)`` 都被强制替换为固定兜底超时，
使阻塞调用在超时后抛出 ``TimeoutError/SSLError`` 异常，由上层调用方
（工具的错误处理或测试的 skipTest）正常捕获。
"""

import socket

# 兜底超时（秒）：任何被清零的 socket 超时都会退化为该值。
_DEFAULT_SOCKET_TIMEOUT = 20.0

_ORIG_SETTIMEOUT = socket.socket.settimeout


def _guarded_settimeout(sock, value):
    """拦截将 socket 超时清零的调用，替换为固定兜底超时。"""
    if value is None:
        value = _DEFAULT_SOCKET_TIMEOUT
    return _ORIG_SETTIMEOUT(sock, value)


# 幂等保护：模块仅加载一次，重复 import 无副作用。
if getattr(socket.socket, "settimeout", None) is not _guarded_settimeout:
    socket.socket.settimeout = _guarded_settimeout