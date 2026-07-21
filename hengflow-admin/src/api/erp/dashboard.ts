import request from '@/config/axios'

/** 获取 ERP 经营驾驶舱聚合数据。 */
export const getErpDashboardApi = (days = 30): Promise<IResponse> =>
  request.get({ url: '/erp/dashboard', params: { days } })
