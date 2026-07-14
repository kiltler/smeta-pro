// Тема интерфейса: light | dark | system. Выбор хранится в ПРОФИЛЕ (API),
// не в localStorage (решение владельца). До загрузки профиля — системная.
import { ref } from 'vue'
import { api } from '../api.js'

export const theme = ref('system')

export function applyTheme(value) {
  theme.value = value
  const el = document.documentElement
  if (value === 'light' || value === 'dark') el.dataset.theme = value
  else delete el.dataset.theme // системная — через prefers-color-scheme
}

export async function loadThemeFromProfile() {
  try {
    const profile = await api('/profile')
    applyTheme(profile.theme || 'system')
    return profile
  } catch {
    applyTheme('system')
    return null
  }
}

export async function setTheme(value) {
  applyTheme(value) // мгновенно, не дожидаясь сети
  try {
    await api('/profile/theme', { method: 'PUT', body: { theme: value } })
  } catch {
    /* тема уже применена локально; при следующей загрузке возьмётся из профиля */
  }
}
