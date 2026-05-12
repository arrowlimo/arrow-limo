<template>
  <div>
    <h1>💰 Owe David Dashboard</h1>
    
    <!-- Summary Stats -->
    <div class="owe-david-stats">
      <div class="stat-card total-owed">
        <div class="stat-value">${{ stats.totalOwed }}</div>
        <div class="stat-label">Total Owed to David</div>
      </div>
      <div class="stat-card last-payment">
        <div class="stat-value">{{ stats.lastPaymentDate }}</div>
        <div class="stat-label">Last Payment</div>
      </div>
      <div class="stat-card avg-monthly">
        <div class="stat-value">${{ stats.avgMonthlyOwed }}</div>
        <div class="stat-label">Avg Monthly Owed</div>
      </div>
      <div class="stat-card pending">
        <div class="stat-value">{{ stats.pendingItems }}</div>
        <div class="stat-label">Pending Items</div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="quick-actions">
      <button @click="showPaymentForm = !showPaymentForm" class="btn-primary">
        {{ showPaymentForm ? 'Hide Payment' : '💳 Record Payment' }}
      </button>
      <button @click="showExpenseForm = !showExpenseForm" class="btn-secondary">
        {{ showExpenseForm ? 'Hide Expense' : '📄 Add Expense' }}
      </button>
      <button @click="generateStatement" class="btn-info">📊 Generate Statement</button>
      <button @click="exportData" class="btn-success">📤 Export Data</button>
    </div>

    <!-- Payment Form -->
    <div v-if="showPaymentForm" class="payment-form-section">
      <div class="payment-form">
        <h3>Record Payment to David</h3>
        <form @submit.prevent="recordPayment">
          <div class="form-row">
            <div class="form-group">
              <label>Payment Date</label>
              <input v-model="newPayment.date" type="date" required />
            </div>
            <div class="form-group">
              <label>Amount</label>
              <input v-model="newPayment.amount" type="number" step="0.01" required />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Payment Method</label>
              <select v-model="newPayment.method" required>
                <option value="">Select Method</option>
                <option value="cash">Cash</option>
                <option value="cheque">Cheque</option>
                <option value="e-transfer">E-Transfer</option>
                <option value="direct-deposit">Direct Deposit</option>
              </select>
            </div>
            <div class="form-group">
              <label>Reference/Note</label>
              <input v-model="newPayment.reference" type="text" />
            </div>
          </div>
          <div class="form-actions">
            <button type="submit" class="btn-save">Record Payment</button>
            <button type="button" @click="cancelPaymentForm" class="btn-cancel">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Expense Form -->
    <div v-if="showExpenseForm" class="expense-form-section">
      <div class="expense-form">
        <h3>Add Expense Owed to David</h3>
        <form @submit.prevent="addExpense">
          <div class="form-row">
            <div class="form-group">
              <label>Date</label>
              <input v-model="newExpense.date" type="date" required />
            </div>
            <div class="form-group">
              <label>Amount</label>
              <input v-model="newExpense.amount" type="number" step="0.01" required />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Category</label>
              <select v-model="newExpense.category" required>
                <option value="">Select Category</option>
                <option value="fuel">Fuel</option>
                <option value="maintenance">Vehicle Maintenance</option>
                <option value="insurance">Insurance</option>
                <option value="supplies">Supplies</option>
                <option value="meals">Meals</option>
                <option value="personal">Personal Advance</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div class="form-group">
              <label>Description</label>
              <input v-model="newExpense.description" type="text" required />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Receipt Reference</label>
              <input v-model="newExpense.receipt_ref" type="text" />
            </div>
            <div class="form-group">
              <label>Priority</label>
              <select v-model="newExpense.priority">
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
          </div>
          <div class="form-actions">
            <button type="submit" class="btn-save">Add Expense</button>
            <button type="button" @click="cancelExpenseForm" class="btn-cancel">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Transaction History -->
    <div class="transaction-section">
      <h2>Transaction History</h2>
      
      <!-- Filters -->
      <div class="transaction-filters">
        <input v-model="searchText" placeholder="Search transactions..." />
        <select v-model="typeFilter">
          <option value="">All Types</option>
          <option value="expense">Expenses</option>
          <option value="payment">Payments</option>
        </select>
        <select v-model="categoryFilter">
          <option value="">All Categories</option>
          <option value="fuel">Fuel</option>
          <option value="maintenance">Maintenance</option>
          <option value="insurance">Insurance</option>
          <option value="personal">Personal</option>
          <option value="other">Other</option>
        </select>
        <input v-model="dateFromFilter" type="date" />
        <input v-model="dateToFilter" type="date" />
      </div>

      <!-- Transaction Table -->
      <table class="transactions-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Type</th>
            <th>Category</th>
            <th>Description</th>
            <th>Amount</th>
            <th>Balance</th>
            <th>Reference</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="transaction in filteredTransactions" :key="transaction.id" :class="getTransactionRowClass(transaction)">
            <td>{{ formatDate(transaction.date) }}</td>
            <td>
              <span :class="'type-' + transaction.type">
                {{ transaction.type === 'expense' ? '📤 Expense' : '💰 Payment' }}
              </span>
            </td>
            <td>{{ transaction.category || '-' }}</td>
            <td>{{ transaction.description }}</td>
            <td :class="transaction.type === 'expense' ? 'amount-expense' : 'amount-payment'">
              {{ transaction.type === 'expense' ? '+' : '-' }}${{ Math.abs(transaction.amount).toFixed(2) }}
            </td>
            <td class="balance-amount">${{ transaction.running_balance.toFixed(2) }}</td>
            <td>{{ transaction.reference || '-' }}</td>
            <td>
              <span :class="'status-' + transaction.status">{{ formatStatus(transaction.status) }}</span>
            </td>
            <td class="actions">
              <button @click="editTransaction(transaction)" class="btn-edit">Edit</button>
              <button @click="deleteTransaction(transaction)" class="btn-delete">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Monthly Summary -->
    <div class="monthly-summary">
      <h2>Monthly Summary</h2>
      <div class="summary-cards">
        <div v-for="month in monthlySummary" :key="month.month" class="month-card">
          <div class="month-header">{{ month.month }}</div>
          <div class="month-expenses">Expenses: ${{ month.expenses.toFixed(2) }}</div>
          <div class="month-payments">Payments: ${{ month.payments.toFixed(2) }}</div>
          <div class="month-net">Net: ${{ month.net.toFixed(2) }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { toast } from '@/toast/toastStore'
import { authFetch } from '@/utils/authFetch'

const showPaymentForm = ref(false)
const showExpenseForm = ref(false)
const searchText = ref('')
const typeFilter = ref('')
const categoryFilter = ref('')
const dateFromFilter = ref('')
const dateToFilter = ref('')

const stats = ref({
  totalOwed: 0,
  lastPaymentDate: '',
  avgMonthlyOwed: 0,
  pendingItems: 0
})

const transactions = ref([])

const newPayment = ref({
  date: '',
  amount: 0,
  method: '',
  reference: ''
})

const newExpense = ref({
  date: '',
  amount: 0,
  category: '',
  description: '',
  receipt_ref: '',
  priority: 'normal'
})

const filteredTransactions = computed(() => {
  let filtered = transactions.value

  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    filtered = filtered.filter(t => 
      t.description.toLowerCase().includes(search) ||
      (t.reference && t.reference.toLowerCase().includes(search))
    )
  }

  if (typeFilter.value) {
    filtered = filtered.filter(t => t.type === typeFilter.value)
  }

  if (categoryFilter.value) {
    filtered = filtered.filter(t => t.category === categoryFilter.value)
  }

  if (dateFromFilter.value) {
    filtered = filtered.filter(t => t.date >= dateFromFilter.value)
  }

  if (dateToFilter.value) {
    filtered = filtered.filter(t => t.date <= dateToFilter.value)
  }

  return filtered
})

