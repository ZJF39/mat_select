# -*- coding: utf-8 -*-
"""本地启动入口：`python run.py` 或 `uvicorn app.main:app`。"""
import uvicorn

from app.core.config import API_HOST, API_PORT


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=API_HOST, port=API_PORT)
