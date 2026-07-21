"""资金账户、一般收付款、转账与不可变资金流水服务。"""

from datetime import datetime
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, false, func, or_, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from apps.erp.common import MONEY, quantize
from core.exception import CustomException
from .. import models, schemas
from .common import columns, next_no
from .period import AccountingPeriodService


class FundPostingEngine:
    """以行锁、幂等键和反向流水维护资金账户余额。"""

    def __init__(self, db, user_id: int | None = None):
        """绑定当前事务和操作人。"""

        self.db = db
        self.user_id = user_id

    async def post(self, *, account_id, amount, source_type, source_id, source_no, posting_version, entry_type, occurred_at):
        """向资金账户写入一条幂等收支流水。"""

        key = f"FUND:{source_type}:{source_id}:{entry_type}:V{posting_version}"
        existing = await self.db.scalar(select(models.ErpFundLedger).where(models.ErpFundLedger.idempotency_key == key))
        if existing:
            return existing
        await AccountingPeriodService(self.db, self.user_id).ensure_open(occurred_at.date(), "资金过账")
        account = await self.db.scalar(select(models.ErpFundAccount).where(
            models.ErpFundAccount.id == account_id, models.ErpFundAccount.is_delete == false(),
            models.ErpFundAccount.is_active == True,
        ))
        if account is None:
            raise CustomException("资金账户不存在或已停用")
        await self.db.execute(mysql_insert(models.ErpFundAccountBalance).values(
            account_id=account_id, amount=0
        ).on_duplicate_key_update(account_id=account_id))
        balance = await self.db.scalar(select(models.ErpFundAccountBalance).where(
            models.ErpFundAccountBalance.account_id == account_id
        ).with_for_update())
        before = quantize(Decimal(balance.amount), MONEY)
        amount = quantize(Decimal(amount), MONEY)
        after = quantize(before + amount, MONEY)
        ledger = models.ErpFundLedger(
            entry_no=f"{source_no}-{entry_type}-V{posting_version}"[:80], idempotency_key=key,
            entry_type=entry_type, account_id=account_id, source_type=source_type,
            source_id=source_id, source_no=source_no, posting_version=posting_version,
            amount=amount, balance_before=before, balance_after=after,
            occurred_at=occurred_at, operator_id=self.user_id,
        )
        balance.amount = after
        balance.last_occurred_at = occurred_at
        self.db.add(ledger)
        await self.db.flush()
        balance.last_entry_id = ledger.id
        return ledger

    async def reverse(self, source_type: str, source_id: int, posting_version: int):
        """为一个来源单据的每条原资金流水生成反向冲销流水。"""

        originals = list((await self.db.scalars(select(models.ErpFundLedger).where(
            models.ErpFundLedger.source_type == source_type,
            models.ErpFundLedger.source_id == source_id,
            models.ErpFundLedger.posting_version == posting_version,
            models.ErpFundLedger.reversal_of_id.is_(None),
        ).with_for_update())).all())
        if not originals:
            raise CustomException("找不到需要冲销的资金流水")
        await AccountingPeriodService(self.db, self.user_id).ensure_open(originals[0].occurred_at.date(), "资金冲销")
        result = []
        for original in originals:
            key = f"FUND:REVERSE:{original.id}"
            existing = await self.db.scalar(select(models.ErpFundLedger).where(models.ErpFundLedger.idempotency_key == key))
            if existing:
                result.append(existing)
                continue
            balance = await self.db.scalar(select(models.ErpFundAccountBalance).where(
                models.ErpFundAccountBalance.account_id == original.account_id
            ).with_for_update())
            before = quantize(Decimal(balance.amount), MONEY)
            after = quantize(before - Decimal(original.amount), MONEY)
            reversal = models.ErpFundLedger(
                entry_no=f"{original.source_no}-FUND-R{original.id}"[:80], idempotency_key=key,
                entry_type="REVERSAL", account_id=original.account_id, source_type=source_type,
                source_id=source_id, source_no=original.source_no, posting_version=posting_version,
                reversal_of_id=original.id, amount=-Decimal(original.amount), balance_before=before,
                balance_after=after, occurred_at=datetime.now(), operator_id=self.user_id,
            )
            balance.amount = after
            balance.last_occurred_at = reversal.occurred_at
            self.db.add(reversal)
            await self.db.flush()
            balance.last_entry_id = reversal.id
            result.append(reversal)
        return result


