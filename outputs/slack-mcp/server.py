from mcp.server.fastmcp import FastMCP
from collector import CHANNELS, collect

mcp = FastMCP("capstone-slack-reader")

@mcp.tool()
def list_experiment_channels() -> dict:
    """List the two allowed experiment channels; no Slack request."""
    return CHANNELS

@mcp.tool()
def read_experiment(case: str) -> dict:
    """Read warranty or sap history. No posting, deletion or other channels."""
    return collect(case)

if __name__ == "__main__":
    mcp.run(transport="stdio")
