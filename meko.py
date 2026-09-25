"""Smallest possible Meko client: open one MCP session and call tools on one datapack."""
import contextlib, json, os
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

AGENT_ID = "jev-code-review"


@contextlib.asynccontextmanager
async def meko(title: str):
    """Yield call(tool, **args). Every call is scoped to your datapack and nested under one trace."""
    headers = {"Authorization": f"Bearer {os.environ['MEKO_API_KEY']}",
               "User-Agent": "meko-jev-code-review-agent/0.1"}  # Meko rejects requests without a User-Agent
    scope = {"agent_id": AGENT_ID, "datapack_id": os.environ["MEKO_DATAPACK_ID"]}
    async with httpx.AsyncClient(headers=headers, timeout=240) as http:
        async with streamable_http_client("https://mcp.mekodata.ai/mcp", http_client=http) as (r, w, _):
            async with ClientSession(r, w) as session:
                await session.initialize()

                async def call(tool: str, **args):
                    result = await session.call_tool(tool, {**scope, **args})
                    text = result.content[0].text
                    data = json.loads(text) if text.lstrip().startswith(("{", "[")) else text
                    if result.isError or (isinstance(data, dict) and "error" in data):
                        raise RuntimeError(f"{tool}: {text}")  # Meko reports some errors inside the payload
                    return data

                scope["conversation_id"] = (await call("conversation_create", title=title))["id"]
                yield call
