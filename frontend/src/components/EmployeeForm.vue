<template>
  <form @submit.prevent="submitForm">
    <h2>Employee Information</h2>
    <div class="container-row">
      <div class="container-box left-box">
        <div class="form-row">
          <label>Employee</label>
          <select v-model="selectedEmployee" @change="onEmployeeSelect">
            <option value="">Select Employee</option>
            <option v-for="e in employeeList" :key="e.employee_id" :value="e.employee_id">
              {{ e.name || e.full_name || e.employee_name }}
            </option>
          </select>
        </div>
        <div class="form-row">
          <label>Name</label>
          <input v-model="form.name" type="text" />
        </div>
        <div class="form-row">
          <label>Email</label>
          <input v-model="form.email" type="email" />
        </div>
        <div class="form-row">
          <label>Phone</label>
          <input v-model="form.phone" type="text" />
        </div>
      </div>
      <div class="container-box right-box">
        <div class="form-row">
          <label>Role</label>
          <input v-model="form.role" type="text" />
        </div>
        <div class="form-row">
          <label>Hire Date</label>
          <input v-model="form.date_hired" type="date" />
        </div>
        <div class="form-row">
          <label>Status</label>
          <input v-model="form.status" type="text" />
        </div>
        <div class="form-row">
          <label>Assigned Vehicle</label>
          <input v-model="form.assigned_vehicle" type="text" />
        </div>
      </div>
    </div>
    <!-- Duties & Compliance -->
    <div class="container-row">
      <div class="container-box">
        <label>Duties</label>
        <select v-model="form.duties" multiple>
          <option>Dispatcher</option>
          <option>Chauffeur</option>
          <option>Cleaner</option>
          <option>Mechanic</option>
          <option>Other</option>
        </select>
        <label>Status</label>
        <select v-model="form.status">
          <option>Active</option>
          <option>Inactive</option>
        </select>
        <label>Restrictions</label>
        <input v-model="form.restrictions" type="text" />
      </div>
      <div class="container-box">
        <label>License Expiry</label>
        <input v-model="form.license_expiry" type="date" />
        <label>AGLC ProServe Expiry</label>
        <input v-model="form.proserve_expiry" type="date" />
        <label>Training Checklist Completed</label>
        <input type="checkbox" v-model="form.training_completed" />
        <label>Resume</label>
        <input type="file" @change="onFileUpload('resume', $event)" accept=".pdf,.jpg,.jpeg" />
        <label>Scanned Forms (Individual Upload)</label>
        <input type="file" @change="onFileUpload('individual', $event)" accept=".pdf,.jpg,.jpeg" />
        <label>Scanned Forms (Group Upload)</label>
        <input type="file" @change="onFileUpload('group', $event)" multiple accept=".pdf,.jpg,.jpeg" />
        <div>
          <h4>Uploaded Files</h4>
          <div
            class="drop-area"
            @dragover.prevent="dragActive = true"
            @dragleave.prevent="dragActive = false"
            @drop.prevent="handleDrop"
            :class="{ 'drag-active': dragActive }"
          >
            <span v-if="!dragActive">Drag & drop files here or </span>
            <span v-if="dragActive" style="color:#1976d2;font-weight:bold;">Drop files to upload</span>
            <input type="file" @change="onDocumentUpload($event)" accept=".pdf,.jpg,.jpeg,.png" multiple style="display:inline-block;margin-left:0.5rem;" />
          </div>
          <div v-if="employeeDocuments.length === 0" style="margin-top:1rem;">No documents uploaded.</div>
          <div v-else class="doc-thumbnails">
            <div v-for="doc in employeeDocuments" :key="doc" class="doc-thumb">
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
import { ref, onMounted } from 'vue'
import { toast } from '@/toast/toastStore'
const dragActive = ref(false)
async function handleDrop(event) {
  dragActive.value = false
  if (!selectedEmployee.value) {
    toast.error('Select an employee first!')
    return
  }
  const files = Array.from(event.dataTransfer.files)
  for (const file of files) {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`/api/employee/${selectedEmployee.value}/upload_document`, {
      method: 'POST',
      body: formData
    })
    if (!res.ok) {
      toast.error('Upload failed: ' + file.name)
    }
  }
  await fetchEmployeeDocuments()
}
      </div>
    </div>
    <!-- Pay & Float History -->
    <div class="container-box">
      <label>Pay History</label>
      <textarea v-model="form.pay_history" rows="2" placeholder="Pay history notes..."></textarea>
      <label>Deductions</label>
      <input v-model="form.deductions" type="text" />
      <label>Floats Given</label>
      <input v-model="form.floats_given" type="text" />
      <label>Receipts Received</label>
      <input v-model="form.receipts_received" type="text" />
      <label>Advances</label>
      <input v-model="form.advances" type="text" />
    </div>
    <div v-if="complianceWarning" class="compliance-warning">
      <strong>⚠ Compliance Issue:</strong> Missing or expired documentation, or does not meet Red Deer bylaw rules for chauffeurs.
    </div>
    <button type="submit">Save Employee</button>
  </form>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { toast } from '@/toast/toastStore'
