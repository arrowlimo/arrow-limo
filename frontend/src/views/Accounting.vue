<template>
  <div>
    <h1>Accounting Dashboard</h1>
    
    <!-- Financial Overview Stats -->
    <div class="accounting-stats">
      <div class="stat-card revenue">
        <div class="stat-value">${{ stats.monthlyRevenue }}</div>
        <div class="stat-label">Monthly Revenue</div>
      </div>
      <div class="stat-card expenses">
        <div class="stat-value">${{ stats.monthlyExpenses }}</div>
        <div class="stat-label">Monthly Expenses</div>
      </div>
      <div class="stat-card profit">
        <div class="stat-value">${{ stats.monthlyProfit }}</div>
        <div class="stat-label">Monthly Profit</div>
      </div>
      <div class="stat-card outstanding">
        <div class="stat-value">${{ stats.outstandingReceivables }}</div>
        <div class="stat-label">Outstanding A/R</div>
      </div>
      <div class="stat-card gst">
        <div class="stat-value">${{ stats.gstOwed }}</div>
        <div class="stat-label">GST Owed</div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="quick-actions">
      <button @click="activeTab = 'invoices'" :class="{ active: activeTab === 'invoices' }" class="action-btn">
        📄 Invoices
      </button>
      <button @click="activeTab = 'receipts'" :class="{ active: activeTab === 'receipts' }" class="action-btn">
        🧾 Receipts & Expenses
      </button>
      <button @click="activeTab = 'gst'" :class="{ active: activeTab === 'gst' }" class="action-btn">
        💰 GST Management
      </button>
      <button @click="activeTab = 'reports'" :class="{ active: activeTab === 'reports' }" class="action-btn">
        📊 Financial Reports
      </button>
    </div>

    <!-- Invoices Tab -->
    <div v-if="activeTab === 'invoices'" class="accounting-section">
      <h2>Invoice Management</h2>
      <div class="invoice-filters">
        <input v-model="invoiceSearch" placeholder="Search invoices..." />
        <select v-model="invoiceStatusFilter">
          <option value="">All Status</option>
          <option value="paid">Paid</option>
          <option value="unpaid">Unpaid</option>
          <option value="overdue">Overdue</option>
        </select>
        <input v-model="invoiceDateFilter" type="month" />
      </div>
      
      <table class="accounting-table">
        <thead>
          <tr>
            <th>Invoice #</th>
            <th>Client</th>
            <th>Date</th>
            <th>Amount</th>
            <th>GST</th>
            <th>Total</th>
            <th>Status</th>
            <th>Due Date</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="invoice in filteredInvoices" :key="invoice.id" :class="getInvoiceRowClass(invoice)">
            <td class="invoice-number">{{ invoice.invoice_number }}</td>
            <td>{{ invoice.client_name }}</td>
            <td>{{ formatDate(invoice.date) }}</td>
            <td>${{ invoice.amount.toFixed(2) }}</td>
            <td>${{ invoice.gst.toFixed(2) }}</td>
            <td class="total-amount">${{ (invoice.amount + invoice.gst).toFixed(2) }}</td>
            <td>
              <span :class="'status-' + invoice.status">{{ formatStatus(invoice.status) }}</span>
            </td>
            <td>{{ formatDate(invoice.due_date) }}</td>
            <td class="actions">
              <button @click="viewInvoice(invoice)" class="btn-view">View</button>
              <button @click="markPaid(invoice)" class="btn-pay" v-if="invoice.status === 'unpaid'">Mark Paid</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Receipts & Expenses Tab -->
    <div v-if="activeTab === 'receipts'" class="accounting-section">
      <h2>Receipts & Expense Management</h2>
      <div class="receipt-actions">
        <button @click="showReceiptForm = !showReceiptForm" class="btn-primary">
          {{ showReceiptForm ? 'Hide Form' : 'Add Receipt/Expense' }}
        </button>
        <button @click="uploadReceipts" class="btn-secondary">Upload Receipt Images</button>
      </div>

      <div v-if="showReceiptForm" class="receipt-form">
        <h3>{{ splitMode ? 'Split Receipt' : 'Add Receipt/Expense' }}</h3>
        <form @submit.prevent="addReceipt">
          <div class="form-row">
            <div class="form-group">
              <label>Date</label>
              <input v-model="newReceipt.date" type="date" required />
            </div>
            <div class="form-group">
              <label>Vendor</label>
              <input v-model="newReceipt.vendor" type="text" required />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>{{ splitMode ? 'Total Receipt Amount' : 'Amount (before GST)' }}</label>
              <input v-model="newReceipt.amount" type="number" step="0.01" required />
            </div>
            <div class="form-group">
              <label>GST Amount</label>
              <input v-model="newReceipt.gst" type="number" step="0.01" />
            </div>
          </div>
          
          <!-- Split Receipt Toggle -->
          <div class="form-row">
            <div class="form-group split-toggle">
              <label>
                <input type="checkbox" v-model="splitMode" @change="toggleSplitMode" />
                Split this receipt (business/personal, payment methods, rebates)
              </label>
            </div>
          </div>

          <!-- Split Components (shown when split mode enabled) -->
          <div v-if="splitMode" class="split-components">
            <h4>Receipt Components</h4>
            <div v-for="(component, index) in splitComponents" :key="index" class="split-component">
              <div class="component-header">
                <span>Component {{ index + 1 }}</span>
                <button type="button" @click="removeSplitComponent(index)" class="btn-remove" v-if="splitComponents.length > 1">
                  ✕
                </button>
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label>Amount</label>
                  <input v-model.number="component.amount" type="number" step="0.01" required />
                </div>
                <div class="form-group">
                  <label>GL Account</label>
                  <select v-model="component.gl_account_code" required>
                    <option value="">Select GL Account</option>
                    <option value="5110">5110 - Vehicle Fuel</option>
                    <option value="6925">6925 - Fuel Expense</option>
                    <option value="5120">5120 - Vehicle Maintenance</option>
                    <option value="6300">6300 - Insurance</option>
                    <option value="6310">6310 - Office Supplies</option>
                    <option value="6350">6350 - Meals & Entertainment</option>
                    <option value="9999">9999 - Personal (Non-Deductible)</option>
                    <option value="4200">4200 - Rebate/Discount</option>
                    <option value="1010">1010 - Cash Account</option>
                    <option value="6900">6900 - Other Expenses</option>
                  </select>
                </div>
              </div>
              <div class="form-group">
                <label>Description</label>
                <input v-model="component.description" type="text" placeholder="e.g., Personal items, FAS Gas rebate" />
              </div>
              <div class="form-row">
                <div class="form-group">
                  <label>
                    <input type="checkbox" v-model="component.is_personal" />
                    Personal Purchase (non-deductible)
                  </label>
                </div>
              </div>
            </div>
            
            <button type="button" @click="addSplitComponent" class="btn-add-component">+ Add Component</button>
            
            <div class="split-summary">
              <strong>Total Components: ${{ splitComponentsTotal.toFixed(2) }}</strong>
              <span v-if="splitComponentsTotal !== parseFloat(newReceipt.amount)" class="split-error">
                ⚠️ Components (${{ splitComponentsTotal.toFixed(2) }}) must equal receipt total (${{ parseFloat(newReceipt.amount).toFixed(2) }})
              </span>
              <span v-else class="split-valid">✓ Components match receipt total</span>
            </div>
          </div>

          <!-- GL Account Code (shown when NOT in split mode) -->
          <div v-if="!splitMode" class="form-row">
            <div class="form-group">
              <label>GL Account</label>
              <select v-model="newReceipt.gl_account_code" required>
                <option value="">Select GL Account</option>
                <option value="5110">5110 - Vehicle Fuel</option>
                <option value="6925">6925 - Fuel Expense</option>
                <option value="5120">5120 - Vehicle Maintenance</option>
                <option value="6300">6300 - Insurance</option>
                <option value="6310">6310 - Office Supplies</option>
                <option value="6350">6350 - Meals & Entertainment</option>
                <option value="6400">6400 - Professional Services</option>
                <option value="6900">6900 - Other Expenses</option>
              </select>
            </div>
            <div class="form-group">
              <label>Description</label>
              <input v-model="newReceipt.description" type="text" />
            </div>
          </div>

          <div class="form-actions">
            <button type="submit" class="btn-save" :disabled="splitMode && splitComponentsTotal !== parseFloat(newReceipt.amount)">
              {{ splitMode ? 'Save Split Receipt' : 'Save Receipt' }}
            </button>
            <button type="button" @click="cancelReceiptForm" class="btn-cancel">Cancel</button>
          </div>
        </form>
      </div>

      <div class="expense-summary">
        <h3>Expense Summary by GL Account</h3>
        <div class="expense-categories">
          <div v-for="glAccount in expenseCategories" :key="glAccount.name" class="category-card">
            <div class="category-name">{{ glAccount.name }}</div>
            <div class="category-amount">${{ glAccount.amount.toFixed(2) }}</div>
            <div class="category-gst">GST: ${{ glAccount.gst.toFixed(2) }}</div>
          </div>
        </div>
      </div>

      <!-- Receipt Verification Status -->
      <div class="verification-section">
        <ReceiptVerificationWidget />
      </div>
    </div>

    <!-- GST Management Tab -->
    <div v-if="activeTab === 'gst'" class="accounting-section">
      <h2>GST Management</h2>
      <div class="gst-overview">
        <div class="gst-card collected">
          <h3>GST Collected (Revenue)</h3>
          <div class="gst-amount">${{ gstData.collected.toFixed(2) }}</div>
        </div>
        <div class="gst-card paid">
          <h3>GST Paid (Expenses)</h3>
          <div class="gst-amount">${{ gstData.paid.toFixed(2) }}</div>
        </div>
        <div class="gst-card owed">
          <h3>Net GST Owed</h3>
          <div class="gst-amount">${{ (gstData.collected - gstData.paid).toFixed(2) }}</div>
        </div>
      </div>
      
      <div class="gst-reporting">
        <h3>GST Reporting Period</h3>
        <div class="period-selector">
          <select v-model="selectedGstPeriod">
            <option value="current">Current Quarter</option>
            <option value="last">Last Quarter</option>
            <option value="annual">Annual</option>
          </select>
          <button @click="generateGstReport" class="btn-primary">Generate GST Report</button>
        </div>
      </div>
    </div>

    <!-- Financial Reports Tab -->
    <div v-if="activeTab === 'reports'" class="accounting-section">
      <h2>Financial Reports</h2>
      <div class="report-grid">
        <div class="report-card" @click="generateReport('profit-loss')">
          <h3>📈 Profit & Loss</h3>
          <p>Monthly and yearly P&L statements</p>
        </div>
        <div class="report-card" @click="generateReport('balance-sheet')">
          <h3>⚖️ Balance Sheet</h3>
          <p>Assets, liabilities, and equity</p>
        </div>
        <div class="report-card" @click="generateReport('cash-flow')">
          <h3>💸 Cash Flow</h3>
          <p>Cash in and out analysis</p>
        </div>
        <div class="report-card" @click="generateReport('ar-aging')">
          <h3>⏰ A/R Aging</h3>
          <p>Outstanding receivables by age</p>
        </div>
        <div class="report-card" @click="generateReport('expense-analysis')">
          <h3>💳 Expense Analysis</h3>
          <p>Detailed expense breakdowns</p>
        </div>
        <div class="report-card" @click="generateReport('tax-summary')">
          <h3>🧾 Tax Summary</h3>
          <p>GST and income tax summaries</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import ReceiptVerificationWidget from '../components/ReceiptVerificationWidget.vue'

