<template>
  <div class="tax-management">
    <div class="header">
      <h1>Tax Management</h1>
      <div class="tabs">
        <button
          :class="['tab', { active: activeTab === 'T4' }]"
          @click="activeTab = 'T4'"
        >
          T4 Forms
        </button>
        <button
          :class="['tab', { active: activeTab === 'T2' }]"
          @click="activeTab = 'T2'"
        >
          T2 Returns
        </button>
      </div>
    </div>

    <!-- T4 FORMS TAB -->
    <div v-if="activeTab === 'T4'" class="tab-content">
      <div class="actions">
        <button @click="showT4Form = true" class="btn btn-primary">
          New T4 Entry
        </button>
        <button @click="generateT4PDF" class="btn btn-secondary">
          Generate PDF
        </button>
      </div>

      <div class="search-bar">
        <select v-model="t4Filters.year" class="form-control">
          <option value="">All Years</option>
          <option value="2024">2024</option>
          <option value="2025">2025</option>
          <option value="2026">2026</option>
        </select>
        <button @click="loadT4Data" class="btn btn-secondary">Search</button>
      </div>

      <table class="data-table">
        <thead>
          <tr>
            <th>Employee</th>
            <th>Tax Year</th>
            <th>Box 14 (Income)</th>
            <th>Box 16 (CPP)</th>
            <th>Box 18 (EI)</th>
            <th>Box 22 (Tax)</th>
            <th>Auto Calc</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in t4Data" :key="`${entry.employee_id}-${entry.tax_year}`">
            <td>{{ entry.employee_name }}</td>
            <td>{{ entry.tax_year }}</td>
            <td>${{ parseFloat(entry.box14 || 0).toFixed(2) }}</td>
            <td>${{ parseFloat(entry.box16 || 0).toFixed(2) }}</td>
            <td>${{ parseFloat(entry.box18 || 0).toFixed(2) }}</td>
            <td>${{ parseFloat(entry.box22 || 0).toFixed(2) }}</td>
            <td>
              <span v-if="entry.auto_box14" class="badge badge-info">
                Box14: ${{ parseFloat(entry.auto_box14).toFixed(2) }}
              </span>
            </td>
            <td>
              <button @click="editT4(entry)" class="btn btn-sm btn-info">Edit</button>
              <button @click="deleteT4(entry.employee_id, entry.tax_year)" class="btn btn-sm btn-danger">
                Delete
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- T4 Form Modal -->
      <div v-if="showT4Form" class="modal">
        <div class="modal-content">
          <h2>{{ editingT4?.employee_id ? 'Edit' : 'New' }} T4 Entry</h2>
          <form @submit.prevent="saveT4">
            <div class="form-group">
              <label>Employee:</label>
              <select v-model="t4Form.employee_id" class="form-control" required>
                <option value="">Select Employee</option>
                <option v-for="emp in employees" :key="emp.id" :value="emp.id">
                  {{ emp.first_name }} {{ emp.last_name }}
                </option>
              </select>
            </div>
            <div class="form-group">
              <label>Tax Year:</label>
              <input v-model.number="t4Form.tax_year" type="number" class="form-control" required />
            </div>
            <div class="form-group">
              <label>Box 14 - Employment Income:</label>
              <input v-model.number="t4Form.box14" type="number" step="0.01" class="form-control" />
            </div>
            <div class="form-group">
              <label>Box 16 - Employee CPP:</label>
              <input v-model.number="t4Form.box16" type="number" step="0.01" class="form-control" />
            </div>
            <div class="form-group">
              <label>Box 18 - Employee EI:</label>
              <input v-model.number="t4Form.box18" type="number" step="0.01" class="form-control" />
            </div>
            <div class="form-group">
              <label>Box 22 - Income Tax:</label>
              <input v-model.number="t4Form.box22" type="number" step="0.01" class="form-control" />
            </div>
            <div class="form-group">
              <label>Box 24 - EI Insurable:</label>
              <input v-model.number="t4Form.box24" type="number" step="0.01" class="form-control" />
            </div>
            <div class="form-group">
              <label>Box 26 - CPP Pensionable:</label>
              <input v-model.number="t4Form.box26" type="number" step="0.01" class="form-control" />
            </div>
            <div class="form-group">
              <label>Box 44 - Commissions:</label>
              <input v-model.number="t4Form.box44" type="number" step="0.01" class="form-control" />
            </div>
            <div class="form-group">
              <label>Box 46 - Other Remuneration:</label>
              <input v-model.number="t4Form.box46" type="number" step="0.01" class="form-control" />
            </div>
            <div class="form-group">
              <label>Box 52 - Union Dues:</label>
              <input v-model.number="t4Form.box52" type="number" step="0.01" class="form-control" />
            </div>
            <div class="form-group">
              <label>Notes:</label>
              <textarea v-model="t4Form.notes" class="form-control" rows="3"></textarea>
            </div>
            <div class="form-actions">
              <button type="submit" class="btn btn-primary">Save</button>
              <button type="button" @click="showT4Form = false" class="btn btn-secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <!-- T2 RETURNS TAB -->
    <div v-if="activeTab === 'T2'" class="tab-content">
      <div class="actions">
        <button @click="showT2Form = true" class="btn btn-primary">
          New T2 Return
        </button>
      </div>

      <table class="data-table">
        <thead>
          <tr>
            <th>Corporation</th>
            <th>Tax Year</th>
            <th>Fiscal Year End</th>
            <th>Status</th>
            <th>Total Revenue</th>
            <th>Total Tax</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="t2 in t2Data" :key="t2.return_id">
            <td>{{ t2.corporation_name }}</td>
            <td>{{ t2.tax_year }}</td>
            <td>{{ formatDate(t2.fiscal_year_end) }}</td>
            <td>
              <span :class="['badge', `badge-${t2.status === 'complete' ? 'success' : 'warning'}`]">
                {{ t2.status }}
              </span>
            </td>
            <td>${{ parseFloat(t2.total_revenue || 0).toFixed(2) }}</td>
            <td>${{ parseFloat(t2.total_tax || 0).toFixed(2) }}</td>
            <td>
              <button @click="editT2(t2)" class="btn btn-sm btn-info">Edit</button>
              <button @click="deleteT2(t2.return_id)" class="btn btn-sm btn-danger">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- T2 Form Modal -->
      <div v-if="showT2Form" class="modal">
        <div class="modal-content">
          <h2>{{ editingT2?.return_id ? 'Edit' : 'New' }} T2 Return</h2>
          <form @submit.prevent="saveT2">
            <div class="form-group">
              <label>Corporation Name:</label>
              <input v-model="t2Form.corporation_name" type="text" class="form-control" required />
            </div>
            <div class="form-group">
              <label>Tax Year:</label>
              <input v-model.number="t2Form.tax_year" type="number" class="form-control" required />
            </div>
            <div class="form-group">
              <label>Business Number:</label>
              <input v-model="t2Form.business_number" type="text" class="form-control" />
            </div>
            <div class="form-group">
              <label>Fiscal Year End:</label>
              <input v-model="t2Form.fiscal_year_end" type="date" class="form-control" required />
            </div>
            <div class="form-actions">
              <button type="submit" class="btn btn-primary">Save</button>
              <button type="button" @click="showT2Form = false" class="btn btn-secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>

    <div v-if="showT4Form || showT2Form" class="modal-overlay" @click="closeModals"></div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { authFetch } from '@/utils/authFetch';
