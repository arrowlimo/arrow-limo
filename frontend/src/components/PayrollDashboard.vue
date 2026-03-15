<script setup>
import { ref, computed, onMounted } from 'vue'
import { toast } from 'vue-sonner'

const selectedEmployee = ref(null)
const selectedYear = ref(new Date().getFullYear())
const selectedMonth = ref(new Date().getMonth() + 1)
const selectedPeriod = computed(() => `${selectedYear.value}-${selectedMonth.value.toString().padStart(2, '0')}`)

// Tab and data
const activeTab = ref('overview')
const workHistory = ref([])
const monthlySummary = ref([])
const matchedCharters = ref([])
const reconciliationStatus = ref(null)

// State flags
const workHistoryLoading = ref(false)
const monthlySummaryLoading = ref(false)
const matchingCharters = ref(false)
const generatingBalance = ref(false)
const employees = ref([])
const employeesLoading = ref(true)

// Computed properties
const totalMonthlyGross = computed(() => {
  const monthData = monthlySummary.value.find(m => m.period === selectedPeriod.value)
  return monthData ? monthData.gross : 0
})

const totalMonthlyDeductions = computed(() => {
  const monthData = monthlySummary.value.find(m => m.period === selectedPeriod.value)
  return monthData ? monthData.deductions : 0
})

const totalMonthlyNet = computed(() => {
  const monthData = monthlySummary.value.find(m => m.period === selectedPeriod.value)
  return monthData ? monthData.net : 0
})

const totalYTDGross = computed(() => {
  return monthlySummary.value.reduce((sum, m) => sum + m.gross, 0)
})

const totalYTDDeductions = computed(() => {
  return monthlySummary.value.reduce((sum, m) => sum + m.deductions, 0)
})

const totalYTDNet = computed(() => {
  return monthlySummary.value.reduce((sum, m) => sum + m.net, 0)
})

// Load employees on mount
onMounted(async () => {
  try {
    const response = await fetch('/api/employees')
    const data = await response.json()
    employees.value = Array.isArray(data) ? data : []
  } catch (error) {
    console.error('Failed to load employees:', error)
    toast.error('Failed to load employee list')
  } finally {
    employeesLoading.value = false
  }
})

// Load work history
const loadWorkHistory = async () => {
  if (!selectedEmployee.value) {
    toast.warning('Please select an employee')
    return
  }

  workHistoryLoading.value = true
  try {
    const response = await fetch(
      `/api/payroll/employee-work-history/${selectedEmployee.value}/${selectedYear.value}`
    )
    
    if (!response.ok) throw new Error('Failed to load work history')
    
    workHistory.value = await response.json()
  } catch (error) {
    console.error('Work history error:', error)
    toast.error('Failed to load work history')
  } finally {
    workHistoryLoading.value = false
  }
}

// Load monthly summary
const loadMonthlySummary = async () => {
  if (!selectedEmployee.value) {
    toast.warning('Please select an employee')
    return
  }

  monthlySummaryLoading.value = true
  try {
    const response = await fetch(
      `/api/payroll/employee-monthly-summary/${selectedEmployee.value}/${selectedYear.value}`
    )
    
    if (!response.ok) throw new Error('Failed to load monthly summary')
    
    monthlySummary.value = await response.json()
  } catch (error) {
    console.error('Monthly summary error:', error)
    toast.error('Failed to load monthly summary')
  } finally {
    monthlySummaryLoading.value = false
  }
}

// Auto-match charters
const matchAllCharters = async () => {
  if (!selectedEmployee.value) {
    toast.warning('Please select an employee')
    return
  }

  matchingCharters.value = true
  try {
    const response = await fetch('/api/payroll/auto-match-charters', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        employee_id: selectedEmployee.value,
        period: selectedPeriod.value
      })
    })
    
    if (!response.ok) throw new Error('Failed to match charters')
    
    const result = await response.json()
    toast.success(`Matched ${result.matched} charters`)
    
    // Reload work history
    await loadWorkHistory()
  } catch (error) {
    console.error('Charter matching error:', error)
    toast.error('Failed to match charters')
  } finally {
    matchingCharters.value = false
  }
}