const monthlySummary = computed(() => {
  const months = {}
  
  transactions.value.forEach(t => {
    const month = t.date.substring(0, 7) // YYYY-MM
    if (!months[month]) {
      months[month] = { month, expenses: 0, payments: 0, net: 0 }
    }
    
    if (t.type === 'expense') {
      months[month].expenses += t.amount
    } else {
      months[month].payments += t.amount
    }
  })

  Object.values(months).forEach(m => {
    m.net = m.expenses - m.payments
  })

  return Object.values(months).sort((a, b) => b.month.localeCompare(a.month))
})

async function loadOweDavidData() {
  try {
    const res = await authFetch('/api/owe-david/transactions')
    if (!res.ok) throw new Error(`Failed to load transactions (${res.status})`)
    const data = await res.json()
    transactions.value = Array.isArray(data) ? data : (Array.isArray(data?.transactions) ? data.transactions : [])
    recalculateBalances()
    calculateStats()
  } catch (error) {
    console.error('Error loading Owe David data:', error)
    transactions.value = []
    calculateStats()
    toast.error(error?.message || 'Failed to load Owe David data')
  }
}

function calculateStats() {
  let balance = 0
  let lastPayment = null
  
  transactions.value.forEach(t => {
    if (t.type === 'expense') {
      balance += t.amount
    } else {
      balance -= t.amount
      if (!lastPayment || t.date > lastPayment) {
        lastPayment = t.date
      }
    }
  })

  stats.value.totalOwed = balance
  stats.value.lastPaymentDate = lastPayment ? formatDate(lastPayment) : 'No payments'
  stats.value.pendingItems = transactions.value.filter(t => t.status === 'pending').length
  
  // Calculate average monthly owed over last 6 months
  const sixMonthsAgo = new Date()
  sixMonthsAgo.setMonth(sixMonthsAgo.getMonth() - 6)
  const recentTransactions = transactions.value.filter(t => new Date(t.date) > sixMonthsAgo)
  const monthlyExpenses = recentTransactions
    .filter(t => t.type === 'expense')
    .reduce((sum, t) => sum + t.amount, 0) / 6
  stats.value.avgMonthlyOwed = monthlyExpenses
}

