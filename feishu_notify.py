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


def send_feishu_message(text, chat_id=None):
    """
    发送文本消息到飞书群聊。

    参数:
      text: 消息文本
      chat_id: 群聊 ID，默认使用 "feishu" 群

    返回:
      dict: 飞书 API 响应（包含 message_id 等）

    异常:
      Exception: API 调用失败时抛出
    """
    chat_id = chat_id or DEFAULT_CHAT_ID
    token = _get_token()
    resp = _request(
        f"{BASE_URL}/im/v1/messages?receive_id_type=chat_id",
        method="POST",
        data={
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
        token=token,
    )
    if resp.get("code") != 0:
        raise Exception(f"飞书发送失败: {resp.get('msg')} (code={resp.get('code')})")
    return resp.get("data", {})


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