// Generate month-end balance
const generateMonthEndBalance = async () => {
  if (!selectedEmployee.value) {
    toast.warning('Please select an employee')
    return
  }

  generatingBalance.value = true
  try {
    const response = await fetch('/api/payroll/month-end-balance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        employee_id: selectedEmployee.value,
        period: selectedPeriod.value
      })
    })
    
    if (!response.ok) throw new Error('Failed to generate balance')
    
    reconciliationStatus.value = await response.json()
  } catch (error) {
    console.error('Balance generation error:', error)
    toast.error('Failed to generate month-end balance')
  } finally {
    generatingBalance.value = false
  }
}

// Generate pay stub
const generatePayStub = async () => {
  if (!selectedEmployee.value) {
    toast.warning('Please select an employee')
    return
  }

  try {
    const response = await fetch(
      `/api/payroll/generate-paystub/${selectedEmployee.value}/${selectedPeriod.value.replace('-', '')}`
    )
    
    if (!response.ok) throw new Error('Failed to generate pay stub')
    
    const data = await response.json()
    
    // In a real app, this would download a PDF
    console.log('Pay stub data:', data)
    toast.success('Pay stub generated')
  } catch (error) {
    console.error('Pay stub error:', error)
    toast.error('Failed to generate pay stub')
  }
}

// Handle year/month changes
const updatePeriod = () => {
  if (activeTab.value === 'overview') {
    loadMonthlySummary()
  }
}

// Load data when employee changes
const handleEmployeeChange = async () => {
  if (selectedEmployee.value) {
    await Promise.all([loadWorkHistory(), loadMonthlySummary()])
  }
}

// Format currency
const formatCurrency = (value) => {
  return new Intl.NumberFormat('en-CA', {
    style: 'currency',
    currency: 'CAD'
  }).format(value || 0)
}

// Format number with 2 decimals
const formatNumber = (value) => {
  return (value || 0).toFixed(2)
}
</script>

