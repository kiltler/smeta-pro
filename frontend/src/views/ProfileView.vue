<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  Sun, Moon, MonitorSmartphone, Crown, LogOut, ImagePlus,
} from 'lucide-vue-next'
import { api, clearToken, fetchLogoUrl } from '../api.js'
import { setTheme, theme } from '../composables/theme.js'
import { toast } from '../composables/ui.js'

const router = useRouter()
const profile = ref({ brand_name: '', full_name: '', inn: '', requisites: { text: '' } })
const logoUrl = ref(null)
const sub = ref(null) // состояние подписки
const saving = ref(false)

const fmtDate = (iso) => new Date(iso).toLocaleDateString('ru-RU')

const THEMES = [
  { value: 'light', label: 'Светлая', icon: Sun },
  { value: 'dark', label: 'Тёмная', icon: Moon },
  { value: 'system', label: 'Система', icon: MonitorSmartphone },
]

onMounted(async () => {
  const p = await api('/profile')
  profile.value = {
    brand_name: p.brand_name || '',
    full_name: p.full_name || '',
    inn: p.inn || '',
    requisites: { text: p.requisites?.text || '' },
  }
  if (p.has_logo) logoUrl.value = await fetchLogoUrl()
  sub.value = await api('/billing/subscription')
})

async function goPro() {
  try {
    const { confirmation_url } = await api('/billing/subscribe', { method: 'POST' })
    location.href = confirmation_url // страница оплаты ЮKassa
  } catch (e) {
    toast(e.message, 'error')
  }
}

async function cancelSub() {
  sub.value = await api('/billing/cancel', { method: 'POST' })
}

async function resumeSub() {
  sub.value = await api('/billing/resume', { method: 'POST' })
}

async function save() {
  saving.value = true
  try {
    await api('/profile', { method: 'PUT', body: profile.value })
    toast('Сохранено')
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    saving.value = false
  }
}

async function uploadLogo(event) {
  const file = event.target.files[0]
  if (!file) return
  logoUrl.value = URL.createObjectURL(file)
  const formData = new FormData()
  formData.append('file', file)
  try {
    await api('/profile/logo', { method: 'POST', formData })
    toast('Логотип обновлён')
  } catch (e) {
    toast(e.message, 'error')
    logoUrl.value = null
  }
}

function logout() {
  clearToken()
  router.push('/login')
}
</script>