const form = ref({
  name: '',
  email: '',
  phone: '',
  role: '',
  date_hired: '',
  status: '',
  assigned_vehicle: '',
  duties: [],
  restrictions: '',
  license_expiry: '',
  proserve_expiry: '',
  training_completed: false,
  resume: null,
  forms: [],
  pay_history: '',
  deductions: '',
  floats_given: '',
  receipts_received: '',
  advances: ''
})

const complianceWarning = computed(() => {
  // Check for missing/expired docs
  const now = new Date()
  let missing = false
  // License expiry
  if (!form.value.license_expiry || new Date(form.value.license_expiry) < now) missing = true
  // ProServe expiry
  if (!form.value.proserve_expiry || new Date(form.value.proserve_expiry) < now) missing = true
  // Training checklist
  if (!form.value.training_completed) missing = true
  // If duties include Chauffeur, check restrictions
  if (form.value.duties.includes('Chauffeur')) {
    if (form.value.restrictions && form.value.restrictions.toLowerCase().includes('does not meet red deer')) missing = true
  }
  // Uploaded files: check for missing/expired required types
  // (Stub: in production, check file.type and file.expiry)
  return missing
})






const employeeDocuments = ref([])


async function onDocumentUpload(event) {
  const files = Array.from(event.target.files)
  if (!selectedEmployee.value) {
    toast.error('Select an employee first!')
    return
  }
  for (const file of files) {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`/api/employee/${selectedEmployee.value}/upload_document`, {
      method: 'POST',
      body: formData
    })
    if (!res.ok) {
      toast.error('Upload failed: ' + file.name)
    }
  }
  await fetchEmployeeDocuments()
}
function isImage(filename) {
  return /\.(jpg|jpeg|png)$/i.test(filename)
}
function isPdf(filename) {
  return /\.pdf$/i.test(filename)
}
function getDocUrl(filename) {
  return `/api/employee/document/${encodeURIComponent(filename)}`
}
async function fetchEmployeeDocuments() {
  if (!selectedEmployee.value) {
    employeeDocuments.value = []
    return
  }
  const res = await fetch(`/api/employee/${selectedEmployee.value}/documents`)
  if (res.ok) {
    const data = await res.json()
    employeeDocuments.value = data.files || []
  } else {
    employeeDocuments.value = []
  }
}

function runOCR(file) {
  // Stub: In production, send file to backend OCR service
  file.ocrText = '[OCR preview: simulated text from ' + file.name + ']'
}

function onFileUpload(type, event) {
  if (type === 'resume') {
    form.value.resume = event.target.files[0]
  } else if (type === 'forms') {
    form.value.forms = Array.from(event.target.files)
  }
}
const employeeList = ref([])
const selectedEmployee = ref('')

onMounted(async () => {
  try {
    const res = await fetch('/api/employees')
    if (res.ok) {
      employeeList.value = await res.json()
    } else {
      console.error('Failed to fetch employees:', res.status)
    }
  } catch (err) {
    console.error('Error fetching employees:', err)
  }
  await fetchEmployeeDocuments()
})

async function onEmployeeSelect() {
  const e = employeeList.value.find(x => x.employee_id === selectedEmployee.value)
  if (e) {
    Object.keys(form.value).forEach(k => {
      form.value[k] = e[k] !== undefined ? e[k] : ''
    })
    await fetchEmployeeDocuments()
  }
}
function submitForm() {
  toast.success('Employee saved!')
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
/* Thumbnails */
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
/* Drag-and-drop area */
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
</style>
<style scoped>
.compliance-warning {
  background: #fff3cd;
  color: #856404;
  border: 1px solid #ffeeba;
  padding: 1rem;
  margin-bottom: 1rem;
  border-radius: 6px;
}
</style>
