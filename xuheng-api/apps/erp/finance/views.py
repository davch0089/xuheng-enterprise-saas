"""资金、核销、会计期间和经营利润 HTTP 接口。"""

from datetime import date

from fastapi import APIRouter, Depends

from apps.vadmin.auth.utils.current import AllUserAuth, FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from core.dependencies import IdList
from utils.response import SuccessResponse
from . import schemas
from .queries import FinanceQueryService
from .services import AccountingPeriodService, FundDocumentService, ProfitQueryService, SettlementService


app = APIRouter()


def permission(domain, action):
    """构造财务模块权限依赖。"""

    return FullAdminAuth(permissions=[f"erp.finance.{domain}.{action}"])


@app.get("/options")
async def options(auth: Auth = Depends(AllUserAuth())):
    """返回财务表单公共选项。"""

    return SuccessResponse(await FinanceQueryService(auth.db).options())


@app.get("/open-items")
async def open_items(customer_id: int | None = None, supplier_id: int | None = None, auth: Auth = Depends(permission("settlement", "list"))):
    """返回可核销开放项目及预收预付来源。"""

    return SuccessResponse(await FinanceQueryService(auth.db).open_items(customer_id, supplier_id))


@app.get("/accounts")
async def accounts(auth: Auth = Depends(permission("account", "list"))):
    """查询资金账户和余额。"""

    return SuccessResponse(await FundDocumentService(auth.db, auth.user.id).accounts())


@app.post("/accounts")
async def create_account(data: schemas.FundAccountInput, auth: Auth = Depends(permission("account", "create"))):
    """新增资金账户。"""

    return SuccessResponse(await FundDocumentService(auth.db, auth.user.id).save_account(data))


@app.put("/accounts/{account_id}")
async def update_account(account_id: int, data: schemas.FundAccountInput, auth: Auth = Depends(permission("account", "update"))):
    """修改资金账户资料。"""

    return SuccessResponse(await FundDocumentService(auth.db, auth.user.id).save_account(data, account_id))


@app.get("/documents")
async def documents(page: int = 1, limit: int = 20, document_type: str | None = None, status: str | None = None, date_start: date | None = None, date_end: date | None = None, auth: Auth = Depends(permission("fund", "list"))):
    """分页查询一般收付款和转账。"""

    data, count = await FundDocumentService(auth.db, auth.user.id).list(page, limit, document_type, status, date_start, date_end)
    return SuccessResponse(data, count=count)


@app.post("/documents")
async def create_document(data: schemas.FundDocumentInput, auth: Auth = Depends(permission("fund", "create"))):
    """新增资金草稿。"""

    return SuccessResponse(await FundDocumentService(auth.db, auth.user.id).save(data))


@app.put("/documents/{document_id}")
async def update_document(document_id: int, data: schemas.FundDocumentInput, auth: Auth = Depends(permission("fund", "update"))):
    """修改资金草稿。"""

    return SuccessResponse(await FundDocumentService(auth.db, auth.user.id).save(data, document_id))


@app.delete("/documents")
async def delete_documents(ids: IdList = Depends(), auth: Auth = Depends(permission("fund", "delete"))):
    """删除资金草稿。"""

    await FundDocumentService(auth.db, auth.user.id).delete(ids.ids)
    return SuccessResponse("删除成功")


@app.post("/documents/{document_id}/approve")
async def approve_document(document_id: int, auth: Auth = Depends(permission("fund", "approve"))):
    """审核资金单据。"""

    return SuccessResponse(await FundDocumentService(auth.db, auth.user.id).approve(document_id))


@app.post("/documents/{document_id}/unapprove")
async def unapprove_document(document_id: int, auth: Auth = Depends(permission("fund", "unapprove"))):
    """反审核并冲销资金单据。"""

    return SuccessResponse(await FundDocumentService(auth.db, auth.user.id).unapprove(document_id))


