import { renderPrintTemplateApi } from '@/api/erp/documents'
import { ElMessage } from 'element-plus'

/** 在新窗口加载业务模板，并在渲染完成后唤起浏览器打印。 */
export const printBusinessDocument = async (
  businessType: string,
  loadData: () => Promise<Record<string, any>>
) => {
  const preview = window.open('', '_blank')
  if (!preview) {
    ElMessage.warning('打印窗口被浏览器拦截，请允许本站打开弹窗')
    return
  }

  preview.document.write(
    "<!doctype html><html><head><meta charset='utf-8'><title>正在生成打印内容</title></head>" +
      "<body style='font-family:Microsoft YaHei;padding:32px'>正在生成打印内容，请稍候……</body></html>"
  )
  preview.document.close()

  try {
    const data = await loadData()
    const response = await renderPrintTemplateApi({ business_type: businessType, data })
    preview.document.open()
    preview.document.write(response.data)
    preview.document.close()
    preview.focus()
    window.setTimeout(() => preview.print(), 300)
  } catch (error: any) {
    preview.document.body.textContent = `打印内容生成失败：${error?.message || '未知错误'}`
    throw error
  }
}

/** 从商品的多单位快照中读取单据行所选单位名称。 */
export const documentUnitName = (line: any) =>
  line.product?.units?.find((item: any) => item.unit_id === line.unit_id)?.unit_name || '-'

/** 生成带 SKU 编码的打印商品名称。 */
export const documentProductName = (line: any) =>
  [line.product?.code, line.product?.name].filter(Boolean).join(' ') || `商品 #${line.product_id}`
