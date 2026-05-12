<template>
  <div class="cash-box-management">
    <div class="header">
      <h1>Cash Box Management</h1>
      <div class="stats">
        <div class="stat-card">
          <div class="label">Total Cash In</div>
          <div class="value">${{ totalCashIn.toFixed(2) }}</div>
        </div>
        <div class="stat-card">
          <div class="label">Total Cash Out</div>
          <div class="value">${{ totalCashOut.toFixed(2) }}</div>
        </div>
        <div class="stat-card">
          <div class="label">Net Balance</div>
          <div class="value" :class="{ positive: netBalance >= 0, negative: netBalance < 0 }">
            ${{ netBalance.toFixed(2) }}
          </div>
        </div>
      </div>
    </div>

    <div class="actions">
      <button @click="showNewTransaction = true" class="btn btn-primary">
        New Transaction
      </button>
      <button @click="exportReport" class="btn btn-secondary">Export Report</button>
    </div>

    <div class="filters">
      <input
        v-model="filterDate"
        type="date"
        class="form-control"
        placeholder="Filter by date"
      />
      <select v-model="filterType" class="form-control">
        <option value="">All Types</option>
        <option value="cash_in">Cash In</option>
        <option value="cash_out">Cash Out</option>
      </select>
      <button @click="loadTransactions" class="btn btn-secondary">Filter</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Type</th>
          <th>Description</th>
          <th>Amount</th>
          <th>Balance</th>
          <th>Notes</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="tx in transactions" :key="tx.id" :class="{ 'cash-in': tx.type === 'cash_in', 'cash-out': tx.type === 'cash_out' }">
          <td>{{ formatDate(tx.date) }}</td>
          <td>
            <span :class="['badge', tx.type === 'cash_in' ? 'badge-success' : 'badge-danger']">
              {{ tx.type === 'cash_in' ? 'IN' : 'OUT' }}
            </span>
          </td>
          <td>{{ tx.description }}</td>
          <td>${{ parseFloat(tx.amount || 0).toFixed(2) }}</td>
          <td>${{ parseFloat(tx.balance || 0).toFixed(2) }}</td>
          <td>{{ tx.notes }}</td>
          <td>
            <button @click="editTransaction(tx)" class="btn btn-sm btn-info">Edit</button>
            <button @click="deleteTransaction(tx.id)" class="btn btn-sm btn-danger">Delete</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Transaction Modal -->
    <div v-if="showNewTransaction" class="modal">
      <div class="modal-content">
        <h2>{{ editingTx?.id ? 'Edit' : 'New' }} Transaction</h2>
        <form @submit.prevent="saveTransaction">
          <div class="form-group">
            <label>Date:</label>
            <input v-model="form.date" type="date" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Type:</label>
            <select v-model="form.type" class="form-control" required>
              <option value="">Select Type</option>
              <option value="cash_in">Cash In</option>
              <option value="cash_out">Cash Out</option>
            </select>
          </div>
          <div class="form-group">
            <label>Description:</label>
            <input v-model="form.description" type="text" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Amount:</label>
            <input v-model.number="form.amount" type="number" step="0.01" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Reference:</label>
            <input v-model="form.reference" type="text" class="form-control" placeholder="e.g., Charter #12345, Receipt #999" />
          </div>
          <div class="form-group">
            <label>Notes:</label>
            <textarea v-model="form.notes" class="form-control" rows="3"></textarea>
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary">Save</button>
            <button type="button" @click="showNewTransaction = false" class="btn btn-secondary">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showNewTransaction" class="modal-overlay" @click="showNewTransaction = false"></div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue';
import { authFetch } from '@/utils/authFetch';
import { useToast } from '@/composables/useToast';

