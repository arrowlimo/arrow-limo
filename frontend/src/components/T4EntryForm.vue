<template>
  <div class="t4-form-container">
    <!-- Header -->
    <div class="form-header">
      <h2>T4 STATEMENT OF REMUNERATION PAID</h2>
      <div class="header-controls">
        <div class="control-group">
          <label for="employee-t4-select">Employee:</label>
          <select id="employee-t4-select" v-model="selectedEmployeeId" @change="loadEmployeeT4" class="form-control">
            <option value="">-- Select Employee --</option>
            <option v-for="emp in employees" :key="emp.id" :value="emp.id">
              {{ emp.name }}
            </option>
          </select>
        </div>
        
        <div class="control-group">
          <label>Tax Year:</label>
          <select v-model="form.taxYear" class="form-control narrow">
            <option value="2024">2024</option>
            <option value="2025">2025</option>
            <option value="2026">2026</option>
          </select>
        </div>
        
        <div class="button-group">
          <button @click="loadT4" class="btn btn-secondary">📥 Load</button>
          <button @click="saveT4" class="btn btn-primary">💾 Save</button>
          <button @click="generatePDF" class="btn btn-info">📄 PDF</button>
          <button @click="resetForm" class="btn btn-outline">🔄 Reset</button>
        </div>
      </div>
    </div>

    <!-- T4 Form Grid -->
    <div class="t4-grid">
      <!-- Employee Info Section -->
      <div class="section employee-info">
        <h3>Employee Information</h3>
        <div class="form-row">
          <label>Full Name:</label>
          <input v-model="form.employeeName" type="text" class="form-input" readonly />
        </div>
        <div class="form-row">
          <label>SIN:</label>
          <input v-model="form.sin" type="text" class="form-input" placeholder="XXX-XXX-XXX" />
        </div>
        <div class="form-row">
          <label>Address:</label>
          <input v-model="form.address" type="text" class="form-input" />
        </div>
        <div class="form-row">
          <label>City/Province/ZIP:</label>
          <input v-model="form.cityProvinceZip" type="text" class="form-input" />
        </div>
      </div>

      <!-- Employer Info Section -->
      <div class="section employer-info">
        <h3>Employer Information</h3>
        <div class="form-row">
          <label>Company Name:</label>
          <input v-model="form.companyName" type="text" class="form-input" readonly />
        </div>
        <div class="form-row">
          <label>BN:</label>
          <input v-model="form.businessNumber" type="text" class="form-input" readonly />
        </div>
        <div class="form-row">
          <label>Phone:</label>
          <input v-model="form.employerPhone" type="tel" class="form-input" readonly />
        </div>
        <div class="form-row">
          <label>Tax Year:</label>
          <input :value="form.taxYear" type="text" class="form-input" readonly />
        </div>
      </div>
    </div>

    <!-- T4 Boxes Grid -->
    <div class="t4-boxes">
      <h3>T4 Boxes (Detachable Record of Employment)</h3>
      
      <div class="boxes-grid">
        <!-- Box 14 -->
        <div class="box">
          <div class="box-label">Box 14</div>
          <label>Employment Income</label>
          <input v-model.number="form.box14" type="number" step="0.01" class="form-input currency" />
          <small>Auto-calculated: ${{ autoCalculated.box14 }}</small>
        </div>

        <!-- Box 16 -->
        <div class="box">
          <div class="box-label">Box 16</div>
          <label>Employee CPP Contributions</label>
          <input v-model.number="form.box16" type="number" step="0.01" class="form-input currency" />
          <small>Auto: ${{ autoCalculated.box16 }}</small>
        </div>

        <!-- Box 18 -->
        <div class="box">
          <div class="box-label">Box 18</div>
          <label>Employee EI Premiums</label>
          <input v-model.number="form.box18" type="number" step="0.01" class="form-input currency" />
          <small>Auto: ${{ autoCalculated.box18 }}</small>
        </div>

        <!-- Box 22 -->
        <div class="box">
          <div class="box-label">Box 22</div>
          <label>Income Tax Deducted</label>
          <input v-model.number="form.box22" type="number" step="0.01" class="form-input currency" />
          <small>Auto: ${{ autoCalculated.box22 }}</small>
        </div>

        <!-- Box 24 -->
        <div class="box">
          <div class="box-label">Box 24</div>
          <label>EI Insurable Earnings</label>
          <input v-model.number="form.box24" type="number" step="0.01" class="form-input currency" />
          <small>Auto: ${{ autoCalculated.box24 }}</small>
        </div>

        <!-- Box 26 -->
        <div class="box">
          <div class="box-label">Box 26</div>
          <label>CPP Pensionable Earnings</label>
          <input v-model.number="form.box26" type="number" step="0.01" class="form-input currency" />
          <small>Auto: ${{ autoCalculated.box26 }}</small>
        </div>

        <!-- Box 44 -->
        <div class="box">
          <div class="box-label">Box 44</div>
          <label>Employment Commissions</label>
          <input v-model.number="form.box44" type="number" step="0.01" class="form-input currency" />
          <small>Auto: ${{ autoCalculated.box44 }}</small>
        </div>

        <!-- Box 46 -->
        <div class="box">
          <div class="box-label">Box 46</div>
          <label>Other Remuneration</label>
          <input v-model.number="form.box46" type="number" step="0.01" class="form-input currency" />
          <small>Auto: ${{ autoCalculated.box46 }}</small>
        </div>

        <!-- Box 52 -->
        <div class="box">
          <div class="box-label">Box 52</div>
          <label>Union Dues</label>
          <input v-model.number="form.box52" type="number" step="0.01" class="form-input currency" />
          <small>Auto: ${{ autoCalculated.box52 }}</small>
        </div>
      </div>
    </div>

    <!-- Sync Status & Comparison -->
    <div class="sync-section">
      <h3>Reconciliation</h3>
      <div class="comparison-table">
        <table>
          <thead>
            <tr>
              <th>Box</th>
              <th>Manual Entry</th>
              <th>Auto-Calculated</th>
              <th>Difference</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="box in t4Boxes" :key="box.name" :class="{ 'has-diff': box.difference !== 0 }">
              <td><strong>{{ box.name }}</strong></td>
              <td class="currency">${{ box.manual.toFixed(2) }}</td>
              <td class="currency">${{ box.auto.toFixed(2) }}</td>
              <td class="currency" :class="box.difference !== 0 ? 'text-warning' : 'text-success'">
                {{ box.difference !== 0 ? box.difference.toFixed(2) : '✓' }}
              </td>
              <td>
                <span v-if="box.difference === 0" class="badge badge-success">Match</span>
                <span v-else class="badge badge-warning">Override</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Notes -->
    <div class="notes-section">
      <h3>Notes / Corrections</h3>
      <textarea v-model="form.notes" class="form-input textarea" rows="4" 
        placeholder="Document any manual overrides or corrections made (e.g., 2013 T4 correction, salary equity adjustment, etc.)..."></textarea>
    </div>

    <!-- Status Message -->
    <div v-if="statusMessage" :class="['status-message', statusType]">
      {{ statusMessage }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const selectedEmployeeId = ref('')
const form = ref({
  employeeName: '',
  sin: '',
  address: '',
  cityProvinceZip: '',
  companyName: 'Arrow Limousine Ltd.',
  businessNumber: '',
  employerPhone: '',
  taxYear: new Date().getFullYear().toString(),
  box14: 0,  // Employment Income
  box16: 0,  // Employee CPP
  box18: 0,  // Employee EI
  box22: 0,  // Income Tax
  box24: 0,  // EI Insurable
  box26: 0,  // CPP Pensionable
  box44: 0,  // Commissions
  box46: 0,  // Other Remuneration
  box52: 0,  // Union Dues
  notes: ''
})

const autoCalculated = ref({
  box14: 0, box16: 0, box18: 0, box22: 0, box24: 0, box26: 0, box44: 0, box46: 0, box52: 0
})

const employees = ref([])
const statusMessage = ref('')
const statusType = ref('')

const t4Boxes = computed(() => [
  { name: 'Box 14', manual: form.value.box14, auto: autoCalculated.value.box14 },
  { name: 'Box 16', manual: form.value.box16, auto: autoCalculated.value.box16 },
  { name: 'Box 18', manual: form.value.box18, auto: autoCalculated.value.box18 },
  { name: 'Box 22', manual: form.value.box22, auto: autoCalculated.value.box22 },
  { name: 'Box 24', manual: form.value.box24, auto: autoCalculated.value.box24 },
  { name: 'Box 26', manual: form.value.box26, auto: autoCalculated.value.box26 },
  { name: 'Box 44', manual: form.value.box44, auto: autoCalculated.value.box44 },
  { name: 'Box 46', manual: form.value.box46, auto: autoCalculated.value.box46 },
  { name: 'Box 52', manual: form.value.box52, auto: autoCalculated.value.box52 }
].map(b => ({
  ...b,
  difference: b.manual - b.auto
})))

async function loadEmployeeT4() {
  if (!selectedEmployeeId.value) return
  try {
    const res = await fetch(`/api/employees/${selectedEmployeeId.value}`)
    if (res.ok) {
      const emp = await res.json()
      form.value.employeeName = emp.name || ''
      form.value.sin = emp.sin || ''
      form.value.address = emp.address || ''
      form.value.cityProvinceZip = `${emp.city || ''}, ${emp.province || ''} ${emp.postal_code || ''}`
    }
  } catch (e) {
    showStatus('Failed to load employee', 'error')
  }
}

async function loadT4() {
  if (!selectedEmployeeId.value || !form.value.taxYear) {
    showStatus('Select employee and tax year', 'error')
    return
  }
  try {
    const res = await fetch(`/api/t4/${selectedEmployeeId.value}/${form.value.taxYear}`)
    if (res.ok) {
      const data = await res.json()
      const boxes = ['box14', 'box16', 'box18', 'box22', 'box24', 'box26', 'box44', 'box46', 'box52']
      boxes.forEach(b => {
        form.value[b] = data[b] || 0
        autoCalculated.value[b] = data[`auto_${b}`] || 0
      })
      form.value.notes = data.notes || ''
      showStatus('T4 loaded successfully', 'success')
    }
  } catch (e) {
    showStatus('Failed to load T4', 'error')
  }
}

async function saveT4() {
  if (!selectedEmployeeId.value) {
    showStatus('Select an employee', 'error')
    return
  }
  try {
    const res = await fetch('/api/t4', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        employee_id: selectedEmployeeId.value,
        ...form.value
      })
    })
    if (res.ok) {
      showStatus('T4 saved successfully', 'success')
    } else {
      showStatus('Failed to save T4', 'error')
    }
  } catch (e) {
    showStatus(e.message, 'error')
  }
}

