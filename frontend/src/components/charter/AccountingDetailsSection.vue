<template>
  <div class="accounting-details-section">
    <h2>💰 Accounting & Payment Details</h2>
    
    <div class="accounting-grid">
      <!-- Payment Status -->
      <div class="form-field">
        <label>Payment Status</label>
        <select 
          :value="paymentStatus"
          @change="$emit('update:paymentStatus', $event.target.value)"
        >
          <option value="pending">Pending</option>
          <option value="partial">Partial Payment</option>
          <option value="paid">Paid in Full</option>
          <option value="overdue">Overdue</option>
          <option value="refunded">Refunded</option>
        </select>
      </div>

      <div class="form-field">
        <label>Invoice Number</label>
        <input 
          type="text"
          :value="invoiceNumber"
          @input="$emit('update:invoiceNumber', $event.target.value)"
          placeholder="INV-XXXXX"
        />
      </div>

      <div class="form-field">
        <label>Invoice Date</label>
        <input 
          type="date"
          :value="invoiceDate"
          @input="$emit('update:invoiceDate', $event.target.value)"
        />
      </div>

      <!-- Payment Details -->
      <div class="form-field">
        <label>Amount Due</label>
        <input 
          type="number"
          step="0.01"
          :value="amountDue"
          readonly
          class="readonly-field amount-highlight"
        />
      </div>

      <div class="form-field">
        <label>Amount Paid</label>
        <input 
          type="number"
          step="0.01"
          :value="amountPaid"
          @input="$emit('update:amountPaid', parseFloat($event.target.value) || 0)"
          placeholder="0.00"
        />
      </div>

      <div class="form-field">
        <label>Balance Remaining</label>
        <input 
          type="number"
          step="0.01"
          :value="balanceRemaining"
          readonly
          class="readonly-field balance-highlight"
        />
      </div>

      <!-- Payment Methods -->
      <div class="form-field full-width">
        <h3>Payment Methods</h3>
      </div>

      <div class="form-field">
        <label>Primary Payment Method</label>
        <select 
          :value="paymentMethod"
          @change="$emit('update:paymentMethod', $event.target.value)"
        >
          <option value="">-- Select Method --</option>
          <option value="cash">Cash</option>
          <option value="credit_card">Credit Card</option>
          <option value="debit_card">Debit Card</option>
          <option value="cheque">Cheque</option>
          <option value="etransfer">E-Transfer</option>
          <option value="wire_transfer">Wire Transfer</option>
          <option value="account">Account/Invoice</option>
        </select>
      </div>

      <div class="form-field" v-if="paymentMethod === 'cheque'">
        <label>Cheque Number</label>
        <input 
          type="text"
          :value="chequeNumber"
          @input="$emit('update:chequeNumber', $event.target.value)"
          placeholder="Cheque #"
        />
      </div>

      <div class="form-field" v-if="['credit_card', 'debit_card'].includes(paymentMethod)">
        <label>Last 4 Digits</label>
        <input 
          type="text"
          :value="cardLast4"
          @input="$emit('update:cardLast4', $event.target.value)"
          placeholder="****"
          maxlength="4"
        />
      </div>

      <div class="form-field" v-if="paymentMethod === 'etransfer'">
        <label>E-Transfer Reference</label>
        <input 
          type="text"
          :value="eTransferRef"
          @input="$emit('update:eTransferRef', $event.target.value)"
          placeholder="Reference/Confirmation"
        />
      </div>

      <!-- Deposit/Retainer -->
      <div class="form-field">
        <label>Deposit/Retainer Received</label>
        <input 
          type="number"
          step="0.01"
          :value="depositAmount"
          @input="$emit('update:depositAmount', parseFloat($event.target.value) || 0)"
          placeholder="0.00"
        />
      </div>

      <div class="form-field">
        <label>Deposit Date</label>
        <input 
          type="date"
          :value="depositDate"
          @input="$emit('update:depositDate', $event.target.value)"
        />
      </div>

      <div class="form-field">
        <label>Deposit Method</label>
        <select 
          :value="depositMethod"
          @change="$emit('update:depositMethod', $event.target.value)"
        >
          <option value="">-- Select --</option>
          <option value="cash">Cash</option>
          <option value="credit_card">Credit Card</option>
          <option value="debit_card">Debit Card</option>
          <option value="etransfer">E-Transfer</option>
        </select>
      </div>

      <!-- Gratuity -->
      <div class="form-field">
        <label>Gratuity/Tip (Cash)</label>
        <input 
          type="number"
          step="0.01"
          :value="gratuityAmount"
          @input="$emit('update:gratuityAmount', parseFloat($event.target.value) || 0)"
          placeholder="0.00"
        />
      </div>

      <div class="form-field">
        <label class="checkbox-label">
          <input 
            type="checkbox"
            :checked="gratuityOnCard"
            @change="$emit('update:gratuityOnCard', $event.target.checked)"
          />
          Gratuity on Card
        </label>
      </div>

      <!-- GL Accounts -->
      <div class="form-field full-width">
        <h3>GL Account Codes</h3>
      </div>

      <div class="form-field">
        <label>Revenue Account</label>
        <select 
          :value="revenueAccount"
          @change="$emit('update:revenueAccount', $event.target.value)"
        >
          <option value="">-- Select Account --</option>
          <option value="4000">4000 - Charter Revenue</option>
          <option value="4100">4100 - Airport Transfer Revenue</option>
          <option value="4200">4200 - Long Distance Revenue</option>
          <option value="4300">4300 - Standby Revenue</option>
        </select>
      </div>

      <div class="form-field">
        <label>Expense Account (Driver Pay)</label>
        <select 
          :value="expenseAccount"
          @change="$emit('update:expenseAccount', $event.target.value)"
        >
          <option value="">-- Select Account --</option>
          <option value="5100">5100 - Driver Wages</option>
          <option value="5110">5110 - Driver Overtime</option>
          <option value="5120">5120 - Contractor Payments</option>
        </select>
      </div>

      <div class="form-field">
        <label>Tax Code</label>
        <select 
          :value="taxCode"
          @change="$emit('update:taxCode', $event.target.value)"
        >
          <option value="GST">GST (5%)</option>
          <option value="EXEMPT">GST Exempt</option>
          <option value="ZERO">Zero-Rated</option>
        </select>
      </div>

      <!-- Notes -->
      <div class="form-field full-width">
        <label>Accounting Notes</label>
        <textarea
          :value="accountingNotes"
          @input="$emit('update:accountingNotes', $event.target.value)"
          rows="3"
          placeholder="Special accounting instructions, cost center allocations, etc..."
        ></textarea>
      </div>

      <!-- Summary Box -->
      <div class="summary-box full-width">
        <div class="summary-row">
          <span class="summary-label">Subtotal:</span>
          <span class="summary-value">${{ subtotal.toFixed(2) }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">GST (5%):</span>
          <span class="summary-value">${{ gstAmount.toFixed(2) }}</span>
        </div>
        <div class="summary-row">
          <span class="summary-label">Gratuity:</span>
          <span class="summary-value">${{ gratuityAmount.toFixed(2) }}</span>
        </div>
        <div class="summary-row total">
          <span class="summary-label">Total:</span>
          <span class="summary-value">${{ totalAmount.toFixed(2) }}</span>
        </div>
        <div class="summary-row paid">
          <span class="summary-label">Paid:</span>
          <span class="summary-value">-${{ amountPaid.toFixed(2) }}</span>
        </div>
        <div class="summary-row balance">
          <span class="summary-label">Balance Due:</span>
          <span class="summary-value">${{ balanceRemaining.toFixed(2) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  paymentStatus: String,
  invoiceNumber: String,
  invoiceDate: String,
  amountDue: Number,
  amountPaid: Number,
  paymentMethod: String,
  chequeNumber: String,
  cardLast4: String,
  eTransferRef: String,
  depositAmount: Number,
  depositDate: String,
  depositMethod: String,
  gratuityAmount: Number,
  gratuityOnCard: Boolean,
  revenueAccount: String,
  expenseAccount: String,
  taxCode: String,
  accountingNotes: String,
  subtotal: Number,
  gstAmount: Number
})

defineEmits([
  'update:paymentStatus',
  'update:invoiceNumber',
  'update:invoiceDate',
  'update:amountPaid',
  'update:paymentMethod',
  'update:chequeNumber',
  'update:cardLast4',
  'update:eTransferRef',
  'update:depositAmount',
  'update:depositDate',
  'update:depositMethod',
  'update:gratuityAmount',
  'update:gratuityOnCard',
  'update:revenueAccount',
  'update:expenseAccount',
  'update:taxCode',
  'update:accountingNotes'
])

const totalAmount = computed(() => {
  return (props.subtotal || 0) + (props.gstAmount || 0) + (props.gratuityAmount || 0)
})

const balanceRemaining = computed(() => {
  return totalAmount.value - (props.amountPaid || 0)
})
</script>

<style scoped>
.accounting-details-section {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  border: 2px solid #48bb78;
}

.accounting-details-section h2 {
  margin: 0 0 0.75rem 0;
  color: #2d3748;
  font-size: 1.3rem;
}

.accounting-details-section h3 {
  margin: 0;
  color: #2d3748;
  font-size: 1.1rem;
  font-weight: 600;
}

.accounting-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
}

