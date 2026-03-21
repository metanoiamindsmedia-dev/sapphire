# core/mcp_integration.py
"""
MCP Docker Server Integration for Sapphire

Handles connection to MCP Docker Server and tool registration with the chat system.
Provides safe, async access to all available MCP tools from Docker environment.

Usage:
    from core.mcp_integration import mcp_client
    
    # Get available tools (filtered by settings)
    tools = await mcp_client.get_available_tools()
    
    # Call a tool
    result = await mcp_client.call_tool(
        tool_name="fetch",
        args={"url": "https://example.com"}
    )
"""

import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Represents a tool available from MCP Server."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    category: str  # e.g., 'github', 'azure', 'filesystem'


class MCPClient:
    """
    Client for communicating with MCP Docker Server.
    
    This client:
    - Maintains connection to MCP server
    - Filters tools based on .env settings
    - Provides tool calling interface
    - Handles errors and fallbacks gracefully
    """
    
    def __init__(self):
        self.host = os.getenv('MCP_SERVER_HOST', 'localhost')
        self.port = int(os.getenv('MCP_SERVER_PORT', '5000'))
        self.base_url = f"http://{self.host}:{self.port}"
        
        # Tool enablement flags from .env
        self.enabled_categories = self._parse_enabled_categories()
        
        # Cached tool list
        self._tools_cache: Dict[str, MCPTool] = {}
        self._tools_initialized = False
        
        logger.info(f"MCP Client initialized: {self.base_url}")
        logger.debug(f"Enabled categories: {list(self.enabled_categories.keys())}")
    
    def _parse_enabled_categories(self) -> Dict[str, bool]:
        """Parse MCP_ENABLE_* environment variables."""
        categories = {
            'github': os.getenv('MCP_ENABLE_GITHUB', 'true').lower() == 'true',
            'azure': os.getenv('MCP_ENABLE_AZURE', 'true').lower() == 'true',
            'aws': os.getenv('MCP_ENABLE_AWS', 'true').lower() == 'true',
            'filesystem': os.getenv('MCP_ENABLE_FILESYSTEM', 'true').lower() == 'true',
            'fetch': os.getenv('MCP_ENABLE_FETCH', 'true').lower() == 'true',
            'memory': os.getenv('MCP_ENABLE_MEMORY', 'true').lower() == 'true',
            'sequentialthinking': os.getenv('MCP_ENABLE_SEQUENTIALTHINKING', 'true').lower() == 'true',
            'playwright': os.getenv('MCP_ENABLE_PLAYWRIGHT', 'true').lower() == 'true',
            'git': os.getenv('MCP_ENABLE_GIT', 'true').lower() == 'true',
            'node_sandbox': os.getenv('MCP_ENABLE_NODE_SANDBOX', 'true').lower() == 'true',
            'huggingface': os.getenv('MCP_ENABLE_HUGGINGFACE', 'true').lower() == 'true',
            'desktop_commander': os.getenv('MCP_ENABLE_DESKTOP_COMMANDER', 'true').lower() == 'true',
        }
        return categories
    
    def _get_tool_category(self, tool_name: str) -> Optional[str]:
        """Determine which category a tool belongs to."""
        prefix_map = {
            'github_': 'github',
            'azure_': 'azure',
            'aws_': 'aws',
            'fs_': 'filesystem',
            'file_': 'filesystem',
            'fetch': 'fetch',
            'memories_': 'memory',
            'think': 'sequentialthinking',
            'playwright_': 'playwright',
            'git_': 'git',
            'node_': 'node_sandbox',
            'hf_': 'huggingface',
            'dc_': 'desktop_commander',
        }
        
        for prefix, category in prefix_map.items():
            if tool_name.startswith(prefix):
                return category
        
        # Try to infer from tool name keywords
        if any(x in tool_name.lower() for x in ['github', 'pull', 'issue']):
            return 'github'
        if any(x in tool_name.lower() for x in ['azure', 'subscription', 'resource']):
            return 'azure'
        if any(x in tool_name.lower() for x in ['aws', 'ec2', 's3']):
            return 'aws'
        
        return None
    
    async def initialize(self):
        """Fetch available tools from server and cache them."""
        if self._tools_initialized:
            return
        
        try:
            import aiohttp
        except ImportError:
            logger.warning("aiohttp not available, MCP tools will be unavailable")
            self._tools_initialized = True
            return
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/tools",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._process_tools_response(data)
                    else:
                        logger.warning(f"MCP server returned {resp.status}")
        except asyncio.TimeoutError:
            logger.warning(f"MCP server timeout at {self.base_url}")
        except Exception as e:
            logger.warning(f"Failed to initialize MCP tools: {e}")
        
        self._tools_initialized = True
    
    def _process_tools_response(self, data: Dict) -> None:
        """Process tools response from MCP server."""
        tools = data.get('tools', [])
        logger.info(f"Received {len(tools)} tools from MCP server")
        
        for tool_data in tools:
            name = tool_data.get('name')
            if not name:
                continue
            
            category = self._get_tool_category(name)
            
            # Skip if category is disabled
            if category and not self.enabled_categories.get(category, True):
                logger.debug(f"Skipping disabled tool: {name} (category: {category})")
                continue
            
            tool = MCPTool(
                name=name,
                description=tool_data.get('description', ''),
                input_schema=tool_data.get('inputSchema', {}),
                category=category or 'unknown'
            )
            self._tools_cache[name] = tool
        
        logger.info(f"Cached {len(self._tools_cache)} available tools")
    
    async def get_available_tools(self) -> List[MCPTool]:
        """Get list of available tools, filtered by enabled categories."""
        await self.initialize()
        return list(self._tools_cache.values())
    
    async def get_tool(self, name: str) -> Optional[MCPTool]:
        """Get a specific tool definition."""
        await self.initialize()
        return self._tools_cache.get(name)
    
    async def call_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool via the MCP server.
        
        Args:
            tool_name: Name of the tool to call
            args: Tool arguments dict
        
        Returns:
            Tool result dict with 'success' and 'result' or 'error' keys
        """
        try:
            import aiohttp
        except ImportError:
            return {
                'success': False,
                'error': 'aiohttp library required for MCP calls'
            }
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    'tool_name': tool_name,
                    'arguments': args
                }
                
                async with session.post(
                    f"{self.base_url}/call",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        error_text = await resp.text()
                        return {
                            'success': False,
                            'error': f"MCP server error {resp.status}: {error_text}"
                        }
        
        except asyncio.TimeoutError:
            return {
                'success': False,
                'error': f"Tool execution timeout"
            }
        except Exception as e:
            logger.error(f"Tool call failed: {tool_name}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def is_available(self) -> bool:
        """Check if MCP server is reachable."""
        try:
            import requests
            resp = requests.get(f"{self.base_url}/health", timeout=2)
            return resp.status_code == 200
        except Exception:
            return False
    
    def get_tool_category(self, tool_name: str) -> Optional[str]:
        """Get the category of a tool (without async)."""
        if tool_name in self._tools_cache:
            return self._tools_cache[tool_name].category
        return self._get_tool_category(tool_name)


# Global MCP client instance
mcp_client = MCPClient()


def get_mcp_tools_for_agent(provided_toolset: Optional[str] = None) -> Dict[str, Any]:
    """
    Get MCP tools formatted for agent use.
    
    Args:
        provided_toolset: Optional toolset name to filter (e.g., 'github', 'azure')
    
    Returns:
        Dict formatted for addition to agent tool context
    """
    tools = {}
    
    for name, tool in mcp_client._tools_cache.items():
        # Filter by toolset if provided
        if provided_toolset and tool.category != provided_toolset:
            continue
        
        tools[name] = {
            'description': tool.description,
            'parameters': tool.input_schema,
            'handler': f'mcp.{name}'  # Mark as MCP-routed
        }
    
    return tools
