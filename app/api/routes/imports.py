"""Роуты импорта - только HTTP-слой."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_shop_id
from app.api.schemas.stats import ImportResponse
from app.core.rate_limit import rate_limit
from app.core.rbac import Perm
from app.db.session import get_session
from app.services import import_service as svc

router = APIRouter(prefix="/import", tags=["import"])

# A3: 5 импортов в минуту с одного IP — защита от flood-атак на тяжёлый endpoint
_import_limit = rate_limit("import_products", max_requests=5, window=60)


@router.post("/products", response_model=ImportResponse)
async def import_products(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
    shop_id: int = require_shop_id(Perm.IMPORT_WRITE),
    _rl: None = _import_limit,
):
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Only .xlsx files are allowed")
    content = await file.read()
    return await svc.import_products(content, session, shop_id)
