import axios from 'axios'

export const cmpApi = axios.create({ baseURL: '/api/cmp', timeout: 180000 })
export const apiError = (error) => {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) return detail.map(x => `${x.loc?.join('.')}: ${x.msg}`).join('; ')
  return typeof detail === 'string' ? detail : error?.message || 'Request failed'
}
export const isCancelled = error => axios.isCancel(error) || error?.code === 'ERR_CANCELED'
export const downloadUrl = path => `/api/cmp${path}`
