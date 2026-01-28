<template>
  <div>
    <h1>📄 Document Management</h1>
    
    <!-- Document Categories -->
    <div class="document-tabs">
      <button 
        v-for="tab in documentTabs" 
        :key="tab.id"
        @click="activeTab = tab.id"
        :class="['tab-button', { active: activeTab === tab.id }]"
      >
        {{ tab.icon }} {{ tab.name }}
      </button>
    </div>

    <!-- Upload Section -->
    <div class="upload-section">
      <div class="upload-card">
        <h3>📤 Upload Documents</h3>
        <div class="upload-form">
          <div class="form-row">
            <div class="form-group">
              <label>Document Category</label>
              <select v-model="uploadForm.category" required>
                <option value="">Select Category</option>
                <option value="contracts">Contracts</option>
                <option value="insurance">Insurance</option>
                <option value="licenses">Licenses</option>
                <option value="maintenance">Maintenance Records</option>
                <option value="financial">Financial Documents</option>
                <option value="legal">Legal Documents</option>
                <option value="hr">HR Documents</option>
                <option value="other">Other</option>
              </select>
            </div>
            <div class="form-group">
              <label>Document Title</label>
              <input v-model="uploadForm.title" type="text" placeholder="Enter document title" required />
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label>Description</label>
              <input v-model="uploadForm.description" type="text" placeholder="Brief description" />
            </div>
            <div class="form-group">
              <label>Tags</label>
              <input v-model="uploadForm.tags" type="text" placeholder="Comma-separated tags" />
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label>Expiry Date (if applicable)</label>
              <input v-model="uploadForm.expiryDate" type="date" />
            </div>
            <div class="form-group">
              <label>Access Level</label>
              <select v-model="uploadForm.accessLevel">
                <option value="public">Public</option>
                <option value="internal">Internal Only</option>
                <option value="restricted">Restricted</option>
                <option value="confidential">Confidential</option>
              </select>
            </div>
          </div>
          
          <div class="file-upload">
            <div class="drop-zone" 
                 @dragover.prevent 
                 @drop.prevent="handleFileDrop"
                 @click="$refs.fileInput.click()">
              <div v-if="!selectedFile" class="drop-placeholder">
                <span class="upload-icon">📁</span>
                <p>Drag & drop files here or click to browse</p>
                <small>Supported: PDF, DOC, DOCX, XLS, XLSX, JPG, PNG (Max 10MB)</small>
              </div>
              <div v-else class="file-preview">
                <span class="file-icon">📄</span>
                <div class="file-info">
                  <strong>{{ selectedFile.name }}</strong>
                  <small>{{ formatFileSize(selectedFile.size) }}</small>
                </div>
                <button @click.stop="clearFile" class="btn-clear">✕</button>
              </div>
            </div>
            <input ref="fileInput" type="file" @change="handleFileSelect" style="display: none" 
                   accept=".pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png" />
          </div>
          
          <div class="upload-actions">
            <button @click="uploadDocument" :disabled="!selectedFile || uploading" class="btn-upload">
              {{ uploading ? 'Uploading...' : '📤 Upload Document' }}
            </button>
            <button @click="clearForm" class="btn-clear-form">Clear Form</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Document Lists by Category -->
    <div class="documents-section">
      
      <!-- All Documents -->
      <div v-if="activeTab === 'all'" class="documents-list">
        <div class="list-header">
          <h2>📋 All Documents</h2>
          <div class="search-controls">
            <input v-model="searchTerm" placeholder="Search documents..." />
            <select v-model="sortBy">
              <option value="upload_date">Sort by Upload Date</option>
              <option value="title">Sort by Title</option>
              <option value="category">Sort by Category</option>
              <option value="expiry_date">Sort by Expiry</option>
            </select>
          </div>
        </div>
        
        <div class="documents-grid">
          <div v-for="doc in filteredDocuments" :key="doc.id" class="document-card">
            <div class="doc-header">
              <div class="doc-icon">{{ getDocumentIcon(doc.filename) }}</div>
              <div class="doc-info">
                <h4>{{ doc.title || doc.filename }}</h4>
                <p class="doc-category">{{ formatCategory(doc.category) }}</p>
              </div>
              <div class="doc-status">
                <span :class="'status-' + getDocumentStatus(doc)">
                  {{ getDocumentStatus(doc) }}
                </span>
              </div>
            </div>
            
            <div class="doc-details">
              <p v-if="doc.description" class="doc-description">{{ doc.description }}</p>
              <div class="doc-meta">
                <small>📅 Uploaded: {{ formatDate(doc.upload_date) }}</small>
                <small v-if="doc.expiry_date">⏰ Expires: {{ formatDate(doc.expiry_date) }}</small>
                <small>📏 Size: {{ formatFileSize(doc.file_size) }}</small>
              </div>
              <div v-if="doc.tags" class="doc-tags">
                <span v-for="tag in doc.tags.split(',')" :key="tag" class="tag">{{ tag.trim() }}</span>
              </div>
            </div>
            
            <div class="doc-actions">
              <button @click="viewDocument(doc)" class="btn-view">👁️ View</button>
              <button @click="downloadDocument(doc)" class="btn-download">💾 Download</button>
              <button @click="editDocument(doc)" class="btn-edit">✏️ Edit</button>
              <button @click="deleteDocument(doc)" class="btn-delete">🗑️ Delete</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Contracts -->
      <div v-if="activeTab === 'contracts'" class="documents-list">
        <h2>📋 Contracts & Agreements</h2>
        <div class="category-documents">
          <div v-for="doc in getDocumentsByCategory('contracts')" :key="doc.id" class="contract-item">
            <div class="contract-header">
              <h4>{{ doc.title || doc.filename }}</h4>
              <div class="contract-status">
                <span :class="'status-' + getContractStatus(doc)">{{ getContractStatus(doc) }}</span>
              </div>
            </div>
            <div class="contract-details">
              <p><strong>Type:</strong> {{ doc.contract_type || 'General Contract' }}</p>
              <p><strong>Party:</strong> {{ doc.contract_party || 'N/A' }}</p>
              <p><strong>Value:</strong> {{ doc.contract_value || 'N/A' }}</p>
              <p><strong>Start Date:</strong> {{ formatDate(doc.start_date) || 'N/A' }}</p>
              <p><strong>End Date:</strong> {{ formatDate(doc.end_date) || 'N/A' }}</p>
            </div>
            <div class="contract-actions">
              <button @click="viewDocument(doc)" class="btn-view">View</button>
              <button @click="renewContract(doc)" class="btn-renew">Renew</button>
              <button @click="downloadDocument(doc)" class="btn-download">Download</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Insurance -->
      <div v-if="activeTab === 'insurance'" class="documents-list">
        <h2>🛡️ Insurance Documents</h2>
        <div class="insurance-overview">
          <div class="insurance-stats">
            <div class="stat-card">
              <div class="stat-value">{{ getInsuranceStats().active }}</div>
              <div class="stat-label">Active Policies</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">{{ getInsuranceStats().expiring }}</div>
              <div class="stat-label">Expiring Soon</div>
            </div>
            <div class="stat-card">
              <div class="stat-value">${{ getInsuranceStats().totalCoverage }}</div>
              <div class="stat-label">Total Coverage</div>
            </div>
          </div>
        </div>
        
        <div class="category-documents">
          <div v-for="doc in getDocumentsByCategory('insurance')" :key="doc.id" class="insurance-item">
            <div class="insurance-header">
              <h4>{{ doc.title || doc.filename }}</h4>
              <div class="insurance-status">
                <span :class="'status-' + getInsuranceStatus(doc)">{{ getInsuranceStatus(doc) }}</span>
              </div>
            </div>
            <div class="insurance-details">
              <p><strong>Policy Type:</strong> {{ doc.policy_type || 'General' }}</p>
              <p><strong>Provider:</strong> {{ doc.insurance_provider || 'N/A' }}</p>
              <p><strong>Policy Number:</strong> {{ doc.policy_number || 'N/A' }}</p>
              <p><strong>Coverage Amount:</strong> {{ doc.coverage_amount || 'N/A' }}</p>
              <p><strong>Premium:</strong> {{ doc.premium_amount || 'N/A' }}</p>
              <p><strong>Expiry:</strong> {{ formatDate(doc.expiry_date) || 'N/A' }}</p>
            </div>
            <div class="insurance-actions">
              <button @click="viewDocument(doc)" class="btn-view">View Policy</button>
              <button @click="renewInsurance(doc)" class="btn-renew">Renew</button>
              <button @click="claimInsurance(doc)" class="btn-claim">File Claim</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Licenses -->
      <div v-if="activeTab === 'licenses'" class="documents-list">
        <h2>🪪 Licenses & Permits</h2>
        <div class="license-alerts">
          <div v-for="alert in getLicenseAlerts()" :key="alert.id" :class="'alert alert-' + alert.type">
            {{ alert.message }}
          </div>
        </div>
        
        <div class="category-documents">
          <div v-for="doc in getDocumentsByCategory('licenses')" :key="doc.id" class="license-item">
            <div class="license-header">
              <h4>{{ doc.title || doc.filename }}</h4>
              <div class="license-status">
                <span :class="'status-' + getLicenseStatus(doc)">{{ getLicenseStatus(doc) }}</span>
              </div>
            </div>
            <div class="license-details">
              <p><strong>License Type:</strong> {{ doc.license_type || 'General' }}</p>
              <p><strong>License Number:</strong> {{ doc.license_number || 'N/A' }}</p>
              <p><strong>Issued By:</strong> {{ doc.issuing_authority || 'N/A' }}</p>
              <p><strong>Issue Date:</strong> {{ formatDate(doc.issue_date) || 'N/A' }}</p>
              <p><strong>Expiry Date:</strong> {{ formatDate(doc.expiry_date) || 'N/A' }}</p>
              <p><strong>Holder:</strong> {{ doc.license_holder || 'N/A' }}</p>
            </div>
            <div class="license-actions">
              <button @click="viewDocument(doc)" class="btn-view">View License</button>
              <button @click="renewLicense(doc)" class="btn-renew">Renew</button>
              <button @click="downloadDocument(doc)" class="btn-download">Download</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Financial -->
      <div v-if="activeTab === 'financial'" class="documents-list">
        <h2>💰 Financial Documents</h2>
        <div class="financial-categories">
          <div class="financial-section">
            <h3>Tax Documents</h3>
            <div class="financial-docs">
              <div v-for="doc in getFinancialDocs('tax')" :key="doc.id" class="financial-doc-item">
                <span class="doc-icon">📄</span>
                <div class="doc-info">
                  <strong>{{ doc.title }}</strong>
                  <small>{{ formatDate(doc.upload_date) }}</small>
                </div>
                <div class="doc-actions">
                  <button @click="viewDocument(doc)" class="btn-view">View</button>
                  <button @click="downloadDocument(doc)" class="btn-download">Download</button>
                </div>
              </div>
            </div>
          </div>
          
          <div class="financial-section">
            <h3>Banking Documents</h3>
            <div class="financial-docs">
              <div v-for="doc in getFinancialDocs('banking')" :key="doc.id" class="financial-doc-item">
                <span class="doc-icon">🏦</span>
                <div class="doc-info">
                  <strong>{{ doc.title }}</strong>
                  <small>{{ formatDate(doc.upload_date) }}</small>
                </div>
                <div class="doc-actions">
                  <button @click="viewDocument(doc)" class="btn-view">View</button>
                  <button @click="downloadDocument(doc)" class="btn-download">Download</button>
                </div>
              </div>
            </div>
          </div>
          
          <div class="financial-section">
            <h3>Receipts & Invoices</h3>
            <div class="financial-docs">
              <div v-for="doc in getFinancialDocs('receipts')" :key="doc.id" class="financial-doc-item">
                <span class="doc-icon">🧾</span>
                <div class="doc-info">
                  <strong>{{ doc.title }}</strong>
                  <small>{{ formatDate(doc.upload_date) }}</small>
                </div>
                <div class="doc-actions">
                  <button @click="viewDocument(doc)" class="btn-view">View</button>
                  <button @click="downloadDocument(doc)" class="btn-download">Download</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Document Viewer Modal -->
    <div v-if="viewingDocument" class="document-modal" @click="closeViewer">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ viewingDocument.title || viewingDocument.filename }}</h3>
          <button @click="closeViewer" class="btn-close">✕</button>
        </div>
        <div class="modal-body">
          <iframe v-if="isPDF(viewingDocument)" 
                  :src="getDocumentUrl(viewingDocument)" 
                  width="100%" 
                  height="600px">
          </iframe>
          <img v-else-if="isImage(viewingDocument)" 
               :src="getDocumentUrl(viewingDocument)" 
               style="max-width: 100%; height: auto;" />
          <div v-else class="unsupported-preview">
            <p>Preview not available for this file type.</p>
            <button @click="downloadDocument(viewingDocument)" class="btn-download">Download to View</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { toast } from '@/toast/toastStore'

