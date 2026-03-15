<template>
  <div class="banking-deposits">
    <div class="deposits-header">
      <h2>🏦 Banking Deposits</h2>
      <button @click="loadDeposits" class="btn-refresh">🔄 Refresh</button>
    </div>

    <!-- Filters -->
    <div class="filters">
      <input
        v-model.number="searchAmount"
        type="number"
        step="0.01"
        placeholder="Amount"
        class="search-input search-amount"
      />

      <input
        v-model="searchVendor"
        placeholder="Vendor/Description"
        class="search-input"
      />

      <button @click="searchDeposits" class="btn-refresh btn-search">Search</button>
      <button @click="clearSearch" class="btn-refresh btn-clear">Clear</button>

      <input 
        v-model="searchText" 
        @input="filterDeposits"
        placeholder="Search deposits..." 
        class="search-input"
      />
      
      <select v-model="accountFilter" @change="filterDeposits" class="filter-select">
        <option value="">All Accounts</option>
        <option v-for="account in accounts" :key="account" :value="account">
          {{ account }}
        </option>
      </select>

      <input 
        v-model="startDate" 
        @change="filterDeposits"
        type="date" 
        class="date-input"
      />
      
      <input 
        v-model="endDate" 
        @change="filterDeposits"
        type="date" 
        class="date-input"
      />

      <label class="checkbox-label">
        <input type="checkbox" v-model="showUnmatchedOnly" @change="filterDeposits" />
        <span>Unmatched Only</span>
      </label>
    </div>

    <!-- Deposits Table -->
    <div class="table-container">
      <p v-if="loading" class="loading">Loading deposits...</p>
      <p v-else-if="!filteredDeposits.length" class="no-data">No deposits found</p>
      
      <table v-else class="deposits-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Date</th>
            <th>Account</th>
            <th>Description</th>
            <th>Amount</th>
            <th>Category</th>
            <th>Verified</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr 
            v-for="deposit in filteredDeposits" 
            :key="deposit.transaction_id"
            :class="{ 'editing-row': editingId === deposit.transaction_id }"
          >
            <td>{{ deposit.transaction_id }}</td>
            <td>{{ formatDate(deposit.transaction_date) }}</td>
            <td>{{ deposit.account_number }}</td>
            
            <!-- Editable Description -->
            <td class="description-cell">
              <input 
                v-if="editingId === deposit.transaction_id"
                v-model="editForm.description"
                @keyup.enter="saveEdit(deposit.transaction_id)"
                @keyup.esc="cancelEdit"
                class="edit-input"
                ref="editInput"
              />
              <span 
                v-else 
                :class="{ 'empty-description': !deposit.description }"
                @dblclick="startEdit(deposit)"
              >
                {{ deposit.description || '(no description - double-click to edit)' }}
              </span>
            </td>
            
            <td class="amount">{{ formatCurrency(deposit.credit_amount) }}</td>
            
            <!-- Editable Category -->
            <td>
              <select 
                v-if="editingId === deposit.transaction_id"
                v-model="editForm.category"
                class="category-select"
              >
                <option value="">Uncategorized</option>
                <option value="customer_payment">Customer Payment</option>
                <option value="charter_deposit">Charter Deposit</option>
                <option value="refund">Refund</option>
                <option value="transfer">Transfer</option>
                <option value="other_income">Other Income</option>
              </select>
              <span v-else :class="{ 'no-category': !deposit.category }">
                {{ deposit.category || 'Uncategorized' }}
              </span>
            </td>
            
            <!-- Verified Status -->
            <td class="verified-cell">
              <input 
                v-if="editingId === deposit.transaction_id"
                type="checkbox" 
                v-model="editForm.verified"
              />
              <span v-else :class="deposit.verified ? 'verified-yes' : 'verified-no'">
                {{ deposit.verified ? '✓ Yes' : '✗ No' }}
              </span>
            </td>
            
            <!-- Actions -->
            <td class="actions">
              <template v-if="editingId === deposit.transaction_id">
                <button @click="saveEdit(deposit.transaction_id)" class="btn-save">💾 Save</button>
                <button @click="cancelEdit" class="btn-cancel">✕ Cancel</button>
              </template>
              <template v-else>
                <button @click="startEdit(deposit)" class="btn-edit">✏️ Edit</button>
              </template>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Summary Stats -->
    <div v-if="filteredDeposits.length" class="summary">
      <div class="stat">
        <span class="stat-label">Total Deposits:</span>
        <span class="stat-value">{{ filteredDeposits.length }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">Total Amount:</span>
        <span class="stat-value">{{ formatCurrency(totalAmount) }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">Verified:</span>
        <span class="stat-value">{{ verifiedCount }} / {{ filteredDeposits.length }}</span>
      </div>
      <div class="stat">
        <span class="stat-label">Unmatched:</span>
        <span class="stat-value">{{ unmatchedCount }}</span>
      </div>
    </div>

    <!-- Toast Notifications -->
    <div v-if="successMessage" class="toast toast-success">{{ successMessage }}</div>
    <div v-if="errorMessage" class="toast toast-error">{{ errorMessage }}</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'

const deposits = ref([])
const filteredDeposits = ref([])
const accounts = ref([])
const loading = ref(false)
const searchText = ref('')
const searchAmount = ref(null)
const searchVendor = ref('')
const accountFilter = ref('')
const startDate = ref('')
const endDate = ref('')
const showUnmatchedOnly = ref(false)
const editingId = ref(null)
const editForm = ref({
  description: '',
  category: '',
  verified: false
})
const successMessage = ref('')
const errorMessage = ref('')

const totalAmount = computed(() => {
  return filteredDeposits.value.reduce((sum, d) => sum + (d.credit_amount || 0), 0)
})

const verifiedCount = computed(() => {
  return filteredDeposits.value.filter(d => d.verified).length
})

const unmatchedCount = computed(() => {
  return filteredDeposits.value.filter(d => !d.category || d.category === '').length
})

async function loadDeposits() {
  loading.value = true
  try {
    const response = await fetch('/api/banking/transactions?limit=1000')
    const data = await response.json()
    
    // Filter only credits (deposits)
    deposits.value = data.filter(t => t.credit_amount > 0)
    
    // Extract unique accounts
    accounts.value = [...new Set(deposits.value.map(d => d.account_number).filter(Boolean))]
    
    filterDeposits()
  } catch (error) {
    console.error('Error loading deposits:', error)
    showError('Failed to load deposits')
  } finally {
    loading.value = false
  }
}

async function searchDeposits() {
  const vendor = (searchVendor.value || '').trim()
  const hasAmount = searchAmount.value !== null && searchAmount.value !== ''

  if (!hasAmount && !vendor) {
    showError('Enter an amount or vendor to search')
    return
  }

  loading.value = true
  try {
    const params = new URLSearchParams()
    if (hasAmount) {
      params.set('amount', searchAmount.value)
    }
    if (vendor) {
      params.set('vendor', vendor)
    }
    if (startDate.value) {
      params.set('start_date', startDate.value)
    }
    if (endDate.value) {
      params.set('end_date', endDate.value)
    }
    params.set('limit', '1000')

    const response = await fetch(`/api/banking/search?${params.toString()}`)
    if (!response.ok) {
      throw new Error('Failed to search deposits')
    }
    const data = await response.json()

    deposits.value = data.filter(t => t.credit_amount > 0)
    accounts.value = [...new Set(deposits.value.map(d => d.account_number).filter(Boolean))]
    filterDeposits()
  } catch (error) {
    console.error('Error searching deposits:', error)
    showError('Failed to search deposits')
  } finally {
    loading.value = false
  }
}

function clearSearch() {
  searchAmount.value = null
  searchVendor.value = ''
  loadDeposits()
}

function filterDeposits() {
  let filtered = deposits.value

  // Text search
  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    filtered = filtered.filter(d =>
      d.description?.toLowerCase().includes(search) ||
      d.transaction_id.toString().includes(search) ||
      d.category?.toLowerCase().includes(search)
    )
  }

  // Account filter
  if (accountFilter.value) {
    filtered = filtered.filter(d => d.account_number === accountFilter.value)
  }

  // Date range
  if (startDate.value) {
    filtered = filtered.filter(d => d.transaction_date >= startDate.value)
  }
  if (endDate.value) {
    filtered = filtered.filter(d => d.transaction_date <= endDate.value)
  }

  // Unmatched only
  if (showUnmatchedOnly.value) {
    filtered = filtered.filter(d => !d.category || d.category === '')
  }

  filteredDeposits.value = filtered
}

function startEdit(deposit) {
  editingId.value = deposit.transaction_id
  editForm.value = {
    description: deposit.description || '',
    category: deposit.category || '',
    verified: deposit.verified || false
  }
  
  // Focus the input field
  nextTick(() => {
    const input = document.querySelector('.edit-input')
    if (input) input.focus()
  })
}

function cancelEdit() {
  editingId.value = null
  editForm.value = {
    description: '',
    category: '',
    verified: false
  }
}

async function saveEdit(transactionId) {
  try {
    const response = await fetch(`/api/banking/transactions/${transactionId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(editForm.value)
    })

    if (!response.ok) {
      throw new Error('Failed to update transaction')
    }

    const result = await response.json()
    
    // Update local data
    const index = deposits.value.findIndex(d => d.transaction_id === transactionId)
    if (index !== -1) {
      deposits.value[index] = result.transaction
    }
    
    filterDeposits()
    cancelEdit()
    showSuccess('Deposit updated successfully')
  } catch (error) {
    console.error('Error saving deposit:', error)
    showError('Failed to update deposit')
  }
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleDateString('en-CA')
}

function formatCurrency(amount) {
  if (amount === null || amount === undefined) return '$0.00'
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
  }).format(amount)
}

function showSuccess(message) {
  successMessage.value = message
  setTimeout(() => { successMessage.value = '' }, 3000)
}

function showError(message) {
  errorMessage.value = message
  setTimeout(() => { errorMessage.value = '' }, 5000)
}

onMounted(() => {
  loadDeposits()
})
</script>

<style scoped>
.banking-deposits {
  padding: 1.5rem;
  max-width: 1800px;
  margin: 0 auto;
}

.deposits-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.deposits-header h2 {
  margin: 0;
  color: #2d3748;
}

.btn-refresh {
  padding: 0.5rem 1rem;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
}

.btn-refresh:hover {
  background: #5a67d8;
}

.filters {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  padding: 1rem;
  background: #f7fafc;
  border-radius: 8px;
}

.search-input,
.filter-select,
.date-input {
  padding: 0.5rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.9rem;
}

.search-input {
  flex: 1;
  min-width: 250px;
}

.search-amount {
  max-width: 160px;
  min-width: 140px;
}

.btn-search {
  background: #2b6cb0;
}

.btn-search:hover {
  background: #2c5282;
}

.btn-clear {
  background: #718096;
}

.btn-clear:hover {
  background: #4a5568;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
  cursor: pointer;
}

.table-container {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  overflow-x: auto;
}

.loading,
.no-data {
  text-align: center;
  padding: 3rem;
  color: #718096;
  font-style: italic;
}

.deposits-table {
  width: 100%;
  border-collapse: collapse;
}

.deposits-table thead {
  background: #2d3748;
  color: white;
  position: sticky;
  top: 0;
  z-index: 10;
}

.deposits-table th {
  padding: 1rem;
  text-align: left;
  font-weight: 600;
  font-size: 0.85rem;
  text-transform: uppercase;
}

.deposits-table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #e2e8f0;
  font-size: 0.9rem;
}

.deposits-table tr:hover {
  background: #f7fafc;
}

.editing-row {
  background: #fff3cd !important;
}

.description-cell {
  max-width: 400px;
}

.description-cell span {
  cursor: pointer;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  display: block;
}

.description-cell span:hover {
  background: #edf2f7;
}

.empty-description {
  color: #a0aec0;
  font-style: italic;
}

.edit-input {
  width: 100%;
  padding: 0.5rem;
  border: 2px solid #667eea;
  border-radius: 4px;
  font-size: 0.9rem;
}

.category-select {
  padding: 0.5rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.9rem;
}

.no-category {
  color: #a0aec0;
  font-style: italic;
}

.amount {
  text-align: right;
  font-weight: 600;
  font-family: 'Courier New', monospace;
  color: #22543d;
}

.verified-cell {
  text-align: center;
}

.verified-yes {
  color: #22543d;
  font-weight: 600;
}

.verified-no {
  color: #742a2a;
}

.actions {
  text-align: center;
  white-space: nowrap;
}

.btn-edit,
.btn-save,
.btn-cancel {
  padding: 0.25rem 0.75rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  margin: 0 0.25rem;
}

.btn-edit {
  background: #667eea;
  color: white;
}

.btn-edit:hover {
  background: #5a67d8;
}

.btn-save {
  background: #48bb78;
  color: white;
}

.btn-save:hover {
  background: #38a169;
}

.btn-cancel {
  background: #e2e8f0;
  color: #2d3748;
}

.btn-cancel:hover {
  background: #cbd5e0;
}

.summary {
  display: flex;
  gap: 2rem;
  margin-top: 1.5rem;
  padding: 1.5rem;
  background: #f7fafc;
  border-radius: 8px;
  flex-wrap: wrap;
}

.stat {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.stat-label {
  font-size: 0.85rem;
  color: #718096;
  font-weight: 500;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: 700;
  color: #2d3748;
}

.toast {
  position: fixed;
  top: 2rem;
  right: 2rem;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  animation: slideIn 0.3s ease-out;
}

.toast-success {
  background: #48bb78;
  color: white;
}

.toast-error {
  background: #f56565;
  color: white;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}
</style>
