# Sapphire Setup - Local & Free Cloud LLMs (No Anthropic)

Your Sapphire is now configured to use **6 LLM providers** without needing Anthropic. Here's what to do:

## 🚀 Quick Start

### Step 1: Start Local Models (Optional but Recommended)

**Ollama (Easiest):**
```bash
# Install from https://ollama.ai
# Then run any model:
ollama run mistral      # Recommended: fastest, good quality
ollama run dolphin-mixtral
ollama run neural-chat
```

**LM Studio:**
- Already configured to your network IP: `http://100.113.135.14:1234`
- Load the Qwen model you have downloaded
- It will automatically be available

### Step 2: Start Sapphire

```bash
python main.py
```

Your settings will load with this fallback order:
```
1. Ollama (local - FREE, instant, no API key)
   ↓ (if down)
2. LM Studio (local - FREE, your Qwen model)
   ↓ (if down)
3. GitHub Models (FREE tier, Claude/Llama)
   ↓ (if down)
4. Google Gemini (FREE tier, great for reasoning)
   ↓ (if down)
5. HuggingFace (FREE tier)
   ↓ (if down)
6. AWS Bedrock (requires AWS setup)
```

### Step 3: Try It Out

Open http://localhost:8073 and chat!

---

## 📊 LLM Provider Comparison

| Provider | Cost | Speed | Quality | Setup | Notes |
|----------|------|-------|---------|-------|-------|
| **Ollama** | 🟢 FREE | ⚡ Instant | 🟡 Good | Local | Best for always-on |
| **LM Studio** | 🟢 FREE | ⚡ Instant | 🟡 Good | Local | Your Qwen model |
| **GitHub Models** | 🟢 FREE Tier | 🟡 Fast | 🟢 Excellent | API | Claude, Llama, Phi |
| **Google Gemini** | 🟢 FREE Tier | 🟡 Fast | 🟢 Excellent | API | Great for reasoning |
| **HuggingFace** | 🟢 FREE Tier | 🟡 Medium | 🟡 Good | API | Simple inference |
| **AWS Bedrock** | 🔴 Paid | 🟢 Fast | 🟢 Excellent | AWS | Need AWS account |

---

## 🔧 Configuration Details

### Local Providers (No API Key)
These run on your machine and never send data to the cloud:

**Ollama:**
```
Base URL: http://localhost:11434/v1
Default Model: mistral (7B - 4GB RAM)
```

**LM Studio:**
```
Base URL: http://100.113.135.14:1234/v1
Your Model: Qwen 3.5 (9B)
```

### Free Cloud Providers (API Key Required)
These are **completely free** at current usage rates:

**GitHub Models:**
- API: `GITHUB_PERSONAL_ACCESS_TOKEN` ✅ You have this
- Free Claude, Llama, Phi models
- Best quality for code/reasoning

**Google Gemini:**
- API: `GOOGLE_API_KEY` ✅ You have this
- Free 2M tokens/month
- Great for extended thinking

**HuggingFace:**
- API: `HUGGINGFACE_TOKEN` ✅ You have this
- Free tier: 30K requests/month
- Good for experimentation

### Paid Provider (Optional)

**AWS Bedrock:**
- Set `"enabled": true` in settings.json to use
- Billing: Pay per request (~$0.003 per 1K tokens)
- Best models: Claude 3.5 Sonnet
- Need AWS credentials in .env

---

## 🎯 How Sapphire Uses These

1. **Chat** → Uses primary provider (Ollama by default)
2. **If provider is down** → Falls back to next in order
3. **Agents** → Can use different model per agent
4. **Tools** → Use provider specified in agent config

### Switch Providers Manually

**Via Web UI:**
Settings → LLM → Select provider from dropdown

**Or in settings.json:**
```json
"llm": {
  "LLM_PRIMARY": "gemini",
  "LLM_MODEL": "gemini-2.5-flash"
}
```

---

## 🎓 Model Recommendations

