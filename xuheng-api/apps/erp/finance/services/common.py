"""财务服务共用的编号和序列化能力。"""

from apps.erp.common.numbering import allocate_document_no


async def next_no(db, document_type: str, prefix: str, business_date) -> str:
    """按序衡行锁序列生成财务单号。"""

    return await allocate_document_no(db, document_type, prefix, business_date)


def columns(obj) -> dict:
    """把 BaseModel ORM 实体转换成普通字典。"""

    # 服务器默认时间字段在 flush 后可能仍处于 expired 状态；这里不触发异步懒加载。
    return {key: obj.__dict__.get(key) for key in obj.get_column_attrs()}
