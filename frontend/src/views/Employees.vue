<template>
  <div>
    <h1>Employee Management</h1>
    
    <!-- Employee Stats -->
    <div class="employee-stats">
      <div class="stat-card total">
        <div class="stat-value">{{ stats.totalEmployees }}</div>
        <div class="stat-label">Total Employees</div>
      </div>
      <div class="stat-card drivers">
        <div class="stat-value">{{ stats.drivers }}</div>
        <div class="stat-label">Drivers</div>
      </div>
      <div class="stat-card active">
        <div class="stat-value">{{ stats.activeEmployees }}</div>
        <div class="stat-label">Active Today</div>
      </div>
      <div class="stat-card payroll">
        <div class="stat-value">${{ stats.monthlyPayroll }}</div>
        <div class="stat-label">Monthly Payroll</div>
      </div>
    </div>

    <!-- Employee Filters and Actions -->
    <div class="employee-actions">
      <div class="filters">
        <input v-model="searchText" placeholder="Search employees..." />
        <select v-model="departmentFilter" class="filter-select">
          <option value="">All Departments</option>
          <option value="Operations">Operations</option>
          <option value="Administration">Administration</option>
          <option value="Maintenance">Maintenance</option>
        </select>
        <select v-model="statusFilter" class="filter-select">
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="on_leave">On Leave</option>
        </select>
      </div>
      <button @click="showForm = !showForm" class="btn-primary">
        {{ showForm ? 'Hide Form' : 'Add New Employee' }}
      </button>
    </div>

    <!-- Employee Form -->
    <div v-if="showForm" class="form-section">
      <div class="employee-form">
        <h3>Add New Employee</h3>
        <form @submit.prevent="addEmployee">
          <div class="form-row">
            <div class="form-group">
              <label>Full Name</label>
              <input v-model="newEmployee.name" type="text" required />
            </div>
            <div class="form-group">
              <label>Employee ID</label>
              <input v-model="newEmployee.employee_id" type="text" required />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Department</label>
              <select v-model="newEmployee.department" required>
                <option value="">Select Department</option>
                <option value="Operations">Operations</option>
                <option value="Administration">Administration</option>
                <option value="Maintenance">Maintenance</option>
              </select>
            </div>
            <div class="form-group">
              <label>Position</label>
              <input v-model="newEmployee.position" type="text" required />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Phone</label>
              <input v-model="newEmployee.phone" type="tel" />
            </div>
            <div class="form-group">
              <label>Email</label>
              <input v-model="newEmployee.email" type="email" />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Hire Date</label>
              <input v-model="newEmployee.hire_date" type="date" required />
            </div>
            <div class="form-group">
              <label>Hourly Rate</label>
              <input v-model="newEmployee.hourly_rate" type="number" step="0.01" min="0" />
            </div>
          </div>
          <div class="form-actions">
            <button type="submit" class="btn-save">Save Employee</button>
            <button type="button" @click="cancelForm" class="btn-cancel">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Employee List -->
    <div class="employee-list">
      <h2>Employee Directory</h2>
      <table class="employees-table">
        <thead>
          <tr>
            <th>Employee ID</th>
            <th>Name</th>
            <th>Department</th>
            <th>Position</th>
            <th>Phone</th>
            <th>Email</th>
            <th>Hire Date</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="employee in filteredEmployees" :key="employee.id" :class="getRowClass(employee)">
            <td class="employee-id">{{ employee.employee_id }}</td>
            <td class="employee-name">{{ employee.name }}</td>
            <td>{{ employee.department }}</td>
            <td>{{ employee.position }}</td>
            <td>{{ employee.phone }}</td>
            <td>{{ employee.email }}</td>
            <td>{{ formatDate(employee.hire_date) }}</td>
            <td>
              <span :class="'status-' + (employee.status || 'active')">
                {{ formatStatus(employee.status) }}
              </span>
            </td>
            <td class="actions">
              <button @click="editEmployee(employee)" class="btn-edit">Edit</button>
              <button @click="openPayroll(employee)" class="btn-view">Payroll</button>
              <button @click="openFiles(employee)" class="btn-view">Files</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Employee Files Modal -->
    <div v-if="showFiles" class="files-modal" @click.self="closeFiles">
      <div class="files-content">
        <div class="files-header">
          <h3>Employee Files — {{ selectedEmployee?.name || selectedEmployee?.employee_id }}</h3>
          <button class="close" @click="closeFiles">×</button>
        </div>
        
        <div class="files-sections">
          <div class="file-section">
            <FileUpload 
              title="Licenses" 
              hint="Driver's license, chauffeur permit, etc."
              category="employees" 
              :entity-id="String(selectedEmployee?.employee_id || selectedEmployee?.id)" 
              subfolder="licenses"
            />
          </div>
          
          <div class="file-section">
            <FileUpload 
              title="Qualifications" 
              hint="Certificates, training records, etc."
              category="employees" 
              :entity-id="String(selectedEmployee?.employee_id || selectedEmployee?.id)" 
              subfolder="qualifications"
            />
          </div>
          
          <div class="file-section">
            <FileUpload 
              title="Permits" 
              hint="Work permits, special authorizations, etc."
              category="employees" 
              :entity-id="String(selectedEmployee?.employee_id || selectedEmployee?.id)" 
              subfolder="permits"
            />
          </div>
          
          <div class="file-section">
            <FileUpload 
              title="Documents" 
              hint="Employment contracts, HR documents, etc."
              category="employees" 
              :entity-id="String(selectedEmployee?.employee_id || selectedEmployee?.id)" 
              subfolder="documents"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Payroll Summary Modal -->
    <div v-if="showPayroll" class="payroll-modal" @click.self="closePayroll">
      <div class="payroll-content">
        <div class="payroll-header">
          <h3>Payroll Summary — {{ selectedEmployee?.name || selectedEmployee?.employee_id }}</h3>
          <button class="close" @click="closePayroll">×</button>
        </div>
        <div class="period-row">
          <label>Start</label><input type="date" v-model="payStart" />
          <label>End</label><input type="date" v-model="payEnd" />
          <button class="btn-primary" @click="loadPayrollSummary" :disabled="!selectedEmployee">Refresh</button>
        </div>
        <div v-if="payrollLoading">Loading…</div>
        <div v-else-if="payrollError" style="color:#c00">{{ payrollError }}</div>
        <div v-else class="payroll-grid">
          <div class="pay-item"><label>Regular Hours</label><span>{{ nz(payrollSummary.regular_hours) }}</span></div>
          <div class="pay-item"><label>Overtime Hours</label><span>{{ nz(payrollSummary.overtime_hours) }}</span></div>
          <div class="pay-item"><label>Gross Pay</label><span>${{ nz(payrollSummary.gross_pay).toFixed(2) }}</span></div>
          <div class="pay-item"><label>Net Pay</label><span>${{ nz(payrollSummary.net_pay).toFixed(2) }}</span></div>
          <div class="pay-item"><label>CPP</label><span>${{ nz(payrollSummary.employee_cpp_deduction).toFixed(2) }}</span></div>
          <div class="pay-item"><label>EI</label><span>${{ nz(payrollSummary.employee_ei_deduction).toFixed(2) }}</span></div>
          <div class="pay-item"><label>Fed Tax</label><span>${{ nz(payrollSummary.income_tax_withheld_federal).toFixed(2) }}</span></div>
          <div class="pay-item"><label>AB Tax</label><span>${{ nz(payrollSummary.income_tax_withheld_alberta).toFixed(2) }}</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { toast } from '@/toast/toastStore'
