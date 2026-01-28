<template>
  <form @submit.prevent="submitForm">
    <h2>Vehicle Information</h2>
    <div class="form-row">
      <label for="vehicleSelect">Select Vehicle:</label>
      <select id="vehicleSelect" v-model="selectedVehicle" @change="onVehicleSelect" class="medium">
        <option value="">-- Choose Vehicle --</option>
        <option v-for="v in vehicleList" :key="v.vehicle_number" :value="v.vehicle_number">{{ v.vehicle_number }} - {{ v.make }} {{ v.model }} ({{ v.year }})</option>
      </select>
    </div>
    <div class="container-row">
      <!-- Identification -->
      <div class="container-box">
        <h3>Identification</h3>
        <div class="form-row"><label>Vehicle Number</label><input v-model="form.vehicle_number" type="text" class="short" /></div>
        <div class="form-row"><label>VIN Number</label><input v-model="form.vin_number" type="text" class="medium" /></div>
        <div class="form-row"><label>Vehicle Code</label><input v-model="form.vehicle_code" type="text" class="short" /></div>
        <div class="form-row"><label>Fleet Number</label><input v-model="form.fleet_number" type="text" class="short" /></div>
        <div class="form-row"><label>Fleet Position</label><input v-model="form.fleet_position" type="number" class="short" /></div>
        <div class="form-row"><label>License Plate</label><input v-model="form.license_plate" type="text" class="short" /></div>
        <div class="form-row"><label>Make</label><input v-model="form.make" type="text" class="short" /></div>
        <div class="form-row"><label>Model</label><input v-model="form.model" type="text" class="short" /></div>
        <div class="form-row"><label>Year</label><input v-model="form.year" type="number" class="short" /></div>
        <div class="form-row"><label>Type</label><select v-model="form.type" class="short"><option>Sedan</option><option>SUV</option><option>Shuttle Bus</option><option>Party Bus</option></select></div>
        <div class="form-row"><label>Vehicle Category</label><input v-model="form.vehicle_category" type="text" class="short" /></div>
        <div class="form-row"><label>Vehicle Class</label><input v-model="form.vehicle_class" type="text" class="short" /></div>
        <div class="form-row"><label>Passenger Capacity</label><input v-model="form.passenger_capacity" type="number" class="short" /></div>
        <div class="form-row"><label>Description</label><textarea v-model="form.description" class="long"></textarea></div>
      </div>
      <!-- Operational Status -->
      <div class="container-box">
        <h3>Operational Status</h3>
        <div class="form-row"><label>Operational Status</label><select v-model="form.operational_status" class="short"><option>Active</option><option>Inactive</option><option>Maintenance</option></select></div>
        <div class="form-row"><label>Is Active</label><input v-model="form.is_active" type="checkbox" /></div>
        <div class="form-row"><label>Commission Date</label><input v-model="form.commission_date" type="date" class="short" /></div>
        <div class="form-row"><label>Decommission Date</label><input v-model="form.decommission_date" type="date" class="short" /></div>
      </div>
      <!-- Physical Specs -->
      <div class="container-box">
        <h3>Physical Specs</h3>
        <div class="form-row"><label>Exterior Color</label><input v-model="form.ext_color" type="text" class="short" /></div>
        <div class="form-row"><label>Interior Color</label><input v-model="form.int_color" type="text" class="short" /></div>
        <div class="form-row"><label>Length</label><input v-model="form.length" type="number" class="short" /></div>
        <div class="form-row"><label>Width</label><input v-model="form.width" type="number" class="short" /></div>
        <div class="form-row"><label>Height</label><input v-model="form.height" type="number" class="short" /></div>
        <div class="form-row"><label>Odometer</label><input v-model="form.odometer" type="number" class="medium" /></div>
      </div>
      <!-- Maintenance/History -->
      <div class="container-box">
        <h3>Maintenance/History</h3>
        <div class="form-row"><label>Next Service Due</label><input v-model="form.next_service_due" type="date" class="short" /></div>
        <div class="form-row"><label>Last Service Date</label><input v-model="form.last_service_date" type="date" class="short" /></div>
        <div class="form-row"><label>Service Type</label><input v-model="form.service_type" type="text" class="short" /></div>
        <div class="form-row"><label>Service Cost</label><input v-model="form.service_cost" type="number" class="short" /></div>
        <div class="form-row"><label>Maintenance Notes</label><textarea v-model="form.maintenance_notes" class="long"></textarea></div>
      </div>
      <!-- Insurance/Registration/Financing -->
      <div class="container-box">
        <h3>Insurance/Registration/Financing</h3>
        <div class="form-row"><label>Insurance Policy Number</label><input v-model="form.insurance_policy_number" type="text" class="medium" /></div>
        <div class="form-row"><label>Policy End Date</label><input v-model="form.policy_end_date" type="date" class="short" /></div>
        <div class="form-row"><label>Registration Expiry</label><input v-model="form.registration_expiry" type="date" class="short" /></div>
        <div class="form-row"><label>Financing Status</label><select v-model="form.financing_status" class="short"><option>Financed</option><option>Leased</option><option>Owned</option></select></div>
        <div class="form-row"><label>Financing Notes</label><textarea v-model="form.financing_notes" class="long"></textarea></div>
      </div>
    </div>
    <!-- Vehicle Documents Upload -->
    <div>
      <h4>Vehicle Documents</h4>
      <div
        class="drop-area"
        @dragover.prevent="dragActive = true"
        @dragleave.prevent="dragActive = false"
        @drop.prevent="handleDrop"
        :class="{ 'drag-active': dragActive }"
      >
        <span v-if="!dragActive">Drag & drop files here or </span>
        <span v-if="dragActive" style="color:#1976d2;font-weight:bold;">Drop files to upload</span>
        <input type="file" @change="onDocumentUpload($event)" accept=".pdf,.jpg,.jpeg,.png" multiple style="display:inline-block;margin-left:0.5rem;" :disabled="uploadingDocs" />
      </div>
      <div v-if="vehicleDocuments.length === 0" style="margin-top:1rem;">No documents uploaded.</div>
      <div v-else class="doc-thumbnails">
        <div v-for="doc in vehicleDocuments" :key="doc" class="doc-thumb">
          <template v-if="isImage(doc)">
            <img :src="getDocUrl(doc)" :alt="doc" class="thumb-img" />
          </template>
          <template v-else-if="isPdf(doc)">
            <a :href="getDocUrl(doc)" target="_blank"><span class="pdf-icon">📄</span> {{ doc }}</a>
          </template>
          <template v-else>
            <a :href="getDocUrl(doc)" target="_blank">{{ doc }}</a>
          </template>
        </div>
      </div>
    </div>
    <button type="submit" :disabled="saving">{{ saving ? 'Saving…' : 'Save Vehicle' }}</button>
  </form>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { toast } from '@/toast/toastStore'
