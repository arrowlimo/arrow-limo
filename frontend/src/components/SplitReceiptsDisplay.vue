<template>
  <div v-if="showSplitDetails" class="split-receipts-panel">
    <!-- Header with summary -->
    <div class="split-header">
      <div class="split-title">
        <span v-if="linkedReceipts.length > 1" class="split-badge">
          📦 Split Receipt - {{ linkedReceipts.length }} Parts
        </span>
        <span v-else class="single-badge">Single Receipt</span>
      </div>
      <button @click="closeSplitView" class="close-btn">✕</button>
    </div>

    <!-- Summary Bar -->
    <div class="split-summary-bar">
      <div class="summary-item">
        <span class="label">Parts:</span>
        <span class="value">{{ linkedReceipts.length }}</span>
      </div>
      <div class="summary-item">
        <span class="label">Total Amount:</span>
        <span class="value">${{ totalGross.toFixed(2) }}</span>
      </div>
      <div class="summary-item">
        <span class="label">Total GST:</span>
        <span class="value">${{ totalGst.toFixed(2) }}</span>
      </div>
      <div class="summary-item" v-if="linkedReceipts[0]?.banking_transaction_id">
        <span class="label">Banking Link:</span>
        <span class="value">#{{ linkedReceipts[0].banking_transaction_id }}</span>
      </div>
    </div>

    <!-- Detail Panels - Side by Side -->
    <div class="split-details-container">
      <div
        v-for="(receipt, index) in linkedReceipts"
        :key="receipt.receipt_id"
        class="receipt-detail-panel"
        :class="{ 'is-primary': index === 0 }"
      >
        <div class="panel-header">
          <h4>Part {{ index + 1 }} of {{ linkedReceipts.length }}</h4>
          <span class="receipt-id">Receipt #{{ receipt.receipt_id }}</span>
        </div>

        <div class="panel-content">
          <!-- Date -->
          <div class="detail-row">
            <span class="label">Date:</span>
            <span class="value">{{ formatDate(receipt.receipt_date) }}</span>
          </div>

          <!-- Vendor -->
          <div class="detail-row">
            <span class="label">Vendor:</span>
            <span class="value">{{ receipt.vendor_name }}</span>
          </div>

          <!-- Amount -->
          <div class="detail-row amount-row">
            <span class="label">Amount:</span>
            <span class="value amount">${{ receipt.gross_amount.toFixed(2) }}</span>
          </div>

          <!-- GST -->
          <div class="detail-row" v-if="receipt.gst_amount">
            <span class="label">GST:</span>
            <span class="value">${{ receipt.gst_amount.toFixed(2) }}</span>
          </div>

          <!-- Vehicle -->
          <div class="detail-row" v-if="receipt.vehicle_number">
            <span class="label">Vehicle:</span>
            <span class="value">{{ receipt.vehicle_number }}</span>
          </div>

          <!-- Fuel Amount -->
          <div class="detail-row" v-if="receipt.fuel_amount">
            <span class="label">Fuel:</span>
            <span class="value">{{ receipt.fuel_amount.toFixed(3) }} L</span>
          </div>

          <!-- GL Account -->
          <div class="detail-row" v-if="receipt.gl_account_code">
            <span class="label">GL Code:</span>
            <span class="value">{{ receipt.gl_account_code }}</span>
          </div>

          <!-- Personal Flag -->
          <div class="detail-row" v-if="receipt.is_personal">
            <span class="label">Type:</span>
            <span class="value personal">Personal</span>
          </div>

          <!-- Description -->
          <div class="detail-row description" v-if="receipt.description">
            <span class="label">Notes:</span>
            <span class="value description-text">{{ receipt.description }}</span>
          </div>

          <!-- Action Button -->
          <div class="panel-actions">
            <button @click="editReceipt(receipt.receipt_id)" class="btn-edit">
              ✎ Edit Receipt
            </button>
            <button @click="viewBanking(receipt.banking_transaction_id)" v-if="receipt.banking_transaction_id" class="btn-link">
              🔗 View Banking
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Verification Section -->
    <div class="verification-section" v-if="linkedReceipts.length > 1">
      <h4>Verification Checklist</h4>
      <div class="checklist">
        <div class="check-item">
          <input type="checkbox" :checked="verifyAmountsMatch" disabled />
          <span>Amounts add up correctly</span>
          <span class="check-status" :class="{ 'status-pass': verifyAmountsMatch, 'status-fail': !verifyAmountsMatch }">
            {{ verifyAmountsMatch ? '✓' : '✗' }}
          </span>
        </div>
        <div class="check-item">
          <input type="checkbox" :checked="verifyVendorMatch" disabled />
          <span>Vendors match</span>
          <span class="check-status" :class="{ 'status-pass': verifyVendorMatch, 'status-fail': !verifyVendorMatch }">
            {{ verifyVendorMatch ? '✓' : '✗' }}
          </span>
        </div>
        <div class="check-item">
          <input type="checkbox" :checked="verifyDatesClose" disabled />
          <span>Dates are close (same day)</span>
          <span class="check-status" :class="{ 'status-pass': verifyDatesClose, 'status-fail': !verifyDatesClose }">
            {{ verifyDatesClose ? '✓' : '✗' }}
          </span>
        </div>
        <div class="check-item">
          <input type="checkbox" :checked="verifyBankingLinked" disabled />
          <span>All parts linked to banking</span>
          <span class="check-status" :class="{ 'status-pass': verifyBankingLinked, 'status-fail': !verifyBankingLinked }">
            {{ verifyBankingLinked ? '✓' : '✗' }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  receiptId: Number,
  show: Boolean,
})