const activeTab = ref('all')
const documents = ref([])
const searchTerm = ref('')
const sortBy = ref('upload_date')
const selectedFile = ref(null)
const uploading = ref(false)
const viewingDocument = ref(null)

const documentTabs = [
  { id: 'all', name: 'All Documents', icon: '📋' },
  { id: 'contracts', name: 'Contracts', icon: '📋' },
  { id: 'insurance', name: 'Insurance', icon: '🛡️' },
  { id: 'licenses', name: 'Licenses', icon: '🪪' },
  { id: 'financial', name: 'Financial', icon: '💰' }
]

const uploadForm = ref({
  category: '',
  title: '',
  description: '',
  tags: '',
  expiryDate: '',
  accessLevel: 'internal'
})

const filteredDocuments = computed(() => {
  let filtered = documents.value

  if (searchTerm.value) {
    const search = searchTerm.value.toLowerCase()
    filtered = filtered.filter(doc => 
      (doc.title || '').toLowerCase().includes(search) ||
      (doc.filename || '').toLowerCase().includes(search) ||
      (doc.description || '').toLowerCase().includes(search) ||
      (doc.tags || '').toLowerCase().includes(search)
    )
  }

  // Sort documents
  filtered.sort((a, b) => {
    switch (sortBy.value) {
      case 'title':
        return (a.title || a.filename).localeCompare(b.title || b.filename)
      case 'category':
        return (a.category || '').localeCompare(b.category || '')
      case 'expiry_date':
        return new Date(a.expiry_date || 0) - new Date(b.expiry_date || 0)
      default: // upload_date
        return new Date(b.upload_date || 0) - new Date(a.upload_date || 0)
    }
  })

  return filtered
})