const activeTab = ref('invoices')
const showReceiptForm = ref(false)
const splitMode = ref(false)
const splitComponents = ref([{ amount: 0, gl_account_code: '', description: '', is_personal: false }])
const invoiceSearch = ref('')
const invoiceStatusFilter = ref('')
const invoiceDateFilter = ref('')
const selectedGstPeriod = ref('current')

const stats = ref({
  monthlyRevenue: 0,
  monthlyExpenses: 0,
  monthlyProfit: 0,
  outstandingReceivables: 0,
  gstOwed: 0
})

const invoices = ref([])
const receipts = ref([])

const newReceipt = ref({
  date: '',
  vendor: '',
  amount: 0,
  gst: 0,
  gl_account_code: '',
  description: ''
})

const gstData = ref({
  collected: 0,
  paid: 0
})

const expenseCategories = computed(() => {
  const glAccounts = {}
  receipts.value.forEach(receipt => {
    const glCode = receipt.gl_account_code || 'Unknown'
    if (!glAccounts[glCode]) {
      glAccounts[glCode] = { name: glCode, amount: 0, gst: 0 }
    }
    glAccounts[glCode].amount += receipt.amount
    glAccounts[glCode].gst += receipt.gst
  })
  return Object.values(glAccounts)
})

const splitComponentsTotal = computed(() => {
  return splitComponents.value.reduce((sum, comp) => sum + (parseFloat(comp.amount) || 0), 0)
})

