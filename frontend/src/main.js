import { createApp } from 'vue'
import App from './App.vue'
import { router } from './router.js'
import './styles/base.css'
import { getToken } from './api.js'
import { loadThemeFromProfile } from './composables/theme.js'

// Тема хранится в профиле (не в localStorage): подтягиваем при старте,
// до ответа сервера работает системная.
if (getToken()) loadThemeFromProfile()

createApp(App).use(router).mount('#app')

if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js')
}
