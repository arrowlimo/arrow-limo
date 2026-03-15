<script setup>
import { ref, computed, onMounted } from 'vue'

const selectedEmployee = ref(null)
const employees = ref([])
const payrollLoading = ref(false)

const form = ref({
  year: new Date().getFullYear().toString(),
  payPeriod: '',
  // Hours & Rates
  regularHours: 0,
  otHours: 0,
  hourlyRate: 0,
  // Pay Components
  baseSalary: 0,
  bonus: 0,
  gratuity: 0,
  otherBenefits: 0,
  // Deductions
  cpp: 0,
  ei: 0,
  incomeTax: 0,
  // Employment Details
  sin: '',
  hireDate: '',
  employmentType: 'employee'
})

const statusMessage = ref('')
const statusType = ref('') // 'success', 'error', 'info'

// Computed properties
const otRate = computed(() => {
  return form.value.hourlyRate * 1.5
})

const baseCharterIncome = computed(() => {
  return (form.value.regularHours * form.value.hourlyRate) + 
         (form.value.otHours * otRate.value)
})

const grossIncome = computed(() => {
  return baseCharterIncome.value + 
         form.value.baseSalary + 
         form.value.bonus + 
         form.value.gratuity + 
         form.value.otherBenefits
})

const totalDeductions = computed(() => {
  return form.value.cpp + form.value.ei + form.value.incomeTax
})

const netPay = computed(() => {
  return grossIncome.value - totalDeductions.value
})

// Load employees on mount
onMounted(async () => {
  try {
    const response = await fetch('/api/employees')
    employees.value = await response.json()
  } catch (error) {
    showStatus('Failed to load employees', 'error')
  }
})

// Load payroll for selected employee
const loadPayroll = async () => {
  if (!selectedEmployee.value) {
    showStatus('Please select an employee first', 'info')
    return
  }

  payrollLoading.value = true
  try {
    const response = await fetch(
      `/api/payroll/${selectedEmployee.value}/${form.value.year}/${form.value.payPeriod}`
    )
    if (response.ok) {
      const data = await response.json()
      Object.assign(form.value, data)
      showStatus('Payroll loaded successfully', 'success')
    } else {
      showStatus('No payroll found for this period', 'info')
    }
  } catch (error) {
    showStatus('Failed to load payroll: ' + error.message, 'error')
  } finally {
    payrollLoading.value = false
  }
}

// Save payroll
const savePayroll = async () => {
  if (!selectedEmployee.value) {
    showStatus('Please select an employee first', 'info')
    return
  }

  payrollLoading.value = true
  try {
    const response = await fetch('/api/payroll/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        employee_id: selectedEmployee.value,
        ...form.value
      })
    })

    if (response.ok) {
      showStatus('✓ Payroll saved successfully', 'success')
    } else {
      showStatus('Failed to save payroll', 'error')
    }
  } catch (error) {
    showStatus('Error saving payroll: ' + error.message, 'error')
  } finally {
    payrollLoading.value = false
  }
}

// Clear form
const clearForm = () => {
  form.value = {
    year: new Date().getFullYear().toString(),
    payPeriod: '',
    regularHours: 0,
    otHours: 0,
    hourlyRate: 0,
    baseSalary: 0,
    bonus: 0,
    gratuity: 0,
    otherBenefits: 0,
    cpp: 0,
    ei: 0,
    incomeTax: 0,
    sin: '',
    hireDate: '',
    employmentType: 'employee'
  }
  showStatus('Form cleared', 'info')
}

// Recalculate
const recalculate = () => {
  // Trigger computed properties
  const _ = grossIncome.value
  showStatus('✓ Calculations recalculated', 'success')
}

const showStatus = (message, type) => {
  statusMessage.value = message
  statusType.value = type
  setTimeout(() => {
    statusMessage.value = ''
  }, 4000)
}

const formatCurrency = (value) => {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD'
  }).format(value || 0)
}

const formatHours = (value) => {
  return (value || 0).toFixed(2)
}
</script>

