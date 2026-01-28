import { ref } from 'vue'

// Simple global route loading state with flicker guard
const isRouteLoading = ref(false)
let pending = 0
let showTimer = null
let hideTimer = null

function startRouteLoading() {
  pending++
  if (hideTimer) {
    clearTimeout(hideTimer)
    hideTimer = null
  }
  if (!showTimer && !isRouteLoading.value) {
    // delay show to avoid flicker on very fast navigations
    showTimer = setTimeout(() => {
      isRouteLoading.value = true
      showTimer = null
    }, 120)
  }
}

function stopRouteLoading() {
  pending = Math.max(0, pending - 1)
  if (pending === 0) {
    if (showTimer) {
      clearTimeout(showTimer)
      showTimer = null
    }
    // delay hide slightly so it feels smoother
    hideTimer = setTimeout(() => {
      isRouteLoading.value = false
      hideTimer = null
    }, 150)
  }
}

export const routeLoading = {
  isRouteLoading,
  start: startRouteLoading,
  stop: stopRouteLoading
}
