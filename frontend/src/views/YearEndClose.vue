<template>
  <div class="year-end-close">
    <div class="header">
      <h1>Year-End Close</h1>
      <div class="fiscal-year">
        <label>Fiscal Year:</label>
        <select v-model.number="selectedYear" class="form-control">
          <option v-for="year in availableYears" :key="year" :value="year">
            {{ year }}
          </option>
        </select>
      </div>
    </div>

    <div class="close-status">
      <div v-if="closeStatus" :class="['status-card', `status-${closeStatus.status}`]">
        <h3>Close Status: {{ closeStatus.status }}</h3>
        <p>{{ closeStatus.message }}</p>
        <div v-if="closeStatus.summary" class="summary">
          <div>Total Revenue: ${{ closeStatus.summary.total_revenue }}</div>
          <div>Total Expenses: ${{ closeStatus.summary.total_expenses }}</div>
          <div>Net Income: ${{ closeStatus.summary.net_income }}</div>
          <div v-if="closeStatus.summary.closed_at">
            Closed: {{ formatDate(closeStatus.summary.closed_at) }}
          </div>
        </div>
      </div>
    </div>

    <div class="checklist">
      <h2>Pre-Close Checklist</h2>
      <div class="checklist-items">
        <div v-for="item in checklistItems" :key="item.id" class="checklist-item">
          <input
            type="checkbox"
            :id="`item-${item.id}`"
            v-model="item.completed"
            @change="updateChecklist(item)"
          />
          <label :for="`item-${item.id}`">{{ item.title }}</label>
          <span class="description">{{ item.description }}</span>
        </div>
      </div>
    </div>

    <div class="financial-summary">
      <h2>Financial Summary</h2>
      <table class="summary-table">
        <tbody>
          <tr>
            <th>Revenue</th>
            <td>${{ summary.revenue.toFixed(2) }}</td>
          </tr>
          <tr>
            <th>Expenses</th>
            <td>${{ summary.expenses.toFixed(2) }}</td>
          </tr>
          <tr class="total-row">
            <th>Net Income</th>
            <td>${{ summary.net_income.toFixed(2) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="actions">
      <button
        @click="performPreCloseValidation"
        class="btn btn-secondary"
        :disabled="!allChecklistsComplete"
      >
        Validate Before Close
      </button>
      <button
        @click="executeYearEndClose"
        class="btn btn-primary"
        :disabled="!validationPassed"
      >
        Execute Year-End Close
      </button>
      <button @click="generateCloseReport" class="btn btn-secondary">
        Generate Report
      </button>
    </div>

    <div v-if="validationErrors.length" class="errors">
      <h3>Validation Errors</h3>
      <ul>
        <li v-for="(error, index) in validationErrors" :key="index">
          {{ error }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch } from 'vue';
import { authFetch } from '@/utils/authFetch';
import { useToast } from '@/composables/useToast';

export default {
  name: 'YearEndClose',
  setup() {
    const selectedYear = ref(new Date().getFullYear());
    const closeStatus = ref(null);
    const checklistItems = ref([
      {
        id: 1,
        title: 'Reconcile all accounts',
        description: 'Ensure all bank accounts and general ledger accounts are reconciled',
        completed: false
      },
      {
        id: 2,
        title: 'Review accounts receivable',
        description: 'Check for outstanding invoices and bad debts',
        completed: false
      },
      {
        id: 3,
        title: 'Review accounts payable',
        description: 'Verify all vendor invoices are recorded',
        completed: false
      },
      {
        id: 4,
        title: 'Inventory count',
        description: 'Physical inventory count and valuation complete',
        completed: false
      },
      {
        id: 5,
        title: 'Accruals review',
        description: 'Review and record all necessary accruals',
        completed: false
      },
      {
        id: 6,
        title: 'Depreciation calculation',
        description: 'Calculate and record depreciation entries',
        completed: false
      },
      {
        id: 7,
        title: 'Cut-off testing',
        description: 'Ensure transactions are in correct period',
        completed: false
      },
      {
        id: 8,
        title: 'Review for contingencies',
        description: 'Identify and disclose contingencies',
        completed: false
      }
    ]);
    const validationPassed = ref(false);
    const validationErrors = ref([]);
    const { showToast } = useToast();

    const availableYears = computed(() => {
      const current = new Date().getFullYear();
      return [current - 1, current, current + 1];
    });

    const summary = ref({
      revenue: 0,
      expenses: 0,
      net_income: 0
    });

    const allChecklistsComplete = computed(() => {
      return checklistItems.value.every(item => item.completed);
    });

    const parseApiResponse = async (res) => {
      if (!res) throw new Error('No response received');
      if (!res.ok) {
        const txt = await res.text().catch(() => 'Request failed');
        throw new Error(txt || `Request failed (${res.status})`);
      }
      return res.json();
    };

    const mergeChecklistFromApi = (items) => {
      const byId = new Map((items || []).map((i) => [Number(i.item_id), i]));
      checklistItems.value = checklistItems.value.map((item) => {
        const remote = byId.get(Number(item.id));
        return remote
          ? {
              ...item,
              title: remote.title || item.title,
              description: remote.description || item.description,
              completed: Boolean(remote.completed)
            }
          : item;
      });
    };

    const loadCloseStatus = async () => {
      try {
        const statusRes = await authFetch(`/api/year-end/status/${selectedYear.value}`);
        const statusJson = await parseApiResponse(statusRes);
        closeStatus.value = statusJson;

        if (statusJson.summary) {
          summary.value = {
            revenue: Number(statusJson.summary.total_revenue || 0),
            expenses: Number(statusJson.summary.total_expenses || 0),
            net_income: Number(statusJson.summary.net_income || 0)
          };
        }

        const checklistRes = await authFetch(`/api/year-end/checklist/${selectedYear.value}`);
        const checklistJson = await parseApiResponse(checklistRes);
        mergeChecklistFromApi(checklistJson.items || []);

        validationPassed.value = false;
        validationErrors.value = [];
      } catch (error) {
        showToast(`Failed to load close status: ${error?.message || error}`, 'error');
      }
    };

    const updateChecklist = async (item) => {
      try {
        const res = await authFetch(`/api/year-end/checklist/${selectedYear.value}`, {
          method: 'POST',
          body: JSON.stringify({
            item_id: Number(item.id),
            title: item.title,
            description: item.description,
            completed: Boolean(item.completed)
          })
        });
        await parseApiResponse(res);
      } catch (error) {
        item.completed = !item.completed;
        showToast(`Failed to update checklist item: ${error?.message || error}`, 'error');
      }
    };

    const performPreCloseValidation = async () => {
      try {
        validationErrors.value = [];
        
        // Example validations
        if (summary.value.revenue === 0) {
          validationErrors.value.push('No revenue recorded for this period');
        }

        if (!allChecklistsComplete.value) {
          validationErrors.value.push('Not all pre-close checklist items are complete');
        }

        if (validationErrors.value.length === 0) {
          validationPassed.value = true;
          showToast('Validation passed', 'success');
        } else {
          showToast(`${validationErrors.value.length} validation errors found`, 'warning');
        }
      } catch (error) {
        showToast('Validation failed', 'error');
      }
    };

    const executeYearEndClose = async () => {
      if (!confirm(`Close fiscal year ${selectedYear.value}? This cannot be undone.`)) {
        return;
      }

      try {
        const res = await authFetch('/api/year-end/close', {
          method: 'POST',
          body: JSON.stringify({ fiscal_year: selectedYear.value })
        });
        const json = await parseApiResponse(res);

        showToast('Year-end close executed', 'success');
        closeStatus.value = {
          ...closeStatus.value,
          ...json
        };
        await loadCloseStatus();
      } catch (error) {
        showToast(`Failed to execute close: ${error?.message || error}`, 'error');
      }
    };

    const generateCloseReport = async () => {
      try {
        const res = await authFetch(`/api/year-end/report/${selectedYear.value}`);
        const report = await parseApiResponse(res);
        const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `year-end-close-${selectedYear.value}.json`;
        a.click();
        window.URL.revokeObjectURL(url);
        showToast('Report generated', 'success');
      } catch (error) {
        showToast(`Failed to generate report: ${error?.message || error}`, 'error');
      }
    };

    const formatDate = (date) => {
      return new Date(date).toLocaleDateString();
    };

    onMounted(() => {
      loadCloseStatus();
    });

    watch(selectedYear, () => {
      loadCloseStatus();
    });

    return {
      selectedYear,
      availableYears,
      closeStatus,
      checklistItems,
      validationPassed,
      validationErrors,
      summary,
      allChecklistsComplete,
      loadCloseStatus,
      updateChecklist,
      performPreCloseValidation,
      executeYearEndClose,
      generateCloseReport,
      formatDate
    };
  }
};
</script>

<style scoped>
.year-end-close {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
}

.fiscal-year {
  display: flex;
  gap: 10px;
  align-items: center;
}

.fiscal-year label {
  font-weight: 500;
}

.form-control {
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.close-status {
  margin-bottom: 30px;
}

.status-card {
  padding: 20px;
  border-radius: 8px;
  border-left: 4px solid;
}

.status-card.status-open {
  background-color: #e7f3ff;
  border-left-color: #0066cc;
}

.status-card.status-closed {
  background-color: #d4edda;
  border-left-color: #28a745;
}

.status-card h3 {
  margin-top: 0;
}

.summary {
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid rgba(0, 0, 0, 0.1);
}

.summary div {
  margin: 5px 0;
}

.checklist {
  margin-bottom: 30px;
  background: #f9f9f9;
  padding: 20px;
  border-radius: 8px;
}

.checklist h2 {
  margin-top: 0;
}

.checklist-items {
  display: grid;
  gap: 15px;
}

.checklist-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.checklist-item input[type='checkbox'] {
  margin-top: 5px;
  cursor: pointer;
}

.checklist-item label {
  font-weight: 500;
  cursor: pointer;
  flex: 1;
}

.description {
  display: block;
  font-size: 13px;
  color: #666;
  margin-left: 24px;
  margin-top: 3px;
}

.financial-summary {
  margin-bottom: 30px;
}

.summary-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 15px;
}

.summary-table tr {
  border-bottom: 1px solid #ddd;
}

.summary-table th {
  text-align: left;
  padding: 12px;
  background-color: #f5f5f5;
  font-weight: 600;
}

.summary-table td {
  text-align: right;
  padding: 12px;
}

.summary-table tr.total-row {
  background-color: #f5f5f5;
  font-weight: 600;
  border-top: 2px solid #ddd;
}

.actions {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.btn {
  padding: 10px 20px;
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

.btn-primary:hover:not(:disabled) {
  background-color: #0056b3;
}

.btn-primary:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.btn-secondary {
  background-color: #6c757d;
  color: white;
}

.btn-secondary:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.errors {
  background-color: #f8d7da;
  border: 1px solid #f5c6cb;
  border-radius: 4px;
  padding: 15px;
  color: #721c24;
}

.errors h3 {
  margin-top: 0;
}

.errors ul {
  margin: 10px 0;
  padding-left: 20px;
}

.errors li {
  margin: 5px 0;
}
</style>