import FileUpload from '@/components/FileUpload.vue'

const showForm = ref(false)
const showFiles = ref(false)
const searchText = ref('')
const departmentFilter = ref('')
const statusFilter = ref('')
const employees = ref([])
const stats = ref({
  totalEmployees: 0,
  drivers: 0,
  activeEmployees: 0,
  monthlyPayroll: 0
})

const newEmployee = ref({
  name: '',
  employee_id: '',
  department: '',
  position: '',
  phone: '',
  email: '',
  hire_date: '',
  hourly_rate: 0,
  status: 'active'
})

const filteredEmployees = computed(() => {
  let filtered = employees.value

  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    filtered = filtered.filter(e => 
      (e.name && e.name.toLowerCase().includes(search)) ||
      (e.employee_id && e.employee_id.toLowerCase().includes(search)) ||
      (e.department && e.department.toLowerCase().includes(search)) ||
      (e.position && e.position.toLowerCase().includes(search))
    )
  }

  if (departmentFilter.value) {
    filtered = filtered.filter(e => e.department === departmentFilter.value)
  }

  if (statusFilter.value) {
    filtered = filtered.filter(e => (e.status || 'active') === statusFilter.value)
  }

  return filtered
})

async function loadEmployees() {
  try {
    const response = await fetch('/api/employees')
    if (response.ok) {
      employees.value = await response.json()
      calculateStats()
    } else {
      console.error('Failed to load employees:', response.status)
      // Add some mock data for demonstration
      employees.value = [
        {
          id: 1,
          employee_id: 'EMP001',
          name: 'John Smith',
          department: 'Operations',
          position: 'Senior Driver',
          phone: '(555) 123-4567',
          email: 'john.smith@company.com',
          hire_date: '2020-01-15',
          hourly_rate: 25.00,
          status: 'active'
        },
        {
          id: 2,
          employee_id: 'EMP002',
          name: 'Sarah Johnson',
          department: 'Administration',
          position: 'Dispatcher',
          phone: '(555) 234-5678',
          email: 'sarah.johnson@company.com',
          hire_date: '2019-06-01',
          hourly_rate: 22.50,
          status: 'active'
        },
        {
          id: 3,
          employee_id: 'EMP003',
          name: 'Mike Wilson',
          department: 'Operations',
          position: 'Driver',
          phone: '(555) 345-6789',
          email: 'mike.wilson@company.com',
          hire_date: '2021-03-10',
          hourly_rate: 20.00,
          status: 'active'
        }
      ]
      calculateStats()
    }
  } catch (error) {
    console.error('Error loading employees:', error)
  }
}

