import request from '@/config/axios'

/** 查询附件。 */
export const getAttachmentsApi = (params: {
  business_type: string
  business_id: number
}): Promise<IResponse> => request.get({ url: '/erp/documents/attachments', params })

/** 上传附件并选择本地或 OSS 存储。 */
export const uploadAttachmentApi = (data: FormData): Promise<IResponse> =>
  request.post({
    url: '/erp/documents/attachments',
    data,
    headersType: 'multipart/form-data'
  })

/** 下载附件文件流。 */
export const downloadAttachmentApi = (id: number): Promise<any> =>
  request.get({ url: `/erp/documents/attachments/${id}/download`, responseType: 'blob' })

/** 获取 OSS 私有附件的一小时临时签名地址。 */
export const getAttachmentDownloadUrlApi = (id: number): Promise<IResponse> =>
  request.get({ url: `/erp/documents/attachments/${id}/download-url` })

/** 删除附件。 */
export const deleteAttachmentApi = (id: number): Promise<IResponse> =>
  request.delete({ url: `/erp/documents/attachments/${id}` })

/** 查询打印模板。 */
export const getPrintTemplatesApi = (business_type?: string): Promise<IResponse> =>
  request.get({ url: '/erp/documents/print-templates', params: { business_type } })

/** 新增打印模板。 */
export const addPrintTemplateApi = (data: any): Promise<IResponse> =>
  request.post({ url: '/erp/documents/print-templates', data })

/** 修改打印模板。 */
export const putPrintTemplateApi = (id: number, data: any): Promise<IResponse> =>
  request.put({ url: `/erp/documents/print-templates/${id}`, data })

/** 删除打印模板。 */
export const deletePrintTemplateApi = (id: number): Promise<IResponse> =>
  request.delete({ url: `/erp/documents/print-templates/${id}` })

/** 使用模板和业务上下文生成完整打印 HTML。 */
export const renderPrintTemplateApi = (data: any): Promise<IResponse> =>
  request.post({ url: '/erp/documents/print-templates/render', data })

/** 查询支持 Excel 导入导出的资源。 */
export const getExchangeResourcesApi = (): Promise<IResponse> =>
  request.get({ url: '/erp/documents/exchange/resources' })

/** 下载 Excel 导入模板。 */
export const downloadExchangeTemplateApi = (resource: string): Promise<any> =>
  request.get({
    url: `/erp/documents/exchange/${resource}/template`,
    responseType: 'blob'
  })

/** 导出资源 Excel。 */
export const exportExchangeResourceApi = (resource: string): Promise<any> =>
  request.get({
    url: `/erp/documents/exchange/${resource}/export`,
    responseType: 'blob'
  })

/** 导入资源 Excel。 */
export const importExchangeResourceApi = (resource: string, data: FormData): Promise<IResponse> =>
  request.post({
    url: `/erp/documents/exchange/${resource}/import`,
    data,
    headersType: 'multipart/form-data'
  })

/** 查询数据交换历史。 */
export const getExchangeTasksApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/documents/exchange-tasks', params })
