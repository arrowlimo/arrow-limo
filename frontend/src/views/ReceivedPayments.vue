<template>
  <div class="received-payments">
    <div class="page-header">
      <h1>💰 Record Received Payment</h1>
      <p>Enter customer payments received (cheques, cash, e-transfers)</p>
    </div>

    <!-- Quick Entry Form -->
    <div class="entry-form">
      <h2>New Payment</h2>
      
      <form @submit.prevent="recordPayment" class="payment-form">
        <div class="form-row">
          <div class="form-group required">
            <label>Amount Received</label>
            <div class="input-with-prefix">
              <span class="prefix">$</span>
              <input 
                v-model.number="form.amount" 
                type="number" 
                step="0.01"
                min="0.01"
                required
                class="form-control"
                placeholder="0.00"
                @input="calculateGST"
              />
            </div>
            <div v-if="gstAmount > 0" class="hint">
              Includes GST: ${{ formatMoney(gstAmount) }} 
              <span class="subtle">(Net: ${{ formatMoney(form.amount - gstAmount) }})</span>
            </div>
          </div>
          
          <div class="form-group required">
            <label>Date Received</label>
            <input 
              v-model="form.payment_date" 
              type="date"
              required
              class="form-control"
            />
          </div>
          
          <div class="form-group required">
            <label>Payment Method</label>
            <select v-model="form.payment_method" required class="form-control">
              <option value="cheque">Cheque</option>
              <option value="cash">Cash</option>
              <option value="e-transfer">E-Transfer</option>
              <option value="credit_card">Credit Card</option>
              <option value="debit">Debit</option>
              <option value="wire_transfer">Wire Transfer</option>
            </select>
          </div>
        </div>

        <div class="form-row">
          <div class="form-group required">
            <label>Paid By (Customer/Company Name)</label>
            <input 
              v-model="form.payer_name" 
              type="text"
              required
              class="form-control"
              placeholder="e.g., Essential Coil Well"
              list="customer-names"
            />
            <datalist id="customer-names">
              <option v-for="customer in recentCustomers" :key="customer" :value="customer" />
            </datalist>
          </div>
        </div>

        <!-- Cheque-Specific Fields -->
        <div v-if="form.payment_method === 'cheque'" class="cheque-details">
          <h3>Cheque Details</h3>
          <div class="form-row">
            <div class="form-group">
              <label>Cheque Number</label>
              <input 
                v-model="form.cheque_number" 
                type="text"
                class="form-control"
                placeholder="e.g., 1234"
              />
            </div>
            
            <div class="form-group">
              <label>Bank Name</label>
              <input 
                v-model="form.bank_name" 
                type="text"
                class="form-control"
                placeholder="e.g., TD Canada Trust"
              />
            </div>
          </div>
        </div>

        <!-- Allocation Section -->
        <div class="allocation-section">
          <h3>Allocate Payment (Optional)</h3>
          <div class="form-row">
            <div class="form-group">
              <label>Reserve Number</label>
              <input 
                v-model="form.reserve_number" 
                type="text"
                class="form-control"
                placeholder="e.g., 012345"
                @blur="lookupCharter"
              />
              <div v-if="charterInfo" class="charter-info">
                ✓ Found: {{ charterInfo.customer_name }} - {{ formatDate(charterInfo.pickup_date) }} 
                ({{ formatMoney(charterInfo.total_amount) }})
              </div>
            </div>
            
            <div class="form-group">
              <label>Payment Type</label>
              <select v-model="form.deposit_type" class="form-control">
                <option value="payment">Full Payment</option>
                <option value="deposit">Deposit</option>
                <option value="partial_payment">Partial Payment</option>
              </select>
            </div>
          </div>
        </div>

        <!-- Additional Notes -->
        <div class="form-group">
          <label>Additional Notes</label>
          <textarea 
            v-model="form.notes" 
            class="form-control"
            rows="3"
            placeholder="Additional details about this payment..."
          ></textarea>
        </div>

        <!-- Action Buttons -->
        <div class="form-actions">
          <button type="submit" class="btn btn-primary" :disabled="loading">
            <span v-if="loading">💾 Saving...</span>
            <span v-else>💾 Record Payment</span>
          </button>
          <button type="button" @click="clearForm" class="btn btn-secondary">
            Clear Form
          </button>
        </div>
      </form>
    </div>

    <!-- Recent Payments List -->
    <div class="recent-payments">
      <div class="section-header">
        <h2>Recent Payments</h2>
        <div class="filters">
          <input 
            v-model="searchQuery" 
            type="text" 
            placeholder="Search by payer or cheque #"
            class="search-input"
          />
          <button @click="showUnallocated = !showUnallocated" class="btn btn-filter">
            <span v-if="showUnallocated">📋 Show All</span>
            <span v-else>⚠️ Unallocated Only</span>
          </button>
          <button @click="loadRecentPayments" class="btn btn-secondary">
            🔄 Refresh
          </button>
        </div>
      </div>

      <div class="table-container">
        <table class="payments-table">
          <thead>
            <tr>
              <th>Date</th>
              <th>Payer</th>
              <th>Amount</th>
              <th>Method</th>
              <th>Cheque #</th>
              <th>Reserve #</th>
              <th>Type</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr 
              v-for="payment in filteredPayments" 
              :key="payment.payment_id"
              :class="{ 'unallocated': !payment.charter_id }"
            >
              <td>{{ formatDate(payment.payment_date) }}</td>
              <td>{{ payment.payer_name }}</td>
              <td class="amount">${{ formatMoney(payment.amount) }}</td>
              <td>{{ formatPaymentMethod(payment.payment_method) }}</td>
              <td>{{ payment.cheque_number || '-' }}</td>
              <td>{{ payment.reserve_number || '-' }}</td>
              <td>{{ formatDepositType(payment.deposit_type) }}</td>
              <td>
                <span v-if="payment.charter_id" class="status allocated">✓ Allocated</span>
                <span v-else class="status unallocated">⚠ Unallocated</span>
              </td>
              <td>
                <button @click="editPayment(payment)" class="btn-icon" title="Edit">
                  ✏️
                </button>
                <button @click="deletePayment(payment)" class="btn-icon danger" title="Delete">
                  🗑️
                </button>
              </td>
            </tr>
          </tbody>
        </table>

        <div v-if="filteredPayments.length === 0" class="empty-state">
          <p>No payments found</p>
        </div>
      </div>

      <!-- Summary -->
      <div v-if="filteredPayments.length > 0" class="payments-summary">
        <div class="summary-item">
          <span class="label">Total Shown:</span>
          <span class="value">${{ formatMoney(totalShown) }}</span>
        </div>
        <div class="summary-item">
          <span class="label">Allocated:</span>
          <span class="value">${{ formatMoney(totalAllocated) }}</span>
        </div>
        <div class="summary-item warning">
          <span class="label">Unallocated:</span>
          <span class="value">${{ formatMoney(totalUnallocated) }}</span>
        </div>
      </div>
    </div>

    <!-- Success Message -->
    <div v-if="successMessage" class="success-toast">
      ✓ {{ successMessage }}
    </div>

    <!-- Loading Overlay -->
    <div v-if="loading" class="loading-overlay">
      <div class="spinner"></div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import axios from 'axios';

