import request from '@/config/axios'

export type SalesDocumentKind = 'orders' | 'deliveries' | 'returns'

/** 获取销售单据表单选项。 */
export const getSalesOptionsApi = (): Promise<IResponse> =>
  request.get({ url: '/erp/sales/options' })

/** 搜索销售商品及指定仓库的可用库存。 */
export const searchSalesProductsApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/sales/products', params })

/** 分页查询指定类型的销售单据。 */
export const getSalesDocumentListApi = (kind: SalesDocumentKind, params: any): Promise<IResponse> =>
  request.get({ url: `/erp/sales/${kind}`, params })

/** 获取指定销售单据详情。 */
export const getSalesDocumentApi = (kind: SalesDocumentKind, id: number): Promise<IResponse> =>
  request.get({ url: `/erp/sales/${kind}/${id}` })

/** 新增指定类型的销售草稿。 */
export const addSalesDocumentApi = (kind: SalesDocumentKind, data: any): Promise<IResponse> =>
  request.post({ url: `/erp/sales/${kind}`, data })

/** 修改指定类型的销售草稿。 */
export const putSalesDocumentApi = (
  kind: SalesDocumentKind,
  id: number,
  data: any
): Promise<IResponse> => request.put({ url: `/erp/sales/${kind}/${id}`, data })

/** 批量删除指定类型的销售草稿。 */
export const delSalesDocumentApi = (kind: SalesDocumentKind, ids: number[]): Promise<IResponse> =>
  request.delete({ url: `/erp/sales/${kind}`, data: ids })

/** 审核指定销售单据。 */
export const approveSalesDocumentApi = (kind: SalesDocumentKind, id: number): Promise<IResponse> =>
  request.post({ url: `/erp/sales/${kind}/${id}/approve` })

/** 反审核指定销售单据。 */
export const unapproveSalesDocumentApi = (
  kind: SalesDocumentKind,
  id: number
): Promise<IResponse> => request.post({ url: `/erp/sales/${kind}/${id}/unapprove` })

/** 获取仍有可出库数量的销售订单。 */
export const getSalesSourceOrdersApi = (params?: any): Promise<IResponse> =>
  request.get({ url: '/erp/sales/source-orders', params })

/** 获取仍有可退数量的销售出库单。 */
export const getSalesSourceDeliveriesApi = (params?: any): Promise<IResponse> =>
  request.get({ url: '/erp/sales/source-deliveries', params })

/** 分页查询客户应收开放项。 */
export const getReceivableListApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/sales/receivables', params })

/** 分页查询销售收款单。 */
export const getSalesReceiptListApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/sales/receipts', params })

/** 获取销售收款单详情。 */
export const getSalesReceiptApi = (id: number): Promise<IResponse> =>
  request.get({ url: `/erp/sales/receipts/${id}` })

/** 新增销售收款草稿。 */
export const addSalesReceiptApi = (data: any): Promise<IResponse> =>
  request.post({ url: '/erp/sales/receipts', data })

/** 修改销售收款草稿。 */
export const putSalesReceiptApi = (id: number, data: any): Promise<IResponse> =>
  request.put({ url: `/erp/sales/receipts/${id}`, data })

/** 批量删除销售收款草稿。 */
export const delSalesReceiptApi = (ids: number[]): Promise<IResponse> =>
  request.delete({ url: '/erp/sales/receipts', data: ids })

/** 审核收款并核销应收。 */
export const approveSalesReceiptApi = (id: number): Promise<IResponse> =>
  request.post({ url: `/erp/sales/receipts/${id}/approve` })

/** 反审核收款并撤销核销。 */
export const unapproveSalesReceiptApi = (id: number): Promise<IResponse> =>
  request.post({ url: `/erp/sales/receipts/${id}/unapprove` })