<template>
  <div class="screen">
    <h1>Профиль</h1>
  
    <!-- Подписка -->
    <section v-if="sub" class="card">
      <h2 class="sec-title"><Crown :size="17" aria-hidden="true" /> Подписка</h2>
      <template v-if="sub.plan === 'pro'">
        <p style="margin: 0 0 6px">Тариф <b>Pro</b> — безлимит документов, без водяного знака.</p>
        <p v-if="sub.past_due" class="error" style="min-height: 0">
          Не удалось продлить подписку — проверьте карту. Пробуем ещё
          {{ fmtDate(sub.period_end) }} + 3 дня, потом тариф станет Free.
        </p>
        <p v-else-if="sub.cancel_at_period_end" class="muted" style="margin: 0 0 12px">
          Продление отключено. Pro работает до {{ fmtDate(sub.period_end) }},
          дальше — Free (данные сохранятся).
        </p>
        <p v-else class="muted" style="margin: 0 0 12px">
          Следующее списание {{ sub.price_rub }} ₽ — {{ fmtDate(sub.period_end) }}.
        </p>
        <button v-if="sub.cancel_at_period_end" class="secondary" @click="resumeSub">
          Возобновить продление
        </button>
        <button v-else class="secondary" @click="cancelSub">Отменить подписку</button>
      </template>
      <template v-else>
        <p style="margin: 0 0 6px">
          Тариф <b>Free</b> — использовано
          <b>{{ sub.documents_used }} из {{ sub.documents_limit }}</b>
          документов в этом месяце.
        </p>
        <div class="usage" aria-hidden="true">
          <div class="usage-fill" :style="{ width: Math.min(100, sub.documents_used / sub.documents_limit * 100) + '%' }" />
        </div>
        <p class="muted" style="margin: 0 0 12px">На PDF — водяной знак сервиса.</p>
        <button class="cta" @click="goPro">Подключить Pro — {{ sub.price_rub }} ₽/мес</button>
      </template>
    </section>
  
    <!-- Тема -->
    <section class="card">
      <h2>Тема</h2>
      <div class="segment" role="radiogroup" aria-label="Тема оформления">
        <button
          v-for="t in THEMES" :key="t.value" role="radio"
          :aria-checked="theme === t.value" :class="{ active: theme === t.value }"
          @click="setTheme(t.value)"
        >
          <component :is="t.icon" :size="16" aria-hidden="true" /> {{ t.label }}
        </button>
      </div>
    </section>
  
    <!-- Данные для документов -->
    <section class="card">
      <h2>Данные для документов</h2>
      <label>Название бренда</label>
      <input v-model="profile.brand_name" />
      <label>ФИО</label>
      <input v-model="profile.full_name" />
      <label>ИНН</label>
      <input v-model="profile.inn" inputmode="numeric" />
      <label>Реквизиты</label>
      <textarea v-model="profile.requisites.text" />
      <button style="margin-top: 14px" :disabled="saving" @click="save">
        {{ saving ? 'Сохраняю…' : 'Сохранить' }}
      </button>
    </section>
  
    <!-- Логотип -->
    <section class="card">
      <h2>Логотип</h2>
      <div class="logo-row">
        <div class="logo-circle">
          <img v-if="logoUrl" :src="logoUrl" alt="Логотип" />
          <ImagePlus v-else :size="26" aria-hidden="true" />
        </div>
        <label class="soft replace-btn">
          {{ logoUrl ? 'Заменить' : 'Загрузить' }}
          <input
            type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml"
            class="visually-hidden" @change="uploadLogo"
          />
        </label>
      </div>
      <p class="muted" style="margin: 10px 0 0">PNG, JPEG, WebP или SVG до 2 МБ — попадёт на сметы и договоры.</p>
    </section>
  
    <button class="danger" @click="logout"><LogOut :size="17" style="margin-right: 8px" /> Выйти</button>
  </div>
</template>

<style scoped>
.sec-title { display: flex; align-items: center; gap: 7px; }
.sec-title svg { color: var(--warning); }

.segment { display: flex; gap: 4px; padding: 4px; background: var(--surface-2); border-radius: var(--r); }
.segment button {
  min-height: 42px; font-size: 14px; border-radius: 10px;
  background: transparent; color: var(--text-2);
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
}
.segment button.active { background: var(--surface); color: var(--text); box-shadow: var(--shadow-card); }

.usage {
  height: 6px; border-radius: 3px; background: var(--surface-2);
  margin: 4px 0 10px; overflow: hidden;
}
.usage-fill { height: 100%; border-radius: 3px; background: var(--accent); transition: width 400ms var(--ease); }

.logo-row { display: flex; align-items: center; gap: var(--s4); }
.logo-circle {
  width: 84px; height: 84px; border-radius: 50%; flex: none;
  background: var(--surface-2); color: var(--text-3);
  display: flex; align-items: center; justify-content: center;
  overflow: hidden; border: 1px solid var(--border);
}
.logo-circle img { width: 100%; height: 100%; object-fit: cover; }
.replace-btn {
  display: inline-flex; align-items: center; justify-content: center;
  min-height: 44px; padding: 0 20px; margin: 0;
  border-radius: var(--r-s); font-size: 15px; font-weight: 600;
  background: var(--accent-soft); color: var(--accent-soft-text);
  cursor: pointer; width: auto;
}
.visually-hidden {
  position: absolute; width: 1px; height: 1px; min-height: 0;
  overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap;
}
button.danger { display: flex; align-items: center; justify-content: center; }
</style>
