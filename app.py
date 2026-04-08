#!/usr/bin/env python3
"""Runtime wrapper for local + Hugging Face Spaces deployment."""

from __future__ import annotations

import os

import uvicorn

from server.app import app


def main() -> None:
    """Run the API server using root-level entrypoint for deployment validators."""
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run("app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
