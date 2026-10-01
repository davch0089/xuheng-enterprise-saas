"""从环境变量读取数据库、缓存及外部服务配置。"""

import os


def as_bool(name: str, default: bool = False) -> bool:
    """把环境变量解析为布尔值。"""

    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+asyncmy://root:change_me@127.0.0.1:3306/hengflow",
)
REDIS_DB_ENABLE = as_bool("REDIS_ENABLED", True)
REDIS_DB_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/1")
MONGO_DB_ENABLE = as_bool("MONGO_ENABLED", False)
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "xuheng")
MONGO_DB_URL = os.getenv(
    "MONGO_URL",
    f"mongodb://127.0.0.1:27017/?authSource={MONGO_DB_NAME}",
)

ALIYUN_OSS = {
    "accessKeyId": os.getenv("OSS_ACCESS_KEY_ID", ""),
    "accessKeySecret": os.getenv("OSS_ACCESS_KEY_SECRET", ""),
    "endpoint": os.getenv("OSS_ENDPOINT", ""),
    "bucket": os.getenv("OSS_BUCKET", ""),
    "baseUrl": os.getenv("OSS_BASE_URL", ""),
}

IP_PARSE_ENABLE = as_bool("IP_PARSE_ENABLED", False)
IP_PARSE_TOKEN = os.getenv("IP_PARSE_TOKEN", "")