class FundDocumentService:
    """管理资金账户以及一般收款、付款和内部转账。"""

    def __init__(self, db, user_id: int | None = None):
        """绑定当前事务和操作人。"""

        self.db = db
        self.user_id = user_id

    async def options(self):
        """返回启用资金账户及其实时余额。"""

        rows = (await self.db.execute(select(models.ErpFundAccount, models.ErpFundAccountBalance.amount).outerjoin(
            models.ErpFundAccountBalance, models.ErpFundAccountBalance.account_id == models.ErpFundAccount.id
        ).where(models.ErpFundAccount.is_delete == false(), models.ErpFundAccount.is_active == True).order_by(models.ErpFundAccount.code))).all()
        return jsonable_encoder([{"value": account.id, "label": f"{account.code} - {account.name}", "balance": amount or 0} for account, amount in rows])

    async def accounts(self):
        """返回全部资金账户及余额。"""

        rows = (await self.db.execute(select(models.ErpFundAccount, models.ErpFundAccountBalance.amount).outerjoin(
            models.ErpFundAccountBalance, models.ErpFundAccountBalance.account_id == models.ErpFundAccount.id
        ).where(models.ErpFundAccount.is_delete == false()).order_by(models.ErpFundAccount.code))).all()
        return jsonable_encoder([{**columns(account), "balance": amount or 0} for account, amount in rows])

    async def save_account(self, data: schemas.FundAccountInput, account_id: int | None = None):
        """新增或修改资金账户；开户余额仅在新增时写入资金流水。"""

        duplicate = select(models.ErpFundAccount.id).where(models.ErpFundAccount.code == data.code, models.ErpFundAccount.is_delete == false())
        if account_id:
            duplicate = duplicate.where(models.ErpFundAccount.id != account_id)
        if await self.db.scalar(duplicate) is not None:
            raise CustomException("资金账户编码已存在")
        if account_id:
            account = await self.db.get(models.ErpFundAccount, account_id)
            if account is None or account.is_delete:
                raise CustomException("资金账户不存在")
        else:
            account = models.ErpFundAccount()
            self.db.add(account)
        values = data.model_dump(exclude={"opening_balance"})
        for key, value in values.items():
            setattr(account, key, value)
        await self.db.flush()
        balance = await self.db.scalar(select(models.ErpFundAccountBalance).where(models.ErpFundAccountBalance.account_id == account.id))
        if balance is None:
            balance = models.ErpFundAccountBalance(account_id=account.id, amount=data.opening_balance)
            self.db.add(balance)
        elif account_id and data.opening_balance != Decimal(balance.amount):
            raise CustomException("账户建立后不能直接修改余额，请使用收付款或转账单")
        await self.db.flush()
        return jsonable_encoder({**columns(account), "balance": balance.amount})

    async def save(self, data: schemas.FundDocumentInput, document_id: int | None = None):
        """新增或修改一般资金草稿。"""

        await AccountingPeriodService(self.db, self.user_id).ensure_open(data.business_date, "新增或修改资金单据")
        if document_id:
            document = await self._lock(document_id)
            if document.status != "draft":
                raise CustomException("只有草稿资金单据可以修改")
        else:
            prefix = {"receipt": "FR", "payment": "FP", "transfer": "FT"}.get(data.document_type)
            if not prefix:
                raise CustomException("不支持的资金单据类型")
            number = data.document_no or await next_no(self.db, f"fund_{data.document_type}", prefix, data.business_date)
            document = models.ErpFundDocument(document_no=number, created_by_id=self.user_id)
            self.db.add(document)
        for key, value in data.model_dump(exclude={"document_no"}).items():
            setattr(document, key, value)
        await self.db.flush()
        return jsonable_encoder(columns(document))

    async def approve(self, document_id: int):
        """审核收款、付款或转账并写入资金流水。"""

        document = await self._lock(document_id)
        if document.status != "draft":
            raise CustomException("只有草稿资金单据可以审核")
        version, now = document.posting_version + 1, datetime.now()
        engine = FundPostingEngine(self.db, self.user_id)
        if document.document_type in ("payment", "transfer"):
            await engine.post(account_id=document.from_account_id, amount=-Decimal(document.amount), source_type="fund_document", source_id=document.id, source_no=document.document_no, posting_version=version, entry_type="PAYMENT" if document.document_type == "payment" else "TRANSFER_OUT", occurred_at=datetime.combine(document.business_date, now.time()))
        if document.document_type in ("receipt", "transfer"):
            await engine.post(account_id=document.to_account_id, amount=Decimal(document.amount), source_type="fund_document", source_id=document.id, source_no=document.document_no, posting_version=version, entry_type="RECEIPT" if document.document_type == "receipt" else "TRANSFER_IN", occurred_at=datetime.combine(document.business_date, now.time()))
        document.status, document.posting_version = "approved", version
        document.approved_by_id, document.approved_at = self.user_id, now
        await self.db.flush()
        return jsonable_encoder(columns(document))

    async def unapprove(self, document_id: int):
        """反审核资金单据并生成反向资金流水。"""

        document = await self._lock(document_id)
        if document.status != "approved":
            raise CustomException("只有已审核资金单据可以反审核")
        await FundPostingEngine(self.db, self.user_id).reverse("fund_document", document.id, document.posting_version)
        document.status, document.approved_by_id, document.approved_at = "draft", None, None
        await self.db.flush()
        return jsonable_encoder(columns(document))

    async def list(self, page, limit, document_type=None, status=None, date_start=None, date_end=None):
        """分页查询一般资金单据。"""

        conditions = [models.ErpFundDocument.is_delete == false()]
        if document_type:
            conditions.append(models.ErpFundDocument.document_type == document_type)
        if status:
            conditions.append(models.ErpFundDocument.status == status)
        if date_start:
            conditions.append(models.ErpFundDocument.business_date >= date_start)
        if date_end:
            conditions.append(models.ErpFundDocument.business_date <= date_end)
        count = await self.db.scalar(select(func.count(models.ErpFundDocument.id)).where(*conditions))
        rows = list((await self.db.scalars(select(models.ErpFundDocument).where(*conditions).order_by(models.ErpFundDocument.business_date.desc(), models.ErpFundDocument.id.desc()).offset((page - 1) * limit).limit(limit))).all())
        return jsonable_encoder([columns(item) for item in rows]), count or 0

    async def delete(self, ids):
        """删除资金草稿。"""

        rows = list((await self.db.scalars(select(models.ErpFundDocument).where(models.ErpFundDocument.id.in_(ids), models.ErpFundDocument.is_delete == false()))).all())
        if len(rows) != len(set(ids)) or any(item.status != "draft" for item in rows):
            raise CustomException("只能删除存在的草稿资金单据")
        for item in rows:
            await AccountingPeriodService(self.db, self.user_id).ensure_open(item.business_date, "删除资金单据")
            item.is_delete = True
        await self.db.flush()

    async def ledgers(self, page, limit, account_id=None, date_start=None, date_end=None):
        """分页查询不可变资金流水。"""

        conditions = [models.ErpFundLedger.is_delete == false()]
        if account_id:
            conditions.append(models.ErpFundLedger.account_id == account_id)
        if date_start:
            conditions.append(models.ErpFundLedger.occurred_at >= datetime.combine(date_start, datetime.min.time()))
        if date_end:
            conditions.append(models.ErpFundLedger.occurred_at <= datetime.combine(date_end, datetime.max.time()))
        count = await self.db.scalar(select(func.count(models.ErpFundLedger.id)).where(*conditions))
        rows = list((await self.db.scalars(select(models.ErpFundLedger).where(*conditions).order_by(models.ErpFundLedger.occurred_at.desc(), models.ErpFundLedger.id.desc()).offset((page - 1) * limit).limit(limit))).all())
        return jsonable_encoder([columns(item) for item in rows]), count or 0

    async def _lock(self, document_id):
        """锁定并返回资金单据。"""

        document = await self.db.scalar(select(models.ErpFundDocument).where(models.ErpFundDocument.id == document_id, models.ErpFundDocument.is_delete == false()).with_for_update())
        if document is None:
            raise CustomException("资金单据不存在")
        return document
