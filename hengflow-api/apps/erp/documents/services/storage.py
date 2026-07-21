"""ERP 附件本地与阿里云 OSS 存储适配器。"""

import hashlib
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from application.settings import ALIYUN_OSS, STATIC_ROOT
from core.exception import CustomException
from utils.file.aliyun_oss import AliyunOSS, BucketConf
from utils.file.file_manage import FileManage


ALLOWED_EXTENSIONS = {
    ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt",
    ".zip", ".rar", ".7z", ".xml", ".json",
}
MAX_FILE_SIZE = 50 * 1024 * 1024


@dataclass(frozen=True)
class StoredFile:
    """描述文件保存后的统一结果。"""

    storage_key: str
    file_url: str
    file_size: int
    checksum: str


class AttachmentStorage:
    """根据请求选择本地磁盘或阿里云 OSS 保存附件。"""

    @staticmethod
    async def validate(file: UploadFile) -> tuple[bytes, str]:
        """校验扩展名和文件大小，并返回内容及 SHA256。"""

        suffix = Path(file.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise CustomException(f"不支持 {suffix or '无扩展名'} 附件")
        content = await file.read()
        if not content:
            raise CustomException("不能上传空文件")
        if len(content) > MAX_FILE_SIZE:
            raise CustomException("附件大小不能超过 50MB")
        await file.seek(0)
        return content, hashlib.sha256(content).hexdigest()

    @staticmethod
    def oss_client() -> AliyunOSS:
        """校验 OSS 配置并创建客户端。"""

        required = ("accessKeyId", "accessKeySecret", "endpoint", "bucket", "baseUrl")
        if any(not ALIYUN_OSS.get(key) or ALIYUN_OSS.get(key) == key for key in required):
            raise CustomException("OSS 尚未配置，请先完善 application 配置")
        return AliyunOSS(BucketConf(**ALIYUN_OSS))

    @classmethod
    async def save(cls, file: UploadFile, storage_type: str) -> StoredFile:
        """保存附件并返回与存储实现无关的文件信息。"""

        content, checksum = await cls.validate(file)
        if storage_type == "local":
            result = await FileManage(file, "erp/attachments").async_save_local()
            return StoredFile(result["local_path"], result["remote_path"], len(content), checksum)
        if storage_type == "oss":
            client = cls.oss_client()
            url = await client.upload_file("erp/attachments", file)
            key = url.removeprefix(client.baseUrl).lstrip("/")
            return StoredFile(key, url, len(content), checksum)
        raise CustomException("附件存储方式只能选择 local 或 oss")

    @classmethod
    async def delete(cls, storage_type: str, storage_key: str) -> None:
        """删除附件的物理文件。"""

        if storage_type == "oss":
            cls.oss_client().delete_file(storage_key)
            return
        root = Path(STATIC_ROOT).resolve()
        target = Path(storage_key).resolve()
        if root not in target.parents:
            raise CustomException("附件路径不合法")
        if target.exists() and target.is_file():
            target.unlink()

    @classmethod
    def download_url(cls, storage_key: str) -> str:
        """为 OSS 私有文件生成一小时有效的下载地址。"""

        return cls.oss_client().sign_download_url(storage_key)
