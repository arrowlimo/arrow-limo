<template>
  <div class="t2-form-container">
    <!-- Header -->
    <div class="form-header">
      <h2>T2 CORPORATION INCOME TAX RETURN - HISTORICAL DATA ENTRY</h2>
      <div class="year-selection">
        <div class="control-group">
          <label>Tax Year:</label>
          <select v-model="selectedYear" @change="loadReturnData" class="form-control">
            <option v-for="year in taxYears" :key="year" :value="year">{{ year }}</option>
          </select>
        </div>
        
        <div class="control-group">
          <label>Fiscal Year End:</label>
          <input v-model="fiscalYearEnd" type="date" class="form-control" />
        </div>
        
        <div class="control-group">
          <label>Business Number:</label>
          <input v-model="businessNumber" type="text" class="form-control" placeholder="123456789 RC 0001" />
        </div>
        
        <div class="button-group">
          <button @click="createNewReturn" class="btn btn-secondary">📄 New Return</button>
          <button @click="saveAllData" class="btn btn-primary">💾 Save All</button>
        </div>
      </div>
    </div>

    <!-- Status Bar -->
    <div v-if="statusMessage" :class="['status-message', statusType]">
      {{ statusMessage }}
    </div>

    <!-- Tabs -->
    <div class="tabs-container">
      <div class="tab-headers">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          :class="['tab-btn', { active: activeTab === tab.id }]"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- Tab Content -->
      <div class="tab-content">
        
        <!-- Schedule 125 - Income Statement -->
        <div v-show="activeTab === 'sch125'" class="tab-pane">
          <div class="info-box">
            📋 Schedule 125: Income Statement<br>
            Enter revenue and expenses from your paper T2 Schedule 125
          </div>

          <div class="section-grid">
            <!-- Revenue Section -->
            <div class="section">
              <h3>Revenue</h3>
              <div class="form-row">
                <label>8000 - Charter Revenue:</label>
                <input v-model.number="schedule125.charterRevenue" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>8299 - Other Revenue:</label>
                <input v-model.number="schedule125.otherRevenue" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row total-row">
                <label><strong>Total Revenue:</strong></label>
                <input :value="totals.revenue.toFixed(2)" type="text" class="currency-input readonly" readonly />
              </div>
            </div>

            <!-- Expenses Section -->
            <div class="section">
              <h3>Expenses</h3>
              <div class="form-row">
                <label>8518 - Cost of Sales:</label>
                <input v-model.number="schedule125.costOfSales" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>8513 - Salaries, Wages, Benefits:</label>
                <input v-model.number="schedule125.salaries" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>8523 - Employee Benefits:</label>
                <input v-model.number="schedule125.benefits" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>8690 - Rent:</label>
                <input v-model.number="schedule125.rent" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>8690 - Repairs & Maintenance:</label>
                <input v-model.number="schedule125.repairs" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>8590 - Bad Debts:</label>
                <input v-model.number="schedule125.badDebts" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>8711 - Interest & Bank Charges:</label>
                <input v-model.number="schedule125.interest" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>9270 - Insurance:</label>
                <input v-model.number="schedule125.insurance" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>8810 - Office Expenses:</label>
                <input v-model.number="schedule125.office" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>8860 - Professional Fees:</label>
                <input v-model.number="schedule125.professionalFees" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>9180 - Property Taxes:</label>
                <input v-model.number="schedule125.propertyTax" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>9200 - Travel:</label>
                <input v-model.number="schedule125.travel" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>9281 - Vehicle Expenses:</label>
                <input v-model.number="schedule125.vehicle" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row">
                <label>9923 - Other Expenses:</label>
                <input v-model.number="schedule125.otherExpenses" type="number" step="0.01" class="currency-input" @input="calculateTotals" />
              </div>
              <div class="form-row total-row">
                <label><strong>Total Expenses:</strong></label>
                <input :value="totals.expenses.toFixed(2)" type="text" class="currency-input readonly" readonly />
              </div>
            </div>

            <!-- Net Income -->
            <div class="section net-income">
              <h3>Net Income</h3>
              <div class="form-row total-row highlight">
                <label><strong>Net Income Before Tax:</strong></label>
                <input :value="totals.netIncome.toFixed(2)" type="text" class="currency-input readonly" readonly />
              </div>
            </div>
          </div>

          <button @click="saveSchedule125" class="btn btn-primary">💾 Save Schedule 125</button>
        </div>

        <!-- Schedule 100 - Balance Sheet -->
        <div v-show="activeTab === 'sch100'" class="tab-pane">
          <div class="info-box">
            📑 Schedule 100: Balance Sheet<br>
            Enter beginning and ending balances from your paper T2
          </div>

          <div class="section-grid">
            <!-- Assets -->
            <div class="section">
              <h3>Assets</h3>
              <div class="balance-row">
                <label>Cash:</label>
                <div class="balance-inputs">
                  <input v-model.number="schedule100.cashBegin" type="number" step="0.01" class="currency-input" placeholder="Beginning" />
                  <input v-model.number="schedule100.cashEnd" type="number" step="0.01" class="currency-input" placeholder="Ending" />
                </div>
              </div>
              <div class="balance-row">
                <label>Accounts Receivable:</label>
                <div class="balance-inputs">
                  <input v-model.number="schedule100.arBegin" type="number" step="0.01" class="currency-input" placeholder="Beginning" />
                  <input v-model.number="schedule100.arEnd" type="number" step="0.01" class="currency-input" placeholder="Ending" />
                </div>
              </div>
              <div class="balance-row">
                <label>Inventory:</label>
                <div class="balance-inputs">
                  <input v-model.number="schedule100.inventoryBegin" type="number" step="0.01" class="currency-input" placeholder="Beginning" />
                  <input v-model.number="schedule100.inventoryEnd" type="number" step="0.01" class="currency-input" placeholder="Ending" />
                </div>
              </div>
              <div class="balance-row">
                <label>Property, Plant & Equipment:</label>
                <div class="balance-inputs">
                  <input v-model.number="schedule100.ppeBegin" type="number" step="0.01" class="currency-input" placeholder="Beginning" />
                  <input v-model.number="schedule100.ppeEnd" type="number" step="0.01" class="currency-input" placeholder="Ending" />
                </div>
              </div>
            </div>

            <!-- Liabilities -->
            <div class="section">
              <h3>Liabilities</h3>
              <div class="balance-row">
                <label>Accounts Payable:</label>
                <div class="balance-inputs">
                  <input v-model.number="schedule100.apBegin" type="number" step="0.01" class="currency-input" placeholder="Beginning" />
                  <input v-model.number="schedule100.apEnd" type="number" step="0.01" class="currency-input" placeholder="Ending" />
                </div>
              </div>
              <div class="balance-row">
                <label>Loans/Debt:</label>
                <div class="balance-inputs">
                  <input v-model.number="schedule100.loansBegin" type="number" step="0.01" class="currency-input" placeholder="Beginning" />
                  <input v-model.number="schedule100.loansEnd" type="number" step="0.01" class="currency-input" placeholder="Ending" />
                </div>
              </div>
            </div>

            <!-- Equity -->
            <div class="section">
              <h3>Equity</h3>
              <div class="balance-row">
                <label>Retained Earnings:</label>
                <div class="balance-inputs">
                  <input v-model.number="schedule100.retainedEarningsBegin" type="number" step="0.01" class="currency-input" placeholder="Beginning" />
                  <input v-model.number="schedule100.retainedEarningsEnd" type="number" step="0.01" class="currency-input" placeholder="Ending" />
                </div>
              </div>
            </div>
          </div>

          <button @click="saveSchedule100" class="btn btn-primary">💾 Save Schedule 100</button>
        </div>

        <!-- Tax Calculation -->
        <div v-show="activeTab === 'tax'" class="tab-pane">
          <div class="info-box">
            🧮 Tax Calculation<br>
            Enter tax calculation from Schedule 2 or auto-calculate from rates
          </div>

          <div class="section-grid">
            <div class="section">
              <h3>Taxable Income</h3>
              <div class="form-row">
                <label>Net Income (from Schedule 1):</label>
                <input :value="totals.netIncome.toFixed(2)" type="text" class="currency-input readonly" readonly />
              </div>
              <div class="form-row">
                <label>Taxable Income:</label>
                <input v-model.number="taxCalc.taxableIncome" type="number" step="0.01" class="currency-input" @input="calculateTax" />
              </div>
              <div class="form-row">
                <label>Small Business Income (≤ $500K):</label>
                <input v-model.number="taxCalc.smallBusinessIncome" type="number" step="0.01" class="currency-input" @input="calculateTax" />
              </div>
              <div class="form-row">
                <label>General Income:</label>
                <input :value="taxCalc.generalIncome.toFixed(2)" type="text" class="currency-input readonly" readonly />
              </div>
            </div>

            <div class="section" v-if="taxRates">
              <h3>Tax Rates ({{ selectedYear }})</h3>
              <div class="tax-rates-display">
                <p><strong>Federal SBD:</strong> {{ (taxRates.federal_small_business_rate * 100).toFixed(2) }}%</p>
                <p><strong>Federal General:</strong> {{ (taxRates.federal_general_rate * 100).toFixed(2) }}%</p>
                <p><strong>Alberta SBD:</strong> {{ (taxRates.alberta_small_business_rate * 100).toFixed(2) }}%</p>
                <p><strong>Alberta General:</strong> {{ (taxRates.alberta_general_rate * 100).toFixed(2) }}%</p>
                <p><strong>SBD Limit:</strong> ${{ taxRates.small_business_limit.toLocaleString() }}</p>
              </div>
            </div>

            <div class="section">
              <h3>Calculated Tax</h3>
              <div class="form-row">
                <label>Federal Tax (SBD):</label>
                <input :value="taxCalc.federalTaxSBD.toFixed(2)" type="text" class="currency-input readonly" readonly />
              </div>
              <div class="form-row">
                <label>Federal Tax (General):</label>
                <input :value="taxCalc.federalTaxGeneral.toFixed(2)" type="text" class="currency-input readonly" readonly />
              </div>
              <div class="form-row total-row">
                <label><strong>Total Federal Tax:</strong></label>
                <input :value="taxCalc.totalFederal.toFixed(2)" type="text" class="currency-input readonly" readonly />
              </div>
              
              <div class="form-row">
                <label>Provincial Tax (SBD):</label>
                <input :value="taxCalc.provincialTaxSBD.toFixed(2)" type="text" class="currency-input readonly" readonly />
              </div>
              <div class="form-row">
                <label>Provincial Tax (General):</label>
                <input :value="taxCalc.provincialTaxGeneral.toFixed(2)" type="text" class="currency-input readonly" readonly />
              </div>
              <div class="form-row total-row">
                <label><strong>Total Provincial Tax:</strong></label>
                <input :value="taxCalc.totalProvincial.toFixed(2)" type="text" class="currency-input readonly" readonly />
              </div>
              
              <div class="form-row total-row highlight">
                <label><strong>TOTAL TAX OWING:</strong></label>
                <input :value="taxCalc.totalTax.toFixed(2)" type="text" class="currency-input readonly" readonly />
              </div>
            </div>
          </div>

          <button @click="saveTaxCalculation" class="btn btn-primary">💾 Save Tax Calculation</button>
        </div>

        <!-- Summary & Filing -->
        <div v-show="activeTab === 'summary'" class="tab-pane">
          <div class="info-box">
            📊 Summary & Filing Information<br>
            Review totals and update filing status
          </div>

          <div class="section-grid">
            <div class="section">
              <h3>Financial Summary</h3>
              <div class="summary-row">
                <label>Total Revenue:</label>
                <span class="summary-value">${{ totals.revenue.toFixed(2) }}</span>
              </div>
              <div class="summary-row">
                <label>Total Expenses:</label>
                <span class="summary-value">${{ totals.expenses.toFixed(2) }}</span>
              </div>
              <div class="summary-row">
                <label>Net Income:</label>
                <span class="summary-value">${{ totals.netIncome.toFixed(2) }}</span>
              </div>
              <div class="summary-row">
                <label>Taxable Income:</label>
                <span class="summary-value">${{ taxCalc.taxableIncome.toFixed(2) }}</span>
              </div>
              <div class="summary-row highlight">
                <label><strong>Total Tax Owing:</strong></label>
                <span class="summary-value"><strong>${{ taxCalc.totalTax.toFixed(2) }}</strong></span>
              </div>
            </div>

            <div class="section">
              <h3>Filing Information</h3>
              <div class="form-row">
                <label>Status:</label>
                <select v-model="filingInfo.status" class="form-control">
                  <option value="draft">Draft</option>
                  <option value="calculated">Calculated</option>
                  <option value="filed">Filed</option>
                  <option value="amended">Amended</option>
                </select>
              </div>
              <div class="form-row">
                <label>Filed Date:</label>
                <input v-model="filingInfo.filedDate" type="date" class="form-control" />
              </div>
              <div class="form-row">
                <label>CRA Confirmation #:</label>
                <input v-model="filingInfo.confirmationNumber" type="text" class="form-control" placeholder="Enter confirmation number" />
              </div>
            </div>

            <div class="section">
              <h3>Notes</h3>
              <textarea v-model="filingInfo.notes" class="form-textarea" rows="6" 
                placeholder="Add notes about this return..."></textarea>
            </div>
          </div>

          <div class="button-group">
            <button @click="updateFilingInfo" class="btn btn-success">✓ Mark as Filed</button>
            <button @click="refreshSummary" class="btn btn-secondary">🔄 Refresh Summary</button>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'

