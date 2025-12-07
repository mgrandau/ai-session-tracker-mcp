"""
Package entry point for python -m execution.

USAGE:
    python -m ai_session_tracker_mcp           # Run MCP server
    python -m ai_session_tracker_mcp server    # Run MCP server
    python -m ai_session_tracker_mcp dashboard # Launch GUI
    python -m ai_session_tracker_mcp report    # Print report
"""

from ai_session_tracker_mcp.cli import main

if __name__ == "__main__":
    main()
