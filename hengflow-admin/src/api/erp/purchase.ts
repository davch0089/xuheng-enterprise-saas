import request from '@/config/axios'

export type PurchaseDocumentKind = 'orders' | 'receipts' | 'returns'

/** 获取采购基础资料选项。 */
export const getPurchaseOptionsApi = (): Promise<IResponse> =>
  request.get({ url: '/erp/purchase/options' })

/** 搜索采购商品。 */
export const searchPurchaseProductsApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/purchase/products', params })

/** 查询采购订单、收货或退货列表。 */
export const getPurchaseDocumentListApi = (
  kind: PurchaseDocumentKind,
  params: any
): Promise<IResponse> => request.get({ url: `/erp/purchase/${kind}`, params })

/** 查询采购单据详情。 */
export const getPurchaseDocumentApi = (
  kind: PurchaseDocumentKind,
  id: number
): Promise<IResponse> => request.get({ url: `/erp/purchase/${kind}/${id}` })

/** 新增采购单据草稿。 */
export const addPurchaseDocumentApi = (kind: PurchaseDocumentKind, data: any): Promise<IResponse> =>
  request.post({ url: `/erp/purchase/${kind}`, data })

/** 修改采购单据草稿。 */
export const putPurchaseDocumentApi = (
  kind: PurchaseDocumentKind,
  id: number,
  data: any
): Promise<IResponse> => request.put({ url: `/erp/purchase/${kind}/${id}`, data })

/** 删除采购单据草稿。 */
export const delPurchaseDocumentApi = (
  kind: PurchaseDocumentKind,
  ids: number[]
): Promise<IResponse> => request.delete({ url: `/erp/purchase/${kind}`, data: ids })

/** 审核采购单据。 */
export const approvePurchaseDocumentApi = (
  kind: PurchaseDocumentKind,
  id: number
): Promise<IResponse> => request.post({ url: `/erp/purchase/${kind}/${id}/approve` })

/** 反审核采购单据。 */
export const unapprovePurchaseDocumentApi = (
  kind: PurchaseDocumentKind,
  id: number
): Promise<IResponse> => request.post({ url: `/erp/purchase/${kind}/${id}/unapprove` })

/** 查询仍有未收数量的采购订单。 */
export const getPurchaseSourceOrdersApi = (params?: any): Promise<IResponse> =>
  request.get({ url: '/erp/purchase/source-orders', params })

/** 查询仍有可退数量的采购收货单。 */
export const getPurchaseSourceReceiptsApi = (params?: any): Promise<IResponse> =>
  request.get({ url: '/erp/purchase/source-receipts', params })

/** 查询供应商应付开放项目。 */
export const getPayableListApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/purchase/payables', params })

/** 查询采购付款单。 */
export const getPurchasePaymentListApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/purchase/payments', params })

/** 查询采购付款详情。 */
export const getPurchasePaymentApi = (id: number): Promise<IResponse> =>
  request.get({ url: `/erp/purchase/payments/${id}` })

/** 新增采购付款草稿。 */
export const addPurchasePaymentApi = (data: any): Promise<IResponse> =>
  request.post({ url: '/erp/purchase/payments', data })

/** 修改采购付款草稿。 */
export const putPurchasePaymentApi = (id: number, data: any): Promise<IResponse> =>
  request.put({ url: `/erp/purchase/payments/${id}`, data })

/** 删除采购付款草稿。 */
export const delPurchasePaymentApi = (ids: number[]): Promise<IResponse> =>
  request.delete({ url: '/erp/purchase/payments', data: ids })

/** 审核供应商付款。 */
export const approvePurchasePaymentApi = (id: number): Promise<IResponse> =>
  request.post({ url: `/erp/purchase/payments/${id}/approve` })

/** 反审核供应商付款。 */
export const unapprovePurchasePaymentApi = (id: number): Promise<IResponse> =>
  request.post({ url: `/erp/purchase/payments/${id}/unapprove` })
