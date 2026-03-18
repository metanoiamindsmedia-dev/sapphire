# Telegram

Connect Sapphire to Telegram. She can read chats, send messages, and automatically respond to incoming messages via daemons.

## Setup

This is a two-phase process — first save your API credentials, then add an account.

### Step 1: Get API Credentials

1. Go to [my.telegram.org](https://my.telegram.org)
2. Log in with your phone number
3. Go to "API development tools"
4. Create an app — you'll get an **API ID** and **API Hash**

### Step 2: Save Credentials in Sapphire

1. Open **Settings → expand Plugin Settings → Telegram**
2. Enter your **API ID** and **API Hash** in the fields at the top
3. Click **Save Settings**

You must save these before adding an account — the auth flow needs them to connect.

### Step 3: Add an Account

1. Scroll down to the **Accounts** section
2. Click **+ Add Account**
3. Enter a name for this account (e.g., "personal") and your phone number
4. Enter the verification code Telegram sends you
5. If you have 2FA enabled, enter your cloud password when prompted

This uses the Telegram Client API (Telethon), not the Bot API — so Sapphire acts as your account, not a separate bot.

## Available Tools

| Tool | What it does |
|------|--------------|
| `telegram_get_chats` | List your recent chats with preview and unread count |
| `telegram_read_messages` | Read messages from a specific chat |
| `telegram_send` | Send a message to a chat |

## Multi-Account

Multiple Telegram accounts can be connected, each on its own scope.

1. Add accounts in Settings → Plugins → Telegram
2. Switch using the Telegram scope dropdown in Chat Settings

## Daemon (Auto-React to Messages)

Sapphire can listen for incoming Telegram messages and respond automatically.

### Quick Setup

1. Go to **Schedule** → **+ New Task** → choose **Daemon**
2. Set source to **Telegram Message**
3. Configure filters and source settings
4. Set a prompt and toolset

### Filters

| Filter | What it matches |
|--------|----------------|
| `chat_id` | Specific Telegram chat ID |
| `username` | Sender's username |
| `chat_type` | `"private"`, `"group"`, or `"supergroup"` |

### Source Settings

| Setting | Description |
|---------|-------------|
| Account | Which Telegram account to listen on |
| Reply Format | Plain text, Markdown, or HTML |

### Example: Personal Assistant

```
Filter: {"chat_type": "private"}
Account: personal
Reply Format: Markdown
Message: "You are my personal assistant on Telegram. Help with whatever I ask."
Toolset: default
```

Responds to all private messages on the selected account.

### Example: Group Monitor

```
Filter: {"chat_type": "group", "username": "boss"}
Message: "My boss sent a message in a group. Summarize it and save to memory."
Auto-reply: Off
```

## Example Commands

- "Check my Telegram messages"
- "Read the last 20 messages from the family group"
- "Send 'on my way' to mom on Telegram"
- "Any unread messages?"

## Troubleshooting

- **Auth failed** — Double-check API ID and Hash from my.telegram.org
- **2FA prompt** — Enter your Telegram cloud password, not your phone PIN
- **Messages not arriving** — Make sure the daemon task is enabled and the account is selected
- **Tools not available** — Add Telegram tools to your active toolset

## Reference for AI

Telegram integration via Client API (Telethon).

SETUP (two phases):
- Phase 1: Settings → Plugin Settings → Telegram → enter API ID + API Hash → Save Settings
- Phase 2: Scroll to Accounts → + Add Account → phone + code (+ 2FA if enabled)
- API credentials must be saved BEFORE adding an account

AVAILABLE TOOLS:
- telegram_get_chats(limit?) - list recent chats with previews (default 15)
- telegram_read_messages(chat_id, limit?) - read messages from chat (default 20)
- telegram_send(chat_id, text) - send message to chat

DAEMON:
- Source: telegram_message
- Filters: chat_id, username, chat_type (private/group/supergroup)
- Task fields: account (select), reply_format (text/markdown/html)

SCOPES:
- scope_telegram ContextVar for multi-account
- Sidebar dropdown to switch

TROUBLESHOOTING:
- Auth failed: verify API ID/Hash at my.telegram.org
- 2FA: use Telegram cloud password
- No events: check daemon enabled + correct account selected