<template>
  <div class="payroll-entry-form bg-gradient-to-br from-slate-50 to-slate-100 min-h-screen p-6">
    <!-- Header -->
    <div class="mb-8">
      <h1 class="text-4xl font-bold text-slate-900 mb-6">Payroll Entry Form</h1>
      
      <!-- Top Control Bar -->
      <div class="bg-white rounded-lg shadow-md p-6 mb-7">
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 items-end">
          <div>
            <label for="emp-select" class="block text-sm font-semibold text-slate-700 mb-2">Employee</label>
            <select
              id="emp-select"
              v-model.number="selectedEmployee"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-slate-900"
            >
              <option :value="null">-- Select Employee --</option>
              <option v-for="emp in employees" :key="emp.employee_id" :value="emp.employee_id">
                {{ emp.full_name }} (ID: {{ emp.employee_id }})
              </option>
            </select>
          </div>

          <div>
            <label for="year-select" class="block text-sm font-semibold text-slate-700 mb-2">Year</label>
            <select
              id="year-select"
              v-model="form.year"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-slate-900"
            >
              <option value="2024">2024</option>
              <option value="2025">2025</option>
              <option value="2026">2026</option>
            </select>
          </div>

          <div>
            <label for="period-select" class="block text-sm font-semibold text-slate-700 mb-2">Pay Period</label>
            <select
              id="period-select"
              v-model="form.payPeriod"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-slate-900"
            >
              <option value="">-- Select Period --</option>
              <option value="P01">P01 - Jan 1-14</option>
              <option value="P02">P02 - Jan 15-31</option>
              <option value="P03">P03 - Feb 1-14</option>
            </select>
          </div>

          <div class="lg:col-span-2">
            <div class="flex gap-2">
              <button
                @click="loadPayroll"
                :disabled="payrollLoading"
                class="flex-1 px-4 py-2.5 bg-slate-600 hover:bg-slate-700 text-white font-semibold rounded-lg transition disabled:opacity-50"
              >
                📥 Load
              </button>
              <button
                @click="savePayroll"
                :disabled="payrollLoading"
                class="flex-1 px-4 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition disabled:opacity-50"
              >
                💾 Save
              </button>
              <button
                @click="clearForm"
                class="flex-1 px-4 py-2.5 bg-slate-300 hover:bg-slate-400 text-slate-900 font-semibold rounded-lg transition"
              >
                🔄 Clear
              </button>
              <button
                @click="recalculate"
                class="flex-1 px-4 py-2.5 bg-green-600 hover:bg-green-700 text-white font-semibold rounded-lg transition"
              >
                ⚙️ Calc
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Status Message -->
      <div
        v-if="statusMessage"
        :class="[
          'rounded-lg px-6 py-3 mb-6 font-semibold text-sm',
          statusType === 'success' ? 'bg-green-50 text-green-800 border border-green-200' :
          statusType === 'error' ? 'bg-red-50 text-red-800 border border-red-200' :
          'bg-blue-50 text-blue-800 border border-blue-200'
        ]"
      >
        {{ statusMessage }}
      </div>
    </div>

    <!-- THREE COLUMN MAIN LAYOUT -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
      
      <!-- COLUMN 1: HOURS & RATES -->
      <div class="bg-white rounded-lg shadow-md hover:shadow-lg transition p-6 border-l-4 border-blue-500">
        <h2 class="text-lg font-bold text-slate-900 mb-5 uppercase tracking-wide">Hours & Rates</h2>
        
        <div class="space-y-4">
          <!-- Regular Hours -->
          <div>
            <label for="regular-hours" class="block text-sm font-semibold text-slate-700 mb-1.5">
              Regular Hours
            </label>
            <input
              id="regular-hours"
              v-model.number="form.regularHours"
              type="number"
              step="0.5"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-right text-slate-900"
            />
          </div>

          <!-- Hourly Rate -->
          <div>
            <label for="hourly-rate" class="block text-sm font-semibold text-slate-700 mb-1.5">
              Hourly Rate
            </label>
            <input
              id="hourly-rate"
              v-model.number="form.hourlyRate"
              type="number"
              step="0.01"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-right text-slate-900 font-mono"
            />
          </div>

          <!-- OT Hours -->
          <div>
            <label for="ot-hours" class="block text-sm font-semibold text-slate-700 mb-1.5">
              Overtime Hours
            </label>
            <input
              id="ot-hours"
              v-model.number="form.otHours"
              type="number"
              step="0.5"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-right text-slate-900"
            />
          </div>

          <!-- OT Rate (Read-only: 1.5x) -->
          <div>
            <label for="ot-rate" class="block text-sm font-semibold text-slate-700 mb-1.5">
              OT Rate (1.5x)
            </label>
            <input
              id="ot-rate"
              :value="formatCurrency(otRate)"
              type="text"
              disabled
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg bg-slate-100 text-right text-slate-600 font-mono cursor-not-allowed"
            />
          </div>

          <!-- Charter Income Display -->
          <div class="mt-6 pt-4 border-t border-slate-200">
            <p class="text-xs text-slate-600 uppercase font-semibold mb-2">Charter Income</p>
            <p class="text-2xl font-bold text-blue-600">{{ formatCurrency(baseCharterIncome) }}</p>
            <p class="text-xs text-slate-500 mt-1">{{ formatHours(form.regularHours) }} hrs × {{ formatCurrency(form.hourlyRate) }} + {{ formatHours(form.otHours) }} OT hrs</p>
          </div>
        </div>
      </div>

      <!-- COLUMN 2: PAY COMPONENTS -->
      <div class="bg-white rounded-lg shadow-md hover:shadow-lg transition p-6 border-l-4 border-green-500">
        <h2 class="text-lg font-bold text-slate-900 mb-5 uppercase tracking-wide">Pay Components</h2>
        
        <div class="space-y-4">
          <!-- Base Salary -->
          <div>
            <label for="base-salary" class="block text-sm font-semibold text-slate-700 mb-1.5">
              Base Salary
            </label>
            <input
              id="base-salary"
              v-model.number="form.baseSalary"
              type="number"
              step="0.01"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 text-right text-slate-900 font-mono"
            />
          </div>

          <!-- Bonus -->
          <div>
            <label for="bonus" class="block text-sm font-semibold text-slate-700 mb-1.5">
              Bonus
            </label>
            <input
              id="bonus"
              v-model.number="form.bonus"
              type="number"
              step="0.01"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 text-right text-slate-900 font-mono"
            />
          </div>

          <!-- Gratuity -->
          <div>
            <label for="gratuity" class="block text-sm font-semibold text-slate-700 mb-1.5">
              Gratuity / Tips
            </label>
            <input
              id="gratuity"
              v-model.number="form.gratuity"
              type="number"
              step="0.01"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 text-right text-slate-900 font-mono"
            />
          </div>

          <!-- Other Benefits -->
          <div>
            <label for="other-benefits" class="block text-sm font-semibold text-slate-700 mb-1.5">
              Other Benefits
            </label>
            <input
              id="other-benefits"
              v-model.number="form.otherBenefits"
              type="number"
              step="0.01"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500 text-right text-slate-900 font-mono"
            />
          </div>

          <!-- Gross Income Display -->
          <div class="mt-6 pt-4 border-t border-slate-200">
            <p class="text-xs text-slate-600 uppercase font-semibold mb-2">Total Gross Income</p>
            <p class="text-2xl font-bold text-green-600">{{ formatCurrency(grossIncome) }}</p>
          </div>
        </div>
      </div>

      <!-- COLUMN 3: DEDUCTIONS & NET -->
      <div class="bg-white rounded-lg shadow-md hover:shadow-lg transition p-6 border-l-4 border-orange-500">
        <h2 class="text-lg font-bold text-slate-900 mb-5 uppercase tracking-wide">Deductions & Net</h2>
        
        <div class="space-y-4">
          <!-- CPP -->
          <div>
            <label for="cpp" class="block text-sm font-semibold text-slate-700 mb-1.5">
              CPP Contribution
            </label>
            <input
              id="cpp"
              v-model.number="form.cpp"
              type="number"
              step="0.01"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-right text-slate-900 font-mono"
            />
          </div>

          <!-- EI -->
          <div>
            <label for="ei" class="block text-sm font-semibold text-slate-700 mb-1.5">
              EI Premium
            </label>
            <input
              id="ei"
              v-model.number="form.ei"
              type="number"
              step="0.01"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-right text-slate-900 font-mono"
            />
          </div>

          <!-- Income Tax -->
          <div>
            <label for="income-tax" class="block text-sm font-semibold text-slate-700 mb-1.5">
              Income Tax
            </label>
            <input
              id="income-tax"
              v-model.number="form.incomeTax"
              type="number"
              step="0.01"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-orange-500 focus:border-orange-500 text-right text-slate-900 font-mono"
            />
          </div>

          <!-- Total Deductions Display -->
          <div class="mt-6 pt-4 border-t border-slate-200">
            <p class="text-xs text-slate-600 uppercase font-semibold mb-2">Total Deductions</p>
            <p class="text-2xl font-bold text-orange-600">-{{ formatCurrency(totalDeductions) }}</p>
          </div>

          <!-- NET PAY - HIGHLIGHTED -->
          <div class="mt-6 pt-4 border-t-2 border-slate-300 bg-gradient-to-r from-purple-50 to-indigo-50 -mx-6 px-6 py-4 rounded-b-lg">
            <p class="text-xs text-slate-600 uppercase font-semibold mb-2">💰 NET PAY (Take Home)</p>
            <p class="text-3xl font-bold text-purple-700">{{ formatCurrency(netPay) }}</p>
          </div>
        </div>
      </div>
    </div>

    <!-- EMPLOYMENT DETAILS & SUMMARY SECTION -->
    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <!-- Employment Details Card -->
      <div class="bg-white rounded-lg shadow-md p-6 border-l-4 border-indigo-500">
        <h2 class="text-lg font-bold text-slate-900 mb-5 uppercase tracking-wide">Employment Details</h2>
        
        <div class="space-y-4">
          <div>
            <label for="sin" class="block text-sm font-semibold text-slate-700 mb-1.5">
              SIN (Social Insurance Number)
            </label>
            <input
              id="sin"
              v-model="form.sin"
              type="text"
              placeholder="XXX-XXX-XXX"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-slate-900 font-mono"
            />
          </div>

          <div>
            <label for="hire-date" class="block text-sm font-semibold text-slate-700 mb-1.5">
              Hire Date
            </label>
            <input
              id="hire-date"
              v-model="form.hireDate"
              type="date"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-slate-900"
            />
          </div>

          <div>
            <label for="emp-type" class="block text-sm font-semibold text-slate-700 mb-1.5">
              Employment Type
            </label>
            <select
              id="emp-type"
              v-model="form.employmentType"
              class="w-full px-4 py-2.5 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 text-slate-900"
            >
              <option value="employee">Employee</option>
              <option value="contractor">Contractor</option>
              <option value="owner">Owner</option>
            </select>
          </div>
        </div>
      </div>

      <!-- Pay Period Summary Card -->
      <div class="bg-white rounded-lg shadow-md p-6 border-l-4 border-teal-500">
        <h2 class="text-lg font-bold text-slate-900 mb-5 uppercase tracking-wide">Period Summary</h2>
        
        <div class="space-y-3">
          <div class="flex justify-between items-center pb-3 border-b border-slate-200">
            <span class="text-slate-700 font-semibold">Regular Hours:</span>
            <span class="text-xl font-bold text-slate-900">{{ formatHours(form.regularHours) }}</span>
          </div>
          <div class="flex justify-between items-center pb-3 border-b border-slate-200">
            <span class="text-slate-700 font-semibold">OT Hours:</span>
            <span class="text-xl font-bold text-slate-900">{{ formatHours(form.otHours) }}</span>
          </div>
          <div class="flex justify-between items-center pb-3 border-b border-slate-200">
            <span class="text-slate-700 font-semibold">Gross Income:</span>
            <span class="text-xl font-bold text-green-600">{{ formatCurrency(grossIncome) }}</span>
          </div>
          <div class="flex justify-between items-center pb-3 border-b border-slate-200">
            <span class="text-slate-700 font-semibold">Total Deductions:</span>
            <span class="text-xl font-bold text-orange-600">{{ formatCurrency(totalDeductions) }}</span>
          </div>
          <div class="flex justify-between items-center pt-2 bg-gradient-to-r from-purple-50 to-indigo-50 px-4 py-3 rounded-lg">
            <span class="text-lg font-bold text-purple-900">NET PAY:</span>
            <span class="text-2xl font-bold text-purple-700">{{ formatCurrency(netPay) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
::-webkit-input-placeholder {
  color: #999;
}

input::-webkit-outer-spin-button,
input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

input[type=number] {
  -moz-appearance: textfield;
}
</style>