async function loadDocuments() {
  try {
    const response = await fetch('/api/business/documents')
    if (response.ok) {
      const data = await response.json()
      documents.value = data.documents || []
    } else {
      console.error('Failed to load documents:', response.status)
    }
  } catch (error) {
    console.error('Error loading documents:', error)
  }
}

function handleFileSelect(event) {
  const file = event.target.files[0]
  if (file) {
    selectedFile.value = file
  }
}

function handleFileDrop(event) {
  const file = event.dataTransfer.files[0]
  if (file) {
    selectedFile.value = file
  }
}

function clearFile() {
  selectedFile.value = null
}

function clearForm() {
  uploadForm.value = {
    category: '',
    title: '',
    description: '',
    tags: '',
    expiryDate: '',
    accessLevel: 'internal'
  }
  selectedFile.value = null
}

async function uploadDocument() {
  if (!selectedFile.value || !uploadForm.value.category) {
    toast.error('Please select a file and category')
    return
  }

  uploading.value = true
  
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)
    formData.append('category', uploadForm.value.category)
    formData.append('title', uploadForm.value.title)
    formData.append('description', uploadForm.value.description)
    formData.append('tags', uploadForm.value.tags)
    formData.append('expiry_date', uploadForm.value.expiryDate)
    formData.append('access_level', uploadForm.value.accessLevel)

    const response = await fetch('/api/business/upload_document', {
      method: 'POST',
      body: formData
    })

    if (response.ok) {
      toast.success('Document uploaded successfully!')
      clearForm()
      await loadDocuments()
    } else {
      const error = await response.json()
      toast.error('Upload failed: ' + (error.detail || 'Unknown error'))
    }
  } catch (error) {
    console.error('Upload error:', error)
    toast.error('Upload failed: ' + error.message)
  } finally {
    uploading.value = false
  }
}

