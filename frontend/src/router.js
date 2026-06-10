import { createRouter, createWebHistory } from 'vue-router'
import { registerAuthGuard } from './router/authGuard'
import { routes } from './router/routes'

const router = createRouter({
  history: createWebHistory(),
  routes
})

registerAuthGuard(router)

export default router
