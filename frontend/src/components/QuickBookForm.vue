<template>
  <form @submit.prevent="submitForm">
    <h2>Quick Book</h2>
    <div class="container-row">
      <!-- Client Lookup/Add -->
      <div class="container-box">
        <div class="form-row">
          <label>Client Name</label>
          <input v-model="clientNameInput" @input="onClientNameInput" list="client-suggestions" type="text" placeholder="Search or add client" />
          <datalist id="client-suggestions">
            <option v-for="c in filteredClients" :key="c.client_id" :value="c.client_name" />
          </datalist>
        </div>
        <div v-if="!clientExists">
          <div class="form-row"><label>Email</label><input v-model="form.email" type="email" /></div>
          <div class="form-row"><label>Phone</label><input v-model="form.phone" type="text" /></div>
          <div class="form-row"><label>Date</label><input v-model="form.date" type="date" /></div>
        </div>
      </div>
      <!-- Vehicle & Booking Info -->
      <div class="container-box">
        <div class="form-row"><label>Vehicle Type</label><input v-model="form.vehicle_type" type="text" /></div>
        <div class="form-row"><label>Passenger Total</label><input v-model="form.passenger_total" type="number" /></div>
        <div class="form-row"><label>Number of Hours</label><input v-model="form.hours" type="number" /></div>
        <div class="form-row"><label>Credit Card</label><input v-model="form.credit_card" type="text" /></div>
      </div>
    </div>
    <button type="submit">Create Quote</button>
  </form>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { toast } from '@/toast/toastStore'
const form = ref({
  client_id: '', client_name: '', email: '', phone: '', date: '', vehicle_type: '', passenger_total: '', hours: '', credit_card: ''
})
const clientList = ref([])
const clientNameInput = ref('')
const filteredClients = ref([])
const clientExists = ref(false)

onMounted(async () => {
  try {
  const res = await fetch('/api/clients')
    if (res.ok) {
      clientList.value = await res.json()
    }
  } catch (err) {
    console.error('Error fetching clients:', err)
  }
})

function onClientNameInput(e) {
  const val = clientNameInput.value.toLowerCase()
  filteredClients.value = clientList.value.filter(c => c.client_name && c.client_name.toLowerCase().includes(val))
  const match = clientList.value.find(c => c.client_name && c.client_name.toLowerCase() === val)
  clientExists.value = !!match
  if (match) {
    form.value.client_id = match.client_id
    form.value.client_name = match.client_name
    form.value.email = match.email || ''
    form.value.phone = match.phone || ''
  } else {
    form.value.client_id = ''
    form.value.client_name = clientNameInput.value
    form.value.email = ''
    form.value.phone = ''
  }
}

function submitForm() {
  toast.success('Quote created!')
}
</script>

<style scoped>
.container-row {
  display: flex;
  flex-wrap: wrap;
  gap: 2rem;
  justify-content: flex-start;
  align-items: flex-start;
}
.container-box {
  border: 2px solid #1976d2;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 2rem;
  background: #f5f8ff;
  box-shadow: 0 2px 8px rgba(25, 118, 210, 0.08);
  min-width: 260px;
  max-width: 350px;
  flex: 1 1 320px;
}
.form-row {
  display: flex;
  flex-direction: column;
  margin-bottom: 1rem;
}
label {
  font-weight: 500;
  margin-bottom: 0.3rem;
}
input, select {
  padding: 0.5rem;
  border-radius: 5px;
  border: 1px solid #ddd;
  font-size: 1rem;
}
button {
  margin-top: 1.5rem;
  padding: 0.75rem 2rem;
  background: #667eea;
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 1.1rem;
  cursor: pointer;
}
button:hover {
  background: #4f46e5;
}
</style>