function getDocumentsByCategory(category) {
  return documents.value.filter(doc => doc.category === category)
}

function getFinancialDocs(type) {
  return documents.value.filter(doc => 
    doc.category === 'financial' && 
    (doc.subcategory === type || doc.tags?.includes(type))
  )
}

function getDocumentIcon(filename) {
  const ext = filename.split('.').pop().toLowerCase()
  switch (ext) {
    case 'pdf': return '📄'
    case 'doc':
    case 'docx': return '📝'
    case 'xls':
    case 'xlsx': return '📊'
    case 'jpg':
    case 'jpeg':
    case 'png': return '🖼️'
    default: return '📎'
  }
}

function getDocumentStatus(doc) {
  if (!doc.expiry_date) return 'active'
  
  const expiryDate = new Date(doc.expiry_date)
  const today = new Date()
  const daysUntilExpiry = Math.ceil((expiryDate - today) / (1000 * 60 * 60 * 24))
  
  if (daysUntilExpiry < 0) return 'expired'
  if (daysUntilExpiry <= 30) return 'expiring'
  return 'active'
}

function getContractStatus(doc) {
  // Mock contract status logic
  return 'active'
}

function getInsuranceStatus(doc) {
  return getDocumentStatus(doc)
}

function getLicenseStatus(doc) {
  return getDocumentStatus(doc)
}