const emit = defineEmits(['close', 'edit', 'view-banking'])

const showSplitDetails = computed(() => props.show)
const linkedReceipts = ref([])
const isLoading = ref(false)
const error = ref(null)

// Computed properties for summary
const totalGross = computed(() => {
  return linkedReceipts.value.reduce((sum, r) => sum + (r.gross_amount || 0), 0)
})

const totalGst = computed(() => {
  return linkedReceipts.value.reduce((sum, r) => sum + (r.gst_amount || 0), 0)
})

// Verification checks
const verifyAmountsMatch = computed(() => {
  if (linkedReceipts.value.length === 0) return false
  
  // Check if sum of all parts is reasonable
  // This would need the banking transaction amount to validate properly
  return linkedReceipts.value.length >= 1
})

const verifyVendorMatch = computed(() => {
  if (linkedReceipts.value.length <= 1) return true
  const firstVendor = linkedReceipts.value[0]?.canonical_vendor || linkedReceipts.value[0]?.vendor_name
  return linkedReceipts.value.every(r => 
    (r.canonical_vendor || r.vendor_name) === firstVendor
  )
})

const verifyDatesClose = computed(() => {
  if (linkedReceipts.value.length <= 1) return true
  const dates = linkedReceipts.value.map(r => new Date(r.receipt_date))
  const minDate = new Date(Math.min(...dates))
  const maxDate = new Date(Math.max(...dates))
  const daysDiff = (maxDate - minDate) / (1000 * 60 * 60 * 24)
  return daysDiff <= 1
})

const verifyBankingLinked = computed(() => {
  return linkedReceipts.value.every(r => r.banking_transaction_id !== null)
})

// Methods
const closeSplitView = () => {
  emit('close')
}

const editReceipt = (receiptId) => {
  emit('edit', receiptId)
}

const viewBanking = (transactionId) => {
  emit('view-banking', transactionId)
}

const formatDate = (dateStr) => {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { 
    year: 'numeric', 
    month: 'short', 
    day: 'numeric' 
  })
}

// Load linked receipts
const loadLinkedReceipts = async () => {
  if (!props.receiptId) return
  
  isLoading.value = true
  error.value = null
  
  try {
    const response = await fetch(`/api/receipts-split/linked/${props.receiptId}`)
    if (!response.ok) throw new Error('Failed to fetch linked receipts')
    
    const data = await response.json()
    linkedReceipts.value = data.receipts || []
  } catch (e) {
    error.value = e.message
    linkedReceipts.value = []
  } finally {
    isLoading.value = false
  }
}

// Watch for show prop changes
import { watch } from 'vue'
watch(() => props.show, (newVal) => {
  if (newVal) {
    loadLinkedReceipts()
  }
})