function getTransactionRowClass(transaction) {
  const classes = [`type-row-${transaction.type}`]
  if (transaction.status === 'pending') classes.push('pending-row')
  return classes.join(' ')
}

function formatDate(dateString) {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleDateString()
}

function formatStatus(status) {
  const statusMap = {
    'pending': 'Pending',
    'completed': 'Completed',
    'cancelled': 'Cancelled'
  }
  return statusMap[status] || status
}

function recordPayment() {
  console.log('Record payment:', newPayment.value)
  
  // Add to transactions
  const payment = {
    id: transactions.value.length + 1,
    date: newPayment.value.date,
    type: 'payment',
    category: null,
    description: `Payment to David - ${newPayment.value.method}`,
    amount: parseFloat(newPayment.value.amount),
    reference: newPayment.value.reference,
    status: 'completed',
    running_balance: 0 // Will be recalculated
  }
  
  transactions.value.push(payment)
  recalculateBalances()
  calculateStats()
  cancelPaymentForm()
  toast.success('Payment recorded successfully!')
}

function addExpense() {
  console.log('Add expense:', newExpense.value)
  
  // Add to transactions
  const expense = {
    id: transactions.value.length + 1,
    date: newExpense.value.date,
    type: 'expense',
    category: newExpense.value.category,
    description: newExpense.value.description,
    amount: parseFloat(newExpense.value.amount),
    reference: newExpense.value.receipt_ref,
    status: 'pending',
    running_balance: 0 // Will be recalculated
  }
  
  transactions.value.push(expense)
  recalculateBalances()
  calculateStats()
  cancelExpenseForm()
  toast.success('Expense added successfully!')
}

function recalculateBalances() {
  // Sort by date
  transactions.value.sort((a, b) => a.date.localeCompare(b.date))
  
  let balance = 0
  transactions.value.forEach(t => {
    if (t.type === 'expense') {
      balance += t.amount
    } else {
      balance -= t.amount
    }
    t.running_balance = balance
  })
}

function cancelPaymentForm() {
  showPaymentForm.value = false
  newPayment.value = {
    date: '',
    amount: 0,
    method: '',
    reference: ''
  }
}

function cancelExpenseForm() {
  showExpenseForm.value = false
  newExpense.value = {
    date: '',
    amount: 0,
    category: '',
    description: '',
    receipt_ref: '',
    priority: 'normal'
  }
}

function editTransaction(transaction) {
  const amountRaw = prompt('Amount', String(transaction.amount ?? ''))
  if (amountRaw === null) return
  const description = prompt('Description', transaction.description || '')
  if (description === null) return
  const date = prompt('Date (YYYY-MM-DD)', transaction.date || '')
  if (date === null) return

  const amount = parseFloat(amountRaw)
  if (Number.isNaN(amount) || amount < 0) {
    toast.error('Invalid amount')
    return
  }

  transaction.amount = amount
  transaction.description = description
  transaction.date = date
  recalculateBalances()
  calculateStats()
  toast.success('Transaction updated')
}

function deleteTransaction(transaction) {
  if (confirm('Are you sure you want to delete this transaction?')) {
    transactions.value = transactions.value.filter(t => t.id !== transaction.id)
    recalculateBalances()
    calculateStats()
  }
}

