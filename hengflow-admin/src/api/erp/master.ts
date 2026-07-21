import request from '@/config/axios'

export const getMasterListApi = (resource: string, params: any): Promise<IResponse> =>
  request.get({ url: `/erp/master/${resource}`, params })

export const getMasterApi = (resource: string, id: number): Promise<IResponse> =>
  request.get({ url: `/erp/master/${resource}/${id}` })

export const addMasterApi = (resource: string, data: any): Promise<IResponse> =>
  request.post({ url: `/erp/master/${resource}`, data })

export const putMasterApi = (resource: string, data: any): Promise<IResponse> =>
  request.put({ url: `/erp/master/${resource}/${data.id}`, data })

export const delMasterApi = (resource: string, ids: number[]): Promise<IResponse> =>
  request.delete({ url: `/erp/master/${resource}`, data: ids })

export const getMasterOptionsApi = (resource: string): Promise<IResponse> => {
  if (resource === 'departments') {
    return request.get({ url: '/vadmin/auth/dept/tree/options' })
  }
  return request.get({ url: `/erp/master/select-options/${resource}/all` })
}

export const getUnitGroupItemsApi = (groupId: number): Promise<IResponse> =>
  request.get({ url: `/erp/master/unit-conversions/${groupId}/items` })

export const addUnitGroupItemApi = (groupId: number, data: any): Promise<IResponse> =>
  request.post({ url: `/erp/master/unit-conversions/${groupId}/items`, data })

export const putUnitGroupItemApi = (groupId: number, data: any): Promise<IResponse> =>
  request.put({ url: `/erp/master/unit-conversions/${groupId}/items/${data.id}`, data })

export const delUnitGroupItemApi = (groupId: number, ids: number[]): Promise<IResponse> =>
  request.delete({ url: `/erp/master/unit-conversions/${groupId}/items`, data: ids })

/** 分页查询商品 SPU、下属 SKU 和库存汇总。 */
export const getProductSpuListApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/master/product-spus', params })

/** 获取一个商品 SPU 及其全部 SKU。 */
export const getProductSpuApi = (id: number): Promise<IResponse> =>
  request.get({ url: `/erp/master/product-spus/${id}` })

/** 新增商品 SPU 和 SKU。 */
export const addProductSpuApi = (data: any): Promise<IResponse> =>
  request.post({ url: '/erp/master/product-spus', data })

/** 修改商品 SPU 和 SKU。 */
export const putProductSpuApi = (id: number, data: any): Promise<IResponse> =>
  request.put({ url: `/erp/master/product-spus/${id}`, data })

/** 删除未被任何业务引用的商品 SPU。 */
export const delProductSpuApi = (id: number): Promise<IResponse> =>
  request.delete({ url: `/erp/master/product-spus/${id}` })

/** 获取历史使用过的 SKU 属性名称和值。 */
export const getProductAttributeOptionsApi = (): Promise<IResponse> =>
  request.get({ url: '/erp/master/product-spus/attribute-options' })
