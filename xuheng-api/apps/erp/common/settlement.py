"""商业单据表尾折扣、抹零和即时收付款计算。"""

from decimal import Decimal

from apps.erp.common import MONEY, quantize
from core.exception import CustomException


def calculate_document_settlement(
    gross_amount: Decimal,
    discount_rate: Decimal,
    rounding_amount: Decimal,
    current_payment_amount: Decimal,
) -> dict[str, Decimal]:
    """计算单据最终往来金额，并校验本次收付款不能超过应收应付。"""

    gross = quantize(Decimal(gross_amount), MONEY)
    rate = Decimal(discount_rate)
    rounding = quantize(Decimal(rounding_amount), MONEY)
    payment = quantize(Decimal(current_payment_amount), MONEY)
    discount = quantize(gross * (Decimal("100") - rate) / Decimal("100"), MONEY)
    settlement = quantize(gross - discount - rounding, MONEY)
    if settlement < 0:
        raise CustomException("折扣和抹零金额不能超过单据总额")
    if payment > settlement:
        raise CustomException("本次收付款不能超过折扣抹零后的单据金额")
    return {
        "settlement_discount_rate": rate,
        "settlement_discount_amount": discount,
        "rounding_amount": rounding,
        "settlement_amount": settlement,
        "current_payment_amount": payment,
    }