// ============================================================================
// STATE
// ============================================================================

const selectedYear = ref(new Date().getFullYear() - 1)
const currentReturnId = ref(null)
const fiscalYearEnd = ref('')
const businessNumber = ref('')
const activeTab = ref('sch125')
const statusMessage = ref('')
const statusType = ref('info')
const taxRates = ref(null)

const taxYears = computed(() => {
  const currentYear = new Date().getFullYear()
  const years = []
  for (let year = 2007; year <= currentYear; year++) {
    years.push(year)
  }
  return years.reverse()
})

const tabs = [
  { id: 'sch125', label: 'Schedule 125 - Income Statement' },
  { id: 'sch100', label: 'Schedule 100 - Balance Sheet' },
  { id: 'tax', label: 'Tax Calculation' },
  { id: 'summary', label: 'Summary & Filing' }
]

// Schedule 125 data
const schedule125 = reactive({
  charterRevenue: 0,
  otherRevenue: 0,
  costOfSales: 0,
  salaries: 0,
  benefits: 0,
  rent: 0,
  repairs: 0,
  badDebts: 0,
  interest: 0,
  insurance: 0,
  office: 0,
  professionalFees: 0,
  propertyTax: 0,
  travel: 0,
  vehicle: 0,
  otherExpenses: 0
})

