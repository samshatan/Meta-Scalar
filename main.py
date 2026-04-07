"""
Entry point — starts the FastAPI server via uvicorn.
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=7860,
        reload=False,
        log_level="info",
    )