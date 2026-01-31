<template>
  <div>
    <h1>Vehicle Management</h1>
    
    <!-- Vehicle Stats -->
    <div class="vehicle-stats">
      <div class="stat-card total">
        <div class="stat-value">{{ stats.totalVehicles }}</div>
        <div class="stat-label">Total Vehicles</div>
      </div>
      <div class="stat-card active">
        <div class="stat-value">{{ stats.activeVehicles }}</div>
        <div class="stat-label">Active</div>
      </div>
      <div class="stat-card maintenance">
        <div class="stat-value">{{ stats.inMaintenance }}</div>
        <div class="stat-label">In Maintenance</div>
      </div>
      <div class="stat-card service">
        <div class="stat-value">{{ stats.serviceDue }}</div>
        <div class="stat-label">Service Due</div>
      </div>
    </div>

    <!-- Vehicle Filters and Actions -->
    <div class="vehicle-actions">
      <div class="filters">
        <input v-model="searchText" placeholder="Search vehicles..." />
        <select v-model="typeFilter" class="filter-select">
          <option value="">All Types</option>
          <option value="Sedan">Sedan</option>
          <option value="SUV">SUV</option>
          <option value="Shuttle Bus">Shuttle Bus</option>
          <option value="Party Bus">Party Bus</option>
        </select>
        <select v-model="statusFilter" class="filter-select">
          <option value="">All Status</option>
          <option value="Active">Active</option>
          <option value="Inactive">Inactive</option>
          <option value="Maintenance">Maintenance</option>
        </select>
      </div>
      <button @click="showForm = !showForm" class="btn-primary">
        {{ showForm ? 'Hide Form' : 'Add New Vehicle' }}
      </button>
    </div>

    <!-- Vehicle Form -->
    <div v-if="showForm" class="vehicle-section">
      <VehicleForm @saved="onVehicleSaved" />
    </div>

    <!-- Vehicle Table -->
    <div class="vehicles-table-container">
      <table class="vehicles-table">
        <thead>
          <tr>
            <th>Vehicle #</th>
            <th>Make/Model</th>
            <th>Year</th>
            <th>Type</th>
            <th>License Plate</th>
            <th>Status</th>
            <th>Next Service</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="vehicle in filteredVehicles" :key="vehicle.vehicle_id" :class="'status-row-' + (vehicle.operational_status || 'active').toLowerCase()">
            <td class="vehicle-number">{{ vehicle.vehicle_number }}</td>
            <td class="vehicle-name">{{ vehicle.make }} {{ vehicle.model }}</td>
            <td>{{ vehicle.year }}</td>
            <td>{{ vehicle.type }}</td>
            <td>{{ vehicle.license_plate }}</td>
            <td>
              <span :class="'status-' + (vehicle.operational_status || 'active').toLowerCase()">
                {{ vehicle.operational_status || 'Active' }}
              </span>
            </td>
            <td>{{ formatDate(vehicle.next_service_due) }}</td>
            <td class="actions">
              <button @click="editVehicle(vehicle)" class="btn-edit">Edit</button>
              <button @click="openFiles(vehicle)" class="btn-view">Files</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Vehicle Files Modal -->
    <div v-if="showFiles" class="files-modal" @click.self="closeFiles">
      <div class="files-content">
        <div class="files-header">
          <h3>Vehicle Files — {{ selectedVehicle?.vehicle_number || selectedVehicle?.vehicle_id }}</h3>
          <button class="close" @click="closeFiles">×</button>
        </div>
        
        <div class="files-sections">
          <div class="file-section">
            <FileUpload 
              title="Maintenance Records" 
              hint="Service records, repair invoices, etc."
              category="vehicles" 
              :entity-id="String(selectedVehicle?.vehicle_number || selectedVehicle?.vehicle_id)" 
              subfolder="maintenance"
            />
          </div>
          
          <div class="file-section">
            <FileUpload 
              title="Inspections" 
              hint="CVIP, safety inspections, etc."
              category="vehicles" 
              :entity-id="String(selectedVehicle?.vehicle_number || selectedVehicle?.vehicle_id)" 
              subfolder="inspections"
            />
          </div>
          
          <div class="file-section">
            <FileUpload 
              title="Registration" 
              hint="Registration documents, renewals, etc."
              category="vehicles" 
              :entity-id="String(selectedVehicle?.vehicle_number || selectedVehicle?.vehicle_id)" 
              subfolder="registration"
            />
          </div>
          
          <div class="file-section">
            <FileUpload 
              title="Insurance" 
              hint="Insurance policies, claims, etc."
              category="vehicles" 
              :entity-id="String(selectedVehicle?.vehicle_number || selectedVehicle?.vehicle_id)" 
              subfolder="insurance"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { toast } from '@/toast/toastStore'
import VehicleForm from '../components/VehicleForm.vue'
import FileUpload from '@/components/FileUpload.vue'

const showForm = ref(false)
const showFiles = ref(false)
const searchText = ref('')
const typeFilter = ref('')
const statusFilter = ref('')
const vehicles = ref([])
const selectedVehicle = ref(null)
const stats = ref({
  totalVehicles: 0,
  activeVehicles: 0,
  inMaintenance: 0,
  serviceDue: 0
})