// Schedule 100 data
const schedule100 = reactive({
  cashBegin: 0,
  cashEnd: 0,
  arBegin: 0,
  arEnd: 0,
  inventoryBegin: 0,
  inventoryEnd: 0,
  ppeBegin: 0,
  ppeEnd: 0,
  apBegin: 0,
  apEnd: 0,
  loansBegin: 0,
  loansEnd: 0,
  retainedEarningsBegin: 0,
  retainedEarningsEnd: 0
})

// Tax calculation
const taxCalc = reactive({
  taxableIncome: 0,
  smallBusinessIncome: 0,
  generalIncome: 0,
  federalTaxSBD: 0,
  federalTaxGeneral: 0,
  totalFederal: 0,
  provincialTaxSBD: 0,
  provincialTaxGeneral: 0,
  totalProvincial: 0,
  totalTax: 0
})

// Filing information
const filingInfo = reactive({
  status: 'draft',
  filedDate: '',
  confirmationNumber: '',
  notes: ''
})

// Totals
const totals = computed(() => {
  const revenue = schedule125.charterRevenue + schedule125.otherRevenue
  const expenses = 
    schedule125.costOfSales +
    schedule125.salaries +
    schedule125.benefits +
    schedule125.rent +
    schedule125.repairs +
    schedule125.badDebts +
    schedule125.interest +
    schedule125.insurance +
    schedule125.office +
    schedule125.professionalFees +
    schedule125.propertyTax +
    schedule125.travel +
    schedule125.vehicle +
    schedule125.otherExpenses
  
  return {
    revenue,
    expenses,
    netIncome: revenue - expenses
  }
})

