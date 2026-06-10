import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { initSentry } from './observability/sentry'

const app = createApp(App)
app.use(router)
initSentry(app, router)
app.mount('#app')
