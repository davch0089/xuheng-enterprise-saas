"""ERP 业务附件应用服务。"""

from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import false, select

from core.exception import CustomException
from ..models import ErpAttachment
from ..schemas import AttachmentOut
from .storage import AttachmentStorage


class AttachmentService:
    """管理附件上传、查询、下载和删除。"""

    def __init__(self, db, user=None):
        """绑定数据库会话和当前操作人。"""

        self.db = db
        self.user = user

    async def list(self, business_type: str, business_id: int) -> list[dict]:
        """查询一个业务对象的全部有效附件。"""

        rows = (
            await self.db.scalars(
                select(ErpAttachment)
                .where(
                    ErpAttachment.business_type == business_type,
                    ErpAttachment.business_id == business_id,
                    ErpAttachment.is_delete == false(),
                )
                .order_by(ErpAttachment.id.desc())
            )
        ).all()
        return [AttachmentOut.model_validate(row).model_dump() for row in rows]

    async def upload(
        self,
        business_type: str,
        business_id: int,
        storage_type: str,
        file: UploadFile,
        description: str | None,
    ) -> dict:
        """保存文件并创建业务附件元数据。"""

        if not business_type.strip() or business_id <= 0:
            raise CustomException("必须指定有效的业务类型和业务 ID")
        stored = await AttachmentStorage.save(file, storage_type)
        row = ErpAttachment(
            business_type=business_type.strip(),
            business_id=business_id,
            file_name=file.filename or "attachment",
            file_ext=Path(file.filename or "").suffix.lower() or None,
            mime_type=file.content_type,
            file_size=stored.file_size,
            storage_type=storage_type,
            storage_key=stored.storage_key,
            file_url=stored.file_url,
            checksum=stored.checksum,
            description=description,
            uploaded_by_id=getattr(self.user, "id", None),
            uploaded_by_name=getattr(self.user, "name", None),
        )
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return AttachmentOut.model_validate(row).model_dump()

    async def get(self, attachment_id: int) -> ErpAttachment:
        """读取有效附件，不存在时抛出业务异常。"""

        row = await self.db.scalar(
            select(ErpAttachment).where(
                ErpAttachment.id == attachment_id,
                ErpAttachment.is_delete == false(),
            )
        )
        if not row:
            raise CustomException("附件不存在")
        return row

    async def delete(self, attachment_id: int) -> None:
        """删除物理文件并软删除附件记录。"""

        row = await self.get(attachment_id)
        await AttachmentStorage.delete(row.storage_type, row.storage_key)
        row.is_delete = True
        self.db.add(row)
        await self.db.flush()
