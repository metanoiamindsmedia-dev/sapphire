#!/usr/bin/env python3
"""
Sapphire MCP Integration Validator

Run this script to verify your Sapphire + MCP setup is configured correctly.
Usage: python validate_mcp_setup.py

This script checks:
1. .env file exists and has required API keys
2. MCP server is reachable
3. LLM providers are configured
4. Personas and toolsets are loaded
5. MCP tools are available
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

# ANSI colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

class Validator:
    def __init__(self):
        self.checks_passed = 0
        self.checks_failed = 0
        self.warnings = []
        self.project_root = Path(__file__).parent
    
    def log_pass(self, msg: str):
        print(f"{GREEN}✓{RESET} {msg}")
        self.checks_passed += 1
    
    def log_fail(self, msg: str):
        print(f"{RED}✗{RESET} {msg}")
        self.checks_failed += 1
    
    def log_warn(self, msg: str):
        print(f"{YELLOW}⚠{RESET} {msg}")
        self.warnings.append(msg)
    
    def log_info(self, msg: str):
        print(f"{BLUE}ℹ{RESET} {msg}")
    
    def section(self, title: str):
        print(f"\n{BOLD}{title}{RESET}")
        print("─" * (len(title) + 10))
    
    def run(self):
        print(f"\n{BOLD}Sapphire MCP Integration Validator{RESET}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        self.check_env_file()
        self.check_mcp_server()
        self.check_llm_providers()
        self.check_personas()
        self.check_toolsets()
        self.check_python_modules()
        
        self.summary()
    
    def check_env_file(self):
        self.section("1. Environment Configuration (.env)")
        
        env_path = self.project_root / '.env'
        if not env_path.exists():
            self.log_warn(".env file not found - using defaults")
            self.log_info("Run: cp .env.example .env")
            return
        
        self.log_pass(".env file exists")
        
        # Check for at least one API key
        env_vars = {}
        try:
            with open(env_path) as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        env_vars[key] = value
        except Exception as e:
            self.log_fail(f"Failed to parse .env: {e}")
            return
        
        # Check for LLM API keys
        llm_keys = [
            'ANTHROPIC_API_KEY',
            'OPENAI_API_KEY',
            'GOOGLE_API_KEY',
            'FIREWORKS_API_KEY'
        ]
        
        found_llm_key = False
        for key in llm_keys:
            if key in env_vars and env_vars[key]:
                self.log_pass(f"Found {key}")
                found_llm_key = True
            else:
                self.log_warn(f"Missing {key}")
        
        if not found_llm_key:
            self.log_fail("No LLM API keys configured")
        
        # Check MCP settings
        mcp_host = env_vars.get('MCP_SERVER_HOST', 'localhost')
        mcp_port = env_vars.get('MCP_SERVER_PORT', '5000')
        self.log_pass(f"MCP Server target: {mcp_host}:{mcp_port}")
        
        # Check MCP categories
        mcp_enabled = [k for k, v in env_vars.items() 
                       if k.startswith('MCP_ENABLE_') and v.lower() == 'true']
        if mcp_enabled:
            self.log_pass(f"Enabled MCP categories: {len(mcp_enabled)}")
        else:
            self.log_warn("No MCP categories explicitly enabled (defaults to all)")
    
    def check_mcp_server(self):
        self.section("2. MCP Server Connectivity")
        
        try:
            import requests
        except ImportError:
            self.log_warn("requests library not installed")
            return
        
        mcp_host = os.getenv('MCP_SERVER_HOST', 'localhost')
        mcp_port = int(os.getenv('MCP_SERVER_PORT', '5000'))
        mcp_url = f"http://{mcp_host}:{mcp_port}"
        
        try:
            resp = requests.get(f"{mcp_url}/health", timeout=2)
            if resp.status_code == 200:
                self.log_pass(f"MCP server reachable at {mcp_url}")
            else:
                self.log_fail(f"MCP server returned status {resp.status_code}")
        except requests.ConnectError:
            self.log_fail(f"Cannot connect to MCP server at {mcp_url}")
            self.log_info("Make sure MCP Docker server is running")
        except Exception as e:
            self.log_fail(f"MCP connection error: {e}")
    
    def check_llm_providers(self):
        self.section("3. LLM Provider Configuration")
        
        settings_path = self.project_root / 'sapphire-data' / 'settings.json'
        if not settings_path.exists():
            self.log_warn("settings.json not found - will use defaults")
            self.log_info("First run creates default settings")
            return
        
        try:
            with open(settings_path) as f:
                settings = json.load(f)
            
            llm_config = settings.get('llm', {})
            providers = llm_config.get('LLM_PROVIDERS', {})
            
            if not providers:
                self.log_fail("No LLM providers configured")
                return
            
            enabled_count = 0
            for name, config in providers.items():
                if config.get('enabled'):
                    model = config.get('model', 'unknown')
                    self.log_pass(f"Provider '{name}' enabled: {model}")
                    enabled_count += 1
            
            if enabled_count == 0:
                self.log_warn("No LLM providers enabled in settings.json")
            
            # Check fallback order
            fallback = llm_config.get('LLM_FALLBACK_ORDER', [])
            if fallback:
                self.log_pass(f"Fallback order configured: {' → '.join(fallback)}")
        
        except json.JSONDecodeError as e:
            self.log_fail(f"Invalid JSON in settings.json: {e}")
        except Exception as e:
            self.log_fail(f"Error reading settings: {e}")
    
    def check_personas(self):
        self.section("4. Personas")
        
        persona_path = self.project_root / 'user' / 'personas' / 'personas.json'
        if not persona_path.exists():
            self.log_warn("No custom personas found")
            self.log_info("Run Sapphire once to seed default personas")
            return
        
        try:
            with open(persona_path) as f:
                personas = json.load(f)
            
            persona_names = [k for k in personas.keys() if not k.startswith('_')]
            self.log_pass(f"Found {len(persona_names)} personas")
            
            for name in persona_names[:5]:  # Show first 5
                settings = personas[name].get('settings', {})
                toolset = settings.get('toolset', 'none')
                model = settings.get('llm_model', 'auto')
                print(f"  - {name}: toolset={toolset}, model={model}")
            
            if len(persona_names) > 5:
                print(f"  ... and {len(persona_names) - 5} more")
        
        except Exception as e:
            self.log_fail(f"Error reading personas: {e}")
    
    def check_toolsets(self):
        self.section("5. Toolsets")
        
        toolset_path = self.project_root / 'user' / 'toolsets' / 'toolsets.json'
        if not toolset_path.exists():
            self.log_warn("No custom toolsets found")
            self.log_info("Copy from user/toolsets/toolsets.example.json")
            return
        
        try:
            with open(toolset_path) as f:
                toolsets = json.load(f)
            
            toolset_names = [k for k in toolsets.keys() if not k.startswith('_')]
            self.log_pass(f"Found {len(toolset_names)} toolsets")
            
            for name in toolset_names[:5]:
                ts = toolsets[name]
                tool_count = len(ts.get('tools', []))
                print(f"  - {name}: {tool_count} tools")
        
        except Exception as e:
            self.log_fail(f"Error reading toolsets: {e}")
    
    def check_python_modules(self):
        self.section("6. Python Dependencies")
        
        required_modules = [
            ('requests', 'HTTP requests'),
            ('aiohttp', 'Async HTTP (for MCP calls)'),
            ('fastapi', 'Web framework'),
            ('pydantic', 'Data validation'),
        ]
        
        optional_modules = [
            ('tenacity', 'Retry logic'),
            ('jinja2', 'Templating'),
            ('redis', 'Caching'),
        ]
        
        for module_name, display_name in required_modules:
            try:
                __import__(module_name)
                self.log_pass(f"{display_name} ({module_name})")
            except ImportError:
                self.log_fail(f"Missing {display_name} ({module_name})")
        
        for module_name, display_name in optional_modules:
            try:
                __import__(module_name)
                self.log_pass(f"{display_name} ({module_name}) - optional")
            except ImportError:
                self.log_warn(f"Missing {display_name} ({module_name}) - optional")
    
    def summary(self):
        self.section("Summary")
        
        print(f"{GREEN}Passed:{RESET} {self.checks_passed}")
        print(f"{RED}Failed:{RESET} {self.checks_failed}")
        print(f"{YELLOW}Warnings:{RESET} {len(self.warnings)}")
        
        if self.warnings:
            print(f"\n{BOLD}Action Items:{RESET}")
            for warning in self.warnings[:5]:
                print(f"  • {warning}")
        
        if self.checks_failed == 0:
            print(f"\n{GREEN}{BOLD}✓ All checks passed! Ready to run Sapphire.{RESET}")
            print(f"\nNext steps:")
            print(f"  1. Start Sapphire: python main.py")
            print(f"  2. Open: http://localhost:8073")
            print(f"  3. Try spawning an agent with tools")
        else:
            print(f"\n{RED}{BOLD}✗ Some checks failed. Fix issues above before running.{RESET}")
        
        print("\nFor more help, see:")
        print("  - MCP-QUICKSTART.md")
        print("  - docs/MCP-INTEGRATION.md")
        print("  - docs/MCP-AGENTS.md")
        print()

if __name__ == '__main__':
    validator = Validator()
    validator.run()
    sys.exit(1 if validator.checks_failed > 0 else 0)
