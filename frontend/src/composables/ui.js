// Мелкая UI-механика: тосты, хаптика, «улёт в корзину», reduced-motion.
import { reactive } from 'vue'

export const reducedMotion = () =>
  window.matchMedia('(prefers-reduced-motion: reduce)').matches

// ---------- тосты ----------
export const toasts = reactive([])
let toastSeq = 0

export function toast(text, type = 'success') {
  const id = ++toastSeq
  toasts.push({ id, text, type })
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id)
    if (i !== -1) toasts.splice(i, 1)
  }, 2600)
}

// ---------- хаптика: лёгкий тик ----------
export function haptic() {
  if (!reducedMotion()) navigator.vibrate?.(8)
}

// ---------- «улёт» позиции в корзину ----------
export function flyToCart(sourceEl, text) {
  const target = document.getElementById('cart-anchor')
  if (!sourceEl || !target || reducedMotion()) return
  const from = sourceEl.getBoundingClientRect()
  const to = target.getBoundingClientRect()
  const chip = document.createElement('div')
  chip.className = 'fly-chip'
  chip.textContent = text
  chip.style.left = `${from.left + from.width / 2 - 40}px`
  chip.style.top = `${from.top}px`
  document.body.appendChild(chip)
  requestAnimationFrame(() => {
    const dx = to.left + to.width / 2 - (from.left + from.width / 2)
    const dy = to.top - from.top
    chip.style.transform = `translate(${dx}px, ${dy}px) scale(0.55)`
    chip.style.opacity = '0'
  })
  setTimeout(() => chip.remove(), 550)
}

// ---------- форматирование денег: tabular + неразрывные пробелы ----------
export function money(value) {
  const n = Number(value) || 0
  const text = n.toLocaleString('ru-RU', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })
  // перед ₽ — узкий неразрывный пробел U+202F
  return `${text} ₽`
}
