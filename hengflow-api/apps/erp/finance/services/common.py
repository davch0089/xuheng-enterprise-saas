"""财务服务共用的编号和序列化能力。"""

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert

from apps.erp.inventory.models import ErpDocumentSequence


async def next_no(db, document_type: str, prefix: str, business_date) -> str:
    """利用 ERP 公共原子序列生成财务单号。"""

    await db.execute(
        mysql_insert(ErpDocumentSequence)
        .values(document_type=document_type, business_date=business_date, current_value=1)
        .on_duplicate_key_update(current_value=ErpDocumentSequence.current_value + 1, update_datetime=func.now())
    )
    value = await db.scalar(select(ErpDocumentSequence.current_value).where(
        ErpDocumentSequence.document_type == document_type,
        ErpDocumentSequence.business_date == business_date,
    ))
    return f"{prefix}{business_date:%Y%m%d}{value:04d}"


def columns(obj) -> dict:
    """把 BaseModel ORM 实体转换成普通字典。"""

    # 服务器默认时间字段在 flush 后可能仍处于 expired 状态；这里不触发异步懒加载。
    return {key: obj.__dict__.get(key) for key in obj.get_column_attrs()}
