<template>
  <transition name="fade">
    <div v-if="routeLoading.isRouteLoading" class="global-loader">
      <div class="bar">
        <div class="indeterminate"></div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { routeLoading } from './loadingStore'
</script>

<style scoped>
.global-loader {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  z-index: 2000;
}
.bar {
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, #007bff22, #007bff22);
  overflow: hidden;
  position: relative;
}
.indeterminate {
  position: absolute;
  width: 20%;
  max-width: 200px;
  height: 100%;
  background: #007bff;
  box-shadow: 0 0 8px #007bff88;
  border-radius: 0 2px 2px 0;
  animation: slide 1.2s infinite ease-in-out;
}
@keyframes slide {
  0% { left: -20%; }
  50% { left: 50%; }
  100% { left: 110%; }
}
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
