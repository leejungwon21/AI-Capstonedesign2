import asyncio
import os
import sys

from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    # 현재 CMD의 환경변수를 MCP Server에도 전달
    env = os.environ.copy()

    params = StdioServerParameters(
        command=sys.executable,
        args=[
            str(
                Path(
                    "outputs/slack-mcp/server.py"
                ).resolve()
            )
        ],
        env=env,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            # MCP 연결
            await session.initialize()

            # 1. MCP Tool 목록 확인
            tools = await session.list_tools()

            names = [
                tool.name
                for tool in tools.tools
            ]

            print("MCP tools:", names)

            # 2. MCP를 통해 실제 Slack SAP 채널 조회
            result = await session.call_tool(
                "read_experiment",
                {
                    "case": "sap",
                },
            )

            if result.isError:
                print("MCP → Slack 호출 실패")

                for item in result.content:
                    print(item)

                return

            print("MCP → Slack 실제 조회 성공")

            for item in result.content:
                print(item)


if __name__ == "__main__":
    asyncio.run(main())