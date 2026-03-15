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
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import NavigationBar from './src/components/NavigationBar.vue'
import ToastHost from './src/toast/ToastHost.vue'

const route = useRoute()
const showNav = computed(() => route.path !== '/login')
</script>

<style>
#app {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  color: #2c3e50;
  height: 100vh;
  width: 100vw;
  display: flex;
  flex-direction: column;
}
body {
  margin: 0;
  background: #f8fafc;
}
.main-content {
  flex: 1;
  padding: 1.5rem;
  overflow-y: auto;
  background: #f8fafc;
}
.main-content-full {
  flex: 1;
  overflow-y: auto;
  background: #f8fafc;
}
</style>
