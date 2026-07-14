<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setToken } from '../api.js'
import { loadThemeFromProfile } from '../composables/theme.js'
import { toast } from '../composables/ui.js'

const router = useRouter()
const step = ref('phone') // phone | code
const phone = ref('')
const code = ref('')
const busy = ref(false)

async function requestCode() {
  busy.value = true
  try {
    await api('/auth/request-code', { method: 'POST', body: { phone: phone.value } })
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
      body: { phone: phone.value, code: code.value },
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
      <div class="login-mark" aria-hidden="true">С</div>
      <h1 class="login-title">СметаПро</h1>
      <p class="login-sub">Смета голосом за минуту —<br />PDF с вашим брендом</p>
    </header>
  
    <div class="card" v-if="step === 'phone'">
      <label for="phone">Номер телефона</label>
      <input
        id="phone" v-model="phone" type="tel" inputmode="tel"
        placeholder="+7 914 123-45-67" autocomplete="tel"
        @keyup.enter="requestCode"
      />
      <button class="cta" style="margin-top: 16px" :disabled="busy || !phone" @click="requestCode">
        Получить код
      </button>
    </div>
  
    <div class="card" v-else>
      <label for="code">Код из SMS на {{ phone }}</label>
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
  width: 64px; height: 64px; margin: 0 auto 14px;
  border-radius: 20px;
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
  display: flex; align-items: center; justify-content: center;
  font-size: 30px; font-weight: 800;
}
.login-title { margin: 0 0 6px; font-size: 28px; }
.login-sub { margin: 0; color: var(--on-hero-2); font-size: 15px; line-height: 1.45; }
.code-input {
  text-align: center; font-size: 26px; letter-spacing: 12px; font-weight: 700;
  font-variant-numeric: tabular-nums;
}
</style>