async function generatePDF() {
  if (!selectedEmployeeId.value) {
    showStatus('Select an employee', 'error')
    return
  }
  try {
    const res = await fetch(`/api/t4/${selectedEmployeeId.value}/${form.value.taxYear}/pdf`, {
      method: 'GET'
    })
    if (res.ok) {
      const blob = await res.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `T4_${form.value.employeeName}_${form.value.taxYear}.pdf`
      a.click()
      showStatus('PDF generated and downloaded', 'success')
    }
  } catch (e) {
    showStatus('Failed to generate PDF', 'error')
  }
}

function resetForm() {
  form.value = {
    employeeName: '',
    sin: '',
    address: '',
    cityProvinceZip: '',
    companyName: 'Arrow Limousine Ltd.',
    businessNumber: '',
    employerPhone: '',
    taxYear: new Date().getFullYear().toString(),
    box14: 0, box16: 0, box18: 0, box22: 0, box24: 0, box26: 0, box44: 0, box46: 0, box52: 0,
    notes: ''
  }
  showStatus('Form reset', 'info')
}

function showStatus(msg, type) {
  statusMessage.value = msg
  statusType.value = type
  setTimeout(() => { statusMessage.value = '' }, 3000)
}

onMounted(async () => {
  try {
    const res = await fetch('/api/employees')
    if (res.ok) {
      employees.value = await res.json()
    }
  } catch (e) {
    console.error('Failed to load employees', e)
  }
})
</script>