const dragActive = ref(false)
const vehicleDocuments = ref([])
const uploadingDocs = ref(false)
const saving = ref(false)
function isImage(filename) {
  return /\.(jpg|jpeg|png)$/i.test(filename)
}
function isPdf(filename) {
  return /\.pdf$/i.test(filename)
}
function getDocUrl(filename) {
  // Update this endpoint if you add backend support for vehicle docs
  return `/api/vehicle/document/${encodeURIComponent(filename)}`
}
async function fetchVehicleDocuments() {
  if (!selectedVehicle.value) {
    vehicleDocuments.value = []
    return
  }
  // Update this endpoint if you add backend support for vehicle docs
  const res = await fetch(`/api/vehicle/${selectedVehicle.value}/documents`)
  if (res.ok) {
    const data = await res.json()
    vehicleDocuments.value = data.files || []
  } else {
    vehicleDocuments.value = []
  }
}
async function onDocumentUpload(event) {
  const files = Array.from(event.target.files)
  if (!selectedVehicle.value) {
    toast.error('Select a vehicle first!')
    return
  }
  if (uploadingDocs.value) return
  uploadingDocs.value = true
  for (const file of files) {
    const formData = new FormData()
    formData.append('file', file)
    // Update this endpoint if you add backend support for vehicle docs
    const res = await fetch(`/api/vehicle/${selectedVehicle.value}/upload_document`, {
      method: 'POST',
      body: formData
    })
    if (!res.ok) {
      toast.error('Upload failed: ' + file.name)
    }
  }
  await fetchVehicleDocuments()
  uploadingDocs.value = false
}
async function handleDrop(event) {
  dragActive.value = false
  if (!selectedVehicle.value) {
    toast.error('Select a vehicle first!')
    return
  }
  if (uploadingDocs.value) return
  uploadingDocs.value = true
  const files = Array.from(event.dataTransfer.files)
  for (const file of files) {
    const formData = new FormData()
    formData.append('file', file)
    // Update this endpoint if you add backend support for vehicle docs
    const res = await fetch(`/api/vehicle/${selectedVehicle.value}/upload_document`, {
      method: 'POST',
      body: formData
    })
    if (!res.ok) {
      toast.error('Upload failed: ' + file.name)
    }
  }
  await fetchVehicleDocuments()
  uploadingDocs.value = false
}
const form = ref({
  vehicle_number: '', vin_number: '', vehicle_code: '', fleet_number: '', fleet_position: '', license_plate: '', make: '', model: '', year: '', type: '', vehicle_category: '', vehicle_class: '', passenger_capacity: '', description: '', operational_status: '', is_active: false, commission_date: '', decommission_date: '', ext_color: '', int_color: '', length: '', width: '', height: '', odometer: '', next_service_due: '', last_service_date: '', service_type: '', service_cost: '', maintenance_notes: '', insurance_policy_number: '', policy_end_date: '', registration_expiry: '', financing_status: '', financing_notes: ''
})

