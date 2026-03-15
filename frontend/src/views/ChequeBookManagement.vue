<template>
  <div class="cheque-book-management">
    <div class="page-header">
      <h1>📋 Cheque Book Management</h1>
      <p>Track and categorize cheques by bank, search by number/amount, mark NSF/void status</p>
    </div>

    <!-- Bank Account Summary -->
    <div class="bank-summary-section">
      <h2>Bank Accounts</h2>
      <div class="bank-cards">
        <div 
          v-for="bank in bankSummaries" 
          :key="bank.bank_account"
          class="bank-card"
          :class="{ active: selectedBank === bank.bank_account }"
          @click="selectBank(bank.bank_account)"
        >
          <div class="bank-header">
            <h3>{{ bank.bank_name }}</h3>
            <span class="account-num">{{ bank.bank_account }}</span>
          </div>
          <div class="bank-stats">
            <div class="stat">
              <span class="label">Total Cheques:</span>
              <span class="value">{{ bank.total_cheques }}</span>
            </div>
            <div class="stat">
              <span class="label">Range:</span>
              <span class="value">{{ bank.cheque_range }}</span>
            </div>
            <div class="stat">
              <span class="label">Categorized:</span>
              <span class="value">{{ bank.categorized }} / {{ bank.total_cheques }}</span>
              <span class="percentage">({{ Math.round(bank.categorized / bank.total_cheques * 100) }}%)</span>
            </div>
            <div class="stat">
              <span class="label">Unknown Payees:</span>
              <span class="value warning">{{ bank.unknown_payees }}</span>
            </div>
            <div class="stat">
              <span class="label">Total Amount:</span>
              <span class="value">${{ formatMoney(bank.total_amount) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Search Form -->
    <div class="search-section">
      <h2>Search Cheques</h2>
      <form @submit.prevent="searchCheques" class="search-form">
        <div class="form-row">
          <div class="form-group">
            <label>Cheque Number</label>
            <input 
              v-model="searchForm.cheque_number" 
              type="text" 
              placeholder="e.g., 123"
              class="form-control"
            />
          </div>
          
          <div class="form-group">
            <label>Amount</label>
            <input 
              v-model.number="searchForm.amount" 
              type="number" 
              step="0.01"
              placeholder="e.g., 250.00"
              class="form-control"
            />
          </div>
          
          <div class="form-group">
            <label>Payee</label>
            <input 
              v-model="searchForm.payee" 
              type="text" 
              placeholder="e.g., Dale Menard"
              class="form-control"
            />
          </div>
          
          <div class="form-group">
            <label>Status</label>
            <select v-model="searchForm.status" class="form-control">
              <option value="">All</option>
              <option value="cleared">Cleared</option>
              <option value="pending">Pending (Uncategorized)</option>
              <option value="nsf">NSF (Returned)</option>
              <option value="void">Void</option>
            </select>
          </div>
        </div>
        
        <div class="form-row">
          <div class="form-group">
            <label>Date From</label>
            <input 
              v-model="searchForm.date_from" 
              type="date" 
              class="form-control"
            />
          </div>
          
          <div class="form-group">
            <label>Date To</label>
            <input 
              v-model="searchForm.date_to" 
              type="date" 
              class="form-control"
            />
          </div>
          
          <div class="form-actions">
            <button type="submit" class="btn btn-primary">
              🔍 Search
            </button>
            <button type="button" @click="clearSearch" class="btn btn-secondary">
              Clear
            </button>
          </div>
        </div>
      </form>
    </div>

    <!-- Results Table -->
    <div v-if="cheques.length > 0" class="results-section">
      <div class="results-header">
        <h2>Cheques Found: {{ cheques.length }}</h2>
        <div class="bulk-actions">
          <button 
            @click="saveBulkUpdates" 
            class="btn btn-success"
            :disabled="!hasPendingChanges"
          >
            💾 Save All Changes ({{ pendingUpdates.length }})
          </button>
        </div>
      </div>

      <div class="table-container">
        <table class="cheque-table">
          <thead>
            <tr>
              <th>Cheque #</th>
              <th>Date</th>
              <th>Payee</th>
              <th>Amount</th>
              <th>Bank</th>
              <th>Status</th>
              <th>GL Code</th>
              <th>Balance After</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr 
              v-for="cheque in cheques" 
              :key="cheque.transaction_id"
              :class="{ 
                'has-changes': hasPendingUpdate(cheque.transaction_id),
                'status-nsf': cheque.status === 'NSF',
                'status-void': cheque.status === 'VOID',
                'status-pending': cheque.status === 'PENDING'
              }"
            >
              <td class="cheque-num">{{ cheque.cheque_number }}</td>
              <td>{{ formatDate(cheque.transaction_date) }}</td>
              <td>
                <input 
                  :value="getEditableValue(cheque.transaction_id, 'payee', cheque.payee)"
                  @input="markForUpdate(cheque, 'payee', $event.target.value)"
                  type="text"
                  class="inline-edit"
                  placeholder="Unknown"
                />
              </td>
              <td class="amount">${{ formatMoney(cheque.amount) }}</td>
              <td>{{ cheque.bank_name }}</td>
              <td>
                <select 
                  :value="getEditableValue(cheque.transaction_id, 'status', cheque.status)"
                  @change="markForUpdate(cheque, 'status', $event.target.value)"
                  class="status-select"
                  :class="`status-${(getEditableValue(cheque.transaction_id, 'status', cheque.status) || '').toLowerCase()}`"
                >
                  <option value="CLEARED">Cleared</option>
                  <option value="PENDING">Pending</option>
                  <option value="NSF">NSF</option>
                  <option value="VOID">Void</option>
                </select>
              </td>
              <td>
                <input 
                  :value="getEditableValue(cheque.transaction_id, 'gl_code', cheque.gl_code)"
                  @input="markForUpdate(cheque, 'gl_code', $event.target.value)"
                  type="text"
                  class="inline-edit gl-code"
                  placeholder="GL"
                  list="gl-codes"
                />
              </td>
              <td class="amount">${{ formatMoney(cheque.balance_after) }}</td>
              <td>
                <button 
                  @click="openEditModal(cheque)" 
                  class="btn-icon"
                  title="Edit Details"
                >
                  ✏️
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- GL Code datalist for autocomplete -->
      <datalist id="gl-codes">
        <option v-for="account in glAccounts" :key="account.account_code" :value="account.account_code">
          {{ account.account_code }} - {{ account.account_name }}
        </option>
      </datalist>
    </div>

    <!-- Edit Modal -->
    <div v-if="showEditModal" class="modal-overlay" @click.self="closeEditModal">
      <div class="modal-content">
        <div class="modal-header">
          <h3>Edit Cheque #{{ editingCheque?.cheque_number }}</h3>
          <button @click="closeEditModal" class="close-btn">&times;</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>Payee</label>
            <input 
              v-model="editForm.payee" 
              type="text"
              class="form-control"
              placeholder="Payee name"
            />
          </div>
          
          <div class="form-group">
            <label>Status</label>
            <select v-model="editForm.status" class="form-control">
              <option value="cleared">Cleared</option>
              <option value="pending">Pending</option>
              <option value="nsf">NSF (Returned)</option>
              <option value="void">Void</option>
            </select>
          </div>
          
          <div class="form-group">
            <label>GL Code</label>
            <input 
              v-model="editForm.gl_code" 
              type="text"
              class="form-control"
              placeholder="e.g., 5305"
              list="gl-codes"
            />
          </div>
          
          <div class="form-group">
            <label>Notes</label>
            <textarea 
              v-model="editForm.notes" 
              class="form-control"
              rows="3"
              placeholder="Additional notes about this cheque"
            ></textarea>
          </div>
          
          <div class="modal-info">
            <p><strong>Amount:</strong> ${{ formatMoney(editingCheque?.amount) }}</p>
            <p><strong>Date:</strong> {{ formatDate(editingCheque?.transaction_date) }}</p>
            <p><strong>Bank:</strong> {{ editingCheque?.bank_name }} ({{ editingCheque?.bank_account }})</p>
          </div>
        </div>
        <div class="modal-footer">
          <button @click="saveEdit" class="btn btn-primary">
            💾 Save Changes
          </button>
          <button @click="closeEditModal" class="btn btn-secondary">
            Cancel
          </button>
        </div>
      </div>
    </div>

    <!-- Loading Overlay -->
    <div v-if="loading" class="loading-overlay">
      <div class="spinner"></div>
      <p>Loading...</p>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';

export default {
  name: 'ChequeBookManagement',
  setup() {
    const bankSummaries = ref([]);
    const cheques = ref([]);
    const selectedBank = ref(null);
    const loading = ref(false);
    const showEditModal = ref(false);
    const editingCheque = ref(null);
    const pendingUpdates = ref(new Map());
    const glAccounts = ref([]);
    
    const searchForm = ref({
      cheque_number: '',
      amount: null,
      payee: '',
      bank_account: '',
      status: '',
      date_from: '',
      date_to: ''
    });
    
    const editForm = ref({
      payee: '',
      status: '',
      gl_code: '',
      notes: ''
    });

    const hasPendingChanges = computed(() => pendingUpdates.value.size > 0);

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

    const loadBankSummaries = async () => {
      loading.value = true;
      try {
        const response = await fetch('http://127.0.0.1:8000/api/cheque-books/summary');
        if (!response.ok) throw new Error('Failed to fetch');
        bankSummaries.value = await response.json();
      } catch (error) {
        console.error('Failed to load bank summaries:', error);
        alert('Failed to load bank summaries');
      } finally {
        loading.value = false;
      }
    };

    const selectBank = (accountNumber) => {
      selectedBank.value = accountNumber;
      searchForm.value.bank_account = accountNumber;
      searchCheques();
    };

    const searchCheques = async () => {
      loading.value = true;
      try {
        const response = await fetch('http://127.0.0.1:8000/api/cheque-books/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(searchForm.value)
        });
        if (!response.ok) throw new Error('Failed to fetch');
        cheques.value = await response.json();
        pendingUpdates.value.clear();
      } catch (error) {
        console.error('Failed to search cheques:', error);
        alert('Failed to search cheques');
      } finally {
        loading.value = false;
      }
    };

    const clearSearch = () => {
      searchForm.value = {
        cheque_number: '',
        amount: null,
        payee: '',
        bank_account: '',
        status: '',
        date_from: '',
        date_to: ''
      };
      cheques.value = [];
      selectedBank.value = null;
    };

    const markForUpdate = (cheque, field, value) => {
      const key = cheque.transaction_id;
      
      if (!pendingUpdates.value.has(key)) {
        pendingUpdates.value.set(key, {
          transaction_id: key,
          cheque_number: cheque.cheque_number,
          changes: {}
        });
      }
      
      const update = pendingUpdates.value.get(key);
      update.changes[field] = value;
      
      // Trigger reactivity
      pendingUpdates.value = new Map(pendingUpdates.value);
    };

    const getEditableValue = (transactionId, field, originalValue) => {
      const update = pendingUpdates.value.get(transactionId);
      if (update && field in update.changes) {
        return update.changes[field];
      }
      return originalValue;
    };

    const hasPendingUpdate = (transactionId) => {
      return pendingUpdates.value.has(transactionId);
    };

    const loadGLAccounts = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/table-management/chart-of-accounts');
        if (!response.ok) throw new Error('Failed to fetch');
        const data = await response.json();
        glAccounts.value = data.filter(acc => acc.is_active);
      } catch (error) {
        console.error('Error loading GL accounts:', error);
      }
    };

    const saveBulkUpdates = async () => {
      if (pendingUpdates.value.size === 0) return;
      
      loading.value = true;
      try {
        const updates = Array.from(pendingUpdates.value.values()).map(update => ({
          cheque_number: update.cheque_number,
          ...update.changes
        }));
        
        const response = await fetch('http://127.0.0.1:8000/api/cheque-books/bulk-update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updates)
        });
        if (!response.ok) throw new Error('Failed to fetch');
        const data = await response.json();
        
        if (data.success) {
          alert(`Successfully updated ${data.updated} cheques!`);
          pendingUpdates.value.clear();
          // Refresh search results
          await searchCheques();
        }
        
        if (response.data.errors && response.data.errors.length > 0) {
          console.warn('Some updates failed:', response.data.errors);
        }
      } catch (error) {
        console.error('Bulk update failed:', error);
        alert('Failed to save changes. Please try again.');
      } finally {
        loading.value = false;
      }
    };

    const openEditModal = (cheque) => {
      editingCheque.value = cheque;
      editForm.value = {
        payee: cheque.payee || '',
        status: cheque.status?.toLowerCase() || 'pending',
        gl_code: cheque.gl_code || '',
        notes: cheque.notes || ''
      };
      showEditModal.value = true;
    };

    const closeEditModal = () => {
      showEditModal.value = false;
      editingCheque.value = null;
    };

    const saveEdit = async () => {
      if (!editingCheque.value) return;
      
      loading.value = true;
      try {
        const response = await fetch(`http://127.0.0.1:8000/api/cheque-books/${editingCheque.value.transaction_id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            cheque_number: editingCheque.value.cheque_number,
            ...editForm.value
          })
        });
        if (!response.ok) throw new Error('Failed to fetch');
        
        alert('Cheque updated successfully!');
        closeEditModal();
        await searchCheques();
      } catch (error) {
        console.error('Failed to update cheque:', error);
        alert('Failed to update cheque');
      } finally {
        loading.value = false;
      }
    };

    onMounted(() => {
      loadBankSummaries();
      loadGLAccounts();
    });

    return {
      bankSummaries,
      cheques,
      selectedBank,
      loading,
      searchForm,
      showEditModal,
      editingCheque,
      editForm,
      pendingUpdates,
      glAccounts,
      hasPendingChanges,
      formatMoney,
      formatDate,
      selectBank,
      searchCheques,
      clearSearch,
      markForUpdate,
      getEditableValue,
      hasPendingUpdate,
      saveBulkUpdates,
      openEditModal,
      closeEditModal,
      saveEdit
    };
  }
};
</script>

<style scoped>
.cheque-book-management {
  padding: 20px;
  max-width: 1600px;
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

/* Bank Summary Section */
.bank-summary-section {
  margin-bottom: 30px;
}

.bank-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 20px;
}

.bank-card {
  background: white;
  border: 2px solid #e2e8f0;
  border-radius: 8px;
  padding: 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.bank-card:hover {
  border-color: #3b82f6;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.bank-card.active {
  border-color: #2563eb;
  background: #eff6ff;
}

.bank-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid #e2e8f0;
}

.bank-header h3 {
  margin: 0;
  color: #1e3a8a;
}

.account-num {
  font-family: 'Courier New', monospace;
  color: #64748b;
  font-size: 14px;
}

.bank-stats {
  display: grid;
  gap: 8px;
}

.stat {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}

.stat .label {
  color: #64748b;
}

.stat .value {
  font-weight: 600;
  color: #1e3a8a;
}

.stat .value.warning {
  color: #dc2626;
}

.stat .percentage {
  color: #059669;
  margin-left: 8px;
}

/* Search Section */
.search-section {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.search-form {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  align-items: end;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group label {
  font-weight: 600;
  margin-bottom: 5px;
  color: #475569;
  font-size: 14px;
}

.form-control {
  padding: 8px 12px;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  font-size: 14px;
}

.form-control:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-actions {
  display: flex;
  gap: 10px;
}

.btn {
  padding: 8px 16px;
  border-radius: 4px;
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

.btn-primary:hover {
  background: #2563eb;
}

.btn-secondary {
  background: #e2e8f0;
  color: #475569;
}

.btn-secondary:hover {
  background: #cbd5e1;
}

.btn-success {
  background: #10b981;
  color: white;
}

.btn-success:hover {
  background: #059669;
}

.btn-success:disabled {
  background: #cbd5e1;
  cursor: not-allowed;
}

/* Results Section */
.results-section {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.results-header h2 {
  margin: 0;
  color: #1e3a8a;
}

.table-container {
  overflow-x: auto;
}

.cheque-table {
  width: 100%;
  border-collapse: collapse;
}

.cheque-table th {
  background: #f1f5f9;
  padding: 12px;
  text-align: left;
  font-weight: 600;
  color: #475569;
  border-bottom: 2px solid #cbd5e1;
  font-size: 13px;
}

.cheque-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #e2e8f0;
  font-size: 14px;
}

.cheque-table tr.has-changes {
  background: #fef3c7;
}

.cheque-table tr.status-nsf {
  background: #fee2e2;
}

.cheque-table tr.status-void {
  background: #f3f4f6;
  opacity: 0.7;
}

.cheque-table tr.status-pending {
  background: #fef9c3;
}

.cheque-num {
  font-family: 'Courier New', monospace;
  font-weight: 600;
  color: #1e3a8a;
}

.amount {
  text-align: right;
  font-family: 'Courier New', monospace;
}

.inline-edit {
  width: 100%;
  padding: 4px 8px;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  font-size: 13px;
}

.inline-edit:focus {
  outline: none;
  border-color: #3b82f6;
}

.inline-edit.gl-code {
  width: 80px;
  font-family: 'Courier New', monospace;
}

.status-select {
  padding: 4px 8px;
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
}

.status-select.status-cleared {
  background: #d1fae5;
  color: #065f46;
}

.status-select.status-pending {
  background: #fef9c3;
  color: #854d0e;
}

.status-select.status-nsf {
  background: #fee2e2;
  color: #991b1b;
}

.status-select.status-void {
  background: #f3f4f6;
  color: #6b7280;
}

.btn-icon {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  padding: 4px;
}

.btn-icon:hover {
  transform: scale(1.2);
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e2e8f0;
}

.modal-header h3 {
  margin: 0;
  color: #1e3a8a;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #64748b;
}

.close-btn:hover {
  color: #1e3a8a;
}

.modal-body {
  padding: 20px;
}

.modal-info {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e2e8f0;
}

.modal-info p {
  margin: 5px 0;
  color: #64748b;
}

.modal-footer {
  padding: 20px;
  border-top: 1px solid #e2e8f0;
  display: flex;
  gap: 10px;
  justify-content: flex-end;
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
  flex-direction: column;
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
