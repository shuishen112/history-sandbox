#!/usr/bin/env python3
"""Launch the Kamer REST API + inspector dashboard."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("kamer.api.server:app", host="0.0.0.0", port=8765, reload=False)
