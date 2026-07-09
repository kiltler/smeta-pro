import { createRouter, createWebHashHistory } from 'vue-router'
import { getToken } from './api.js'
import LoginView from './views/LoginView.vue'
import OnboardingView from './views/OnboardingView.vue'
import EstimateView from './views/EstimateView.vue'
import DocumentsView from './views/DocumentsView.vue'
import PriceListView from './views/PriceListView.vue'
import BundlesView from './views/BundlesView.vue'
import ProfileView from './views/ProfileView.vue'

export const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/', redirect: '/new' },
    { path: '/new', component: EstimateView },
    { path: '/docs', component: DocumentsView },
    { path: '/login', component: LoginView, meta: { public: true } },
    { path: '/onboarding', component: OnboardingView },
    { path: '/price', component: PriceListView },
    { path: '/bundles', component: BundlesView },
    { path: '/profile', component: ProfileView },
  ],
})

router.beforeEach((to) => {
  if (!to.meta.public && !getToken()) return '/login'
})
