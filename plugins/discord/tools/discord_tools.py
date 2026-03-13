# plugins/discord/tools/discord_tools.py — Discord tools for the LLM
#
# Account is read from scope_discord ContextVar (set via sidebar dropdown).
# Output is human-readable text — reduces LLM cognitive overhead.

import asyncio
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ENABLED = True
EMOJI = "🎮"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "discord_get_servers",
            "description": "List Discord servers (guilds) the bot is in, with their channels.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "discord_read_messages",
            "description": "Read recent messages from a Discord channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The channel ID to read from"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of messages to fetch (default 20, max 50)",
                        "default": 20
                    }
                },
                "required": ["channel_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "discord_send_message",
            "description": "Send a message to a Discord channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "The channel ID to send to"
                    },
                    "text": {
                        "type": "string",
                        "description": "Message text to send (max 2000 chars)"
                    }
                },
                "required": ["channel_id", "text"]
            }
        }
    }
]

AVAILABLE_FUNCTIONS = {t["function"]["name"] for t in TOOLS}


def _get_account():
    from core.chat.function_manager import scope_discord
    acct = scope_discord.get()
    return acct if acct and acct != 'none' else None


def _check_ready():
    account = _get_account()
    if not account:
        return "Discord is disabled for this chat. Select an account in the sidebar."
    from plugins.discord.daemon import get_client, get_loop
    client = get_client(account)
    loop = get_loop()
    if not client or not loop:
        return f"Discord bot '{account}' is not connected."
    return (client, loop)


def _header():
    from core.tool_context import context_header
    return context_header()


def _time_ago(dt):
    if not dt:
        return ""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    mins = int(diff.total_seconds() / 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins}m ago"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    return f"{days}d ago"


def _get_servers(client, loop):
    """List servers and their text channels."""
    async def _fetch():
        servers = []
        for guild in client.guilds:
            channels = []
            for ch in guild.text_channels:
                channels.append({"name": ch.name, "id": str(ch.id)})
            servers.append({
                "name": guild.name,
                "id": str(guild.id),
                "channels": channels,
                "members": guild.member_count,
            })
        return servers

    future = asyncio.run_coroutine_threadsafe(_fetch(), loop)
    servers = future.result(timeout=10)

    if not servers:
        return _header() + "Not in any servers.", True

    lines = [_header()]
    ch_num = 1
    for s in servers:
        lines.append(f"{s['name']} ({s['members']} members)")
        for ch in s["channels"]:
            lines.append(f"  [{ch_num}] #{ch['name']}  {ch['id']}")
            ch_num += 1
        lines.append("")

    return "\n".join(lines), True


def _read_messages(client, loop, channel_id, count=20):
    """Read recent messages from a channel."""
    count = min(max(count, 1), 50)

    async def _fetch():
        channel = client.get_channel(int(channel_id))
        if not channel:
            channel = await client.fetch_channel(int(channel_id))
        messages = []
        async for msg in channel.history(limit=count):
            messages.append({
                "author": msg.author.display_name,
                "content": msg.content or "(no text)",
                "time": msg.created_at,
                "attachments": len(msg.attachments),
            })
        return channel.name, list(reversed(messages))  # oldest first

    future = asyncio.run_coroutine_threadsafe(_fetch(), loop)
    channel_name, messages = future.result(timeout=15)

    if not messages:
        return _header() + f"#{channel_name}: No messages.", True

    lines = [_header() + f"#{channel_name} — {len(messages)} messages:\n"]
    for m in messages:
        ago = _time_ago(m["time"])
        attach = f" [{m['attachments']} file(s)]" if m["attachments"] else ""
        lines.append(f"  {m['author']} ({ago}): {m['content']}{attach}")

    return "\n".join(lines), True


def _send_message(client, loop, channel_id, text):
    """Send a message to a channel."""
    if not text or not text.strip():
        return "Message text is required.", False

    if len(text) > 2000:
        return "Message exceeds Discord's 2000 character limit.", False

    async def _send():
        channel = client.get_channel(int(channel_id))
        if not channel:
            channel = await client.fetch_channel(int(channel_id))
        await channel.send(text)
        return channel.name

    future = asyncio.run_coroutine_threadsafe(_send(), loop)
    channel_name = future.result(timeout=10)

    return f"Message sent to #{channel_name}.", True


def execute(function_name, arguments, config=None):
    """Dispatch tool calls. Returns (result_string, success_bool)."""
    ready = _check_ready()
    if isinstance(ready, str):
        return ready, False
    client, loop = ready

    try:
        if function_name == "discord_get_servers":
            return _get_servers(client, loop)
        elif function_name == "discord_read_messages":
            return _read_messages(
                client, loop,
                arguments.get("channel_id", ""),
                arguments.get("count", 20)
            )
        elif function_name == "discord_send_message":
            return _send_message(
                client, loop,
                arguments.get("channel_id", ""),
                arguments.get("text", "")
            )
        else:
            return f"Unknown function: {function_name}", False
    except Exception as e:
        logger.error(f"[DISCORD] Tool error: {e}", exc_info=True)
        return f"Discord error: {e}", False