function getInsuranceStats() {
  const insuranceDocs = getDocumentsByCategory('insurance')
  return {
    active: insuranceDocs.filter(doc => getInsuranceStatus(doc) === 'active').length,
    expiring: insuranceDocs.filter(doc => getInsuranceStatus(doc) === 'expiring').length,
    totalCoverage: '2,500,000' // Mock value
  }
}

function getLicenseAlerts() {
  const alerts = []
  const licenseDocs = getDocumentsByCategory('licenses')
  
  licenseDocs.forEach(doc => {
    const status = getLicenseStatus(doc)
    if (status === 'expired') {
      alerts.push({
        id: doc.id,
        type: 'error',
        message: `${doc.title || doc.filename} has expired!`
      })
    } else if (status === 'expiring') {
      alerts.push({
        id: doc.id,
        type: 'warning',
        message: `${doc.title || doc.filename} expires soon.`
      })
    }
  })
  
  return alerts
}

function formatCategory(category) {
  const categories = {
    contracts: 'Contracts',
    insurance: 'Insurance',
    licenses: 'Licenses',
    maintenance: 'Maintenance',
    financial: 'Financial',
    legal: 'Legal',
    hr: 'Human Resources',
    other: 'Other'
  }
  return categories[category] || category
}

function formatDate(dateString) {
  if (!dateString) return 'N/A'
  return new Date(dateString).toLocaleDateString()
}

function formatFileSize(bytes) {
  if (!bytes) return 'Unknown'
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + sizes[i]
}

function getDocumentUrl(doc) {
  return `/api/business/document/${doc.filename}`
}

function isPDF(doc) {
  return doc.filename.toLowerCase().endsWith('.pdf')
}

function isImage(doc) {
  const imageExts = ['.jpg', '.jpeg', '.png', '.gif']
  return imageExts.some(ext => doc.filename.toLowerCase().endsWith(ext))
}

function viewDocument(doc) {
  viewingDocument.value = doc
}

function closeViewer() {
  viewingDocument.value = null
}

async function downloadDocument(doc) {
  try {
    const response = await fetch(`/api/business/document/${doc.filename}`)
    if (response.ok) {
      const blob = await response.blob()
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.style.display = 'none'
      a.href = url
      a.download = doc.filename
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
    }
  } catch (error) {
    console.error('Download error:', error)
    toast.error('Download failed: ' + error.message)
  }
}

function editDocument(doc) {
  console.log('Edit document:', doc)
  toast.info('Document editing not yet implemented')
}

async function deleteDocument(doc) {
  if (confirm(`Are you sure you want to delete "${doc.title || doc.filename}"?`)) {
    try {
      const response = await fetch(`/api/business/document/${doc.filename}`, {
        method: 'DELETE'
      })
      if (response.ok) {
        toast.success('Document deleted successfully!')
        await loadDocuments()
      } else {
        toast.error('Delete failed')
      }
    } catch (error) {
      console.error('Delete error:', error)
      toast.error('Delete failed: ' + error.message)
    }
  }
}

function renewContract(doc) {
  console.log('Renew contract:', doc)
  toast.info('Contract renewal not yet implemented')
}

function renewInsurance(doc) {
  console.log('Renew insurance:', doc)
  toast.info('Insurance renewal not yet implemented')
}

function claimInsurance(doc) {
  console.log('File insurance claim:', doc)
  toast.info('Insurance claim filing not yet implemented')
}

function renewLicense(doc) {
  console.log('Renew license:', doc)
  toast.info('License renewal not yet implemented')
}

onMounted(() => {
  loadDocuments()
})
</script>

<style scoped>
.document-tabs {
  display: flex;
  gap: 5px;
  margin-bottom: 30px;
  border-bottom: 2px solid #e9ecef;
}

.tab-button {
  padding: 12px 24px;
  background: none;
  border: none;
  border-bottom: 3px solid transparent;
  cursor: pointer;
  font-weight: 500;
  color: #666;
  transition: all 0.3s;
}

.tab-button:hover {
  color: #007bff;
  background: #f8f9fa;
}

.tab-button.active {
  color: #007bff;
  border-bottom-color: #007bff;
  background: white;
}

.upload-section {
  margin-bottom: 40px;
}

.upload-card {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
}

