<template>
  <div id="app">
    <NavigationBar />
    <GlobalLoader />
    <main class="main-content">
      <router-view />
    </main>
    <ToastHost />
  </div>
  
</template>

<script setup>
import NavigationBar from './components/NavigationBar.vue'
import GlobalLoader from './src/loading/GlobalLoader.vue'
import ToastHost from './src/toast/ToastHost.vue'
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
</style>