export default {
  name: 'ReceivedPayments',
  setup() {
    const form = ref({
      amount: null,
      payment_date: new Date().toISOString().split('T')[0],
      payment_method: 'cheque',
      payer_name: '',
      cheque_number: '',
      bank_name: '',
      reserve_number: '',
      charter_id: null,
      deposit_type: 'payment',
      notes: ''
    });

    const payments = ref([]);
    const recentCustomers = ref([]);
    const charterInfo = ref(null);
    const loading = ref(false);
    const successMessage = ref('');
    const searchQuery = ref('');
    const showUnallocated = ref(false);
    const gstAmount = ref(0);

    const filteredPayments = computed(() => {
      let filtered = payments.value;

      if (showUnallocated.value) {
        filtered = filtered.filter(p => !p.charter_id);
      }

      if (searchQuery.value) {
        const query = searchQuery.value.toLowerCase();
        filtered = filtered.filter(p =>
          p.payer_name?.toLowerCase().includes(query) ||
          p.cheque_number?.toLowerCase().includes(query) ||
          p.reserve_number?.toLowerCase().includes(query)
        );
      }

      return filtered;
    });

    const totalShown = computed(() =>
      filteredPayments.value.reduce((sum, p) => sum + p.amount, 0)
    );

    const totalAllocated = computed(() =>
      filteredPayments.value.filter(p => p.charter_id).reduce((sum, p) => sum + p.amount, 0)
    );

    const totalUnallocated = computed(() =>
      filteredPayments.value.filter(p => !p.charter_id).reduce((sum, p) => sum + p.amount, 0)
    );

    const calculateGST = () => {
      if (form.value.amount) {
        // GST = amount / 1.05 * 0.05
        gstAmount.value = form.value.amount / 1.05 * 0.05;
      } else {
        gstAmount.value = 0;
      }
    };

    const formatMoney = (amount) => {
      return new Intl.NumberFormat('en-CA', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      }).format(amount || 0);
    };

    const formatDate = (dateStr) => {
      if (!dateStr) return 'N/A';
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-CA');
    };

    const formatPaymentMethod = (method) => {
      const methods = {
        'cheque': 'Cheque',
        'cash': 'Cash',
        'e-transfer': 'E-Transfer',
        'credit_card': 'Credit Card',
        'debit': 'Debit',
        'wire_transfer': 'Wire Transfer'
      };
      return methods[method] || method;
    };

    const formatDepositType = (type) => {
      const types = {
        'payment': 'Full Payment',
        'deposit': 'Deposit',
        'partial_payment': 'Partial'
      };
      return types[type] || type;
    };

    const lookupCharter = async () => {
      if (!form.value.reserve_number) {
        charterInfo.value = null;
        form.value.charter_id = null;
        return;
      }

      try {
        const response = await axios.get(`/api/charters/search`, {
          params: { q: form.value.reserve_number, limit: 1 }
        });

        if (response.data.charters && response.data.charters.length > 0) {
          charterInfo.value = response.data.charters[0];
          form.value.charter_id = charterInfo.value.charter_id;
        } else {
          charterInfo.value = null;
          form.value.charter_id = null;
          alert('Reserve number not found');
        }
      } catch (error) {
        console.error('Failed to lookup charter:', error);
        charterInfo.value = null;
        form.value.charter_id = null;
      }
    };

    const recordPayment = async () => {
      loading.value = true;
      try {
        const response = await axios.post('/api/received-payments/', form.value);

        if (response.data.success) {
          successMessage.value = `Payment of $${formatMoney(form.value.amount)} from ${form.value.payer_name} recorded!`;
          setTimeout(() => successMessage.value = '', 3000);

          clearForm();
          await loadRecentPayments();
        }
      } catch (error) {
        console.error('Failed to record payment:', error);
        alert('Failed to record payment. Please try again.');
      } finally {
        loading.value = false;
      }
    };

    const loadRecentPayments = async () => {
      loading.value = true;
      try {
        const response = await axios.get('/api/received-payments/search', {
          params: { limit: 100 }
        });
        payments.value = response.data;

        // Extract unique customer names
        const names = new Set();
        payments.value.forEach(p => {
          if (p.payer_name) names.add(p.payer_name);
        });
        recentCustomers.value = Array.from(names).sort();
      } catch (error) {
        console.error('Failed to load payments:', error);
      } finally {
        loading.value = false;
      }
    };

    const clearForm = () => {
      form.value = {
        amount: null,
        payment_date: new Date().toISOString().split('T')[0],
        payment_method: 'cheque',
        payer_name: '',
        cheque_number: '',
        bank_name: '',
        reserve_number: '',
        charter_id: null,
        deposit_type: 'payment',
        notes: ''
      };
      charterInfo.value = null;
      gstAmount.value = 0;
    };

    const editPayment = (payment) => {
      // TODO: Implement edit functionality
      alert('Edit functionality coming soon');
    };

    const deletePayment = async (payment) => {
      if (!confirm(`Delete payment of $${formatMoney(payment.amount)} from ${payment.payer_name}?`)) {
        return;
      }

      try {
        await axios.delete(`/api/received-payments/${payment.payment_id}`);
        successMessage.value = 'Payment deleted';
        setTimeout(() => successMessage.value = '', 3000);
        await loadRecentPayments();
      } catch (error) {
        console.error('Failed to delete payment:', error);
        alert('Failed to delete payment');
      }
    };

    onMounted(() => {
      loadRecentPayments();
    });

    return {
      form,
      payments,
      recentCustomers,
      charterInfo,
      loading,
      successMessage,
      searchQuery,
      showUnallocated,
      gstAmount,
      filteredPayments,
      totalShown,
      totalAllocated,
      totalUnallocated,
      calculateGST,
      formatMoney,
      formatDate,
      formatPaymentMethod,
      formatDepositType,
      lookupCharter,
      recordPayment,
      loadRecentPayments,
      clearForm,
      editPayment,
      deletePayment
    };
  }
};
</script>

