<template>
  <div class="payroll-compliance">
    <div class="header">
      <h1>Payroll Compliance (PD7A)</h1>
      <button @click="startNewSubmission" class="btn btn-primary">
        New PD7A Submission
      </button>
    </div>

    <div class="filters">
      <select v-model.number="filterYear" class="form-control">
        <option value="">All Years</option>
        <option value="2024">2024</option>
        <option value="2025">2025</option>
        <option value="2026">2026</option>
      </select>
      <button @click="loadSubmissions" class="btn btn-secondary">Filter</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th>Year</th>
          <th>Month</th>
          <th>Employees</th>
          <th>Gross Payroll</th>
          <th>CPP Total</th>
          <th>EI Total</th>
          <th>Tax Withheld</th>
          <th>Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="submission in submissions" :key="`${submission.year}-${submission.month}`">
          <td>{{ submission.year }}</td>
          <td>{{ formatMonth(submission.month) }}</td>
          <td>{{ submission.employee_count }}</td>
          <td>${{ parseFloat(submission.total_gross_payroll || 0).toFixed(2) }}</td>
          <td>${{ parseFloat(submission.cpp_total || 0).toFixed(2) }}</td>
          <td>${{ parseFloat(submission.ei_total || 0).toFixed(2) }}</td>
          <td>${{ parseFloat(submission.income_tax_deducted || 0).toFixed(2) }}</td>
          <td>
            <span :class="['badge', submission.is_submitted ? 'badge-success' : 'badge-warning']">
              {{ submission.is_submitted ? 'Submitted' : 'Pending' }}
            </span>
          </td>
          <td>
            <button @click="viewSubmission(submission)" class="btn btn-sm btn-info">
              View
            </button>
            <button v-if="!submission.is_submitted" @click="editSubmission(submission)" class="btn btn-sm btn-primary">
              Edit
            </button>
            <button v-if="!submission.is_submitted" @click="submitPD7A(submission)" class="btn btn-sm btn-success">
              Submit
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- View Submission Modal -->
    <div v-if="showViewModal" class="modal">
      <div class="modal-content">
        <h2>PD7A Submission Details</h2>
        <div class="details">
          <div class="detail-row">
            <span class="label">Reporting Year:</span>
            <span>{{ selectedSubmission?.year }}</span>
          </div>
          <div class="detail-row">
            <span class="label">Reporting Month:</span>
            <span>{{ formatMonth(selectedSubmission?.month) }}</span>
          </div>
          <div class="detail-row">
            <span class="label">Employee Count:</span>
            <span>{{ selectedSubmission?.employee_count }}</span>
          </div>
          <div class="detail-row">
            <span class="label">Total Gross Payroll:</span>
            <span>${{ parseFloat(selectedSubmission?.total_gross_payroll || 0).toFixed(2) }}</span>
          </div>
          <div class="detail-row">
            <span class="label">CPP Contributions Total:</span>
            <span>${{ parseFloat(selectedSubmission?.cpp_total || 0).toFixed(2) }}</span>
          </div>
          <div class="detail-row">
            <span class="label">EI Premiums Total:</span>
            <span>${{ parseFloat(selectedSubmission?.ei_total || 0).toFixed(2) }}</span>
          </div>
          <div class="detail-row">
            <span class="label">Income Tax Deducted:</span>
            <span>${{ parseFloat(selectedSubmission?.income_tax_deducted || 0).toFixed(2) }}</span>
          </div>
          <div class="detail-row">
            <span class="label">Total Remittance Due:</span>
            <span>${{ parseFloat(selectedSubmission?.total_remittance_due || 0).toFixed(2) }}</span>
          </div>
          <div class="detail-row">
            <span class="label">Status:</span>
            <span :class="['badge', selectedSubmission?.is_submitted ? 'badge-success' : 'badge-warning']">
              {{ selectedSubmission?.is_submitted ? 'Submitted' : 'Pending' }}
            </span>
          </div>
          <div v-if="selectedSubmission?.submission_date" class="detail-row">
            <span class="label">Submission Date:</span>
            <span>{{ formatDate(selectedSubmission?.submission_date) }}</span>
          </div>
          <div v-if="selectedSubmission?.submission_reference" class="detail-row">
            <span class="label">Reference Number:</span>
            <span>{{ selectedSubmission?.submission_reference }}</span>
          </div>
        </div>
        <button @click="showViewModal = false" class="btn btn-secondary">Close</button>
      </div>
    </div>

    <!-- Edit Submission Modal -->
    <div v-if="showEditModal" class="modal">
      <div class="modal-content">
        <h2>{{ newSubmission ? 'New' : 'Edit' }} PD7A Submission</h2>
        <form @submit.prevent="saveSubmission">
          <div class="form-group">
            <label>Reporting Year:</label>
            <input v-model.number="formData.year" type="number" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Reporting Month:</label>
            <select v-model.number="formData.month" class="form-control" required>
              <option v-for="m in 12" :key="m" :value="m">
                {{ formatMonth(m) }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>Employee Count:</label>
            <input v-model.number="formData.employee_count" type="number" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Total Gross Payroll:</label>
            <input v-model.number="formData.total_gross_payroll" type="number" step="0.01" class="form-control" required />
          </div>
          <div class="form-group">
            <label>CPP Contributions Total:</label>
            <input v-model.number="formData.cpp_total" type="number" step="0.01" class="form-control" required />
          </div>
          <div class="form-group">
            <label>EI Premiums Total:</label>
            <input v-model.number="formData.ei_total" type="number" step="0.01" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Income Tax Deducted:</label>
            <input v-model.number="formData.income_tax_deducted" type="number" step="0.01" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Notes:</label>
            <textarea v-model="formData.notes" class="form-control" rows="3"></textarea>
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary">Save</button>
            <button type="button" @click="showEditModal = false" class="btn btn-secondary">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showViewModal || showEditModal" class="modal-overlay" @click="closeModals"></div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { authFetch } from '@/utils/authFetch';
import { useToast } from '@/composables/useToast';

export default {
  name: 'PayrollCompliance',
  setup() {
    const submissions = ref([]);
    const showViewModal = ref(false);
    const showEditModal = ref(false);
    const showNewSubmission = ref(false);
    const selectedSubmission = ref(null);
    const newSubmission = ref(false);
    const { showToast } = useToast();

    const filterYear = ref('');

    const formData = ref({
      year: new Date().getFullYear(),
      month: new Date().getMonth() + 1,
      employee_count: 0,
      total_gross_payroll: 0,
      cpp_total: 0,
      ei_total: 0,
      income_tax_deducted: 0,
      notes: ''
    });

    const loadSubmissions = async () => {
      try {
        let url = '/api/payroll-compliance/pd7a';
        if (filterYear.value) url += `/${filterYear.value}`;

        const res = await authFetch(url);
        if (!res || !res.ok) {
          throw new Error(`Failed to load submissions (${res?.status || 'no-response'})`);
        }
        const data = await res.json();
        submissions.value = Array.isArray(data) ? data : [data];
      } catch (error) {
        showToast('Failed to load submissions', 'error');
      }
    };

    const startNewSubmission = () => {
      newSubmission.value = true;
      formData.value = {
        year: Number(filterYear.value) || new Date().getFullYear(),
        month: new Date().getMonth() + 1,
        employee_count: 0,
        total_gross_payroll: 0,
        cpp_total: 0,
        ei_total: 0,
        income_tax_deducted: 0,
        notes: ''
      };
      showEditModal.value = true;
    };

    const viewSubmission = (submission) => {
      selectedSubmission.value = submission;
      showViewModal.value = true;
    };

    const editSubmission = (submission) => {
      newSubmission.value = false;
      Object.assign(formData.value, submission);
      showEditModal.value = true;
    };

    const saveSubmission = async () => {
      try {
        const method = newSubmission.value ? 'POST' : 'PUT';
        const url = newSubmission.value
          ? '/api/payroll-compliance/pd7a'
          : `/api/payroll-compliance/pd7a/${formData.value.year}/${formData.value.month}`;

        const res = await authFetch(url, {
          method,
          body: JSON.stringify(formData.value)
        });
        if (!res || !res.ok) {
          throw new Error(`Failed to save submission (${res?.status || 'no-response'})`);
        }

        showToast('Submission saved', 'success');
        showEditModal.value = false;
        loadSubmissions();
      } catch (error) {
        showToast('Failed to save submission', 'error');
      }
    };

    const submitPD7A = async (submission) => {
      if (!confirm('Mark this submission as submitted to CRA?')) return;

      try {
        const submitData = {
          submitted_by: 'web_app',
          filing_method: 'manual',
          notes: `Submitted on ${new Date().toLocaleDateString()}`
        };

        const res = await authFetch(`/api/payroll-compliance/pd7a/${submission.year}/${submission.month}/submit`, {
          method: 'POST',
          body: JSON.stringify(submitData)
        });
        if (!res || !res.ok) {
          throw new Error(`Failed to submit PD7A (${res?.status || 'no-response'})`);
        }

        showToast('PD7A submitted', 'success');
        loadSubmissions();
      } catch (error) {
        showToast('Failed to submit PD7A', 'error');
      }
    };

    const closeModals = () => {
      showViewModal.value = false;
      showEditModal.value = false;
      showNewSubmission.value = false;
    };

    const formatMonth = (month) => {
      const months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
      ];
      return months[month - 1] || '';
    };

    const formatDate = (date) => {
      return new Date(date).toLocaleDateString();
    };

    onMounted(() => {
      loadSubmissions();
    });

    return {
      submissions,
      showViewModal,
      showEditModal,
      selectedSubmission,
      filterYear,
      formData,
      newSubmission,
      loadSubmissions,
      startNewSubmission,
      viewSubmission,
      editSubmission,
      saveSubmission,
      submitPD7A,
      closeModals,
      formatMonth,
      formatDate
    };
  }
};
</script>

<style scoped>
.payroll-compliance {
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

.details {
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

.btn-success {
  background-color: #28a745;
  color: white;
  padding: 4px 8px;
  font-size: 12px;
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
