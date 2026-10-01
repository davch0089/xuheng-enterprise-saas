"""登录令牌只携带凭据标记，不携带密码哈希。"""

import hashlib
import hmac

from application import settings


def credential_mark(password_hash: str) -> str:
    """用服务端密钥对密码哈希做截断签名。"""

    digest = hmac.new(
        settings.SECRET_KEY.encode(),
        password_hash.encode(),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def access_claims(telephone: str, password_hash: str) -> dict:
    """访问令牌声明。"""

    return {"sub": telephone, "is_refresh": False, "cred": credential_mark(password_hash)}


def refresh_claims(telephone: str, password_hash: str) -> dict:
    """刷新令牌声明。"""

    return {"sub": telephone, "is_refresh": True, "cred": credential_mark(password_hash)}


def marks_match(password_hash: str, presented: str) -> bool:
    """比对令牌中的凭据标记与当前密码哈希。"""

    expected = credential_mark(password_hash)
    if not presented or len(presented) != len(expected):
        return False
    return hmac.compare_digest(expected, presented)