<style scoped>
.t4-form-container {
  padding: 25px;
  background: #f5f5f5;
  border-radius: 8px;
  max-width: 1200px;
  margin: 0 auto;
}

.form-header {
  background: white;
  padding: 20px;
  border-radius: 6px;
  margin-bottom: 25px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.form-header h2 {
  margin: 0 0 15px 0;
  font-size: 18px;
  font-weight: 700;
  color: #1a3a52;
  letter-spacing: 0.5px;
}

.header-controls {
  display: flex;
  gap: 20px;
  align-items: flex-end;
  flex-wrap: wrap;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.control-group label {
  font-size: 12px;
  font-weight: 600;
  color: #555;
}

.form-control {
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 8px 10px;
  font-size: 13px;
  min-width: 150px;
}

.form-control.narrow {
  min-width: 100px;
}

.form-control:focus {
  outline: none;
  border-color: #4a90e2;
  box-shadow: 0 0 0 3px rgba(74,144,226,0.1);
}

.button-group {
  display: flex;
  gap: 8px;
  margin-left: auto;
}

.btn {
  padding: 8px 14px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 600;
  transition: all 0.2s;
}

.btn-primary {
  background: #4a90e2;
  color: white;
}

.btn-primary:hover {
  background: #357abd;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover {
  background: #5a6268;
}

.btn-info {
  background: #17a2b8;
  color: white;
}

.btn-info:hover {
  background: #138496;
}

.btn-outline {
  background: white;
  color: #666;
  border: 1px solid #ddd;
}

.btn-outline:hover {
  background: #f5f5f5;
}

.t4-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  margin-bottom: 25px;
}

@media (max-width: 768px) {
  .t4-grid {
    grid-template-columns: 1fr;
  }
}

.section {
  background: white;
  padding: 18px;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  border-left: 4px solid #4a90e2;
}

.section h3 {
  margin: 0 0 15px 0;
  font-size: 13px;
  font-weight: 700;
  color: #333;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.form-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.form-row label {
  flex: 0 0 30%;
  font-size: 12px;
  font-weight: 500;
  color: #555;
}

.form-input {
  flex: 1;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 8px 10px;
  font-size: 13px;
}

.form-input:focus {
  outline: none;
  border-color: #4a90e2;
  box-shadow: 0 0 0 3px rgba(74,144,226,0.1);
}

.form-input[readonly] {
  background: #f5f5f5;
  color: #666;
}

.form-input.currency {
  text-align: right;
  font-family: 'Courier New', monospace;
  font-weight: 500;
}

.t4-boxes {
  background: white;
  padding: 20px;
  border-radius: 6px;
  margin-bottom: 25px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.t4-boxes h3 {
  margin: 0 0 20px 0;
  font-size: 14px;
  font-weight: 700;
  color: #333;
}

.boxes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 15px;
}

.box {
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 12px;
  background: #f9f9f9;
  transition: all 0.2s;
}

.box:hover {
  background: #f0f0f0;
  border-color: #4a90e2;
}

.box-label {
  font-size: 14px;
  font-weight: 700;
  color: #1a3a52;
  margin-bottom: 8px;
  background: #e8f0f8;
  padding: 4px 8px;
  border-radius: 3px;
  text-align: center;
}

.box label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #555;
  margin-bottom: 6px;
}

