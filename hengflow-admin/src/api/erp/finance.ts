import request from '@/config/axios'

export const getFinanceOptionsApi = (): Promise<IResponse> =>
  request.get({ url: '/erp/finance/options' })
export const getFinanceOpenItemsApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/finance/open-items', params })
export const getFundAccountsApi = (): Promise<IResponse> =>
  request.get({ url: '/erp/finance/accounts' })
export const addFundAccountApi = (data: any): Promise<IResponse> =>
  request.post({ url: '/erp/finance/accounts', data })
export const putFundAccountApi = (id: number, data: any): Promise<IResponse> =>
  request.put({ url: `/erp/finance/accounts/${id}`, data })
export const getFundDocumentsApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/finance/documents', params })
export const addFundDocumentApi = (data: any): Promise<IResponse> =>
  request.post({ url: '/erp/finance/documents', data })
export const putFundDocumentApi = (id: number, data: any): Promise<IResponse> =>
  request.put({ url: `/erp/finance/documents/${id}`, data })
export const delFundDocumentsApi = (ids: number[]): Promise<IResponse> =>
  request.delete({ url: '/erp/finance/documents', data: ids })
export const approveFundDocumentApi = (id: number): Promise<IResponse> =>
  request.post({ url: `/erp/finance/documents/${id}/approve` })
export const unapproveFundDocumentApi = (id: number): Promise<IResponse> =>
  request.post({ url: `/erp/finance/documents/${id}/unapprove` })
export const getFundLedgersApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/finance/ledgers', params })
export const getSettlementsApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/finance/settlements', params })
export const getSettlementApi = (id: number): Promise<IResponse> =>
  request.get({ url: `/erp/finance/settlements/${id}` })
export const addSettlementApi = (data: any): Promise<IResponse> =>
  request.post({ url: '/erp/finance/settlements', data })
export const putSettlementApi = (id: number, data: any): Promise<IResponse> =>
  request.put({ url: `/erp/finance/settlements/${id}`, data })
export const delSettlementsApi = (ids: number[]): Promise<IResponse> =>
  request.delete({ url: '/erp/finance/settlements', data: ids })
export const approveSettlementApi = (id: number): Promise<IResponse> =>
  request.post({ url: `/erp/finance/settlements/${id}/approve` })
export const unapproveSettlementApi = (id: number): Promise<IResponse> =>
  request.post({ url: `/erp/finance/settlements/${id}/unapprove` })
export const getAccountingPeriodsApi = (): Promise<IResponse> =>
  request.get({ url: '/erp/finance/periods' })
export const addAccountingPeriodApi = (data: any): Promise<IResponse> =>
  request.post({ url: '/erp/finance/periods', data })
export const closeAccountingPeriodApi = (id: number): Promise<IResponse> =>
  request.post({ url: `/erp/finance/periods/${id}/close` })
export const reopenAccountingPeriodApi = (id: number): Promise<IResponse> =>
  request.post({ url: `/erp/finance/periods/${id}/reopen` })
export const validatePeriodCostApi = (endDate: string): Promise<IResponse> =>
  request.get({ url: `/erp/finance/periods/cost-validation/${endDate}` })
export const getOperatingProfitApi = (params: any): Promise<IResponse> =>
  request.get({ url: '/erp/finance/profit', params })
