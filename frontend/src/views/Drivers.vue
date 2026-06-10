<template>
  <div class="drivers-container">
    <h1>My Chauffeur Dashboard</h1>
    <div v-if="loading">Loading...</div>
    <div v-else>
      <div v-for="driver in drivers" :key="driver.employee_id" class="driver-card">
        <h3>{{ driver.name || driver.full_name || driver.employee_name }}</h3>
        <p>Email: {{ driver.email }}</p>
        <p>Phone: {{ driver.phone }}</p>
        <p>Role: {{ driver.employee_type || driver.status || driver.employment_status }}</p>
      </div>

      <div class="calendar-card">
        <h2>Upcoming Trips (30 Days)</h2>
        <div v-if="calendarItems.length === 0" class="empty-state">No upcoming trips found.</div>
        <table v-else class="calendar-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Reserve</th>
              <th>Pickup</th>
              <th>Dropoff</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="trip in calendarItems" :key="trip.charter_id">
              <td>{{ trip.date }} {{ trip.pickup_time || '' }}</td>
              <td>{{ trip.reserve_number || trip.charter_id }}</td>
              <td>{{ trip.pickup_address }}</td>
              <td>{{ trip.dropoff_address }}</td>
              <td>{{ trip.status }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { authFetch } from '@/utils/authFetch'

const drivers = ref([])
const calendarItems = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const [profileRes, calendarRes] = await Promise.all([
      authFetch('/api/chauffeur/me/profile'),
      authFetch('/api/chauffeur/me/calendar?days=30')
    ])

    if (profileRes && profileRes.ok) {
      const payload = await profileRes.json()
      drivers.value = [payload]
    } else {
      console.error('Failed to fetch chauffeur profile')
    }

    if (calendarRes && calendarRes.ok) {
      const calendarPayload = await calendarRes.json()
      calendarItems.value = Array.isArray(calendarPayload.items) ? calendarPayload.items : []
    } else {
      console.error('Failed to fetch chauffeur calendar')
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

.calendar-card {
  margin-top: 1rem;
  border: 1px solid #ccc;
  border-radius: 8px;
  padding: 1rem;
  background: #fff;
}

.calendar-table {
  width: 100%;
  border-collapse: collapse;
}

.calendar-table th,
.calendar-table td {
  border: 1px solid #ddd;
  padding: 0.5rem;
  text-align: left;
}

.empty-state {
  color: #555;
}
</style>
