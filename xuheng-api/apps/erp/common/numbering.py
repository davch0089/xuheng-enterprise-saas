"""序衡单据编号。按业务日加行锁取号，不使用插入即更新。"""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from apps.erp.inventory.models import ErpDocumentSequence


async def allocate_document_no(db, document_type: str, prefix: str, business_date) -> str:
    """锁定当天序列行，加一后返回序衡单号。"""

    row = await _lock_sequence(db, document_type, business_date)
    if row is None:
        nested = await db.begin_nested()
        try:
            row = ErpDocumentSequence(
                document_type=document_type,
                business_date=business_date,
                current_value=0,
            )
            db.add(row)
            await db.flush()
            await nested.commit()
        except IntegrityError:
            await nested.rollback()
            row = await _lock_sequence(db, document_type, business_date)
            if row is None:
                raise
    row.current_value = int(row.current_value) + 1
    await db.flush()
    return f"XH-{prefix}-{business_date:%Y%m%d}-{row.current_value:05d}"


async def _lock_sequence(db, document_type: str, business_date):
    """按单据类型和业务日期锁定序列行。"""

    return await db.scalar(
        select(ErpDocumentSequence)
        .where(
            ErpDocumentSequence.document_type == document_type,
            ErpDocumentSequence.business_date == business_date,
        )
        .with_for_update()
    )