.box .form-input {
  width: 100%;
  padding: 6px 8px;
  font-size: 12px;
  margin-bottom: 4px;
}

.box small {
  display: block;
  font-size: 10px;
  color: #999;
  text-align: right;
}

.sync-section {
  background: white;
  padding: 20px;
  border-radius: 6px;
  margin-bottom: 25px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.sync-section h3 {
  margin: 0 0 15px 0;
  font-size: 14px;
  font-weight: 700;
  color: #333;
}

.comparison-table {
  overflow-x: auto;
}

.comparison-table table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

.comparison-table th {
  background: #f0f0f0;
  padding: 10px;
  text-align: left;
  font-weight: 600;
  color: #333;
  border-bottom: 2px solid #ddd;
}

.comparison-table td {
  padding: 10px;
  border-bottom: 1px solid #eee;
}

.comparison-table tr:hover {
  background: #f9f9f9;
}

.comparison-table td.currency {
  text-align: right;
  font-family: 'Courier New', monospace;
  font-weight: 500;
}

.comparison-table tr.has-diff {
  background: #fffbea;
}

.comparison-table .text-success {
  color: #28a745;
  font-weight: 600;
}

.comparison-table .text-warning {
  color: #ff9800;
  font-weight: 600;
}

.badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 600;
}

.badge-success {
  background: #d4edda;
  color: #155724;
}

.badge-warning {
  background: #fff3cd;
  color: #856404;
}

.notes-section {
  background: white;
  padding: 20px;
  border-radius: 6px;
  margin-bottom: 25px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.notes-section h3 {
  margin: 0 0 12px 0;
  font-size: 13px;
  font-weight: 700;
  color: #333;
}

.form-input.textarea {
  width: 100%;
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 10px;
  font-size: 12px;
  font-family: 'Courier New', monospace;
  resize: vertical;
}

.status-message {
  padding: 12px 15px;
  border-radius: 4px;
  margin-top: 15px;
  font-size: 12px;
  font-weight: 500;
}

.status-message.success {
  background: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.status-message.error {
  background: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.status-message.info {
  background: #d1ecf1;
  color: #0c5460;
  border: 1px solid #bee5eb;
}
</style>