<template>
  <div class="payroll-dashboard p-6 bg-gradient-to-br from-slate-50 to-slate-100 min-h-screen">
    <!-- Header -->
    <div class="header mb-8">
      <h1 class="text-4xl font-bold text-slate-900 mb-6">Payroll Operations Dashboard</h1>
      
      <!-- Controls Row -->
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div>
          <label for="emp-select" class="block text-sm font-medium text-slate-700 mb-2">Employee</label>
          <select
            id="emp-select"
            v-model.number="selectedEmployee"
            @change="handleEmployeeChange"
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            :disabled="employeesLoading"
          >
            <option :value="null">Select Employee...</option>
            <option v-for="emp in employees" :key="emp.employee_id" :value="emp.employee_id">
              {{ emp.full_name }} ({{ emp.employee_id }})
            </option>
          </select>
        </div>
        
        <div>
          <label for="year-select" class="block text-sm font-medium text-slate-700 mb-2">Year</label>
          <select 
            id="year-select"
            v-model.number="selectedYear" 
            @change="updatePeriod" 
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option v-for="year in [2024, 2025, 2026]" :key="year" :value="year">{{ year }}</option>
          </select>
        </div>
        
        <div>
          <label for="month-select" class="block text-sm font-medium text-slate-700 mb-2">Month</label>
          <select 
            id="month-select"
            v-model.number="selectedMonth" 
            @change="updatePeriod" 
            class="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            <option v-for="m in 12" :key="m" :value="m">
              {{ new Date(2024, m - 1).toLocaleString('default', { month: 'long' }) }}
            </option>
          </select>
        </div>
        
        <div class="flex items-end">
          <button
            @click="() => { loadWorkHistory(); loadMonthlySummary() }"
            class="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
          >
            Refresh Data
          </button>
        </div>
      </div>
      
      <!-- Stats Cards -->
      <div v-if="selectedEmployee" class="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
        <div class="bg-white rounded-lg shadow p-4 border-l-4 border-green-500">
          <p class="text-xs text-slate-600 uppercase font-semibold">Current Month</p>
          <p class="text-2xl font-bold text-slate-900">{{ formatCurrency(totalMonthlyGross) }}</p>
          <p class="text-xs text-slate-500 mt-1">Gross Income</p>
        </div>
        
        <div class="bg-white rounded-lg shadow p-4 border-l-4 border-blue-500">
          <p class="text-xs text-slate-600 uppercase font-semibold">YTD Income</p>
          <p class="text-2xl font-bold text-slate-900">{{ formatCurrency(totalYTDGross) }}</p>
          <p class="text-xs text-slate-500 mt-1">Year to Date</p>
        </div>
        
        <div class="bg-white rounded-lg shadow p-4 border-l-4 border-orange-500">
          <p class="text-xs text-slate-600 uppercase font-semibold">YTD Deductions</p>
          <p class="text-2xl font-bold text-slate-900">{{ formatCurrency(totalYTDDeductions) }}</p>
          <p class="text-xs text-slate-500 mt-1">CPP, EI, Tax</p>
        </div>
        
        <div class="bg-white rounded-lg shadow p-4 border-l-4 border-purple-500">
          <p class="text-xs text-slate-600 uppercase font-semibold">YTD Net</p>
          <p class="text-2xl font-bold text-slate-900">{{ formatCurrency(totalYTDNet) }}</p>
          <p class="text-xs text-slate-500 mt-1">Take Home</p>
        </div>
        
        <div class="bg-white rounded-lg shadow p-4 border-l-4 border-indigo-500">
          <p class="text-xs text-slate-600 uppercase font-semibold">Work Items</p>
          <p class="text-2xl font-bold text-slate-900">{{ workHistory.length }}</p>
          <p class="text-xs text-slate-500 mt-1">This Year</p>
        </div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tabs mb-6 border-b border-slate-200">
      <div class="flex space-x-8">
        <button
          v-for="tab in ['overview', 'work-history', 'match-charters', 'month-end']"
          :key="tab"
          @click="activeTab = tab"
          :class="[
            'px-4 py-3 font-medium border-b-2 transition',
            activeTab === tab
              ? 'text-blue-600 border-blue-600'
              : 'text-slate-600 border-transparent hover:text-slate-900'
          ]"
        >
          <span v-if="tab === 'overview'">📊 Overview</span>
          <span v-else-if="tab === 'work-history'">📋 Work History</span>
          <span v-else-if="tab === 'match-charters'">🔗 Match Charters</span>
          <span v-else>✅ Month-End</span>
        </button>
      </div>
    </div>

    <!-- Tab Content -->
    <div class="tab-content">
      <!-- Overview Tab -->
      <div v-if="activeTab === 'overview'" class="space-y-6">
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <!-- Monthly Summary Cards -->
          <div v-for="month in monthlySummary" :key="month.period" class="bg-white rounded-lg shadow p-4 hover:shadow-md transition">
            <h3 class="font-semibold text-slate-900 mb-3">
              {{ new Date(month.period + '-01').toLocaleString('default', { month: 'long', year: 'numeric' }) }}
            </h3>
            <div class="space-y-2 text-sm">
              <div class="flex justify-between">
                <span class="text-slate-600">Gross</span>
                <span class="font-semibold text-slate-900">{{ formatCurrency(month.gross) }}</span>
              </div>
              <div class="flex justify-between">
                <span class="text-slate-600">Deductions</span>
                <span class="font-semibold text-orange-600">-{{ formatCurrency(month.deductions) }}</span>
              </div>
              <div class="border-t pt-2 flex justify-between">
                <span class="text-slate-700 font-semibold">Net Pay</span>
                <span class="font-bold text-green-600">{{ formatCurrency(month.net) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- YTD Summary -->
        <div class="bg-white rounded-lg shadow p-6">
          <h2 class="text-xl font-bold text-slate-900 mb-4">Year-to-Date Summary ({{ selectedYear }})</h2>
          <div class="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div>
              <p class="text-sm text-slate-600 mb-1">Total Gross Income</p>
              <p class="text-3xl font-bold text-slate-900">{{ formatCurrency(totalYTDGross) }}</p>
            </div>
            <div>
              <p class="text-sm text-slate-600 mb-1">Total Deductions</p>
              <p class="text-3xl font-bold text-orange-600">{{ formatCurrency(totalYTDDeductions) }}</p>
            </div>
            <div>
              <p class="text-sm text-slate-600 mb-1">Total Net Pay</p>
              <p class="text-3xl font-bold text-green-600">{{ formatCurrency(totalYTDNet) }}</p>
            </div>
            <div>
              <p class="text-sm text-slate-600 mb-1">Work Items</p>
              <p class="text-3xl font-bold text-blue-600">{{ workHistory.length }}</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Work History Tab -->
      <div v-if="activeTab === 'work-history'" class="bg-white rounded-lg shadow overflow-hidden">
        <div class="p-6 border-b border-slate-200">
          <h2 class="text-xl font-bold text-slate-900">Work History - {{ selectedYear }}</h2>
          <p class="text-sm text-slate-600 mt-1">All charters and jobs assigned to this employee</p>
        </div>

        <div v-if="workHistoryLoading" class="p-6 text-center text-slate-600">
          Loading work history...
        </div>
        <div v-else-if="workHistory.length === 0" class="p-6 text-center text-slate-600">
          No work history found for this employee in {{ selectedYear }}
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead class="bg-slate-50 border-b border-slate-200">
              <tr>
                <th class="px-6 py-3 text-left font-semibold text-slate-900">Date</th>
                <th class="px-6 py-3 text-left font-semibold text-slate-900">Charter #</th>
                <th class="px-6 py-3 text-right font-semibold text-slate-900">Hours</th>
                <th class="px-6 py-3 text-right font-semibold text-slate-900">Rate</th>
                <th class="px-6 py-3 text-right font-semibold text-slate-900">Amount</th>
                <th class="px-6 py-3 text-right font-semibold text-slate-900">Gratuity</th>
                <th class="px-6 py-3 text-left font-semibold text-slate-900">Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in workHistory" :key="item.id" class="border-b border-slate-200 hover:bg-slate-50">
                <td class="px-6 py-3 text-slate-900">{{ new Date(item.date).toLocaleDateString() }}</td>
                <td class="px-6 py-3 text-blue-600 font-semibold">#{{ item.charterId }}</td>
                <td class="px-6 py-3 text-right text-slate-900">{{ formatNumber(item.hours) }}</td>
                <td class="px-6 py-3 text-right text-slate-900">{{ formatCurrency(item.hourlyRate) }}</td>
                <td class="px-6 py-3 text-right font-semibold text-slate-900">{{ formatCurrency(item.gross) }}</td>
                <td class="px-6 py-3 text-right text-green-600 font-semibold">{{ formatCurrency(item.gratuity) }}</td>
                <td class="px-6 py-3">
                  <span :class="[
                    'px-3 py-1 rounded-full text-xs font-semibold',
                    item.status === 'completed' ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800'
                  ]">
                    {{ item.status }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Match Charters Tab -->
      <div v-if="activeTab === 'match-charters'" class="space-y-6">
        <div class="bg-white rounded-lg shadow p-6">
          <h2 class="text-xl font-bold text-slate-900 mb-4">Auto-Match Charters to Payroll</h2>
          <p class="text-slate-600 mb-6">Automatically link all charters from the selected period to this employee's payroll entry with one click.</p>
          
          <button
            @click="matchAllCharters"
            :disabled="!selectedEmployee || matchingCharters"
            :class="[
              'px-6 py-3 rounded-lg font-semibold transition',
              matchingCharters
                ? 'bg-slate-300 text-slate-600 cursor-not-allowed'
                : 'bg-green-600 text-white hover:bg-green-700'
            ]"
          >
            <span v-if="matchingCharters">🔄 Matching Charters...</span>
            <span v-else>✓ Match All Charters for {{ new Date(`${selectedYear}-${selectedMonth}`).toLocaleString('default', { month: 'long' }) }}</span>
          </button>
        </div>

        <!-- Matched Results -->
        <div v-if="workHistory.length > 0" class="bg-white rounded-lg shadow overflow-hidden">
          <div class="p-6 border-b border-slate-200">
            <h3 class="font-bold text-slate-900">Matched Items ({{ workHistory.length }})</h3>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full text-sm">
              <thead class="bg-slate-50 border-b border-slate-200">
                <tr>
                  <th class="px-6 py-3 text-left font-semibold text-slate-900">Charter</th>
                  <th class="px-6 py-3 text-right font-semibold text-slate-900">Hours</th>
                  <th class="px-6 py-3 text-right font-semibold text-slate-900">Amount</th>
                  <th class="px-6 py-3 text-right font-semibold text-slate-900">Status</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in workHistory" :key="item.id" class="border-b border-slate-200 hover:bg-slate-50">
                  <td class="px-6 py-3 text-blue-600 font-semibold">#{{ item.charterId }}</td>
                  <td class="px-6 py-3 text-right text-slate-900">{{ formatNumber(item.hours) }}</td>
                  <td class="px-6 py-3 text-right font-semibold text-slate-900">{{ formatCurrency(item.gross) }}</td>
                  <td class="px-6 py-3 text-right">
                    <span class="px-3 py-1 rounded-full text-xs font-semibold bg-green-100 text-green-800">✓ Matched</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Month-End Tab -->
      <div v-if="activeTab === 'month-end'" class="space-y-6">
        <div class="bg-white rounded-lg shadow p-6">
          <h2 class="text-xl font-bold text-slate-900 mb-4">Month-End Reconciliation</h2>
          
          <button
            @click="generateMonthEndBalance"
            :disabled="!selectedEmployee || generatingBalance"
            :class="[
              'px-6 py-3 rounded-lg font-semibold transition mb-6',
              generatingBalance
                ? 'bg-slate-300 text-slate-600 cursor-not-allowed'
                : 'bg-indigo-600 text-white hover:bg-indigo-700'
            ]"
          >
            <span v-if="generatingBalance">⏳ Generating Balance...</span>
            <span v-else>📊 Generate Month-End Balance for {{ new Date(`${selectedYear}-${selectedMonth}`).toLocaleString('default', { month: 'long' }) }}</span>
          </button>

          <!-- Reconciliation Results -->
          <div v-if="reconciliationStatus" class="space-y-6">
            <!-- Balance Summary -->
            <div :class="[
              'rounded-lg p-6',
              reconciliationStatus.balanced ? 'bg-green-50 border-2 border-green-500' : 'bg-orange-50 border-2 border-orange-500'
            ]">
              <div class="flex items-center mb-4">
                <span class="text-4xl mr-4">{{ reconciliationStatus.balanced ? '✓' : '⚠️' }}</span>
                <div>
                  <h3 class="text-xl font-bold" :class="reconciliationStatus.balanced ? 'text-green-900' : 'text-orange-900'">
                    {{ reconciliationStatus.balanced ? 'Month Balanced' : 'Discrepancies Detected' }}
                  </h3>
                  <p :class="reconciliationStatus.balanced ? 'text-green-700' : 'text-orange-700'">
                    {{ reconciliationStatus.balanced ? 'All totals match and reconcile' : `${reconciliationStatus.issues.length} issue(s) found` }}
                  </p>
                </div>
              </div>

              <!-- Issues List -->
              <div v-if="reconciliationStatus.issues.length > 0" class="space-y-2">
                <div v-for="(issue, idx) in reconciliationStatus.issues" :key="idx" class="text-sm font-semibold" :class="reconciliationStatus.balanced ? 'text-green-700' : 'text-orange-700'">
                  • {{ issue }}
                </div>
              </div>
            </div>

            <!-- Detailed Figures -->
            <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div class="bg-slate-50 rounded-lg p-4">
                <p class="text-xs text-slate-600 uppercase font-semibold">Charter Hours</p>
                <p class="text-2xl font-bold text-slate-900">{{ formatNumber(reconciliationStatus.charterHours) }}</p>
              </div>
              <div class="bg-slate-50 rounded-lg p-4">
                <p class="text-xs text-slate-600 uppercase font-semibold">Charter Income</p>
                <p class="text-2xl font-bold text-slate-900">{{ formatCurrency(reconciliationStatus.charterIncome) }}</p>
              </div>
              <div class="bg-slate-50 rounded-lg p-4">
                <p class="text-xs text-slate-600 uppercase font-semibold">Bonus</p>
                <p class="text-2xl font-bold text-slate-900">{{ formatCurrency(reconciliationStatus.bonus) }}</p>
              </div>
              <div class="bg-slate-50 rounded-lg p-4">
                <p class="text-xs text-slate-600 uppercase font-semibold">Gratuity</p>
                <p class="text-2xl font-bold text-slate-900">{{ formatCurrency(reconciliationStatus.gratuity) }}</p>
              </div>
              <div class="bg-green-50 rounded-lg p-4 border-2 border-green-500">
                <p class="text-xs text-slate-600 uppercase font-semibold">Gross Income</p>
                <p class="text-2xl font-bold text-green-700">{{ formatCurrency(reconciliationStatus.totalGross) }}</p>
              </div>
              <div class="bg-orange-50 rounded-lg p-4 border-2 border-orange-500">
                <p class="text-xs text-slate-600 uppercase font-semibold">Total Deductions</p>
                <p class="text-2xl font-bold text-orange-700">-{{ formatCurrency(reconciliationStatus.totalDeductions) }}</p>
              </div>
              <div class="bg-purple-50 rounded-lg p-4 col-span-2 md:col-span-1 border-2 border-purple-500">
                <p class="text-xs text-slate-600 uppercase font-semibold">Net Pay</p>
                <p class="text-2xl font-bold text-purple-700">{{ formatCurrency(reconciliationStatus.netPay) }}</p>
              </div>
            </div>

            <!-- Deduction Breakdown -->
            <div class="bg-slate-50 rounded-lg p-6">
              <h4 class="font-bold text-slate-900 mb-4">Deduction Breakdown</h4>
              <div class="grid grid-cols-3 gap-4 text-sm">
                <div>
                  <p class="text-slate-600 mb-1">CPP Contributions</p>
                  <p class="text-xl font-bold text-slate-900">{{ formatCurrency(reconciliationStatus.cpp) }}</p>
                </div>
                <div>
                  <p class="text-slate-600 mb-1">EI Premiums</p>
                  <p class="text-xl font-bold text-slate-900">{{ formatCurrency(reconciliationStatus.ei) }}</p>
                </div>
                <div>
                  <p class="text-slate-600 mb-1">Income Tax</p>
                  <p class="text-xl font-bold text-slate-900">{{ formatCurrency(reconciliationStatus.incomeTax) }}</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Printout Controls -->
        <div class="bg-white rounded-lg shadow p-6">
          <h3 class="text-lg font-bold text-slate-900 mb-4">Payroll Printouts</h3>
          <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
            <button
              @click="generatePayStub"
              class="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition font-semibold"
            >
              📄 Generate Pay Stub
            </button>
            <button
              disabled
              class="px-4 py-3 bg-slate-300 text-slate-600 rounded-lg font-semibold cursor-not-allowed"
            >
              📋 Payroll Register
            </button>
            <button
              disabled
              class="px-4 py-3 bg-slate-300 text-slate-600 rounded-lg font-semibold cursor-not-allowed"
            >
              📑 T4 Slip
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.payroll-dashboard {
  font-family: system-ui, -apple-system, sans-serif;
}
</style>
