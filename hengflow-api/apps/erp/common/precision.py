"""ERP 各业务领域共用的数量、金额和成本精度规则。"""

from decimal import Decimal, ROUND_HALF_UP


QTY = Decimal("0.000001")
MONEY = Decimal("0.0001")
COST = Decimal("0.000001")


def quantize(value: Decimal, precision: Decimal) -> Decimal:
    """按照 ERP 统一的四舍五入规则格式化数值。"""

    return Decimal(value).quantize(precision, rounding=ROUND_HALF_UP)
