"""ERP 文档中心 HTTP 路由。"""

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse

from apps.vadmin.auth.utils.current import FullAdminAuth
from apps.vadmin.auth.utils.validation.auth import Auth
from core.exception import CustomException
from utils.response import SuccessResponse
from .schemas import PrintRenderInput, PrintTemplateInput
from .services import AttachmentService, DataExchangeService, PrintTemplateService
from .services.storage import AttachmentStorage


app = APIRouter()


@app.get("/attachments", summary="查询业务附件")
async def list_attachments(
    business_type: str,
    business_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.attachment.list"])),
):
    """查询指定业务对象附件。"""

    return SuccessResponse(await AttachmentService(auth.db, auth.user).list(business_type, business_id))


@app.post("/attachments", summary="上传业务附件")
async def upload_attachment(
    business_type: str = Form(...),
    business_id: int = Form(...),
    storage_type: str = Form("local"),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.attachment.create"])),
):
    """将附件保存到本地或 OSS 并关联业务对象。"""

    data = await AttachmentService(auth.db, auth.user).upload(
        business_type, business_id, storage_type, file, description
    )
    return SuccessResponse(data)


@app.get("/attachments/{attachment_id}/download", summary="下载业务附件")
async def download_attachment(
    attachment_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.attachment.list"])),
):
    """下载本地附件或跳转到 OSS 临时签名地址。"""

    row = await AttachmentService(auth.db, auth.user).get(attachment_id)
    if row.storage_type == "oss":
        return RedirectResponse(AttachmentStorage.download_url(row.storage_key))
    return FileResponse(
        path=row.storage_key,
        filename=row.file_name,
        media_type=row.mime_type or "application/octet-stream",
    )


@app.get("/attachments/{attachment_id}/download-url", summary="获取附件下载地址")
async def attachment_download_url(
    attachment_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.attachment.list"])),
):
    """为 OSS 附件返回临时签名地址，避免浏览器跨域跟随文件流重定向。"""

    row = await AttachmentService(auth.db, auth.user).get(attachment_id)
    if row.storage_type != "oss":
        raise CustomException("本地附件请使用文件流下载接口")
    return SuccessResponse(AttachmentStorage.download_url(row.storage_key))


@app.delete("/attachments/{attachment_id}", summary="删除业务附件")
async def delete_attachment(
    attachment_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.attachment.delete"])),
):
    """删除业务附件及对应物理文件。"""

    await AttachmentService(auth.db, auth.user).delete(attachment_id)
    return SuccessResponse("删除成功")


@app.get("/print-templates", summary="查询打印模板")
async def list_print_templates(
    business_type: str | None = None,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.print.list"])),
):
    """查询全部或指定业务类型的模板。"""

    return SuccessResponse(await PrintTemplateService(auth.db).list(business_type))


@app.post("/print-templates", summary="新增打印模板")
async def create_print_template(
    data: PrintTemplateInput,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.print.create"])),
):
    """创建打印模板。"""

    return SuccessResponse(await PrintTemplateService(auth.db).save(data))


@app.put("/print-templates/{template_id}", summary="修改打印模板")
async def update_print_template(
    template_id: int,
    data: PrintTemplateInput,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.print.update"])),
):
    """修改打印模板并增加版本号。"""

    return SuccessResponse(await PrintTemplateService(auth.db).save(data, template_id))


@app.post("/print-templates/render", summary="渲染打印模板")
async def render_print_template(
    data: PrintRenderInput,
    auth: Auth = Depends(FullAdminAuth()),
):
    """为已登录后台用户返回可以直接预览和浏览器打印的 HTML。"""

    html = await PrintTemplateService(auth.db).render(
        data.data, data.template_id, data.business_type
    )
    return SuccessResponse(html)


@app.delete("/print-templates/{template_id}", summary="删除打印模板")
async def delete_print_template(
    template_id: int,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.print.delete"])),
):
    """软删除打印模板。"""

    await PrintTemplateService(auth.db).delete(template_id)
    return SuccessResponse("删除成功")


def excel_response(stream, filename: str) -> StreamingResponse:
    """创建支持中文文件名的 Excel 下载响应。"""

    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@app.get("/exchange/resources", summary="获取可导入导出资源")
async def exchange_resources(
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.exchange.list"])),
):
    """返回数据交换支持的基础资料类型。"""

    return SuccessResponse(DataExchangeService.resources())


@app.get("/exchange/{resource}/template", summary="下载导入模板")
async def download_import_template(
    resource: str,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.exchange.list"])),
):
    """下载指定基础资料的 Excel 模板。"""

    stream, filename = await DataExchangeService(auth.db, auth.user).template(resource)
    return excel_response(stream, filename)


@app.get("/exchange/{resource}/export", summary="导出基础资料")
async def export_resource(
    resource: str,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.exchange.export"])),
):
    """将指定基础资料导出为 Excel。"""

    stream, filename = await DataExchangeService(auth.db, auth.user).export(resource)
    return excel_response(stream, filename)


@app.post("/exchange/{resource}/import", summary="导入基础资料")
async def import_resource(
    resource: str,
    mode: str = Form("upsert"),
    file: UploadFile = File(...),
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.exchange.import"])),
):
    """从 Excel 新增或按编码更新基础资料。"""

    return SuccessResponse(await DataExchangeService(auth.db, auth.user).import_file(resource, file, mode))


@app.get("/exchange-tasks", summary="查询导入导出历史")
async def exchange_tasks(
    page: int = 1,
    limit: int = 20,
    auth: Auth = Depends(FullAdminAuth(permissions=["erp.documents.exchange.list"])),
):
    """分页查询数据交换历史和错误明细。"""

    rows, count = await DataExchangeService(auth.db, auth.user).tasks(page, limit)
    return SuccessResponse(rows, count=count)
