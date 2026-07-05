// Обёртка над fetch: JWT из localStorage, обработка ошибок, редирект на вход при 401.
const TOKEN_KEY = 'smeta_token'

export const getToken = () => localStorage.getItem(TOKEN_KEY)
export const setToken = (t) => localStorage.setItem(TOKEN_KEY, t)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

export async function api(path, { method = 'GET', body, formData } = {}) {
  const headers = {}
  if (getToken()) headers['Authorization'] = `Bearer ${getToken()}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  const resp = await fetch('/api' + path, {
    method,
    headers,
    body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
  })

  if (resp.status === 401) {
    clearToken()
    location.hash = '#/login'
    throw new Error('Требуется вход')
  }
  if (!resp.ok) {
    const data = await resp.json().catch(() => ({}))
    let detail = data.detail
    // Ошибки валидации FastAPI приходят массивом — берём человекочитаемый текст
    if (Array.isArray(detail)) detail = detail[0]?.msg?.replace(/^Value error, /, '')
    throw new Error(typeof detail === 'string' ? detail : `Ошибка ${resp.status}`)
  }
  if (resp.status === 204) return null
  return resp.json()
}

// Логотип отдаётся только с JWT, поэтому <img src> не подходит — грузим blob.
export async function fetchLogoUrl() {
  const resp = await fetch('/api/profile/logo', {
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  if (!resp.ok) return null
  return URL.createObjectURL(await resp.blob())
}
