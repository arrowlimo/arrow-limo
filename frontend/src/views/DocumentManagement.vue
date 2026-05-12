<template>
  <div class="document-management">
    <div class="header">
      <h1>Document Management</h1>
      <div class="actions">
        <button @click="showUploadForm = true" class="btn btn-primary">
          Upload Document
        </button>
      </div>
    </div>

    <div class="filters">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search documents..."
        class="form-control"
      />
      <select v-model="filterCategory" class="form-control">
        <option value="">All Categories</option>
        <option value="employees">Employees</option>
        <option value="vehicles">Vehicles</option>
        <option value="business_documents">Business Documents</option>
        <option value="banking_records">Banking Records</option>
        <option value="reports">Reports</option>
        <option value="backups">Backups</option>
      </select>
      <button @click="loadDocuments" class="btn btn-secondary">Search</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th>Filename</th>
          <th>Category</th>
          <th>Size</th>
          <th>Modified</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="doc in documents" :key="doc.path">
          <td>{{ doc.filename }}</td>
          <td>
            <span class="badge badge-info">{{ doc.category }}</span>
          </td>
          <td>{{ formatFileSize(doc.size) }}</td>
          <td>{{ formatDate(doc.modified) }}</td>
          <td>
            <button @click="downloadDocument(doc)" class="btn btn-sm btn-info">
              Download
            </button>
            <button @click="deleteDocument(doc)" class="btn btn-sm btn-danger">
              Delete
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Upload Modal -->
    <div v-if="showUploadForm" class="modal">
      <div class="modal-content">
        <h2>Upload Document</h2>
        <form @submit.prevent="uploadDocument">
          <div class="form-group">
            <label>Category:</label>
            <select v-model="uploadForm.category" class="form-control" required>
              <option value="">Select Category</option>
              <option value="employees">Employees</option>
              <option value="vehicles">Vehicles</option>
              <option value="business_documents">Business Documents</option>
              <option value="banking_records">Banking Records</option>
              <option value="reports">Reports</option>
              <option value="backups">Backups</option>
            </select>
          </div>
          <div class="form-group" v-if="uploadForm.category === 'employees'">
            <label>Employee:</label>
            <select v-model.number="uploadForm.employee_id" class="form-control">
              <option value="">Select Employee</option>
              <option v-for="emp in employees" :key="emp.id" :value="emp.id">
                {{ emp.first_name }} {{ emp.last_name }}
              </option>
            </select>
          </div>
          <div class="form-group" v-if="uploadForm.category === 'vehicles'">
            <label>Vehicle:</label>
            <select v-model.number="uploadForm.vehicle_id" class="form-control">
              <option value="">Select Vehicle</option>
              <option v-for="vehicle in vehicles" :key="vehicle.id" :value="vehicle.id">
                {{ vehicle.unit_number }} - {{ vehicle.make }} {{ vehicle.model }}
              </option>
            </select>
          </div>
          <div class="form-group">
            <label>File:</label>
            <input type="file" @change="onFileSelected" class="form-control" required />
          </div>
          <div class="form-group">
            <label>Description:</label>
            <textarea v-model="uploadForm.description" class="form-control" rows="3"></textarea>
          </div>
          <div class="form-actions">
            <button type="submit" class="btn btn-primary">Upload</button>
            <button type="button" @click="showUploadForm = false" class="btn btn-secondary">
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showUploadForm" class="modal-overlay" @click="showUploadForm = false"></div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue';
import { authFetch } from '@/utils/authFetch';
import { useToast } from '@/composables/useToast';