const filteredInvoices = computed(() => {
  let filtered = invoices.value

  if (invoiceSearch.value) {
    const search = invoiceSearch.value.toLowerCase()
    filtered = filtered.filter(inv => 
      inv.invoice_number.toLowerCase().includes(search) ||
      inv.client_name.toLowerCase().includes(search)
    )
  }

  if (invoiceStatusFilter.value) {
    filtered = filtered.filter(inv => inv.status === invoiceStatusFilter.value)
  }

  if (invoiceDateFilter.value) {
    const [year, month] = invoiceDateFilter.value.split('-')
    filtered = filtered.filter(inv => {
      const invDate = new Date(inv.date)
      return invDate.getFullYear() == year && (invDate.getMonth() + 1) == month
    })
  }

  return filtered
})

async function loadAccountingData() {
  try {
    // Fetch receipts from backend API
    const receiptsResp = await fetch('http://127.0.0.1:8001/api/receipts-simple/?limit=500');
    if (!receiptsResp.ok) throw new Error('Failed to fetch receipts');
    const receiptsData = await receiptsResp.json();
    // Map backend fields to frontend expected fields
    receipts.value = receiptsData.map(r => ({
      id: r.receipt_id,
      date: r.receipt_date,
      vendor: r.vendor_name,
      amount: r.gross_amount,
      gst: r.gst_amount ?? 0,
      gl_account_code: r.gl_account_code ?? '',
      description: r.description ?? '',
      is_personal: r.is_personal ?? false,
      is_driver_personal: r.is_driver_personal ?? false
    }));

    // Dashboard stats - placeholder since we don't have an aggregation endpoint yet
    stats.value = {
      monthlyRevenue: 0,
      monthlyExpenses: receiptsData.reduce((sum, r) => sum + (parseFloat(r.gross_amount) || 0), 0),
      monthlyProfit: 0,
      outstandingReceivables: 0,
      gstOwed: 0
    };
    // Fetch invoices from backend API
    try {
      const invoicesResp = await fetch('/api/invoices');
      if (invoicesResp.ok) {
        const invoicesData = await invoicesResp.json();
        // Defensive: handle both {results: [...]} and []
        const raw = Array.isArray(invoicesData) ? invoicesData : (invoicesData.results || []);
        invoices.value = raw.map(inv => ({
          id: inv.invoice_id || inv.id || inv.invoice_number || Math.random(),
          invoice_number: inv.invoice_number || inv.id || '',
          client_name: inv.client_name || inv.client || '',
          date: inv.invoice_date || inv.date || '',
          amount: Number(inv.amount) || 0,
          gst: Number(inv.gst) || 0,
          status: inv.status || 'unpaid',
          due_date: inv.due_date || '',
        }));
      } else {
        invoices.value = [];
      }
    } catch (e) {
      invoices.value = [];
    }
    gstData.value = {
      collected: 0,
      paid: 0
    };
  } catch (error) {
    console.error('Error loading accounting data:', error);
  }
}

