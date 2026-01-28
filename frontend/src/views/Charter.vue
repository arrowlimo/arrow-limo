<template>
  <div>
    <h1>Charter Management</h1>
    <div class="charter-section">
      <template v-if="loading">Loading booking details...</template>
      <template v-else-if="error">Error: {{ error }}</template>
      <template v-else-if="booking">
        <h2>Booking #{{ booking.reserve_number }}</h2>
        <ul>
          <li><b>Date:</b> {{ booking.charter_date }}</li>
          <li><b>Client:</b> {{ booking.client_name }}</li>
          <li><b>Vehicle Requested:</b> {{ booking.vehicle_type_requested }}</li>
          <li><b>Vehicle Assigned:</b> {{ booking.vehicle_booked_id }}</li>
          <li><b>Driver:</b> {{ booking.driver_name }}</li>
          <li><b>Vehicle Desc:</b> {{ booking.vehicle_description }}</li>
          <li><b>Passengers:</b> {{ booking.passenger_load }}</li>
          <li><b>Retainer:</b> {{ booking.retainer }}</li>
          <li><b>Odo Start:</b> {{ booking.odometer_start }}</li>
          <li><b>Odo End:</b> {{ booking.odometer_end }}</li>
          <li><b>Fuel:</b> {{ booking.fuel_added }}</li>
          <li><b>Notes:</b> {{ booking.vehicle_notes }}</li>
        </ul>

        <!-- Beverage Orders -->
        <div class="beverage-box">
          <h3>Beverage Orders</h3>
          <div v-if="bevLoading">Loading beverages…</div>
          <div v-else>
            <table v-if="beverages.length" class="beverage-table">
              <thead>
                <tr><th>Item</th><th>Qty</th><th>Price</th><th>Total</th><th>Actions</th></tr>
              </thead>
              <tbody>
                <tr v-for="(b, i) in beverages" :key="b.id || i">
                  <td>{{ b.name }}</td>
                  <td><input type="number" v-model.number="b.qty" min="0" style="width:70px;" /></td>
                  <td>${{ (b.price || 0).toFixed(2) }}</td>
                  <td>${{ ((b.price || 0) * (b.qty || 0)).toFixed(2) }}</td>
                  <td><button class="link danger" @click="removeBeverage(i)">Remove</button></td>
                </tr>
              </tbody>
            </table>
            <p v-else class="no-data">No beverage orders.</p>
            <div class="bev-actions">
              <label style="display:flex; align-items:center; gap:0.5rem;">
                <input type="checkbox" v-model="bevInvoiceSeparately" /> Invoice beverages separately
              </label>
              <button @click="saveBeverages" :disabled="!beverages.length">Save Beverages</button>
              <button class="secondary" @click="openPrint">Print Beverage Order</button>
            </div>
            <div class="bev-add">
              <input v-model="newBev.name" placeholder="Item name" />
              <input v-model.number="newBev.price" type="number" step="0.01" placeholder="Price" />
              <input v-model.number="newBev.qty" type="number" min="1" placeholder="Qty" />
              <button @click="addBeverage" :disabled="!newBev.name || !newBev.qty">Add Item</button>
            </div>
          </div>
        </div>
      </template>
      <template v-else>
        <p>No booking selected.</p>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { toast } from '@/toast/toastStore'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const booking = ref(null)
const loading = ref(false)
const error = ref("")
const beverages = ref([])
const bevLoading = ref(false)
const bevInvoiceSeparately = ref(false)
const newBev = ref({ name: '', price: 0, qty: 1 })

async function fetchBooking(id) {
  loading.value = true
  error.value = ""
  try {
    const res = await fetch(`/api/bookings/${id}`)
    if (!res.ok) throw new Error('Booking not found')
    booking.value = await res.json()
    // Load beverage orders for this charter
    await loadBeverages()
  } catch (e) {
    error.value = e.message || String(e)
  } finally {
    loading.value = false
  }
}

async function loadBeverages() {
  if (!booking.value?.charter_id) return
  bevLoading.value = true
  try {
    const res = await fetch(`/api/charter/${booking.value.charter_id}/beverage_orders`)
    if (res.ok) {
      const data = await res.json()
      beverages.value = data.beverage_orders || []
    }
  } catch (_) { /* ignore */ }
  finally { bevLoading.value = false }
}

async function saveBeverages() {
  if (!booking.value?.charter_id) return
  try {
    const payloadOrders = beverages.value.filter(b => (b.qty || 0) > 0)
    await fetch(`/api/charter/${booking.value.charter_id}/beverage_orders`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ beverage_orders: payloadOrders })
    })
    if (bevInvoiceSeparately.value) {
      await fetch('/api/beverage_orders/invoice_separately', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ charter_id: booking.value.charter_id, invoice_separately: true })
      })
    }
    toast.success('Beverage orders saved')
  } catch (_) { toast.error('Failed to save beverages') }
}

function addBeverage() {
  beverages.value.push({ name: newBev.value.name, price: newBev.value.price || 0, qty: newBev.value.qty || 1 })
  newBev.value = { name: '', price: 0, qty: 1 }
}

function removeBeverage(index) {
  beverages.value.splice(index, 1)
}

onMounted(() => {
  const id = route.query.id
  if (id) fetchBooking(id)
})

function openPrint() {
  const q = new URLSearchParams()
  if (booking.value?.charter_id) q.set('charter_id', booking.value.charter_id)
  // If run_id pattern is known later, can set run_id as well
  const url = `/beverage-order/print?${q.toString()}`
  window.open(url, '_blank')
}
</script>

<style scoped>
.charter-section {
  background: #fff;
  border-radius: 8px;
  padding: 2rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-top: 2rem;
}
.beverage-box { margin-top: 2rem; border-top: 1px solid #eee; padding-top: 1.25rem; }
.beverage-table { width: 100%; border-collapse: collapse; }
.beverage-table th, .beverage-table td { padding: 0.5rem; border-bottom: 1px solid #eee; }
.bev-actions { display:flex; gap: 0.75rem; align-items:center; margin-top: 0.75rem; }
.bev-add { display:flex; gap: 0.5rem; align-items:center; margin-top: 0.75rem; }
.link { background:none; border:none; color:#0a58ca; cursor:pointer; padding:0; }
.link.danger { color:#c62828; }
</style>