// ============================================================================
// LIFECYCLE
// ============================================================================

onMounted(async () => {
  await loadTaxRates()
  await loadReturnData()
})

// ============================================================================
// API CALLS
// ============================================================================

async function loadTaxRates() {
  try {
    const res = await fetch(`/api/t2/tax-rates/${selectedYear.value}`)
    if (res.ok) {
      taxRates.value = await res.json()
    }
  } catch (error) {
    showStatus(`Error loading tax rates: ${error.message}`, 'error')
  }
}

async function loadReturnData() {
  try {
    const res = await fetch(`/api/t2/returns/${selectedYear.value}`)
    if (res.ok) {
      const data = await res.json()
      if (data) {
        currentReturnId.value = data.return_id
        fiscalYearEnd.value = data.fiscal_year_end
        businessNumber.value = data.business_number || ''
        filingInfo.status = data.status || 'draft'
        
        // Load schedules
        await loadSchedule125()
        await loadSchedule100()
        
        // Set tax calculation values
        if (data.taxable_income) {
          taxCalc.taxableIncome = data.taxable_income
          calculateTax()
        }
        
        showStatus(`Loaded T2 return for ${selectedYear.value}`, 'success')
      } else {
        currentReturnId.value = null
        showStatus(`No T2 return exists for ${selectedYear.value}. Click "New Return" to create one.`, 'info')
      }
    }
    
    await loadTaxRates()
  } catch (error) {
    showStatus(`Error loading return: ${error.message}`, 'error')
  }
}