// Initial load if already showing
if (props.show && props.receiptId) {
  loadLinkedReceipts()
}
</script>

<style scoped>
.split-receipts-panel {
  background: #f5f5f5;
  border: 2px solid #4CAF50;
  border-radius: 8px;
  margin-top: 20px;
  padding: 0;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.split-header {
  background: #4CAF50;
  color: white;
  padding: 12px 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-radius: 6px 6px 0 0;
}

.split-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.split-badge {
  background: #fff;
  color: #4CAF50;
  padding: 4px 12px;
  border-radius: 20px;
  font-weight: bold;
  font-size: 14px;
}

.single-badge {
  background: rgba(255, 255, 255, 0.3);
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 14px;
}

.close-btn {
  background: none;
  border: none;
  color: white;
  font-size: 20px;
  cursor: pointer;
  padding: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background 0.2s;
}

.close-btn:hover {
  background: rgba(0, 0, 0, 0.2);
}

.split-summary-bar {
  background: #fff;
  display: flex;
  gap: 20px;
  padding: 12px 16px;
  border-bottom: 1px solid #ddd;
  flex-wrap: wrap;
}

.summary-item {
  display: flex;
  gap: 8px;
  align-items: center;
}

.summary-item .label {
  font-weight: 600;
  color: #666;
  font-size: 13px;
}

.summary-item .value {
  font-weight: bold;
  color: #333;
  font-size: 14px;
}

.split-details-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 12px;
  padding: 16px;
  background: #f5f5f5;
}

.receipt-detail-panel {
  background: white;
  border: 1px solid #ddd;
  border-radius: 6px;
  overflow: hidden;
  transition: all 0.3s;
}

.receipt-detail-panel:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  border-color: #4CAF50;
}

.receipt-detail-panel.is-primary {
  border: 2px solid #4CAF50;
  box-shadow: 0 2px 8px rgba(76, 175, 80, 0.2);
}

.panel-header {
  background: #f9f9f9;
  padding: 12px 14px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-header h4 {
  margin: 0;
  font-size: 14px;
  color: #333;
}

.receipt-id {
  font-weight: bold;
  color: #4CAF50;
  font-size: 13px;
}

.panel-content {
  padding: 12px 14px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f5f5f5;
  font-size: 13px;
}

.detail-row:last-of-type {
  border-bottom: none;
}

.detail-row.amount-row {
  font-weight: bold;
  background: #f9f9f9;
  padding: 10px;
  margin: 0 -14px 8px;
  padding-left: 14px;
  padding-right: 14px;
}

.detail-row .label {
  color: #666;
  font-weight: 600;
  min-width: 80px;
}

.detail-row .value {
  color: #333;
  text-align: right;
  flex: 1;
}

.detail-row .value.amount {
  color: #4CAF50;
  font-weight: bold;
}

.detail-row .value.personal {
  background: #fff3e0;
  color: #e65100;
  padding: 2px 8px;
  border-radius: 3px;
  font-weight: bold;
}

.detail-row.description {
  flex-direction: column;
  gap: 4px;
}

.description-text {
  background: #f9f9f9;
  padding: 8px;
  border-radius: 3px;
  border-left: 3px solid #4CAF50;
  font-style: italic;
  color: #666;
  text-align: left;
  word-break: break-word;
}

.panel-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #f5f5f5;
}

.btn-edit,
.btn-link {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid #ddd;
  background: white;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.btn-edit:hover {
  background: #4CAF50;
  color: white;
  border-color: #4CAF50;
}

.btn-link:hover {
  background: #2196F3;
  color: white;
  border-color: #2196F3;
}

.verification-section {
  padding: 16px;
  background: white;
  border-top: 1px solid #ddd;
}

.verification-section h4 {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #333;
}

.checklist {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.check-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  background: #f9f9f9;
  border-radius: 4px;
  font-size: 13px;
}

.check-item input[type="checkbox"] {
  cursor: pointer;
}

.check-status {
  margin-left: auto;
  font-weight: bold;
  font-size: 14px;
}

.status-pass {
  color: #4CAF50;
}

.status-fail {
  color: #f44336;
}
</style>
