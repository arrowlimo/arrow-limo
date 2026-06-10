import { createApp } from 'vue'
import App from './App.vue'
import router from './router'

// Global auth interceptor: many components call fetch('/api/...') directly
// without attaching the bearer token. Wrap fetch once so every same-origin
// API/auth request carries the token (when present) and we don't have to
// thread it through every call site.
const _originalFetch = window.fetch.bind(window)
window.fetch = (input, init = {}) => {
  try {
    const url = typeof input === 'string' ? input : (input && input.url) || ''
    const isApi = url.startsWith('/api') || url.startsWith('/auth')
    const token = localStorage.getItem('auth_token')
    if (isApi && token) {
      const headers = new Headers(
        (init && init.headers) ||
          (typeof input !== 'string' && input.headers) ||
          {}
      )
      if (!headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${token}`)
        init = { ...init, headers }
      }
    }
  } catch (e) {
    // Never let the interceptor break a request
  }
  return _originalFetch(input, init)
}

const app = createApp(App)
app.use(router)
app.mount('#app')
