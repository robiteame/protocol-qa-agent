from contextlib import asynccontextmanager
from fastapi import FastAPI
from scalar_fastapi import get_scalar_api_reference
from .schemas import router as schemas_router
from ..storage.database import get_db, init_db

@asynccontextmanager
async def lifespan(app):
    init_db(get_db())
    yield

app = FastAPI(title="Protocol QA Agent", lifespan=lifespan)
app.include_router(schemas_router)

@app.get("/api/v1/health")
def health():
    return {"status": "ok"}

@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title=app.title,
    )