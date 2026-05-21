<template>
  <div id="app">
    <NavigationBar v-if="showNav" />
    <main :class="showNav ? 'main-content' : 'main-content-full'">
      <router-view />
    </main>
    <ToastHost />
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import NavigationBar from './components/NavigationBar.vue'
import ToastHost from './toast/ToastHost.vue'

const route = useRoute()
const showNav = computed(() => route.path !== '/login')

onMounted(() => {
  const theme = localStorage.getItem('theme') || 'light'
  document.documentElement.setAttribute('data-theme', theme)
})
</script>

<style>
#app {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  color: var(--main-text-color);
  height: 100vh;
  width: 100vw;
  display: flex;
  flex-direction: column;
}
body {
  margin: 0;
  background: var(--main-bg-color);
}
.main-content {
  flex: 1;
  padding: 1.5rem;
  overflow-y: auto;
  background: var(--main-bg-color);
}
.main-content-full {
  flex: 1;
  overflow-y: auto;
  background: var(--main-bg-color);
}

/* Light theme (default) */
:root[data-theme='light'] {
  --main-bg-color: #f8fafc;
  --main-text-color: #2c3e50;
  --navbar-bg: #667eea;
  --navbar-text: #ffffff;
  --navbar-link: #ffffff;
  --navbar-border: rgba(255, 255, 255, 0.3);
  --navbar-btn-bg: rgba(255, 255, 255, 0.2);
  --navbar-btn-border: rgba(255, 255, 255, 0.4);
  --navbar-btn-text: #ffffff;
  --navbar-btn-hover-bg: rgba(255, 255, 255, 0.3);
  --navbar-btn-hover-border: rgba(255, 255, 255, 0.6);
  --navbar-btn-active-bg: rgba(255, 255, 255, 0.25);
}

/* Dark theme */
:root[data-theme='dark'] {
  --main-bg-color: #23272f;
  --main-text-color: #f1f1f1;
  --navbar-bg: #1b1f27;
  --navbar-text: #f1f1f1;
  --navbar-link: #f1f1f1;
  --navbar-border: rgba(255, 255, 255, 0.2);
  --navbar-btn-bg: rgba(255, 255, 255, 0.08);
  --navbar-btn-border: rgba(255, 255, 255, 0.18);
  --navbar-btn-text: #f1f1f1;
  --navbar-btn-hover-bg: rgba(255, 255, 255, 0.15);
  --navbar-btn-hover-border: rgba(255, 255, 255, 0.25);
  --navbar-btn-active-bg: rgba(255, 255, 255, 0.1);
}
</style>
