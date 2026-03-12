# plugins/telegram/tools/telegram_tools.py — Telegram tools for the LLM
#
# These are for use in regular chat (not daemon responses).
# Daemon responses are routed automatically via the reply handler.

import asyncio
import json
import logging

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "name": "telegram_send",
        "description": "Send a message to a Telegram chat (person, group, or channel). You need the chat_id or username.",
        "parameters": {
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Which Telegram account to send from (e.g. 'personal', 'work')"
                },
                "chat_id": {
                    "type": ["string", "integer"],
                    "description": "Telegram chat ID (number) or @username"
                },
                "text": {
                    "type": "string",
                    "description": "Message text to send"
                }
            },
            "required": ["account", "chat_id", "text"]
        }
    },
    {
        "name": "telegram_get_chats",
        "description": "List recent Telegram chats/conversations for an account. Returns chat names, IDs, and types.",
        "parameters": {
            "type": "object",
            "properties": {
                "account": {
                    "type": "string",
                    "description": "Which Telegram account to list chats from"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max chats to return (default 20)",
                    "default": 20
                }
            },
            "required": ["account"]
        }
    }
]


def telegram_send(args, config):
    """Send a Telegram message."""
    account = args.get("account", "")
    chat_id = args.get("chat_id")
    text = args.get("text", "")

    if not account or not chat_id or not text:
        return "Missing required fields: account, chat_id, text"

    try:
        from plugins.telegram.daemon import get_client, get_loop

        client = get_client(account)
        if not client:
            return f"Account '{account}' is not connected. Check Telegram plugin settings."

        loop = get_loop()
        if not loop:
            return "Telegram daemon is not running."

        # Parse chat_id — could be int or @username
        try:
            chat_id = int(chat_id)
        except (ValueError, TypeError):
            pass  # keep as string (@username)

        future = asyncio.run_coroutine_threadsafe(
            client.send_message(chat_id, text),
            loop
        )
        future.result(timeout=15)
        return f"Message sent to {chat_id}"

    except Exception as e:
        logger.error(f"[TELEGRAM] Send failed: {e}")
        return f"Failed to send message: {e}"


def telegram_get_chats(args, config):
    """List recent Telegram chats."""
    account = args.get("account", "")
    limit = args.get("limit", 20)

    if not account:
        return "Account name required"

    try:
        from plugins.telegram.daemon import get_client, get_loop

        client = get_client(account)
        if not client:
            return f"Account '{account}' is not connected."

        loop = get_loop()
        if not loop:
            return "Telegram daemon is not running."

        async def _get():
            dialogs = []
            async for d in client.iter_dialogs(limit=limit):
                dialogs.append({
                    "name": d.name,
                    "chat_id": d.id,
                    "type": "user" if d.is_user else ("group" if d.is_group else "channel"),
                    "unread": d.unread_count,
                })
            return dialogs

        future = asyncio.run_coroutine_threadsafe(_get(), loop)
        chats = future.result(timeout=15)
        return json.dumps(chats, indent=2)

    except Exception as e:
        logger.error(f"[TELEGRAM] Get chats failed: {e}")
        return f"Failed to list chats: {e}"