function calculateStats() {
  stats.value.totalEmployees = employees.value.length
  stats.value.drivers = employees.value.filter(e => 
    e.position && e.position.toLowerCase().includes('driver')
  ).length
  stats.value.activeEmployees = employees.value.filter(e => 
    (e.status || 'active') === 'active'
  ).length
  
  // Calculate estimated monthly payroll (40 hours/week * 4.33 weeks/month)
  const monthlyHours = 40 * 4.33
  stats.value.monthlyPayroll = employees.value
    .filter(e => (e.status || 'active') === 'active')
    .reduce((total, e) => total + (e.hourly_rate || 0) * monthlyHours, 0)
    .toFixed(0)
}

function getRowClass(employee) {
  const status = employee.status || 'active'
  return `status-row-${status}`
}

function formatDate(dateString) {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleDateString()
}

function formatStatus(status) {
  const statusMap = {
    'active': 'Active',
    'inactive': 'Inactive',
    'on_leave': 'On Leave'
  }
  return statusMap[status] || 'Active'
}

function editEmployee(employee) {
  // TODO: Implement edit functionality
  console.log('Edit employee:', employee)
}

function viewPayroll(employee) {
  // DEPRECATED
  openPayroll(employee)
}

async function addEmployee() {
  try {
    // TODO: Implement API call to add employee
    console.log('Adding employee:', newEmployee.value)
    
    // For now, add locally for demonstration
    const newEmp = { 
      ...newEmployee.value, 
      id: employees.value.length + 1,
      hourly_rate: parseFloat(newEmployee.value.hourly_rate)
    }
    employees.value.push(newEmp)
    calculateStats()
    cancelForm()
    
    toast.success('Employee added successfully!')
  } catch (error) {
    console.error('Error adding employee:', error)
    toast.error('Failed to add employee')
  }
}

function cancelForm() {
  showForm.value = false
  newEmployee.value = {
    name: '',
    employee_id: '',
    department: '',
    position: '',
    phone: '',
    email: '',
    hire_date: '',
    hourly_rate: 0,
    status: 'active'
  }
}

function openFiles(employee) {
  selectedEmployee.value = employee
  showFiles.value = true
}