function generateStatement() {
  const lines = []
  lines.push('Owe David Statement')
  lines.push(`Generated: ${new Date().toLocaleString()}`)
  lines.push('')
  lines.push('Date,Type,Category,Description,Amount,Running Balance')
  for (const t of transactions.value) {
    lines.push([
      t.date || '',
      t.type || '',
      t.category || '',
      (t.description || '').replace(/,/g, ' '),
      Number(t.amount || 0).toFixed(2),
      Number(t.running_balance || 0).toFixed(2)
    ].join(','))
  }
  const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `owe-david-statement-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
  toast.success('Statement generated')
}

function exportData() {
  const headers = ['id', 'date', 'type', 'category', 'description', 'amount', 'status', 'running_balance']
  const csvRows = [headers.join(',')]
  for (const t of transactions.value) {
    const row = headers.map((h) => {
      const val = t[h] ?? ''
      return `"${String(val).replace(/"/g, '""')}"`
    }).join(',')
    csvRows.push(row)
  }
  const blob = new Blob([csvRows.join('\n')], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `owe-david-export-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
  toast.success('Data exported')
}

onMounted(() => {
  loadOweDavidData()
})
</script>

<style scoped>
.owe-david-stats {
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
  min-width: 160px;
  flex: 1;
}

.stat-value {
  font-size: 1.8rem;
  font-weight: bold;
  margin-bottom: 5px;
}

.stat-card.total-owed .stat-value { color: #dc3545; }
.stat-card.last-payment .stat-value { color: #28a745; }
.stat-card.avg-monthly .stat-value { color: #007bff; }
.stat-card.pending .stat-value { color: #ffc107; }

.stat-label {
  font-size: 0.9rem;
  color: #666;
}

.quick-actions {
  display: flex;
  gap: 15px;
  margin-bottom: 30px;
  flex-wrap: wrap;
}

.btn-primary, .btn-secondary, .btn-info, .btn-success {
  padding: 12px 20px;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-primary { background: #007bff; color: white; }
.btn-secondary { background: #6c757d; color: white; }
.btn-info { background: #17a2b8; color: white; }
.btn-success { background: #28a745; color: white; }

.payment-form-section, .expense-form-section {
  background: white;
  border-radius: 8px;
  padding: 25px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.payment-form, .expense-form {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
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

.btn-save {
  background: #28a745;
  color: white;
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-cancel {
  background: #dc3545;
  color: white;
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.transaction-section, .monthly-summary {
  background: white;
  border-radius: 8px;
  padding: 25px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.transaction-filters {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.transaction-filters input, .transaction-filters select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.transactions-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 15px;
}

.transactions-table th,
.transactions-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.transactions-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #333;
}

.transactions-table tr:hover {
  background-color: #f5f5f5;
}

.type-expense { color: #dc3545; font-weight: bold; }
.type-payment { color: #28a745; font-weight: bold; }

.amount-expense { color: #dc3545; font-weight: bold; }
.amount-payment { color: #28a745; font-weight: bold; }

.balance-amount {
  font-weight: bold;
  color: #007bff;
}

.type-row-expense {
  background-color: #fff5f5;
}

.type-row-payment {
  background-color: #f8fff8;
}

.pending-row {
  border-left: 4px solid #ffc107;
}

.status-pending { color: #ffc107; font-weight: bold; }
.status-completed { color: #28a745; font-weight: bold; }
.status-cancelled { color: #dc3545; font-weight: bold; }

.actions {
  display: flex;
  gap: 8px;
}

.btn-edit, .btn-delete {
  padding: 4px 8px;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.85rem;
}

.btn-edit {
  background: #007bff;
  color: white;
}

.btn-delete {
  background: #dc3545;
  color: white;
}

.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-top: 15px;
}

.month-card {
  background: #f8f9fa;
  padding: 15px;
  border-radius: 8px;
  text-align: center;
}

.month-header {
  font-weight: bold;
  margin-bottom: 10px;
  color: #333;
}

.month-expenses {
  color: #dc3545;
  margin-bottom: 5px;
}

.month-payments {
  color: #28a745;
  margin-bottom: 5px;
}

.month-net {
  font-weight: bold;
  color: #007bff;
  font-size: 1.1rem;
}

h1 {
  margin-bottom: 2rem;
  color: #333;
}

h2 {
  margin-bottom: 1.5rem;
  color: #333;
}

h3 {
  margin-bottom: 1rem;
  color: #333;
}
</style>