.form-field {
  display: flex;
  flex-direction: column;
}

.form-field.full-width {
  grid-column: 1 / -1;
}

.form-field label {
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: #2d3748;
  font-size: 0.85rem;
}

.form-field input,
.form-field select,
.form-field textarea {
  width: 100%;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.9rem;
}

.form-field input:focus,
.form-field select:focus,
.form-field textarea:focus {
  outline: none;
  border-color: #48bb78;
  box-shadow: 0 0 0 3px rgba(72, 187, 120, 0.1);
}

.readonly-field {
  background: #f7fafc;
  cursor: not-allowed;
  font-weight: 600;
}

.amount-highlight {
  color: #667eea;
  font-size: 1.1rem;
}

.balance-highlight {
  color: #f56565;
  font-size: 1.1rem;
}

textarea {
  resize: vertical;
  font-family: inherit;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-weight: 600;
}

.checkbox-label input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}

.summary-box {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1rem;
  border-radius: 8px;
  margin-top: 0.5rem;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  padding: 0.4rem 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.summary-row:last-child {
  border-bottom: none;
}

.summary-row.total {
  font-size: 1.2rem;
  font-weight: 700;
  padding-top: 0.75rem;
  border-top: 2px solid rgba(255, 255, 255, 0.4);
  margin-top: 0.5rem;
}

.summary-row.paid {
  color: #9ae6b4;
}

.summary-row.balance {
  font-size: 1.3rem;
  font-weight: 700;
  background: rgba(255, 255, 255, 0.1);
  padding: 0.75rem;
  margin-top: 0.5rem;
  border-radius: 4px;
}

.summary-label {
  font-weight: 600;
}

.summary-value {
  font-weight: 700;
}
</style>