export default {
  name: 'DocumentManagement',
  setup() {
    const documents = ref([]);
    const employees = ref([]);
    const vehicles = ref([]);
    const showUploadForm = ref(false);
    const { showToast } = useToast();

    const searchQuery = ref('');
    const filterCategory = ref('');
    const selectedFile = ref(null);
    const selectedEntityId = ref('general');
    const selectedSubfolder = ref('general');

    const uploadForm = ref({
      category: '',
      employee_id: '',
      vehicle_id: '',
      description: ''
    });

    const currentFilePath = () => {
      const category = filterCategory.value || 'business_documents';
      const entity = String(selectedEntityId.value || 'general');
      const subfolder = String(selectedSubfolder.value || 'general');
      return { category, entity, subfolder };
    };

    const loadDocuments = async () => {
      try {
        const { category, entity, subfolder } = currentFilePath();
        const url = `/api/files/list/${encodeURIComponent(category)}/${encodeURIComponent(entity)}/${encodeURIComponent(subfolder)}`;

        const res = await authFetch(url);
        if (!res || !res.ok) {
          throw new Error(`Failed to load documents (${res?.status || 'no-response'})`);
        }
        const data = await res.json();
        const search = (searchQuery.value || '').trim().toLowerCase();
        documents.value = search
          ? data.filter((d) => String(d.filename || '').toLowerCase().includes(search))
          : data;
      } catch (error) {
        showToast('Failed to load documents', 'error');
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

    const loadVehicles = async () => {
      try {
        const res = await authFetch('/api/vehicles/');
        if (!res || !res.ok) {
          throw new Error(`Failed to load vehicles (${res?.status || 'no-response'})`);
        }
        vehicles.value = await res.json();
      } catch (error) {
        showToast('Failed to load vehicles', 'error');
      }
    };

    const onFileSelected = (event) => {
      selectedFile.value = event.target.files[0];
    };

    const uploadDocument = async () => {
      if (!selectedFile.value) {
        showToast('Please select a file', 'warning');
        return;
      }

      try {
        const formData = new FormData();
        formData.append('file', selectedFile.value);

        const category = uploadForm.value.category;
        let entityId = 'general';
        let subfolder = 'general';
        if (category === 'employees') {
          entityId = String(uploadForm.value.employee_id || '0');
          subfolder = 'documents';
        } else if (category === 'vehicles') {
          const vehicle = vehicles.value.find((v) => Number(v.id) === Number(uploadForm.value.vehicle_id));
          entityId = String(vehicle?.unit_number || uploadForm.value.vehicle_id || 'unknown');
          subfolder = 'documents';
        } else {
          entityId = 'general';
          subfolder = 'general';
        }

        const res = await authFetch(`/api/files/upload/${encodeURIComponent(category)}/${encodeURIComponent(entityId)}/${encodeURIComponent(subfolder)}`, {
          method: 'POST',
          headers: {},
          body: formData
        });
        if (!res || !res.ok) {
          throw new Error(`Upload failed (${res?.status || 'no-response'})`);
        }

        showToast('Document uploaded', 'success');
        showUploadForm.value = false;
        loadDocuments();
      } catch (error) {
        showToast('Failed to upload document', 'error');
      }
    };

    const downloadDocument = async (doc) => {
      try {
        const parts = String(doc.path || '').split('/');
        if (parts.length < 4) throw new Error('Invalid file path');
        const [category, entity, subfolder, ...fileParts] = parts;
        const filename = fileParts.join('/');
        const res = await authFetch(`/api/files/download/${encodeURIComponent(category)}/${encodeURIComponent(entity)}/${encodeURIComponent(subfolder)}/${encodeURIComponent(filename)}`);
        if (!res || !res.ok) {
          throw new Error(`Download failed (${res?.status || 'no-response'})`);
        }
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = doc.filename;
        a.click();
        showToast('Download started', 'success');
      } catch (error) {
        showToast('Failed to download document', 'error');
      }
    };

    const deleteDocument = async (doc) => {
      if (!confirm(`Delete ${doc.filename}?`)) return;

      try {
        const parts = String(doc.path || '').split('/');
        if (parts.length < 4) throw new Error('Invalid file path');
        const [category, entity, subfolder, ...fileParts] = parts;
        const filename = fileParts.join('/');
        const res = await authFetch(`/api/files/delete/${encodeURIComponent(category)}/${encodeURIComponent(entity)}/${encodeURIComponent(subfolder)}/${encodeURIComponent(filename)}`, { method: 'DELETE' });
        if (!res || !res.ok) {
          throw new Error(`Delete failed (${res?.status || 'no-response'})`);
        }
        showToast('Document deleted', 'success');
        loadDocuments();
      } catch (error) {
        showToast('Failed to delete document', 'error');
      }
    };

    const formatFileSize = (bytes) => {
      if (bytes === 0) return '0 B';
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const formatDate = (date) => {
      return new Date(date).toLocaleDateString();
    };

    onMounted(() => {
      loadDocuments();
      loadEmployees();
      loadVehicles();
    });

    return {
      documents,
      employees,
      vehicles,
      showUploadForm,
      searchQuery,
      filterCategory,
      selectedEntityId,
      selectedSubfolder,
      uploadForm,
      loadDocuments,
      onFileSelected,
      uploadDocument,
      downloadDocument,
      deleteDocument,
      formatFileSize,
      formatDate
    };
  }
};
</script>

<style scoped>
.document-management {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.actions {
  display: flex;
  gap: 10px;
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
