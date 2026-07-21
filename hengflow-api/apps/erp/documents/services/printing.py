"""ERP HTML 打印模板应用服务。"""

from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy import false, select, update

from core.exception import CustomException
from ..models import ErpPrintTemplate
from ..schemas import PrintTemplateInput, PrintTemplateOut


class PrintTemplateService:
    """维护打印模板并在沙箱环境内渲染业务数据。"""

    def __init__(self, db):
        """绑定数据库会话。"""

        self.db = db

    async def list(self, business_type: str | None = None) -> list[dict]:
        """按业务类型查询打印模板。"""

        statement = select(ErpPrintTemplate).where(ErpPrintTemplate.is_delete == false())
        if business_type:
            statement = statement.where(ErpPrintTemplate.business_type == business_type)
        rows = (await self.db.scalars(statement.order_by(ErpPrintTemplate.business_type, ErpPrintTemplate.id))).all()
        return [PrintTemplateOut.model_validate(row).model_dump() for row in rows]

    async def get(self, template_id: int) -> ErpPrintTemplate:
        """读取有效打印模板。"""

        row = await self.db.scalar(
            select(ErpPrintTemplate).where(
                ErpPrintTemplate.id == template_id,
                ErpPrintTemplate.is_delete == false(),
            )
        )
        if not row:
            raise CustomException("打印模板不存在")
        return row

    async def save(self, data: PrintTemplateInput, template_id: int | None = None) -> dict:
        """新增或修改模板，并保证同一业务类型只有一个默认模板。"""

        values = data.model_dump()
        duplicate = await self.db.scalar(
            select(ErpPrintTemplate.id).where(
                ErpPrintTemplate.code == data.code,
                ErpPrintTemplate.is_delete == false(),
                ErpPrintTemplate.id != (template_id or 0),
            )
        )
        if duplicate:
            raise CustomException("打印模板编码已存在")
        if data.is_default:
            await self.db.execute(
                update(ErpPrintTemplate)
                .where(
                    ErpPrintTemplate.business_type == data.business_type,
                    ErpPrintTemplate.is_delete == false(),
                )
                .values(is_default=False)
            )
        if template_id:
            row = await self.get(template_id)
            for key, value in values.items():
                setattr(row, key, value)
            row.version += 1
        else:
            row = ErpPrintTemplate(**values)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return PrintTemplateOut.model_validate(row).model_dump()

    async def delete(self, template_id: int) -> None:
        """软删除打印模板。"""

        row = await self.get(template_id)
        row.is_delete = True
        self.db.add(row)
        await self.db.flush()

    async def render(
        self,
        data: dict,
        template_id: int | None = None,
        business_type: str | None = None,
    ) -> str:
        """使用指定模板或业务默认模板渲染完整可打印 HTML。"""

        if template_id:
            row = await self.get(template_id)
        elif business_type:
            row = await self.db.scalar(
                select(ErpPrintTemplate).where(
                    ErpPrintTemplate.business_type == business_type,
                    ErpPrintTemplate.is_default == True,
                    ErpPrintTemplate.is_active == True,
                    ErpPrintTemplate.is_delete == false(),
                )
            )
            if not row and business_type != "generic":
                row = await self.db.scalar(
                    select(ErpPrintTemplate).where(
                        ErpPrintTemplate.business_type == "generic",
                        ErpPrintTemplate.is_default == True,
                        ErpPrintTemplate.is_active == True,
                        ErpPrintTemplate.is_delete == false(),
                    )
                )
            if not row:
                raise CustomException("该业务类型及通用类型均未配置默认打印模板")
        else:
            raise CustomException("必须指定模板或业务类型")
        environment = SandboxedEnvironment(
            autoescape=True,
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        try:
            body = environment.from_string(row.content_html).render(**data)
        except Exception as exc:
            raise CustomException(f"模板渲染失败：{exc}") from exc
        page = f"@page {{ size: {row.paper_size} {row.orientation}; margin: {row.margin_mm}mm; }}"
        return f"<!doctype html><html><head><meta charset='utf-8'><style>{page}{row.style_css or ''}</style></head><body>{body}</body></html>"