function getInvoiceRowClass(invoice) {
  const classes = [`status-${invoice.status}`]
  if (invoice.status === 'overdue') classes.push('overdue-row')
  return classes.join(' ')
}

function formatDate(dateString) {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleDateString()
}

function formatStatus(status) {
  const statusMap = {
    'paid': 'Paid',
    'unpaid': 'Unpaid',
    'overdue': 'Overdue'
  }
  return statusMap[status] || status
}

function viewInvoice(invoice) {
  console.log('View invoice:', invoice)
  // TODO: Open invoice detail view
}

function markPaid(invoice) {
  console.log('Mark paid:', invoice)
  // TODO: Update invoice status to paid
  invoice.status = 'paid'
}

async function addReceipt() {
  if (splitMode.value) {
    // Validate split components total matches receipt amount
    if (splitComponentsTotal.value !== parseFloat(newReceipt.value.amount)) {
      alert('Split components must equal receipt total')
      return
    }
    
    // Save each component as a separate receipt
    try {
      for (const component of splitComponents.value) {
        await fetch('http://127.0.0.1:8001/api/receipts-simple/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            receipt_date: newReceipt.value.date,
            vendor_name: newReceipt.value.vendor,
            gross_amount: parseFloat(component.amount),
            gst_amount: parseFloat(component.amount) * 0.05 / 1.05,
            gst_code: 'GST_INCL_5',
            gl_account_code: component.gl_account_code,
            description: component.description,
            is_personal: component.is_personal,
            is_driver_personal: false
          })
        })
      }
      await loadAccountingData()
      cancelReceiptForm()
    } catch (err) {
      alert('Error saving split receipt: ' + err.message)
    }
    
  } else {
    // Regular single receipt
    try {
      await fetch('http://127.0.0.1:8001/api/receipts-simple/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          receipt_date: newReceipt.value.date,
          vendor_name: newReceipt.value.vendor,
          gross_amount: parseFloat(newReceipt.value.amount),
          gst_amount: parseFloat(newReceipt.value.gst),
          gst_code: 'GST_INCL_5',
          gl_account_code: newReceipt.value.gl_account_code,
          description: newReceipt.value.description,
          is_personal: false,
          is_driver_personal: false
        })
      })
      await loadAccountingData()
      cancelReceiptForm()
    } catch (err) {
      alert('Error saving receipt: ' + err.message)
    }
  }
}