async function createNewReturn() {
  try {
    const today = new Date()
    const defaultFiscalYearEnd = fiscalYearEnd.value || `${selectedYear.value}-12-31`
    
    const res = await fetch('/api/t2/returns', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        tax_year: selectedYear.value,
        corporation_name: 'Arrow Limousine Ltd.',
        business_number: businessNumber.value || null,
        fiscal_year_end: defaultFiscalYearEnd
      })
    })
    
    if (res.ok) {
      const data = await res.json()
      currentReturnId.value = data.return_id
      fiscalYearEnd.value = data.fiscal_year_end
      showStatus(`Created new T2 return for ${selectedYear.value}`, 'success')
    } else {
      const error = await res.json()
      showStatus(`Error: ${error.detail}`, 'error')
    }
  } catch (error) {
    showStatus(`Error creating return: ${error.message}`, 'error')
  }
}

async function loadSchedule125() {
  if (!currentReturnId.value) return
  
  try {
    const res = await fetch(`/api/t2/schedule125/${currentReturnId.value}`)
    if (res.ok) {
      const data = await res.json()
      Object.assign(schedule125, {
        charterRevenue: data.charter_revenue || 0,
        otherRevenue: data.other_revenue || 0,
        costOfSales: data.cost_of_sales || 0,
        salaries: data.salaries || 0,
        benefits: data.benefits || 0,
        rent: data.rent || 0,
        repairs: data.repairs || 0,
        badDebts: data.bad_debts || 0,
        interest: data.interest || 0,
        insurance: data.insurance || 0,
        office: data.office || 0,
        professionalFees: data.professional_fees || 0,
        propertyTax: data.property_tax || 0,
        travel: data.travel || 0,
        vehicle: data.vehicle || 0,
        otherExpenses: data.other_expenses || 0
      })
    }
  } catch (error) {
    console.error('Error loading Schedule 125:', error)
  }
}

