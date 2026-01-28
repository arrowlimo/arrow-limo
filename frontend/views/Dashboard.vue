<template>
  <div>
    <h1>Dashboard</h1>
    <div class="stats-row">
      <div class="stat-card">Vehicles: {{ stats.vehicles }}</div>
      <div class="stat-card">Clients: {{ stats.clients }}</div>
      <div class="stat-card">Employees: {{ stats.employees }}</div>
      <div class="stat-card">Bookings: {{ stats.bookings }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
const stats = ref({ vehicles: 0, clients: 0, employees: 0, bookings: 0 })
// Fetch stats from API in real implementation
</script>

<style scoped>
.stats-row {
  display: flex;
  gap: 2rem;
  margin-top: 2rem;
}
.stat-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 1rem 2rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  font-size: 1.2rem;
}
</style>
