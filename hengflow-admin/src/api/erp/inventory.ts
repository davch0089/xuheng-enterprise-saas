import request from '@/config/axios'

export const getInboundListApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/inventory/inbounds', params })

export const getInboundApi = (id: number): Promise<IResponse> =>
  request.get({ url: `/erp/inventory/inbounds/${id}` })

export const addInboundApi = (data: any): Promise<IResponse> =>
  request.post({ url: '/erp/inventory/inbounds', data })

export const putInboundApi = (id: number, data: any): Promise<IResponse> =>
  request.put({ url: `/erp/inventory/inbounds/${id}`, data })

export const delInboundApi = (ids: number[]): Promise<IResponse> =>
  request.delete({ url: '/erp/inventory/inbounds', data: ids })

export const approveInboundApi = (id: number): Promise<IResponse> =>
  request.post({ url: `/erp/inventory/inbounds/${id}/approve` })

export const unapproveInboundApi = (id: number): Promise<IResponse> =>
  request.post({ url: `/erp/inventory/inbounds/${id}/unapprove` })

export const searchInboundProductsApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/inventory/products', params })

export const getStockListApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/inventory/stocks', params })

export const getStockMovementListApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/inventory/stock-movements', params })

export const getStockBatchListApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/inventory/stock-batches', params })

export const getStockSerialListApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/inventory/stock-serials', params })

/** 按效期优先、先进先出顺序推荐出库批次。 */
export const getBatchAllocationApi = (params: {
  warehouse_id: number
  product_id: number
  quantity: number
}): Promise<IResponse> => request.get({ url: '/erp/inventory/batch-allocation', params })

/** 查询单个序列号的完整库存生命周期。 */
export const getSerialHistoryApi = (id: number): Promise<IResponse> =>
  request.get({ url: `/erp/inventory/stock-serials/${id}/history` })

/** 分页查询简化 BOM。 */
export const getBomListApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/inventory/boms', params })

/** 查询 BOM 及其子件明细。 */
export const getBomApi = (id: number): Promise<IResponse> =>
  request.get({ url: `/erp/inventory/boms/${id}` })

/** 新增 BOM。 */
export const addBomApi = (data: any): Promise<IResponse> =>
  request.post({ url: '/erp/inventory/boms', data })

/** 修改 BOM。 */
export const putBomApi = (id: number, data: any): Promise<IResponse> =>
  request.put({ url: `/erp/inventory/boms/${id}`, data })

/** 删除未被工单引用的 BOM。 */
export const delBomApi = (ids: number[]): Promise<IResponse> =>
  request.delete({ url: '/erp/inventory/boms', data: ids })

/** 分页查询组装/拆卸工单。 */
export const getAssemblyOrderListApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/inventory/assembly-orders', params })

/** 查询组装/拆卸工单及其 BOM 快照。 */
export const getAssemblyOrderApi = (id: number): Promise<IResponse> =>
  request.get({ url: `/erp/inventory/assembly-orders/${id}` })

/** 新增组装/拆卸工单草稿。 */
export const addAssemblyOrderApi = (data: any): Promise<IResponse> =>
  request.post({ url: '/erp/inventory/assembly-orders', data })

/** 修改组装/拆卸工单草稿。 */
export const putAssemblyOrderApi = (id: number, data: any): Promise<IResponse> =>
  request.put({ url: `/erp/inventory/assembly-orders/${id}`, data })

/** 删除组装/拆卸工单草稿。 */
export const delAssemblyOrderApi = (ids: number[]): Promise<IResponse> =>
  request.delete({ url: '/erp/inventory/assembly-orders', data: ids })

/** 审核或反审核组装/拆卸工单。 */
export const actionAssemblyOrderApi = (
  id: number,
  action: 'approve' | 'unapprove'
): Promise<IResponse> => request.post({ url: `/erp/inventory/assembly-orders/${id}/${action}` })

export type InventoryOperationKind = 'transfers' | 'counts' | 'other-orders'

/** 查询库存作业单据列表。 */
export const getInventoryOperationListApi = (
  kind: InventoryOperationKind,
  params: any
): Promise<IResponse> => request.get({ url: `/erp/inventory/${kind}`, params })

/** 获取库存作业单据详情。 */
export const getInventoryOperationApi = (
  kind: InventoryOperationKind,
  id: number
): Promise<IResponse> => request.get({ url: `/erp/inventory/${kind}/${id}` })

/** 新增库存作业草稿。 */
export const addInventoryOperationApi = (
  kind: InventoryOperationKind,
  data: any
): Promise<IResponse> => request.post({ url: `/erp/inventory/${kind}`, data })

/** 修改库存作业草稿。 */
export const putInventoryOperationApi = (
  kind: InventoryOperationKind,
  id: number,
  data: any
): Promise<IResponse> => request.put({ url: `/erp/inventory/${kind}/${id}`, data })

/** 删除库存作业草稿。 */
export const delInventoryOperationApi = (
  kind: InventoryOperationKind,
  ids: number[]
): Promise<IResponse> => request.delete({ url: `/erp/inventory/${kind}`, data: ids })

/** 执行库存作业状态动作。 */
export const actionInventoryOperationApi = (
  kind: InventoryOperationKind,
  id: number,
  action: string
): Promise<IResponse> => request.post({ url: `/erp/inventory/${kind}/${id}/${action}` })

/** 读取指定仓库的盘点快照。 */
export const getInventoryCountSnapshotApi = (warehouse_id: number): Promise<IResponse> =>
  request.get({ url: '/erp/inventory/count-snapshot', params: { warehouse_id } })
