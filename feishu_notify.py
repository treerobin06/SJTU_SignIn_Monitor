#!/usr/bin/env python3
"""
飞书群聊消息通知模块
独立于 MCP，直接调用飞书 REST API 发送群消息。
可被其他脚本 import 使用，也可直接命令行调用。

用法:
  # 命令行
  python feishu_notify.py "签到号变了！当前: 8"
  python feishu_notify.py "自定义消息" --chat_id oc_xxx

  # 作为模块
  from feishu_notify import send_feishu_message
  send_feishu_message("签到号变了！")
"""

import json
import ssl
import urllib.request

# ── 配置 ──────────────────────────────────────────────
APP_ID = "cli_a924694223f89bc3"
APP_SECRET = "GbJPpAlYYWVUbpFIK2gzgcXZiJrRA8mr"
# 默认群聊 ID（"feishu" 群）
DEFAULT_CHAT_ID = "oc_afe51acea89065e9fe3431208b214433"
# 私聊 open_id（姜博文）
DEFAULT_OPEN_ID = "ou_8c0782470768072112d19fbaf799ec34"

BASE_URL = "https://open.feishu.cn/open-apis"
CTX = ssl.create_default_context()


def _request(url, method="GET", data=None, token=None):
    """发送 HTTP 请求，返回解析后的 dict。"""
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(req, context=CTX) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_token():
    """获取 tenant_access_token。"""
    resp = _request(
        f"{BASE_URL}/auth/v3/tenant_access_token/internal",
        method="POST",
        data={"app_id": APP_ID, "app_secret": APP_SECRET},
    )
    return resp["tenant_access_token"]


def _send(receive_id, receive_id_type, text, token):
    """底层发送，返回 data dict。"""
    resp = _request(
        f"{BASE_URL}/im/v1/messages?receive_id_type={receive_id_type}",
        method="POST",
        data={
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
        token=token,
    )
    if resp.get("code") != 0:
        raise Exception(f"飞书发送失败: {resp.get('msg')} (code={resp.get('code')})")
    return resp.get("data", {})


def send_feishu_message(text, chat_id=None, open_id=None):
    """
    同时发送文本消息到飞书群聊 + 私聊。

    参数:
      text: 消息文本
      chat_id: 群聊 ID，默认 "feishu" 群。传 False 跳过群聊
      open_id: 私聊 open_id，默认姜博文。传 False 跳过私聊

    返回:
      dict: {"group": ..., "private": ...} 各自的 API 响应
    """
    if chat_id is None:
        chat_id = DEFAULT_CHAT_ID
    if open_id is None:
        open_id = DEFAULT_OPEN_ID

    token = _get_token()
    results = {}

    # 群聊
    if chat_id:
        try:
            results["group"] = _send(chat_id, "chat_id", text, token)
        except Exception as e:
            results["group_error"] = str(e)

    # 私聊
    if open_id:
        try:
            results["private"] = _send(open_id, "open_id", text, token)
        except Exception as e:
            results["private_error"] = str(e)

    return results


if __name__ == "__main__":
    import sys

    # 解析参数
    msg = "测试消息 from feishu_notify.py 🤖"
    chat_id = None

    args = sys.argv[1:]
    if args:
        msg = args[0]
    if "--chat_id" in args:
        idx = args.index("--chat_id")
        chat_id = args[idx + 1]

    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    try:
        result = send_feishu_message(msg, chat_id)
        print(f"[OK] 发送成功! message_id: {result.get('message_id', 'N/A')}")
    except Exception as e:
        print(f"[FAIL] 发送失败: {e}")
        sys.exit(1)
