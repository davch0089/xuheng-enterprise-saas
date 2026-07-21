"""库存查询的分页和单位展示公共能力。"""

from decimal import Decimal, ROUND_FLOOR

from sqlalchemy.ext.asyncio import AsyncSession

from ..services.inbound import InventoryService


class InventoryQueryBase:
    """为各类库存查询提供数据库会话和单位拆分工具。"""

    def __init__(self, db: AsyncSession):
        """绑定只读查询使用的数据库会话。"""

        self.db = db
        self.inventory = InventoryService(db)

    @staticmethod
    def _page(page: int, limit: int) -> tuple[int, int]:
        """限制页码和每页数量到安全范围。"""

        page = max(page, 1)
        limit = min(max(limit, 1), 100)
        return page, limit

    @staticmethod
    def _decimal_text(value: Decimal) -> str:
        """去掉十进制显示中无意义的尾随零。"""

        text = format(value, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text

    async def _unit_breakdown(self, product, quantity: Decimal) -> str:
        """将主单位数量拆分为多层单位可读文本。"""

        units = await self.inventory.product_units(product)
        if not units:
            return self._decimal_text(quantity)
        if len(units) == 1:
            return f"{self._decimal_text(quantity)}{units[0]['unit_name']}"
        sign = "-" if quantity < 0 else ""
        remaining = abs(Decimal(quantity))
        parts = []
        for index, unit in enumerate(sorted(units, key=lambda item: Decimal(item["to_base_rate"]), reverse=True)):
            rate = Decimal(unit["to_base_rate"])
            if rate <= 0:
                continue
            if index == len(units) - 1:
                count = remaining / rate
            else:
                count = (remaining / rate).to_integral_value(rounding=ROUND_FLOOR)
                remaining -= count * rate
            if count or not parts:
                parts.append(f"{self._decimal_text(count)}{unit['unit_name']}")
        return sign + " ".join(parts)