function closeFiles() {
  showFiles.value = false
  selectedEmployee.value = null
}

onMounted(() => {
  loadEmployees()
})

// Payroll modal state
const showPayroll = ref(false)
const selectedEmployee = ref(null)
const payrollSummary = ref({})
const payrollLoading = ref(false)
const payrollError = ref('')
const payStart = ref('')
const payEnd = ref('')

function openPayroll(employee) {
  selectedEmployee.value = employee
  // Default to current month
  const today = new Date()
  const start = new Date(today.getFullYear(), today.getMonth(), 1)
  const end = new Date(today.getFullYear(), today.getMonth() + 1, 0)
  payStart.value = start.toISOString().slice(0,10)
  payEnd.value = end.toISOString().slice(0,10)
  showPayroll.value = true
  loadPayrollSummary()
}

function closePayroll() {
  showPayroll.value = false
  payrollSummary.value = {}
  payrollError.value = ''
}

function nz(v) { try { return parseFloat(v || 0) } catch (_) { return 0 } }

async function loadPayrollSummary() {
  if (!selectedEmployee.value) return
  payrollLoading.value = true
  payrollError.value = ''
  try {
    const url = `/api/employee/${selectedEmployee.value.id || selectedEmployee.value.employee_id}/payroll_summary?start_date=${encodeURIComponent(payStart.value)}&end_date=${encodeURIComponent(payEnd.value)}`
    const res = await fetch(url)
    if (!res.ok) throw new Error(await res.text())
    const data = await res.json()
    payrollSummary.value = data.payroll_summary || {}
  } catch (e) {
    payrollError.value = e.message || String(e)
  } finally {
    payrollLoading.value = false
  }
}
</script>

<style scoped>
.employee-stats {
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
.stat-card.drivers .stat-value { color: #28a745; }
.stat-card.active .stat-value { color: #007bff; }
.stat-card.payroll .stat-value { color: #6f42c1; }

.stat-label {
  font-size: 0.9rem;
  color: #666;
}

.employee-actions {
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

.employee-form h3 {
  margin-bottom: 20px;
  color: #333;
}

.form-row {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
}

.form-group {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.form-group label {
  margin-bottom: 5px;
  font-weight: 500;
  color: #333;
}

.form-group input, .form-group select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.btn-save {
  padding: 10px 20px;
  background: #28a745;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-save:hover {
  background: #218838;
}

.btn-cancel {
  padding: 10px 20px;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-cancel:hover {
  background: #545b62;
}

.employee-list {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.employees-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 15px;
}

.employees-table th,
.employees-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.employees-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #333;
}

.employees-table tr:hover {
  background-color: #f5f5f5;
}

.employee-id {
  font-weight: 500;
  color: #007bff;
}

.employee-name {
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

.status-on_leave {
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

.status-row-on_leave {
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

h1 {
  margin-bottom: 2rem;
  color: #333;
}

h2 {
  margin-bottom: 1rem;
  color: #333;
}

/* Payroll modal styling */
.payroll-modal {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.payroll-content {
  background: #fff;
  border-radius: 8px;
  width: 90%;
  max-width: 700px;
  padding: 1rem 1.25rem 1.25rem 1.25rem;
  box-shadow: 0 6px 24px rgba(0,0,0,0.2);
}
.payroll-header { display:flex; justify-content: space-between; align-items: center; }
.payroll-header .close { background:none; border:none; font-size: 1.5rem; cursor:pointer; }
.period-row { display:flex; gap:0.75rem; align-items:center; margin: 0.5rem 0 1rem; }
.payroll-grid { display:grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
.pay-item { display:flex; justify-content: space-between; border:1px solid #eee; border-radius:6px; padding: 0.5rem 0.75rem; }
.pay-item label { color:#555; }

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
.files-header { display:flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #007bff; padding-bottom: 0.5rem; margin-bottom: 1rem; }
.files-header .close { background:none; border:none; font-size: 1.5rem; cursor:pointer; }
.files-sections { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; }
@media (max-width: 1024px) {
  .files-sections { grid-template-columns: 1fr; }
}
</style>