async function loadSchedule100() {
  if (!currentReturnId.value) return
  
  try {
    const res = await fetch(`/api/t2/schedule100/${currentReturnId.value}`)
    if (res.ok) {
      const data = await res.json()
      Object.assign(schedule100, {
        cashBegin: data.cash_begin || 0,
        cashEnd: data.cash_end || 0,
        arBegin: data.ar_begin || 0,
        arEnd: data.ar_end || 0,
        inventoryBegin: data.inventory_begin || 0,
        inventoryEnd: data.inventory_end || 0,
        ppeBegin: data.ppe_begin || 0,
        ppeEnd: data.ppe_end || 0,
        apBegin: data.ap_begin || 0,
        apEnd: data.ap_end || 0,
        loansBegin: data.loans_begin || 0,
        loansEnd: data.loans_end || 0,
        retainedEarningsBegin: data.retained_earnings_begin || 0,
        retainedEarningsEnd: data.retained_earnings_end || 0
      })
    }
  } catch (error) {
    console.error('Error loading Schedule 100:', error)
  }
}

async function saveSchedule125() {
  if (!currentReturnId.value) {
    showStatus('Please create or load a return first', 'error')
    return
  }
  
  try {
    const res = await fetch('/api/t2/schedule125', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        return_id: currentReturnId.value,
        charter_revenue: schedule125.charterRevenue,
        other_revenue: schedule125.otherRevenue,
        cost_of_sales: schedule125.costOfSales,
        salaries: schedule125.salaries,
        benefits: schedule125.benefits,
        rent: schedule125.rent,
        repairs: schedule125.repairs,
        bad_debts: schedule125.badDebts,
        interest: schedule125.interest,
        insurance: schedule125.insurance,
        office: schedule125.office,
        professional_fees: schedule125.professionalFees,
        property_tax: schedule125.propertyTax,
        travel: schedule125.travel,
        vehicle: schedule125.vehicle,
        other_expenses: schedule125.otherExpenses
      })
    })
    
    if (res.ok) {
      showStatus('Schedule 125 saved successfully', 'success')
      calculateTotals()
    } else {
      showStatus('Error saving Schedule 125', 'error')
    }
  } catch (error) {
    showStatus(`Error: ${error.message}`, 'error')
  }
}

async function saveSchedule100() {
  if (!currentReturnId.value) {
    showStatus('Please create or load a return first', 'error')
    return
  }
  
  try {
    const res = await fetch('/api/t2/schedule100', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        return_id: currentReturnId.value,
        cash_begin: schedule100.cashBegin,
        cash_end: schedule100.cashEnd,
        ar_begin: schedule100.arBegin,
        ar_end: schedule100.arEnd,
        inventory_begin: schedule100.inventoryBegin,
        inventory_end: schedule100.inventoryEnd,
        ppe_begin: schedule100.ppeBegin,
        ppe_end: schedule100.ppeEnd,
        ap_begin: schedule100.apBegin,
        ap_end: schedule100.apEnd,
        loans_begin: schedule100.loansBegin,
        loans_end: schedule100.loansEnd,
        retained_earnings_begin: schedule100.retainedEarningsBegin,
        retained_earnings_end: schedule100.retainedEarningsEnd
      })
    })
    
    if (res.ok) {
      showStatus('Schedule 100 saved successfully', 'success')
    } else {
      showStatus('Error saving Schedule 100', 'error')
    }
  } catch (error) {
    showStatus(`Error: ${error.message}`, 'error')
  }
}

