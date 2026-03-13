# plugins/telegram/tools/telegram_tools.py — Telegram tools for the LLM
#
# These are for use in regular chat (not daemon responses).
# Account is read from scope_telegram ContextVar (set via sidebar dropdown).

import asyncio
import json
import logging

logger = logging.getLogger(__name__)

ENABLED = True
EMOJI = '✈️'
AVAILABLE_FUNCTIONS = ['telegram_send', 'telegram_get_chats', 'telegram_read_messages']

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "telegram_send",
            "description": "Send a message to a Telegram chat (person, group, or channel). Uses the account selected in sidebar scope.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": ["string", "integer"],
                        "description": "Telegram chat ID (number) or @username"
                    },
                    "text": {
                        "type": "string",
                        "description": "Message text to send"
                    }
                },
                "required": ["chat_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_get_chats",
            "description": "List recent Telegram chats/conversations. Uses the account selected in sidebar scope.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max chats to return (default 20)",
                        "default": 20
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "telegram_read_messages",
            "description": "Read recent messages from a Telegram chat. Uses the account selected in sidebar scope.",
            "parameters": {
                "type": "object",
                "properties": {
                    "chat_id": {
                        "type": ["string", "integer"],
                        "description": "Telegram chat ID (number) or @username"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max messages to return (default 20)",
                        "default": 20
                    }
                },
                "required": ["chat_id"]
            }
        }
    }
]


def _get_account():
    """Read the active Telegram account from scope."""
    from core.chat.function_manager import scope_telegram
    acct = scope_telegram.get()
    return acct if acct and acct != 'none' else None


def _check_ready():
    """Check account + daemon, return (client, loop) or error string."""
    account = _get_account()
    if not account:
        return "No Telegram account selected. Set one in Chat > Sidebar > Mind > Telegram."

    from plugins.telegram.daemon import get_client, get_loop

    client = get_client(account)
    if not client:
        return f"Account '{account}' is not connected. Check Telegram plugin settings."

    loop = get_loop()
    if not loop:
        return "Telegram daemon is not running."

    return client, loop


def execute(function_name, arguments, config):
    """Dispatch tool calls. Returns (result_string, success_bool)."""
    try:
        if function_name == "telegram_send":
            return telegram_send(arguments, config), True
        elif function_name == "telegram_get_chats":
            return telegram_get_chats(arguments, config), True
        elif function_name == "telegram_read_messages":
            return telegram_read_messages(arguments, config), True
        return f"Unknown function: {function_name}", False
    except Exception as e:
        logger.error(f"[TELEGRAM] Tool error: {e}")
        return f"Error: {e}", False


def telegram_send(args, config):
    """Send a Telegram message."""
    ready = _check_ready()
    if isinstance(ready, str):
        return ready
    client, loop = ready

    chat_id = args.get("chat_id")
    text = args.get("text", "")
    if not chat_id or not text:
        return "Missing required fields: chat_id, text"

    try:
        try:
            chat_id = int(chat_id)
        except (ValueError, TypeError):
            pass

        future = asyncio.run_coroutine_threadsafe(
            client.send_message(chat_id, text), loop
        )
        future.result(timeout=15)
        return f"Message sent to {chat_id}"
    except Exception as e:
        logger.error(f"[TELEGRAM] Send failed: {e}")
        return f"Failed to send message: {e}"


def telegram_get_chats(args, config):
    """List recent Telegram chats."""
    ready = _check_ready()
    if isinstance(ready, str):
        return ready
    client, loop = ready

    limit = args.get("limit", 20)

    try:
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


def telegram_read_messages(args, config):
    """Read recent messages from a Telegram chat."""
    ready = _check_ready()
    if isinstance(ready, str):
        return ready
    client, loop = ready

    chat_id = args.get("chat_id")
    limit = args.get("limit", 20)
    if not chat_id:
        return "chat_id is required"

    try:
        try:
            chat_id = int(chat_id)
        except (ValueError, TypeError):
            pass

        async def _read():
            messages = []
            async for msg in client.iter_messages(chat_id, limit=limit):
                sender = None
                if msg.sender:
                    sender = getattr(msg.sender, 'username', None) or \
                             getattr(msg.sender, 'first_name', None) or \
                             str(msg.sender_id)
                messages.append({
                    "id": msg.id,
                    "from": sender,
                    "text": msg.text or "",
                    "date": msg.date.isoformat() if msg.date else None,
                    "reply_to": msg.reply_to_msg_id,
                })
            return messages

        future = asyncio.run_coroutine_threadsafe(_read(), loop)
        msgs = future.result(timeout=15)
        return json.dumps(msgs, indent=2)
    except Exception as e:
        logger.error(f"[TELEGRAM] Read messages failed: {e}")
        return f"Failed to read messages: {e}"
