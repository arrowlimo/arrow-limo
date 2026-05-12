<template>
  <div class="payroll-management">
    <div class="header">
      <h1>Payroll Management</h1>
      <div class="actions">
        <button @click="showNewForm = true" class="btn btn-primary">
          New Payroll Entry
        </button>
      </div>
    </div>

    <div class="search-bar">
      <input
        v-model="filters.employee"
        type="text"
        placeholder="Search employee..."
      />
      <select v-model="filters.year" class="form-control">
        <option value="">All Years</option>
        <option value="2024">2024</option>
        <option value="2025">2025</option>
        <option value="2026">2026</option>
      </select>
      <button @click="loadPayroll" class="btn btn-secondary">Search</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th>Employee</th>
          <th>Year</th>
          <th>Period</th>
          <th>Gross Pay</th>
          <th>Deductions</th>
          <th>Net Pay</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="entry in payroll" :key="`${entry.employee_id}-${entry.year}`">
          <td>{{ entry.employee_name }}</td>
          <td>{{ entry.year }}</td>
          <td>{{ entry.pay_period }}</td>
          <td>${{ parseFloat(entry.gross_pay || 0).toFixed(2) }}</td>
          <td>
            CPP: ${{ parseFloat(entry.cpp || 0).toFixed(2) }}<br />
            EI: ${{ parseFloat(entry.ei || 0).toFixed(2) }}<br />
            TAX: ${{ parseFloat(entry.tax_withheld || 0).toFixed(2) }}
          </td>
          <td>${{ (entry.gross_pay - entry.cpp - entry.ei - entry.tax_withheld || 0).toFixed(2) }}</td>
          <td>
            <button @click="editEntry(entry)" class="btn btn-sm btn-info">Edit</button>
            <button @click="deleteEntry(entry.id)" class="btn btn-sm btn-danger">Delete</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Form Modal -->
    <div v-if="showNewForm" class="modal">
      <div class="modal-content">
        <h2>{{ editingEntry?.id ? 'Edit' : 'New' }} Payroll Entry</h2>
        <form @submit.prevent="savePayroll">
          <div class="form-group">
            <label>Employee:</label>
            <select v-model="form.employee_id" class="form-control" required>
              <option value="">Select Employee</option>
              <option v-for="emp in employees" :key="emp.id" :value="emp.id">
                {{ emp.first_name }} {{ emp.last_name }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>Year:</label>
            <input v-model.number="form.year" type="number" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Pay Period:</label>
            <input v-model="form.pay_period" type="text" class="form-control" placeholder="e.g., 2026-01" required />
          </div>
          <div class="form-group">
            <label>Regular Hours:</label>
            <input v-model.number="form.regular_hours" type="number" step="0.5" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Hourly Rate:</label>
            <input v-model.number="form.hourly_rate" type="number" step="0.01" class="form-control" required />
          </div>
          <div class="form-group">
            <label>OT Hours:</label>
            <input v-model.number="form.ot_hours" type="number" step="0.5" class="form-control" />
          </div>
          <div class="form-group">
            <label>OT Rate:</label>
            <input v-model.number="form.ot_rate" type="number" step="0.01" class="form-control" />
          </div>
          <div class="form-group">
            <label>Bonus:</label>
            <input v-model.number="form.bonus" type="number" step="0.01" class="form-control" />
          </div>
          <div class="form-group">
            <label>CPP Contribution:</label>
            <input v-model.number="form.cpp" type="number" step="0.01" class="form-control" />
          </div>
          <div class="form-group">
            <label>EI Premium:</label>
            <input v-model.number="form.ei" type="number" step="0.01" class="form-control" />
          </div>
          <div class="form-group">
            <label>Income Tax Withheld:</label>
            <input v-model.number="form.income_tax" type="number" step="0.01" class="form-control" />
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary">Save</button>
            <button type="button" @click="showNewForm = false" class="btn btn-secondary">Cancel</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showNewForm" class="modal-overlay" @click="showNewForm = false"></div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { authFetch } from '@/utils/authFetch';
import { useToast } from '@/composables/useToast';

export default {
  name: 'PayrollManagement',
  setup() {
    const payroll = ref([]);
    const employees = ref([]);
    const showNewForm = ref(false);
    const editingEntry = ref(null);
    const { showToast } = useToast();
    
    const filters = ref({
      employee: '',
      year: new Date().getFullYear().toString()
    });

    const form = ref({
      employee_id: '',
      year: new Date().getFullYear(),
      pay_period: '',
      regular_hours: 0,
      hourly_rate: 0,
      ot_hours: 0,
      ot_rate: 0,
      base_salary: 0,
      bonus: 0,
      gratuity: 0,
      other_benefits: 0,
      cpp: 0,
      ei: 0,
      income_tax: 0,
      notes: ''
    });

    const loadPayroll = async () => {
      try {
        const res = await authFetch(`/api/payroll/entries?year=${filters.value.year}`);
        if (!res || !res.ok) {
          throw new Error(`Failed to load payroll (${res?.status || 'no-response'})`);
        }
        payroll.value = await res.json();
      } catch (error) {
        showToast('Failed to load payroll', 'error');
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

    const savePayroll = async () => {
      try {
        const method = editingEntry.value ? 'PUT' : 'POST';
        const url = editingEntry.value ? `/api/payroll/entries/${editingEntry.value.id}` : '/api/payroll/entries';
        
        const res = await authFetch(url, {
          method,
          body: JSON.stringify(form.value)
        });
        if (!res || !res.ok) {
          throw new Error(`Failed to save payroll (${res?.status || 'no-response'})`);
        }
        
        showToast('Payroll entry saved', 'success');
        showNewForm.value = false;
        editingEntry.value = null;
        loadPayroll();
      } catch (error) {
        showToast('Failed to save payroll', 'error');
      }
    };

    const editEntry = (entry) => {
      editingEntry.value = entry;
      Object.assign(form.value, entry);
      showNewForm.value = true;
    };

    const deleteEntry = async (id) => {
      if (!confirm('Delete this payroll entry?')) return;
      try {
        const res = await authFetch(`/api/payroll/entries/${id}`, { method: 'DELETE' });
        if (!res || !res.ok) {
          throw new Error(`Failed to delete payroll entry (${res?.status || 'no-response'})`);
        }
        showToast('Entry deleted', 'success');
        loadPayroll();
      } catch (error) {
        showToast('Failed to delete entry', 'error');
      }
    };

    onMounted(() => {
      loadPayroll();
      loadEmployees();
    });

    return {
      payroll,
      employees,
      showNewForm,
      editingEntry,
      filters,
      form,
      loadPayroll,
      savePayroll,
      editEntry,
      deleteEntry
    };
  }
};
</script>

<style scoped>
.payroll-management {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
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
