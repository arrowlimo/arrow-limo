<template>
  <div class="toast-container">
    <div v-for="t in toasts" :key="t.id" class="toast" :class="t.type" @click="dismiss(t.id)">
      {{ t.message }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { toastStore, dismissToast } from './toastStore'

const toasts = computed(() => toastStore.toasts)
function dismiss(id) { dismissToast(id) }
</script>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 20px;
  right: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 2000;
}
.toast {
  min-width: 240px;
  max-width: 420px;
  background: #1f2937;
  color: #fff;
  padding: 10px 14px;
  border-radius: 6px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
  cursor: pointer;
  opacity: 0.95;
}
.toast.info { background: #374151; }
.toast.success { background: #059669; }
.toast.error { background: #b91c1c; }
</style>