async function loadVehicles() {
  try {
    const res = await fetch('/api/vehicles')
    if (res.ok) {
      vehicles.value = await res.json()
      calculateStats()
    }
  } catch (e) {
    console.error('Failed to load vehicles:', e)
  }
}

function calculateStats() {
  stats.value.totalVehicles = vehicles.value.length
  stats.value.activeVehicles = vehicles.value.filter(v => v.operational_status === 'Active' || v.is_active).length
  stats.value.inMaintenance = vehicles.value.filter(v => v.operational_status === 'Maintenance').length
  
  const today = new Date()
  stats.value.serviceDue = vehicles.value.filter(v => {
    if (!v.next_service_due) return false
    const serviceDate = new Date(v.next_service_due)
    return serviceDate <= today
  }).length
}

const filteredVehicles = computed(() => {
  return vehicles.value.filter(v => {
    const text = searchText.value.toLowerCase()
    const vehicleNum = (v.vehicle_number || "").toString().toLowerCase()
    const make = (v.make || "").toString().toLowerCase()
    const model = (v.model || "").toString().toLowerCase()
    const plate = (v.license_plate || "").toString().toLowerCase()
    
    const matchText = !text || vehicleNum.includes(text) || make.includes(text) || model.includes(text) || plate.includes(text)
    const matchType = !typeFilter.value || v.type === typeFilter.value
    const matchStatus = !statusFilter.value || v.operational_status === statusFilter.value
    
    return matchText && matchType && matchStatus
  })
})

function editVehicle(vehicle) {
  // TODO: Implement edit functionality
  console.log('Edit vehicle:', vehicle)
  showForm.value = true
}

function openFiles(vehicle) {
  selectedVehicle.value = vehicle
  showFiles.value = true
}

function closeFiles() {
  showFiles.value = false
  selectedVehicle.value = null
}

function onVehicleSaved() {
  showForm.value = false
  loadVehicles()
  toast.success('Vehicle saved successfully!')
}

function formatDate(date) {
  if (!date) return 'N/A'
  return new Date(date).toLocaleDateString()
}

onMounted(() => {
  loadVehicles()
})
</script>

<style scoped>
.vehicle-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1.5rem;
  margin-bottom: 2rem;
}

.stat-card {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1.5rem;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.stat-card.total {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.stat-card.active {
  background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
}

.stat-card.maintenance {
  background: linear-gradient(135deg, #ffc107 0%, #ff9800 100%);
}

.stat-card.service {
  background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
}

.stat-value {
  font-size: 2.5rem;
  font-weight: bold;
  margin-bottom: 0.5rem;
}

.stat-label {
  font-size: 0.9rem;
  opacity: 0.9;
}

.vehicle-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
  gap: 1rem;
}

.filters {
  display: flex;
  gap: 1rem;
  flex: 1;
}

.filters input {
  flex: 1;
  max-width: 300px;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.filter-select {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.btn-primary {
  background: #007bff;
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
}

.btn-primary:hover {
  background: #0056b3;
}

.vehicle-section {
  background: #fff;
  border-radius: 8px;
  padding: 2rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-bottom: 2rem;
}

.vehicles-table-container {
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.vehicles-table {
  width: 100%;
  border-collapse: collapse;
}

.vehicles-table th,
.vehicles-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.vehicles-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #333;
}

.vehicles-table tr:hover {
  background-color: #f5f5f5;
}

.vehicle-number {
  font-weight: 500;
  color: #007bff;
}

.vehicle-name {
  font-weight: 500;
  color: #333;
}

.status-active {
  color: #28a745;
  font-weight: bold;
}

.status-inactive {
  color: #dc3545;
  font-weight: bold;
}

.status-maintenance {
  color: #ffc107;
  font-weight: bold;
}

.status-row-active {
  background-color: #f8fff8;
}

.status-row-inactive {
  background-color: #fff5f5;
  opacity: 0.7;
}

.status-row-maintenance {
  background-color: #fffbf0;
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

/* Files modal styling */
.files-modal {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.files-content {
  background: #fff;
  border-radius: 8px;
  width: 95%;
  max-width: 1200px;
  max-height: 90vh;
  overflow-y: auto;
  padding: 1rem 1.25rem 1.25rem 1.25rem;
  box-shadow: 0 6px 24px rgba(0,0,0,0.2);
}
.files-header { 
  display:flex; 
  justify-content: space-between; 
  align-items: center; 
  border-bottom: 2px solid #007bff; 
  padding-bottom: 0.5rem; 
  margin-bottom: 1rem; 
}
.files-header .close { 
  background:none; 
  border:none; 
  font-size: 1.5rem; 
  cursor:pointer; 
}
.files-sections { 
  display: grid; 
  grid-template-columns: repeat(2, 1fr); 
  gap: 1rem; 
}
@media (max-width: 1024px) {
  .files-sections { 
    grid-template-columns: 1fr; 
  }
}

h1 {
  margin-bottom: 2rem;
  color: #333;
}
</style>
