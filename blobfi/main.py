"""
main.py — BlobFi entry point
Run: python main.py  OR  uvicorn main:app --reload
"""
import uvicorn
from api.app import app

if __name__ == "__main__":
    from core.config import settings
    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