async function saveTaxCalculation() {
  if (!currentReturnId.value) {
    showStatus('Please create or load a return first', 'error')
    return
  }
  
  try {
    const res = await fetch('/api/t2/calculate-tax', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        return_id: currentReturnId.value,
        taxable_income: taxCalc.taxableIncome,
        small_business_income: taxCalc.smallBusinessIncome
      })
    })
    
    if (res.ok) {
      const data = await res.json()
      taxCalc.federalTaxSBD = data.federal_tax_sbd
      taxCalc.federalTaxGeneral = data.federal_tax_general
      taxCalc.totalFederal = data.total_federal
      taxCalc.provincialTaxSBD = data.provincial_tax_sbd
      taxCalc.provincialTaxGeneral = data.provincial_tax_general
      taxCalc.totalProvincial = data.total_provincial
      taxCalc.totalTax = data.total_tax
      showStatus('Tax calculation saved successfully', 'success')
    } else {
      showStatus('Error saving tax calculation', 'error')
    }
  } catch (error) {
    showStatus(`Error: ${error.message}`, 'error')
  }
}

async function updateFilingInfo() {
  if (!currentReturnId.value) {
    showStatus('Please create or load a return first', 'error')
    return
  }
  
  try {
    const res = await fetch(`/api/t2/returns/${currentReturnId.value}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        status: filingInfo.status,
        filed_date: filingInfo.filedDate || null
      })
    })
    
    if (res.ok) {
      showStatus('Filing information updated', 'success')
    } else {
      showStatus('Error updating filing info', 'error')
    }
  } catch (error) {
    showStatus(`Error: ${error.message}`, 'error')
  }
}

async function saveAllData() {
  await saveSchedule125()
  await saveSchedule100()
  await saveTaxCalculation()
  showStatus('All data saved successfully', 'success')
}

// ============================================================================
// CALCULATIONS
// ============================================================================

function calculateTotals() {
  // Totals are computed automatically via computed property
}

function calculateTax() {
  if (!taxRates.value) return
  
  const sbd = Math.min(taxCalc.smallBusinessIncome, taxRates.value.small_business_limit)
  const general = Math.max(0, taxCalc.taxableIncome - sbd)
  
  taxCalc.generalIncome = general
  taxCalc.federalTaxSBD = sbd * taxRates.value.federal_small_business_rate
  taxCalc.federalTaxGeneral = general * taxRates.value.federal_general_rate
  taxCalc.totalFederal = taxCalc.federalTaxSBD + taxCalc.federalTaxGeneral
  
  taxCalc.provincialTaxSBD = sbd * taxRates.value.alberta_small_business_rate
  taxCalc.provincialTaxGeneral = general * taxRates.value.alberta_general_rate
  taxCalc.totalProvincial = taxCalc.provincialTaxSBD + taxCalc.provincialTaxGeneral
  
  taxCalc.totalTax = taxCalc.totalFederal + taxCalc.totalProvincial
}

function refreshSummary() {
  loadReturnData()
  showStatus('Summary refreshed', 'info')
}

// ============================================================================
// UTILITIES
// ============================================================================

function showStatus(message, type = 'info') {
  statusMessage.value = message
  statusType.value = type
  setTimeout(() => {
    statusMessage.value = ''
  }, 5000)
}
</script>

<style scoped>
.t2-form-container {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
  font-family: Arial, sans-serif;
}

.form-header {
  background: linear-gradient(135deg, #1e40af 0%, #3b82f6 100%);
  color: white;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
}

.form-header h2 {
  margin: 0 0 15px 0;
  font-size: 20px;
}

.year-selection {
  display: flex;
  gap: 15px;
  align-items: center;
  flex-wrap: wrap;
}

.control-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.control-group label {
  font-weight: 600;
  font-size: 14px;
}

.form-control {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 14px;
}

.button-group {
  display: flex;
  gap: 10px;
  margin-left: auto;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  font-size: 14px;
  transition: all 0.2s;
}

.btn-primary {
  background: #10b981;
  color: white;
}

.btn-primary:hover {
  background: #059669;
}

.btn-secondary {
  background: #6b7280;
  color: white;
}

.btn-secondary:hover {
  background: #4b5563;
}

.btn-success {
  background: #10b981;
  color: white;
}

.btn-success:hover {
  background: #059669;
}

.status-message {
  padding: 12px 20px;
  border-radius: 4px;
  margin-bottom: 20px;
  font-weight: 500;
}

.status-message.success {
  background: #d1fae5;
  color: #065f46;
  border: 1px solid #10b981;
}

.status-message.error {
  background: #fee2e2;
  color: #991b1b;
  border: 1px solid #ef4444;
}

.status-message.info {
  background: #dbeafe;
  color: #1e40af;
  border: 1px solid #3b82f6;
}

.tabs-container {
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.tab-headers {
  display: flex;
  border-bottom: 2px solid #e5e7eb;
  background: #f9fafb;
  border-radius: 8px 8px 0 0;
}

.tab-btn {
  flex: 1;
  padding: 15px 20px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-weight: 600;
  color: #6b7280;
  transition: all 0.2s;
  border-bottom: 3px solid transparent;
}

.tab-btn:hover {
  background: #f3f4f6;
  color: #1f2937;
}

.tab-btn.active {
  color: #1e40af;
  border-bottom-color: #1e40af;
  background: white;
}

.tab-content {
  padding: 30px;
}

.info-box {
  background: #dbeafe;
  padding: 15px;
  border-radius: 6px;
  margin-bottom: 25px;
  border-left: 4px solid #3b82f6;
  line-height: 1.6;
}

.section-grid {
  display: grid;
  gap: 30px;
}

.section {
  background: #f9fafb;
  padding: 20px;
  border-radius: 6px;
  border: 1px solid #e5e7eb;
}

.section h3 {
  margin: 0 0 15px 0;
  color: #1f2937;
  font-size: 16px;
  border-bottom: 2px solid #3b82f6;
  padding-bottom: 8px;
}

.form-row {
  display: grid;
  grid-template-columns: 250px 1fr;
  gap: 15px;
  align-items: center;
  margin-bottom: 12px;
}

.form-row label {
  font-weight: 500;
  color: #374151;
  font-size: 14px;
}

.currency-input {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-size: 14px;
  text-align: right;
  font-family: monospace;
}

.currency-input.readonly {
  background: #e5e7eb;
  border-color: #9ca3af;
  font-weight: 600;
}

.total-row {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 2px solid #d1d5db;
}

.total-row.highlight {
  background: #fef3c7;
  padding: 12px;
  border-radius: 4px;
  border: 2px solid #f59e0b;
}

.balance-row {
  margin-bottom: 15px;
}

.balance-row label {
  display: block;
  font-weight: 500;
  margin-bottom: 8px;
  color: #374151;
}

.balance-inputs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.tax-rates-display {
  background: white;
  padding: 15px;
  border-radius: 4px;
  border: 1px solid #d1d5db;
}

.tax-rates-display p {
  margin: 8px 0;
  font-size: 14px;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #e5e7eb;
}

.summary-row label {
  font-weight: 500;
  color: #374151;
}

.summary-value {
  font-weight: 600;
  font-family: monospace;
  color: #1f2937;
}

.summary-row.highlight {
  background: #fef3c7;
  padding: 12px;
  margin-top: 15px;
  border-radius: 4px;
  border: 2px solid #f59e0b;
  font-size: 16px;
}

.form-textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #d1d5db;
  border-radius: 4px;
  font-family: Arial, sans-serif;
  font-size: 14px;
  resize: vertical;
}

@media (max-width: 768px) {
  .year-selection {
    flex-direction: column;
    align-items: stretch;
  }
  
  .form-row {
    grid-template-columns: 1fr;
  }
  
  .tab-headers {
    flex-direction: column;
  }
}
</style>