.form-row {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.form-group {
  flex: 1;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
  color: #333;
}

.form-group input, .form-group select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 14px;
}

.drop-zone {
  border: 2px dashed #ddd;
  border-radius: 12px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  margin: 20px 0;
}

.drop-zone:hover {
  border-color: #007bff;
  background: #f8f9ff;
}

.upload-icon {
  font-size: 3rem;
  margin-bottom: 15px;
  display: block;
}

.file-preview {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
}

.file-icon {
  font-size: 2rem;
}

.file-info {
  flex: 1;
  text-align: left;
}

.btn-clear {
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 50%;
  width: 30px;
  height: 30px;
  cursor: pointer;
}

.upload-actions {
  display: flex;
  gap: 15px;
  margin-top: 20px;
}

.btn-upload, .btn-clear-form {
  padding: 12px 24px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-upload {
  background: #28a745;
  color: white;
}

.btn-upload:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.btn-clear-form {
  background: #6c757d;
  color: white;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 25px;
}

.search-controls {
  display: flex;
  gap: 15px;
}

.search-controls input, .search-controls select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.documents-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 25px;
}

.document-card {
  background: white;
  border-radius: 12px;
  padding: 25px;
  box-shadow: 0 4px 6px rgba(0,0,0,0.1);
  border-left: 5px solid #007bff;
}

.doc-header {
  display: flex;
  align-items: flex-start;
  gap: 15px;
  margin-bottom: 15px;
}

.doc-icon {
  font-size: 2rem;
}

.doc-info {
  flex: 1;
}

.doc-info h4 {
  margin: 0 0 5px 0;
  color: #333;
  font-size: 1.1rem;
}

.doc-category {
  margin: 0;
  color: #666;
  font-size: 0.9rem;
}

.doc-status span {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 500;
}

.status-active { background: #d4edda; color: #155724; }
.status-expiring { background: #fff3cd; color: #856404; }
.status-expired { background: #f8d7da; color: #721c24; }

.doc-description {
  color: #666;
  margin-bottom: 15px;
  line-height: 1.5;
}

.doc-meta {
  display: flex;
  flex-direction: column;
  gap: 5px;
  margin-bottom: 15px;
}

.doc-meta small {
  color: #999;
  font-size: 0.85rem;
}

.doc-tags {
  margin-bottom: 15px;
}

.tag {
  background: #e9ecef;
  color: #495057;
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 0.8rem;
  margin-right: 8px;
}

.doc-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.btn-view, .btn-download, .btn-edit, .btn-delete, .btn-renew, .btn-claim {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-view { background: #007bff; color: white; }
.btn-download { background: #28a745; color: white; }
.btn-edit { background: #ffc107; color: black; }
.btn-delete { background: #dc3545; color: white; }
.btn-renew { background: #17a2b8; color: white; }
.btn-claim { background: #fd7e14; color: white; }

.insurance-overview {
  margin-bottom: 30px;
}

.insurance-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
}

.stat-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  flex: 1;
}

.stat-value {
  font-size: 1.8rem;
  font-weight: bold;
  color: #007bff;
  margin-bottom: 5px;
}

.stat-label {
  color: #666;
  font-size: 0.9rem;
}

.license-alerts {
  margin-bottom: 25px;
}

.alert {
  padding: 12px 16px;
  border-radius: 6px;
  margin-bottom: 10px;
  font-weight: 500;
}

.alert-error {
  background: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.alert-warning {
  background: #fff3cd;
  color: #856404;
  border: 1px solid #ffeaa7;
}

.financial-categories {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 30px;
}

.financial-section {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.financial-docs {
  margin-top: 15px;
}

.financial-doc-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 12px 0;
  border-bottom: 1px solid #eee;
}

.financial-doc-item .doc-icon {
  font-size: 1.5rem;
}

.financial-doc-item .doc-info {
  flex: 1;
}

.financial-doc-item .doc-actions {
  display: flex;
  gap: 8px;
}

.document-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0,0,0,0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 1000px;
  height: 90%;
  max-height: 800px;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.modal-header h3 {
  margin: 0;
  color: #333;
}

.btn-close {
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 50%;
  width: 35px;
  height: 35px;
  cursor: pointer;
  font-size: 1.2rem;
}

.modal-body {
  height: calc(100% - 80px);
  overflow: auto;
}

.unsupported-preview {
  padding: 40px;
  text-align: center;
  color: #666;
}

h1, h2, h3 {
  color: #333;
  margin-bottom: 1rem;
}
</style>