@app.get("/ledgers")
async def ledgers(page: int = 1, limit: int = 20, account_id: int | None = None, date_start: date | None = None, date_end: date | None = None, auth: Auth = Depends(permission("fund", "list"))):
    """分页查询不可变资金流水。"""

    data, count = await FundDocumentService(auth.db, auth.user.id).ledgers(page, limit, account_id, date_start, date_end)
    return SuccessResponse(data, count=count)


@app.get("/settlements")
async def settlements(page: int = 1, limit: int = 20, writeoff_type: str | None = None, status: str | None = None, auth: Auth = Depends(permission("settlement", "list"))):
    """分页查询核销单。"""

    data, count = await SettlementService(auth.db, auth.user.id).list(page, limit, writeoff_type, status)
    return SuccessResponse(data, count=count)


@app.get("/settlements/{document_id}")
async def settlement_detail(document_id: int, auth: Auth = Depends(permission("settlement", "view"))):
    """获取核销单详情。"""

    return SuccessResponse(await SettlementService(auth.db, auth.user.id).detail(document_id))


@app.post("/settlements")
async def create_settlement(data: schemas.SettlementDocumentInput, auth: Auth = Depends(permission("settlement", "create"))):
    """新增核销草稿。"""

    return SuccessResponse(await SettlementService(auth.db, auth.user.id).save(data))


@app.put("/settlements/{document_id}")
async def update_settlement(document_id: int, data: schemas.SettlementDocumentInput, auth: Auth = Depends(permission("settlement", "update"))):
    """修改核销草稿。"""

    return SuccessResponse(await SettlementService(auth.db, auth.user.id).save(data, document_id))


@app.delete("/settlements")
async def delete_settlements(ids: IdList = Depends(), auth: Auth = Depends(permission("settlement", "delete"))):
    """删除核销草稿。"""

    await SettlementService(auth.db, auth.user.id).delete(ids.ids)
    return SuccessResponse("删除成功")


@app.post("/settlements/{document_id}/approve")
async def approve_settlement(document_id: int, auth: Auth = Depends(permission("settlement", "approve"))):
    """审核核销单。"""

    return SuccessResponse(await SettlementService(auth.db, auth.user.id).approve(document_id))


@app.post("/settlements/{document_id}/unapprove")
async def unapprove_settlement(document_id: int, auth: Auth = Depends(permission("settlement", "unapprove"))):
    """反审核核销单。"""

    return SuccessResponse(await SettlementService(auth.db, auth.user.id).unapprove(document_id))


@app.get("/periods")
async def periods(auth: Auth = Depends(permission("period", "list"))):
    """查询会计期间。"""

    return SuccessResponse(await AccountingPeriodService(auth.db, auth.user.id).list())


@app.post("/periods")
async def create_period(data: schemas.AccountingPeriodInput, auth: Auth = Depends(permission("period", "create"))):
    """启用会计期间。"""

    return SuccessResponse(await AccountingPeriodService(auth.db, auth.user.id).create(data))


@app.post("/periods/{period_id}/close")
async def close_period(period_id: int, auth: Auth = Depends(permission("period", "close"))):
    """执行成本校验并结账。"""

    return SuccessResponse(await AccountingPeriodService(auth.db, auth.user.id).close(period_id))


@app.post("/periods/{period_id}/reopen")
async def reopen_period(period_id: int, auth: Auth = Depends(permission("period", "reopen"))):
    """反结账最近一期。"""

    return SuccessResponse(await AccountingPeriodService(auth.db, auth.user.id).reopen(period_id))


@app.get("/periods/cost-validation/{end_date}")
async def validate_cost(end_date: date, auth: Auth = Depends(permission("period", "list"))):
    """单独执行成本期末检查。"""

    return SuccessResponse(await AccountingPeriodService(auth.db, auth.user.id).validate_cost(end_date))


@app.get("/profit")
async def profit(date_start: date, date_end: date, auth: Auth = Depends(permission("profit", "list"))):
    """查询经营利润及 SKU 毛利明细。"""

    return SuccessResponse(await ProfitQueryService(auth.db).report(date_start, date_end))