function toggleSplitMode() {
  if (splitMode.value) {
    // Initialize with one component
    splitComponents.value = [{ 
      amount: parseFloat(newReceipt.value.amount) || 0, 
      gl_account_code: '', 
      description: '', 
      is_personal: false 
    }]
  } else {
    splitComponents.value = []
  }
}

function addSplitComponent() {
  splitComponents.value.push({ 
    amount: 0, 
    category: '', 
    description: '', 
    is_personal: false 
  })
}

function removeSplitComponent(index) {
  splitComponents.value.splice(index, 1)
}

function cancelReceiptForm() {
  showReceiptForm.value = false
  splitMode.value = false
  splitComponents.value = [{ amount: 0, gl_account_code: '', description: '', is_personal: false }]
  newReceipt.value = {
    date: '',
    vendor: '',
    amount: 0,
    gst: 0,
    gl_account_code: '',
    description: ''
  }
}

function uploadReceipts() {
  console.log('Upload receipts')
  // TODO: Implement file upload
}

function generateGstReport() {
  console.log('Generate GST report for period:', selectedGstPeriod.value)
  // TODO: Generate and download GST report
}

function generateReport(reportType) {
  console.log('Generate report:', reportType)
  // TODO: Generate and download report
}

onMounted(() => {
  loadAccountingData()
})
</script>

<style scoped>
.accounting-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 30px;
  flex-wrap: wrap;
}

.stat-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  min-width: 140px;
  flex: 1;
}

.stat-value {
  font-size: 1.8rem;
  font-weight: bold;
  margin-bottom: 5px;
}

