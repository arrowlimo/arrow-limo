import { reactive } from 'vue'

// Simple toast store with a queue
export const toastStore = reactive({
  toasts: [],
})

let idSeq = 1

export function showToast({ message, type = 'info', timeout = 3000 }) {
  const id = idSeq++
  const toast = { id, message, type }
  toastStore.toasts.push(toast)
  if (timeout > 0) {
    setTimeout(() => dismissToast(id), timeout)
  }
}

export const toast = {
  info(msg, timeout = 3000) { showToast({ message: msg, type: 'info', timeout }) },
  success(msg, timeout = 3000) { showToast({ message: msg, type: 'success', timeout }) },
  error(msg, timeout = 5000) { showToast({ message: msg, type: 'error', timeout }) },
}

export function dismissToast(id) {
  const idx = toastStore.toasts.findIndex(t => t.id === id)
  if (idx >= 0) toastStore.toasts.splice(idx, 1)
}
