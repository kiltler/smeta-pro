<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '../api.js'
import { loadThemeFromProfile } from '../composables/theme.js'
import { toast } from '../composables/ui.js'

const router = useRouter()
const step = ref('phone') // phone | code
const code = ref('')
const busy = ref(false)

// ---------- автомаска телефона: +7 (___) ___-__-__ ----------
const phoneDigits = ref('') // 10 цифр после +7
const phoneShown = ref('')

function formatPhone(d) {
  if (!d.length) return ''
  let out = '+7 (' + d.slice(0, 3)
  if (d.length >= 4) out += ') ' + d.slice(3, 6)
  if (d.length >= 7) out += '-' + d.slice(6, 8)
  if (d.length >= 9) out += '-' + d.slice(8, 10)
  return out
}

function onPhoneInput(e) {
  let d = e.target.value.replace(/\D/g, '')
  if (d.startsWith('7') || d.startsWith('8')) d = d.slice(1)
  d = d.slice(0, 10)
  phoneDigits.value = d
  phoneShown.value = formatPhone(d)
  e.target.value = phoneShown.value
}

const phone = () => `+7${phoneDigits.value}`

async function requestCode() {
  busy.value = true
  try {
    await api('/auth/request-code', { method: 'POST', body: { phone: phone() } })
    step.value = 'code'
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    busy.value = false
  }
}

async function verify() {
  busy.value = true
  try {
    const data = await api('/auth/verify', {
      method: 'POST',
      body: { phone: phone(), code: code.value },
    })
    setToken(data.access_token)
    loadThemeFromProfile() // тема пользователя — из профиля
    // Пустой прайс — значит первый вход: ведём в онбординг
    const items = await api('/pricelist')
    router.push(items.length === 0 ? '/onboarding' : '/new')
  } catch (e) {
    toast(e.message, 'error')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="screen">
    <!-- Хиро на весь вход: градиент задаёт тон продукта -->
    <header class="hero login-hero">
      <img class="login-mark" src="/icons/mark.svg" alt="" aria-hidden="true" />
      <h1 class="login-title">СметаПро</h1>
      <p class="login-sub">
        смета за минуту <span class="dot">·</span> договор и акт
        <span class="dot">·</span> ваш бренд
      </p>
    </header>

    <div class="card" v-if="step === 'phone'">
      <label for="phone">Номер телефона</label>
      <input
        id="phone" :value="phoneShown" type="tel" inputmode="tel"
        placeholder="+7 (___) ___-__-__" autocomplete="tel"
        @input="onPhoneInput"
        @keyup.enter="phoneDigits.length === 10 && requestCode()"
      />
      <button
        class="cta" style="margin-top: 16px"
        :disabled="busy || phoneDigits.length !== 10" @click="requestCode"
      >
        Получить код
      </button>
    </div>

    <div class="card" v-else>
      <label for="code">Код из SMS на {{ phoneShown }}</label>
      <input
        id="code" v-model="code" inputmode="numeric" maxlength="4"
        placeholder="••••" autocomplete="one-time-code" class="code-input"
        @keyup.enter="verify"
      />
      <button class="cta" style="margin-top: 16px" :disabled="busy || code.length !== 4" @click="verify">
        Войти
      </button>
      <button class="ghost" style="margin-top: 8px" @click="step = 'phone'">
        Изменить номер
      </button>
    </div>
  </div>
</template>

<style scoped>
.login-hero {
  padding-top: 64px; padding-bottom: 40px;
  text-align: center; margin-bottom: var(--s5);
}
.login-mark {
  width: 68px; height: 68px; margin: 0 auto 14px;
  display: block;
  border-radius: 20px;
  box-shadow: var(--shadow-float);
  animation: mark-in 400ms var(--ease) both; /* мягкое всплытие */
}
@keyframes mark-in {
  from { opacity: 0; transform: scale(0.9); }
  to { opacity: 1; transform: scale(1); }
}
.login-title { margin: 0 0 8px; font-size: 28px; }
/* три микро-буллета ценности */
.login-sub { margin: 0; color: var(--on-hero-2); font-size: 14px; line-height: 1.45; }
.login-sub .dot { opacity: 0.55; margin: 0 2px; }
.code-input {
  text-align: center; font-size: 26px; letter-spacing: 12px; font-weight: 700;
  font-variant-numeric: tabular-nums;
}
</style>
