"""Роуты импорта - только HTTP-слой."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_owner_shop_id
from app.api.schemas.stats import ImportResponse
from app.db.session import get_session
from app.services import import_service as svc

router = APIRouter(prefix="/import", tags=["import"])


@router.post("/products", response_model=ImportResponse)
async def import_products(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    shop_id: int = Depends(get_owner_shop_id),
):
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Only .xlsx files are allowed")
    content = await file.read()
    return await svc.import_products(content, session, shop_id)