import { useToast } from '@/composables/useToast';

export default {
  name: 'TaxManagement',
  setup() {
    const activeTab = ref('T4');
    const t4Data = ref([]);
    const t2Data = ref([]);
    const employees = ref([]);
    const showT4Form = ref(false);
    const showT2Form = ref(false);
    const editingT4 = ref(null);
    const editingT2 = ref(null);
    const { showToast } = useToast();

    const t4Filters = ref({ year: new Date().getFullYear().toString() });

    const t4Form = ref({
      employee_id: '',
      tax_year: new Date().getFullYear(),
      box14: 0,
      box16: 0,
      box18: 0,
      box22: 0,
      box24: 0,
      box26: 0,
      box44: 0,
      box46: 0,
      box52: 0,
      notes: ''
    });

    const t2Form = ref({
      tax_year: new Date().getFullYear(),
      corporation_name: 'Arrow Limousine Ltd.',
      business_number: '',
      fiscal_year_end: ''
    });

    const loadT4Data = async () => {
      try {
        const year = Number(t4Filters.value.year || new Date().getFullYear());
        const rows = [];
        for (const emp of employees.value) {
          const employeeId = emp.employee_id || emp.id;
          if (!employeeId) continue;
          const res = await authFetch(`/api/t4/${employeeId}/${year}`);
          if (!res || res.status === 404) continue;
          if (!res.ok) {
            throw new Error(`Failed to load T4 data (${res.status})`);
          }
          const data = await res.json();
          rows.push({
            employee_id: employeeId,
            employee_name: emp.full_name || `${emp.first_name || ''} ${emp.last_name || ''}`.trim(),
            tax_year: year,
            box14: data.box14 || 0,
            box16: data.box16 || 0,
            box18: data.box18 || 0,
            box22: data.box22 || 0,
            box24: data.box24 || 0,
            box26: data.box26 || 0,
            box44: data.box44 || 0,
            box46: data.box46 || 0,
            box52: data.box52 || 0,
            notes: data.notes || '',
            auto_box14: data.autoBox14 || 0,
          });
        }
        t4Data.value = rows;
      } catch (error) {
        showToast('Failed to load T4 data', 'error');
      }
    };

    const loadT2Data = async () => {
      try {
        const year = Number(t4Filters.value.year || new Date().getFullYear());
        const res = await authFetch(`/api/t2/returns/${year}`);
        if (!res || res.status === 404) {
          t2Data.value = [];
          return;
        }
        if (!res.ok) {
          throw new Error(`Failed to load T2 data (${res.status})`);
        }
        const data = await res.json();
        t2Data.value = data ? [data] : [];
      } catch (error) {
        showToast('Failed to load T2 data', 'error');
      }
    };

    const loadEmployees = async () => {
      try {
        const res = await authFetch('/api/employees/');
        if (!res || !res.ok) {
          throw new Error(`Failed to load employees (${res?.status || 'no-response'})`);
        }
        employees.value = await res.json();
      } catch (error) {
        showToast('Failed to load employees', 'error');
      }
    };

    const saveT4 = async () => {
      try {
        const res = await authFetch('/api/t4', {
          method: 'POST',
          body: JSON.stringify(t4Form.value)
        });
        if (!res || !res.ok) {
          throw new Error(`Failed to save T4 entry (${res?.status || 'no-response'})`);
        }
        showToast('T4 entry saved', 'success');
        showT4Form.value = false;
        loadT4Data();
      } catch (error) {
        showToast('Failed to save T4 entry', 'error');
      }
    };

    const saveT2 = async () => {
      try {
        const method = editingT2.value ? 'PUT' : 'POST';
        const url = editingT2.value ? `/api/t2/${editingT2.value.return_id}` : '/api/t2';
        const res = await authFetch(url, {
          method,
          body: JSON.stringify(t2Form.value)
        });
        if (!res || !res.ok) {
          throw new Error(`Failed to save T2 return (${res?.status || 'no-response'})`);
        }
        showToast('T2 return saved', 'success');
        showT2Form.value = false;
        loadT2Data();
      } catch (error) {
        showToast('Failed to save T2 return', 'error');
      }
    };

    const editT4 = (entry) => {
      editingT4.value = entry;
      Object.assign(t4Form.value, entry);
      showT4Form.value = true;
    };

    const editT2 = (t2) => {
      editingT2.value = t2;
      Object.assign(t2Form.value, t2);
      showT2Form.value = true;
    };

    const deleteT4 = async (employeeId, taxYear) => {
      showToast('T4 delete endpoint is not available yet', 'warning');
    };

    const deleteT2 = async (returnId) => {
      showToast('T2 delete endpoint is not available yet', 'warning');
    };

    const generateT4PDF = async () => {
      try {
        if (!t4Data.value.length) {
          showToast('Load a T4 entry first', 'warning');
          return;
        }
        const item = t4Data.value[0];
        const res = await authFetch(`/api/t4/${item.employee_id}/${item.tax_year}/pdf`, { method: 'GET' });
        if (!res || !res.ok) {
          throw new Error(`Failed to generate T4 PDF (${res?.status || 'no-response'})`);
        }
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `T4-${item.tax_year}-${item.employee_id}.pdf`;
        a.click();
        showToast('PDF generated', 'success');
      } catch (error) {
        showToast('Failed to generate PDF', 'error');
      }
    };

    const closeModals = () => {
      showT4Form.value = false;
      showT2Form.value = false;
    };

    const formatDate = (date) => {
      return new Date(date).toLocaleDateString();
    };

    onMounted(() => {
      loadT4Data();
      loadT2Data();
      loadEmployees();
    });

    return {
      activeTab,
      t4Data,
      t2Data,
      employees,
      showT4Form,
      showT2Form,
      t4Filters,
      t4Form,
      t2Form,
      loadT4Data,
      loadT2Data,
      saveT4,
      saveT2,
      editT4,
      editT2,
      deleteT4,
      deleteT2,
      generateT4PDF,
      closeModals,
      formatDate
    };
  }
};
</script>

<style scoped>
.tax-management {
  padding: 20px;
}

.header {
  margin-bottom: 20px;
}

.tabs {
  display: flex;
  gap: 10px;
  margin-top: 15px;
  border-bottom: 2px solid #ddd;
}

.tab {
  padding: 10px 20px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 16px;
  color: #666;
  border-bottom: 3px solid transparent;
  transition: all 0.2s;
}

.tab.active {
  color: #007bff;
  border-bottom-color: #007bff;
}

.tab-content {
  margin-top: 20px;
}

.actions {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.search-bar {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
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
  font-size: 11px;
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

.form-control {
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
