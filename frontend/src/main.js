import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { initSentry } from './observability/sentry'

const app = createApp(App)
app.use(router)
initSentry(app, router)
app.mount('#app')

if ('serviceWorker' in navigator && process.env.NODE_ENV === 'production') {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js')
  })
}