<style scoped>
.received-payments {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 30px;
}

.page-header h1 {
  color: #1e3a8a;
  margin: 0 0 10px 0;
}

.page-header p {
  color: #64748b;
  margin: 0;
}

/* Entry Form */
.entry-form {
  background: white;
  border-radius: 8px;
  padding: 25px;
  margin-bottom: 30px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.entry-form h2, .entry-form h3 {
  color: #1e3a8a;
  margin-top: 0;
}

.entry-form h3 {
  font-size: 16px;
  margin: 20px 0 10px 0;
  padding-top: 15px;
  border-top: 1px solid #e2e8f0;
}

.payment-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group.required label::after {
  content: ' *';
  color: #dc2626;
}

.form-group label {
  font-weight: 600;
  margin-bottom: 6px;
  color: #475569;
  font-size: 14px;
}

.form-control {
  padding: 10px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  font-size: 14px;
}

.form-control:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.input-with-prefix {
  position: relative;
  display: flex;
}

.input-with-prefix .prefix {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #64748b;
  font-weight: 600;
}

.input-with-prefix input {
  padding-left: 30px;
}

.hint {
  font-size: 12px;
  color: #64748b;
  margin-top: 4px;
}

.hint .subtle {
  color: #94a3b8;
}

.cheque-details, .allocation-section {
  background: #f8fafc;
  padding: 15px;
  border-radius: 6px;
  margin-top: 10px;
}

.charter-info {
  margin-top: 6px;
  padding: 8px 12px;
  background: #d1fae5;
  color: #065f46;
  border-radius: 4px;
  font-size: 13px;
}

.form-actions {
  display: flex;
  gap: 10px;
  padding-top: 10px;
}

.btn {
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.btn-primary {
  background: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-primary:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

.btn-secondary {
  background: #e2e8f0;
  color: #475569;
}

.btn-secondary:hover {
  background: #cbd5e1;
}

/* Recent Payments */
.recent-payments {
  background: white;
  border-radius: 8px;
  padding: 25px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h2 {
  color: #1e3a8a;
  margin: 0;
}

.filters {
  display: flex;
  gap: 10px;
}

.search-input {
  padding: 8px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  width: 250px;
}

.btn-filter {
  background: #fef3c7;
  color: #92400e;
}

.btn-filter:hover {
  background: #fde68a;
}

.table-container {
  overflow-x: auto;
}

.payments-table {
  width: 100%;
  border-collapse: collapse;
}

.payments-table th {
  background: #f1f5f9;
  padding: 12px;
  text-align: left;
  font-weight: 600;
  color: #475569;
  border-bottom: 2px solid #cbd5e1;
  font-size: 13px;
}

.payments-table td {
  padding: 12px;
  border-bottom: 1px solid #e2e8f0;
  font-size: 14px;
}

.payments-table tr.unallocated {
  background: #fef9c3;
}

.amount {
  text-align: right;
  font-family: 'Courier New', monospace;
  font-weight: 600;
}

.status {
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
}

.status.allocated {
  background: #d1fae5;
  color: #065f46;
}

.status.unallocated {
  background: #fee2e2;
  color: #991b1b;
}

.btn-icon {
  background: none;
  border: none;
  font-size: 16px;
  cursor: pointer;
  padding: 4px;
  margin: 0 2px;
}

.btn-icon:hover {
  transform: scale(1.2);
}

.btn-icon.danger:hover {
  filter: brightness(1.2);
}

.empty-state {
  text-align: center;
  padding: 40px;
  color: #64748b;
}

.payments-summary {
  display: flex;
  gap: 30px;
  padding-top: 20px;
  margin-top: 20px;
  border-top: 2px solid #e2e8f0;
}

.summary-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.summary-item.warning {
  color: #dc2626;
}

.summary-item .label {
  font-size: 13px;
  color: #64748b;
}

.summary-item .value {
  font-size: 20px;
  font-weight: 600;
  font-family: 'Courier New', monospace;
}

/* Success Toast */
.success-toast {
  position: fixed;
  bottom: 30px;
  right: 30px;
  background: #10b981;
  color: white;
  padding: 15px 25px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  animation: slideIn 0.3s ease-out;
  z-index: 1000;
}

@keyframes slideIn {
  from {
    transform: translateX(400px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

/* Loading */
.loading-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.spinner {
  width: 50px;
  height: 50px;
  border: 4px solid #e2e8f0;
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