export default {
  name: 'CashBoxManagement',
  setup() {
    const transactions = ref([]);
    const showNewTransaction = ref(false);
    const editingTx = ref(null);
    const { showToast } = useToast();

    const filterDate = ref('');
    const filterType = ref('');

    const form = ref({
      date: new Date().toISOString().split('T')[0],
      type: '',
      description: '',
      amount: 0,
      reference: '',
      notes: ''
    });

    const totalCashIn = computed(() => {
      return transactions.value
        .filter(tx => tx.type === 'cash_in')
        .reduce((sum, tx) => sum + parseFloat(tx.amount || 0), 0);
    });

    const totalCashOut = computed(() => {
      return transactions.value
        .filter(tx => tx.type === 'cash_out')
        .reduce((sum, tx) => sum + parseFloat(tx.amount || 0), 0);
    });

    const netBalance = computed(() => {
      return totalCashIn.value - totalCashOut.value;
    });

    const loadTransactions = async () => {
      try {
        let url = '/api/cash-box/transactions';
        const params = [];
        if (filterDate.value) params.push(`date=${filterDate.value}`);
        if (filterType.value) params.push(`type=${filterType.value}`);
        if (params.length) url += '?' + params.join('&');

        const res = await authFetch(url);
        if (!res || !res.ok) {
          throw new Error(`Failed to load transactions (${res?.status || 'no-response'})`);
        }
        transactions.value = await res.json();
      } catch (error) {
        showToast('Failed to load transactions', 'error');
      }
    };

    const saveTransaction = async () => {
      try {
        const method = editingTx.value ? 'PUT' : 'POST';
        const url = editingTx.value ? `/api/cash-box/transactions/${editingTx.value.id}` : '/api/cash-box/transactions';

        const res = await authFetch(url, {
          method,
          body: JSON.stringify(form.value)
        });
        if (!res || !res.ok) {
          throw new Error(`Failed to save transaction (${res?.status || 'no-response'})`);
        }

        showToast('Transaction saved', 'success');
        showNewTransaction.value = false;
        editingTx.value = null;
        loadTransactions();
      } catch (error) {
        showToast('Failed to save transaction', 'error');
      }
    };

    const editTransaction = (tx) => {
      editingTx.value = tx;
      Object.assign(form.value, tx);
      showNewTransaction.value = true;
    };

    const deleteTransaction = async (id) => {
      if (!confirm('Delete this transaction?')) return;
      try {
        const res = await authFetch(`/api/cash-box/transactions/${id}`, { method: 'DELETE' });
        if (!res || !res.ok) {
          throw new Error(`Failed to delete transaction (${res?.status || 'no-response'})`);
        }
        showToast('Transaction deleted', 'success');
        loadTransactions();
      } catch (error) {
        showToast('Failed to delete transaction', 'error');
      }
    };

    const exportReport = async () => {
      try {
        const csv = [
          ['Date', 'Type', 'Description', 'Amount', 'Balance', 'Notes'].join(','),
          ...transactions.value.map(tx =>
            [
              tx.date,
              tx.type,
              `"${tx.description}"`,
              tx.amount,
              tx.balance,
              `"${tx.notes || ''}"`
            ].join(',')
          )
        ].join('\n');

        const blob = new Blob([csv], { type: 'text/csv' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `cash-box-${new Date().toISOString().split('T')[0]}.csv`;
        a.click();
        showToast('Report exported', 'success');
      } catch (error) {
        showToast('Failed to export report', 'error');
      }
    };

    const formatDate = (date) => {
      return new Date(date).toLocaleDateString();
    };

    onMounted(() => {
      loadTransactions();
    });

    return {
      transactions,
      showNewTransaction,
      editingTx,
      filterDate,
      filterType,
      form,
      totalCashIn,
      totalCashOut,
      netBalance,
      loadTransactions,
      saveTransaction,
      editTransaction,
      deleteTransaction,
      exportReport,
      formatDate
    };
  }
};
</script>

<style scoped>
.cash-box-management {
  padding: 20px;
}

.header {
  margin-bottom: 30px;
}

.stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-top: 20px;
}

.stat-card {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
}

.stat-card .label {
  font-size: 14px;
  color: #666;
  margin-bottom: 10px;
}

.stat-card .value {
  font-size: 28px;
  font-weight: bold;
  color: #333;
}

.stat-card .value.positive {
  color: #28a745;
}

.stat-card .value.negative {
  color: #dc3545;
}

.actions {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.filters {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.form-control {
  flex: 1;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
}

.data-table th,
.data-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.data-table th {
  background-color: #f5f5f5;
  font-weight: bold;
}

.data-table tr.cash-in {
  background-color: #f0f8f5;
}

.data-table tr.cash-out {
  background-color: #fef5f5;
}

.badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.badge-success {
  background-color: #d4edda;
  color: #155724;
}

.badge-danger {
  background-color: #f8d7da;
  color: #721c24;
}

.modal {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: white;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  max-height: 90vh;
  overflow-y: auto;
  width: 90%;
  max-width: 600px;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 999;
}

.form-group {
  margin-bottom: 15px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
}

.form-group input,
.form-group select,
.form-group textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 20px;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background-color 0.2s;
}

.btn-primary {
  background-color: #007bff;
  color: white;
}

.btn-primary:hover {
  background-color: #0056b3;
}

.btn-secondary {
  background-color: #6c757d;
  color: white;
}

.btn-info {
  background-color: #17a2b8;
  color: white;
  padding: 4px 8px;
  font-size: 12px;
}

.btn-danger {
  background-color: #dc3545;
  color: white;
  padding: 4px 8px;
  font-size: 12px;
}

.btn-sm {
  padding: 4px 8px;
  font-size: 12px;
}
</style>