const vehicleList = ref([])
const selectedVehicle = ref('')

onMounted(async () => {
  try {
    const res = await fetch('/api/vehicles')
    if (res.ok) {
      vehicleList.value = await res.json()
    } else {
      console.error('Failed to fetch vehicles:', res.status)
    }
  } catch (err) {
    console.error('Error fetching vehicles:', err)
  }
  await fetchVehicleDocuments()
})

async function onVehicleSelect() {
  const v = vehicleList.value.find(x => x.vehicle_number === selectedVehicle.value)
  if (v) {
    Object.keys(form.value).forEach(k => {
      form.value[k] = v[k] !== undefined ? v[k] : ''
    })
    await fetchVehicleDocuments()
  }
}
async function submitForm() {
  try {
  saving.value = true
  const res = await fetch('/api/vehicles', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value)
    });
    if (res.ok) {
      toast.success('Vehicle saved!')
    } else {
      const err = await res.text();
      toast.error('Save failed: ' + err)
    }
  } catch (e) {
    toast.error('Save failed: ' + e)
  } finally {
    saving.value = false
  }
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
input, select, textarea {
  padding: 0.5rem;
  border-radius: 5px;
  border: 1px solid #ddd;
  font-size: 1rem;
}
input.short, select.short {
  width: 120px;
}
input.medium, select.medium {
  width: 200px;
}
textarea.long {
  width: 100%;
  min-height: 60px;
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
/* Drag-and-drop area and thumbnails */
.drop-area {
  border: 2px dashed #1976d2;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
  background: #f0f6ff;
  text-align: center;
  transition: background 0.2s, border-color 0.2s;
}
.drop-area.drag-active {
  background: #e3f0ff;
  border-color: #1565c0;
}
.drop-area:has(input[disabled]) {
  opacity: 0.7;
  cursor: not-allowed;
}
.doc-thumbnails {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  margin-top: 1rem;
}
.doc-thumb {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 120px;
  word-break: break-all;
}
.thumb-img {
  width: 100px;
  height: 100px;
  object-fit: cover;
  border: 1px solid #ccc;
  border-radius: 6px;
  margin-bottom: 0.5rem;
}
.pdf-icon {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}
</style>