### For General Chat
- **Best:** Ollama Mistral (free, local, stable)
- **Fallback:** GitHub Models Claude (free, excellent)

### For Code
- **Best:** GitHub Models Claude (best code understanding)
- **Fallback:** LM Studio Qwen (local, good enough)

### For Research/Writing
- **Best:** Google Gemini (excellent reasoning)
- **Fallback:** GitHub Models Llama (good alternative)

### For Cost Control
- **All local:** Ollama + LM Studio (completely free)
- **Hybrid:** Ollama primary, GitHub Models fallback

---

## 🚨 Troubleshooting

### "No model available" error

**Solution:** Start at least one provider:
```bash
# Option 1: Start Ollama (fix network issues first)
winget install Ollama.Ollama
ollama run mistral --platform linux/amd64  # Bypass IPv6/Cloudflare issues
# Or disable IPv6: netsh interface ipv6 install (admin PowerShell)

# Option 2: Start LM Studio (it auto-serves on 100.113.135.14:1234)
# Download: https://lmstudio.ai/

# Option 3: Check GitHub Models API key
# Verify GITHUB_PERSONAL_ACCESS_TOKEN in .env
```

### MCP Validation
```bash
python validate_mcp_setup.py
# All green ✓ then ready for agents/API
```


### Poor response quality

Try a better model:
```json
"llm": {
  "LLM_PRIMARY": "github-models",
  "LLM_MODEL": "gpt-4o"
}
```

### Slow responses

- Ollama: Use smaller model (phi-2, neural-chat)
- Cloud: Check internet connection
- AWS Bedrock: May need AWS setup

### Provider keeps failing

Check logs at: `sapphire-data/logs/`
Look for errors about:
- Connection refused → Provider not running
- Invalid API key → Check .env file
- Rate limited → Hit free tier limit

---

## 💡 Tips

1. **Start with Ollama** - it's local, always available, no setup
2. **Add GitHub Models as fallback** - for when you need better quality
3. **Keep Gemini enabled** - use it for complex reasoning tasks
4. **Test each provider** - try them before relying on fallbacks

---

## 🔐 Security Notes

Your `.env` file contains real API keys. Make sure it's:
```bash
# Add to .gitignore if not already there
echo ".env" >> .gitignore

# Don't commit it to git
git status  # Should not show .env
```

---

## 📚 Models You Can Use

### Ollama (Local)
```
ollama run mistral          # ⭐ Recommended - 4GB RAM
ollama run neural-chat      # Good - 3GB RAM
ollama run dolphin-mixtral  # Excellent - 16GB RAM
ollama run llama2           # Classic - 10GB RAM
ollama run phi-2            # Fast - 1.5GB RAM
```

### GitHub Models (Free)
- Claude models
- Llama 2, 3.1 series  
- Phi-3, Phi-4
- Cohere models

### Google Gemini
- gemini-2.5-flash (default)
- gemini-2.5-pro (more powerful)
- Free up to 2M tokens/month

---

## ✅ Setup Checklist

- [ ] Ollama running or LM Studio available
- [ ] `.env` file has API keys for cloud providers
- [ ] `settings.json` has LLM providers configured
- [ ] Run `python validate_mcp_setup.py` (all green ✓)
- [ ] Start Sapphire with `python main.py`
- [ ] Open http://localhost:8073
- [ ] Send test message in chat
- [ ] Check which provider was used in logs

---

## Need Help?

**Check logs:**
```bash
tail -f sapphire-data/logs/sapphire.log
```

**Test MCP setup:**
```bash
python validate_mcp_setup.py
```

**Manual provider test (Python):**
```python
import asyncio
from core.mcp_integration import mcp_client

async def test():
    await mcp_client.initialize()
    tools = await mcp_client.get_available_tools()
    print(f"Available tools: {len(tools)}")

asyncio.run(test())
```

Enjoy your AI assistant with no Anthropic dependency! 🚀
