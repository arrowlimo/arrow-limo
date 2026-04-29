<template>
  <div class="confirmation-print-page">
    <div class="no-print print-actions">
      <button @click="window.print()">Print</button>
      <button @click="goBack">Close</button>
    </div>

    <div v-if="loading" class="state-message">Loading charter...</div>
    <div v-else-if="error" class="state-message error">{{ error }}</div>
    <CharterPrintTemplate v-else-if="booking" :booking="booking" />
    <div v-else class="state-message">No charter selected.</div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import CharterPrintTemplate from '@/components/CharterPrintTemplate.vue'

const route = useRoute()
const router = useRouter()

const booking = ref(null)
const loading = ref(false)
const error = ref('')

async function fetchBooking() {
  const charterId = route.query.charter_id || route.query.run_id || route.params.id
  if (!charterId) {
    error.value = 'Missing charter_id'
    return
  }

  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`/api/bookings/${charterId}`)
    if (!res.ok) {
      throw new Error(`Failed to load charter (${res.status})`)
    }
    booking.value = await res.json()
  } catch (err) {
    error.value = err?.message || 'Failed to load charter'
  } finally {
    loading.value = false
  }
}

function goBack() {
  router.back()
}

onMounted(fetchBooking)
</script>

<style scoped>
.confirmation-print-page {
  background: #ffffff;
  min-height: 100vh;
}

.print-actions {
  display: flex;
  gap: 8px;
  padding: 12px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}

.state-message {
  padding: 24px;
  color: #334155;
}

.state-message.error {
  color: #b91c1c;
}

@media print {
  .no-print {
    display: none;
  }
}
</style>
