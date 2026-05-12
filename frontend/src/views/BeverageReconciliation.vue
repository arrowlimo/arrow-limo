<template>
  <div class="beverage-reconciliation">
    <div class="header">
      <h1>Beverage Reconciliation</h1>
      <button @click="startNewReconciliation" class="btn btn-primary">
        Start Reconciliation
      </button>
    </div>

    <div class="filters">
      <input v-model="filterDate" type="date" class="form-control" />
      <select v-model="filterStatus" class="form-control">
        <option value="">All Status</option>
        <option value="pending">Pending</option>
        <option value="reconciled">Reconciled</option>
        <option value="variance">Variance Found</option>
      </select>
      <button @click="loadReconciliations" class="btn btn-secondary">Filter</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Period</th>
          <th>Expected Inventory</th>
          <th>Actual Count</th>
          <th>Variance</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="reconciliation in reconciliations" :key="reconciliation.id">
          <td>{{ formatDate(reconciliation.date) }}</td>
          <td>{{ reconciliation.period }}</td>
          <td>{{ reconciliation.expected_count }}</td>
          <td>{{ reconciliation.actual_count }}</td>
          <td :class="{ variance: reconciliation.variance !== 0 }">
            {{ reconciliation.variance > 0 ? '+' : '' }}{{ reconciliation.variance }}
          </td>
          <td>
            <span :class="['badge', `badge-${statusColor(reconciliation.status)}`]">
              {{ reconciliation.status }}
            </span>
          </td>
          <td>
            <button @click="viewDetails(reconciliation)" class="btn btn-sm btn-info">
              View
            </button>
            <button v-if="reconciliation.status !== 'reconciled'" @click="editReconciliation(reconciliation)" class="btn btn-sm btn-primary">
              Edit
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Reconciliation Details Modal -->
    <div v-if="showDetails" class="modal">
      <div class="modal-content">
        <h2>Reconciliation Details</h2>
        <div class="details-view">
          <div class="detail-row">
            <span class="label">Date:</span>
            <span>{{ formatDate(selectedReconciliation?.date) }}</span>
          </div>
          <div class="detail-row">
            <span class="label">Period:</span>
            <span>{{ selectedReconciliation?.period }}</span>
          </div>
          <div class="detail-row">
            <span class="label">Expected Count:</span>
            <span>{{ selectedReconciliation?.expected_count }}</span>
          </div>
          <div class="detail-row">
            <span class="label">Actual Count:</span>
            <span>{{ selectedReconciliation?.actual_count }}</span>
          </div>
          <div class="detail-row">
            <span class="label">Variance:</span>
            <span :class="{ variance: selectedReconciliation?.variance !== 0 }">
              {{ selectedReconciliation?.variance > 0 ? '+' : '' }}{{ selectedReconciliation?.variance }}
            </span>
          </div>
          <div class="detail-row">
            <span class="label">Notes:</span>
            <span>{{ selectedReconciliation?.notes }}</span>
          </div>
        </div>
        <button @click="showDetails = false" class="btn btn-secondary">Close</button>
      </div>
    </div>

    <!-- Edit Reconciliation Modal -->
    <div v-if="showEditForm" class="modal">
      <div class="modal-content">
        <h2>Edit Reconciliation</h2>
        <form @submit.prevent="saveReconciliation">
          <div class="form-group">
            <label>Date:</label>
            <input v-model="reconcilForm.date" type="date" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Period:</label>
            <input v-model="reconcilForm.period" type="text" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Expected Inventory Count:</label>
            <input v-model.number="reconcilForm.expected_count" type="number" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Actual Count:</label>
            <input v-model.number="reconcilForm.actual_count" type="number" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Notes:</label>
            <textarea v-model="reconcilForm.notes" class="form-control" rows="4"></textarea>
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary">Save</button>
            <button type="button" @click="showEditForm = false" class="btn btn-secondary">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showDetails || showEditForm" class="modal-overlay" @click="closeModals"></div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { authFetch } from '@/utils/authFetch';
import { useToast } from '@/composables/useToast';

export default {
  name: 'BeverageReconciliation',
  setup() {
    const reconciliations = ref([]);
    const showDetails = ref(false);
    const showEditForm = ref(false);
    const selectedReconciliation = ref(null);
    const { showToast } = useToast();

    const filterDate = ref('');
    const filterStatus = ref('');

    const reconcilForm = ref({
      date: new Date().toISOString().split('T')[0],
      period: '',
      expected_count: 0,
      actual_count: 0,
      notes: ''
    });

    const loadReconciliations = async () => {
      try {
        let url = '/api/beverage/reconciliations';
        const params = [];
        if (filterDate.value) params.push(`date=${filterDate.value}`);
        if (filterStatus.value) params.push(`status=${filterStatus.value}`);
        if (params.length) url += '?' + params.join('&');

        const res = await authFetch(url);
        if (!res || !res.ok) {
          throw new Error(`Failed to load reconciliations (${res?.status || 'no-response'})`);
        }
        reconciliations.value = await res.json();
      } catch (error) {
        showToast('Failed to load reconciliations', 'error');
      }
    };

    const startNewReconciliation = () => {
      reconcilForm.value = {
        date: new Date().toISOString().split('T')[0],
        period: '',
        expected_count: 0,
        actual_count: 0,
        notes: ''
      };
      showEditForm.value = true;
    };

    const viewDetails = (reconciliation) => {
      selectedReconciliation.value = reconciliation;
      showDetails.value = true;
    };

    const editReconciliation = (reconciliation) => {
      Object.assign(reconcilForm.value, reconciliation);
      showEditForm.value = true;
    };

    const saveReconciliation = async () => {
      try {
        const method = reconcilForm.value.id ? 'PUT' : 'POST';
        const url = reconcilForm.value.id
          ? `/api/beverage/reconciliations/${reconcilForm.value.id}`
          : '/api/beverage/reconciliations';

        const res = await authFetch(url, {
          method,
          body: JSON.stringify(reconcilForm.value)
        });
        if (!res || !res.ok) {
          throw new Error(`Failed to save reconciliation (${res?.status || 'no-response'})`);
        }

        showToast('Reconciliation saved', 'success');
        showEditForm.value = false;
        loadReconciliations();
      } catch (error) {
        showToast('Failed to save reconciliation', 'error');
      }
    };

    const closeModals = () => {
      showDetails.value = false;
      showEditForm.value = false;
    };

    const statusColor = (status) => {
      switch (status) {
        case 'reconciled':
          return 'success';
        case 'variance':
          return 'warning';
        default:
          return 'info';
      }
    };

    const formatDate = (date) => {
      return new Date(date).toLocaleDateString();
    };

    onMounted(() => {
      loadReconciliations();
    });

    return {
      reconciliations,
      showDetails,
      showEditForm,
      selectedReconciliation,
      filterDate,
      filterStatus,
      reconcilForm,
      loadReconciliations,
      startNewReconciliation,
      viewDetails,
      editReconciliation,
      saveReconciliation,
      closeModals,
      statusColor,
      formatDate
    };
  }
};
</script>

<style scoped>
.beverage-reconciliation {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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

.variance {
  color: #dc3545;
  font-weight: bold;
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

.badge-warning {
  background-color: #fff3cd;
  color: #856404;
}

.badge-info {
  background-color: #d1ecf1;
  color: #0c5460;
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

.details-view {
  margin: 20px 0;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #eee;
}

.detail-row .label {
  font-weight: 500;
  color: #666;
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

.btn-sm {
  padding: 4px 8px;
  font-size: 12px;
}
</style>
