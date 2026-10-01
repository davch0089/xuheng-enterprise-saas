import request from '@/config/axios'

export const getTenantsApi = () => request.get({ url: '/xuheng/tenants' })

export const addTenantApi = (data: { code: string; name: string }) =>
  request.post({ url: '/xuheng/tenants', data })

export const getProductsApi = (tenantId: number) =>
  request.get({ url: '/xuheng/products', params: { tenant_id: tenantId } })

export const addProductApi = (data: any) => request.post({ url: '/xuheng/products', data })

export const receiveStockApi = (data: {
  tenant_id: number
  product_id: number
  quantity: number
}) => request.post({ url: '/xuheng/stocks/receive', data })

export const getOrdersApi = (tenantId: number) =>
  request.get({ url: '/xuheng/orders', params: { tenant_id: tenantId } })

export const addOrderApi = (data: any) => request.post({ url: '/xuheng/orders', data })

export const orderActionApi = (orderId: number, tenantId: number, action: string) =>
  request.post({ url: `/xuheng/orders/${orderId}/${action}`, params: { tenant_id: tenantId } })
