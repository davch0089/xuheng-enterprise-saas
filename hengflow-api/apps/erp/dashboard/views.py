"""ERP 经营驾驶舱 HTTP 接口。"""

from fastapi import APIRouter, Depends, Query

from apps.vadmin.auth.utils.current import FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from utils.response import SuccessResponse

from .service import ErpDashboardService


app = APIRouter()


@app.get("", summary="ERP 经营驾驶舱")
async def dashboard(
    days: int = Query(default=30, ge=7, le=90),
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.dashboard.view"])),
):
    """返回指定周期的 ERP 核心经营指标、趋势和预警。"""

    return SuccessResponse(await ErpDashboardService(auth.db).overview(days))
