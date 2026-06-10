<template>
  <div class="drivers-container">
    <h1>Drivers</h1>
    <div v-if="loading">Loading...</div>
    <div v-else>
      <div v-if="!drivers.length">No drivers found.</div>
      <div v-for="driver in drivers" :key="driver.employee_id" class="driver-card">
        <h3>{{ driver.display || driver.name || `${driver.first_name || ''} ${driver.last_name || ''}`.trim() }}</h3>
        <p>Employee ID: {{ driver.employee_id }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
const drivers = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
  const res = await fetch('/api/employees/drivers')
    if (res.ok) {
      drivers.value = await res.json()
    } else {
      console.error('Failed to fetch drivers:', res.status)
    }
  } catch (err) {
    console.error('Error fetching drivers:', err)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.drivers-container {
  padding: 2rem;
}
.driver-card {
  border: 1px solid #1976d2;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
  background: #f5f8ff;
}
</style>
