from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from vce.auth.router import router as auth_router
from vce.coin.router import router as coin_router
from vce.orm import start_orm_mappers
from vce.settings import BACKEND_DB_URL, CG_API_URL
from vce.user.router import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[dict[str, Any]]:
    """Owns the app-wide resources. The yielded dict becomes request.state (see vce/db.py and vce/dependencies.py)."""
    start_orm_mappers()
    engine = create_async_engine(BACKEND_DB_URL)
    try:
        async with AsyncClient(base_url=CG_API_URL) as http_client:
            yield {
                "sessionmaker": async_sessionmaker(engine, expire_on_commit=False),
                "http_client": http_client,
            }
    finally:
        await engine.dispose()


app = FastAPI(root_path="/api", lifespan=lifespan, title="Virtual Crypto Exchange")

origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "https://mmlynarik.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(coin_router)
app.include_router(user_router)
app.include_router(auth_router)


@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI app!"}
