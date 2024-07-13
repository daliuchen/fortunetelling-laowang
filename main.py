import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn

from app.server import app

if __name__ == "__main__":
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"
    uvicorn.run(app, host="0.0.0.0", port=8000)
