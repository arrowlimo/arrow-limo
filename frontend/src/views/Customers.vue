<template>
  <div>
    <h1>Customer Management</h1>
    
    <!-- Customer Stats -->
    <div class="customer-stats">
      <div class="stat-card total">
        <div class="stat-value">{{ stats.totalCustomers }}</div>
        <div class="stat-label">Total Customers</div>
      </div>
      <div class="stat-card active">
        <div class="stat-value">{{ stats.activeCustomers }}</div>
        <div class="stat-label">Active Customers</div>
      </div>
      <div class="stat-card corporate">
        <div class="stat-value">{{ stats.corporateCustomers }}</div>
        <div class="stat-label">Corporate Clients</div>
      </div>
      <div class="stat-card gst-exempt">
        <div class="stat-value">{{ stats.gstExemptCustomers }}</div>
        <div class="stat-label">GST Exempt</div>
      </div>
    </div>

    <!-- Customer Filters and Actions -->
    <div class="customer-actions">
      <div class="filters">
        <input v-model="searchText" placeholder="Search customers..." />
        <select v-model="clientTypeFilter" class="filter-select">
          <option value="">All Types</option>
          <option value="Individual">Individual</option>
          <option value="Corporate">Corporate</option>
        </select>
        <select v-model="gstFilter" class="filter-select">
          <option value="">All GST Status</option>
          <option value="exempt">GST Exempt</option>
          <option value="regular">Regular</option>
        </select>
      </div>
      <button @click="showForm = !showForm" class="btn-primary">
        {{ showForm ? 'Hide Form' : 'Add New Customer' }}
      </button>
    </div>

    <!-- Customer Form -->
    <div v-if="showForm" class="form-section">
      <CustomerForm @customer-saved="onCustomerSaved" />
    </div>

    <!-- Customer List -->
    <div class="customer-list">
      <h2>Customer Directory</h2>
      <table class="customers-table">
        <thead>
          <tr>
            <th>Client Name</th>
            <th>Type</th>
            <th>Phone</th>
            <th>Email</th>
            <th>Company</th>
            <th>GST Status</th>
            <th>Last Booking</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="customer in filteredCustomers" :key="customer.id" :class="getRowClass(customer)">
            <td class="customer-name">{{ customer.client_name }}</td>
            <td>
              <span :class="'type-' + (customer.client_type || 'individual').toLowerCase()">
                {{ customer.client_type || 'Individual' }}
              </span>
            </td>
            <td>{{ customer.phone }}</td>
            <td>{{ customer.email }}</td>
            <td>{{ customer.company_name || '-' }}</td>
            <td>
              <span :class="customer.is_gst_exempt ? 'gst-exempt' : 'gst-regular'">
                {{ customer.is_gst_exempt ? 'Exempt' : 'Regular' }}
              </span>
            </td>
            <td>{{ formatDate(customer.last_booking_date) }}</td>
            <td class="actions">
              <button @click="editCustomer(customer)" class="btn-edit">Edit</button>
              <button @click="viewBookings(customer)" class="btn-view">Bookings</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import CustomerForm from '../components/CustomerForm.vue'

const showForm = ref(false)
const searchText = ref('')
const clientTypeFilter = ref('')
const gstFilter = ref('')
const customers = ref([])
const stats = ref({
  totalCustomers: 0,
  activeCustomers: 0,
  corporateCustomers: 0,
  gstExemptCustomers: 0
})

const filteredCustomers = computed(() => {
  let filtered = customers.value

  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    filtered = filtered.filter(c => 
      (c.client_name && c.client_name.toLowerCase().includes(search)) ||
      (c.email && c.email.toLowerCase().includes(search)) ||
      (c.phone && c.phone.toLowerCase().includes(search)) ||
      (c.company_name && c.company_name.toLowerCase().includes(search))
    )
  }

  if (clientTypeFilter.value) {
    filtered = filtered.filter(c => c.client_type === clientTypeFilter.value)
  }

  if (gstFilter.value) {
    if (gstFilter.value === 'exempt') {
      filtered = filtered.filter(c => c.is_gst_exempt)
    } else if (gstFilter.value === 'regular') {
      filtered = filtered.filter(c => !c.is_gst_exempt)
    }
  }

  return filtered
})

async function loadCustomers() {
  try {
    const response = await fetch('/api/clients')
    if (response.ok) {
      customers.value = await response.json()
      calculateStats()
    } else {
      console.error('Failed to load customers:', response.status)
    }
  } catch (error) {
    console.error('Error loading customers:', error)
  }
}

function calculateStats() {
  stats.value.totalCustomers = customers.value.length
  stats.value.corporateCustomers = customers.value.filter(c => c.client_type === 'Corporate').length
  stats.value.gstExemptCustomers = customers.value.filter(c => c.is_gst_exempt).length
  
  // Calculate active customers (those with recent bookings)
  const sixMonthsAgo = new Date()
  sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6)
  stats.value.activeCustomers = customers.value.filter(c => 
    c.last_booking_date && new Date(c.last_booking_date) > sixMonthsAgo
  ).length
}

function getRowClass(customer) {
  const classes = []
  if (customer.client_type === 'Corporate') classes.push('corporate-customer')
  if (customer.is_gst_exempt) classes.push('gst-exempt-customer')
  return classes.join(' ')
}

function formatDate(dateString) {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleDateString()
}

function editCustomer(customer) {
  // TODO: Implement edit functionality
  console.log('Edit customer:', customer)
}

function viewBookings(customer) {
  // TODO: Navigate to bookings filtered by customer
  console.log('View bookings for:', customer)
}

function onCustomerSaved() {
  showForm.value = false
  loadCustomers() // Refresh the list
}

onMounted(() => {
  loadCustomers()
})
</script>

<style scoped>
.customer-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  min-width: 140px;
}

.stat-value {
  font-size: 2rem;
  font-weight: bold;
  margin-bottom: 5px;
}

.stat-card.total .stat-value { color: #333; }
.stat-card.active .stat-value { color: #28a745; }
.stat-card.corporate .stat-value { color: #007bff; }
.stat-card.gst-exempt .stat-value { color: #ffc107; }

.stat-label {
  font-size: 0.9rem;
  color: #666;
}

.customer-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
}

.filters {
  display: flex;
  gap: 15px;
}

.filters input, .filter-select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.btn-primary {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-primary:hover {
  background: #0056b3;
}

.form-section {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.customer-list {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.customers-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 15px;
}

.customers-table th,
.customers-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.customers-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #333;
}

.customers-table tr:hover {
  background-color: #f5f5f5;
}

.customer-name {
  font-weight: 500;
  color: #333;
}

.type-corporate {
  color: #007bff;
  font-weight: bold;
}

.type-individual {
  color: #6c757d;
}

.gst-exempt {
  color: #ffc107;
  font-weight: bold;
}

.gst-regular {
  color: #28a745;
}

.corporate-customer {
  background-color: #e3f2fd;
}

.gst-exempt-customer {
  border-left: 4px solid #ffc107;
}

.actions {
  display: flex;
  gap: 8px;
}

.btn-edit, .btn-view {
  padding: 4px 8px;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn-edit {
  background: #28a745;
  color: white;
}

.btn-edit:hover {
  background: #218838;
}

.btn-view {
  background: #17a2b8;
  color: white;
}

.btn-view:hover {
  background: #138496;
}

h1 {
  margin-bottom: 2rem;
  color: #333;
}

h2 {
  margin-bottom: 1rem;
  color: #333;
}
</style>