.stat-card.revenue .stat-value { color: #28a745; }
.stat-card.expenses .stat-value { color: #dc3545; }
.stat-card.profit .stat-value { color: #007bff; }
.stat-card.outstanding .stat-value { color: #ffc107; }
.stat-card.gst .stat-value { color: #6f42c1; }

.stat-label {
  font-size: 0.9rem;
  color: #666;
}

.quick-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 30px;
  flex-wrap: wrap;
}

.action-btn {
  padding: 12px 20px;
  border: 2px solid #007bff;
  background: white;
  color: #007bff;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s;
}

.action-btn:hover, .action-btn.active {
  background: #007bff;
  color: white;
}

.accounting-section {
  background: white;
  border-radius: 8px;
  padding: 25px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  margin-bottom: 20px;
}

.invoice-filters, .receipt-actions {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
  align-items: center;
  flex-wrap: wrap;
}

.invoice-filters input, .invoice-filters select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.accounting-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 15px;
}

.accounting-table th,
.accounting-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.accounting-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #333;
}

.accounting-table tr:hover {
  background-color: #f5f5f5;
}

.invoice-number {
  font-weight: 500;
  color: #007bff;
}

.total-amount {
  font-weight: bold;
}

.status-paid { color: #28a745; font-weight: bold; }
.status-unpaid { color: #ffc107; font-weight: bold; }
.status-overdue { color: #dc3545; font-weight: bold; }

.overdue-row {
  background-color: #fff5f5;
}

.receipt-form {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
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
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.btn-primary, .btn-secondary, .btn-save {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}

.btn-primary, .btn-save {
  background: #007bff;
  color: white;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-cancel {
  padding: 10px 20px;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

/* Split Receipt Styles */
.split-toggle {
  margin: 15px 0;
  padding: 10px;
  background: #e7f3ff;
  border-radius: 4px;
}

.split-toggle label {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-weight: 500;
  color: #0056b3;
}

.split-toggle input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.split-components {
  margin: 20px 0;
  padding: 15px;
  background: #f0f8ff;
  border: 2px dashed #007bff;
  border-radius: 8px;
}

.split-components h4 {
  margin: 0 0 15px 0;
  color: #0056b3;
}

.split-component {
  background: white;
  padding: 15px;
  margin-bottom: 15px;
  border-radius: 6px;
  border: 1px solid #cce5ff;
}

.component-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e0e0e0;
}

.component-header span {
  font-weight: 600;
  color: #333;
}

.btn-remove {
  background: #dc3545;
  color: white;
  border: none;
  padding: 4px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-remove:hover {
  background: #c82333;
}

.btn-add-component {
  background: #28a745;
  color: white;
  border: none;
  padding: 10px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  width: 100%;
  margin-top: 10px;
}

.btn-add-component:hover {
  background: #218838;
}

.split-summary {
  margin-top: 15px;
  padding: 12px;
  background: white;
  border-radius: 4px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 16px;
}

.split-error {
  color: #dc3545;
  font-weight: 500;
}

.split-valid {
  color: #28a745;
  font-weight: 500;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}


.expense-categories {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-top: 15px;
}

.category-card {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 8px;
  text-align: center;
}

.category-name {
  font-weight: bold;
  margin-bottom: 8px;
  text-transform: capitalize;
}

.category-amount {
  font-size: 1.2rem;
  color: #007bff;
  font-weight: bold;
}

.category-gst {
  font-size: 0.9rem;
  color: #666;
}

.gst-overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.gst-card {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  text-align: center;
}

.gst-card h3 {
  margin-bottom: 10px;
  color: #333;
}

.gst-amount {
  font-size: 1.5rem;
  font-weight: bold;
  color: #007bff;
}

.period-selector {
  display: flex;
  gap: 15px;
  align-items: center;
}

.report-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.report-card {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
  border: 2px solid transparent;
}

.report-card:hover {
  background: #e9ecef;
  border-color: #007bff;
}

.report-card h3 {
  margin-bottom: 10px;
  color: #333;
}

.report-card p {
  color: #666;
  margin: 0;
}

.actions {
  display: flex;
  gap: 8px;
}

.btn-view, .btn-pay {
  padding: 4px 8px;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn-view {
  background: #17a2b8;
  color: white;
}

.btn-pay {
  background: #28a745;
  color: white;
}

h1 {
  margin-bottom: 2rem;
  color: #333;
}

h2 {
  margin-bottom: 1.5rem;
  color: #333;
}

.verification-section {
  margin-top: 30px;
  padding-top: 30px;
  border-top: 1px solid #ddd;
}
</style>