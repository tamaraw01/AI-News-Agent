"""Prefect Horizon/FastMCP entrypoint.

Horizon can import this module and discover the `mcp` server object.
The implementation lives in `mcp_server.py` so local execution remains:

    python mcp_server.py
"""

from mcp_server import mcp

