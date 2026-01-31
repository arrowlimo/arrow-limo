<template>
  <div class="file-upload-widget">
    <h4>{{ title }}</h4>
    
    <!-- Upload Area -->
    <div 
      class="upload-zone"
      :class="{ 'drag-over': isDragging }"
      @drop.prevent="handleDrop"
      @dragover.prevent="isDragging = true"
      @dragleave="isDragging = false"
    >
      <input 
        type="file" 
        ref="fileInput"
        @change="handleFileSelect"
        :multiple="allowMultiple"
        style="display: none;"
      />
      <div class="upload-prompt">
        <span class="upload-icon">📁</span>
        <p>Drag & drop files here or <button @click="$refs.fileInput.click()" class="btn-link">browse</button></p>
        <p class="upload-hint">{{ hint }}</p>
      </div>
    </div>

    <!-- Upload Progress -->
    <div v-if="uploading" class="upload-progress">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
      </div>
      <p>Uploading... {{ uploadProgress }}%</p>
    </div>

    <!-- File List -->
    <div v-if="files.length > 0" class="file-list">
      <h5>Files ({{ files.length }})</h5>
      <table>
        <thead>
          <tr>
            <th>Filename</th>
            <th>Size</th>
            <th>Modified</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="file in files" :key="file.path">
            <td>{{ file.filename }}</td>
            <td>{{ formatSize(file.size) }}</td>
            <td>{{ formatDate(file.modified) }}</td>
            <td>
              <button @click="downloadFile(file)" class="btn-sm">Download</button>
              <button @click="deleteFile(file)" class="btn-sm btn-danger" v-if="canDelete">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-else-if="!uploading" class="no-files">
      <p>No files uploaded yet.</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { toast } from '@/toast/toastStore'

const props = defineProps({
  title: { type: String, default: 'File Upload' },
  hint: { type: String, default: 'Supported: PDF, JPG, PNG, DOCX (max 10MB)' },
  category: { type: String, required: true },  // 'employees', 'vehicles', 'business_documents'
  entityId: { type: String, required: true },  // employee_id, vehicle_number, etc.
  subfolder: { type: String, required: true },  // 'licenses', 'maintenance', etc.
  allowMultiple: { type: Boolean, default: true },
  canDelete: { type: Boolean, default: true }
})

const files = ref([])
const isDragging = ref(false)
const uploading = ref(false)
const uploadProgress = ref(0)
const fileInput = ref(null)

async function loadFiles() {
  try {
    const res = await fetch(`/api/files/list/${props.category}/${props.entityId}/${props.subfolder}`)
    if (res.ok) {
      files.value = await res.json()
    }
  } catch (e) {
    console.error('Failed to load files:', e)
  }
}

async function handleFileSelect(event) {
  const selectedFiles = Array.from(event.target.files)
  await uploadFiles(selectedFiles)
}

async function handleDrop(event) {
  isDragging.value = false
  const droppedFiles = Array.from(event.dataTransfer.files)
  await uploadFiles(droppedFiles)
}

async function uploadFiles(fileList) {
  if (fileList.length === 0) return
  
  uploading.value = true
  uploadProgress.value = 0
  
  for (let i = 0; i < fileList.length; i++) {
    const file = fileList[i]
    
    // Validate file size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
      toast.error(`File ${file.name} exceeds 10MB limit`)
      continue
    }
    
    const formData = new FormData()
    formData.append('file', file)
    
    try {
      const res = await fetch(`/api/files/upload/${props.category}/${props.entityId}/${props.subfolder}`, {
        method: 'POST',
        body: formData
      })
      
      if (res.ok) {
        toast.success(`Uploaded ${file.name}`)
      } else {
        const err = await res.json()
        toast.error(`Failed to upload ${file.name}: ${err.detail || 'Unknown error'}`)
      }
    } catch (e) {
      toast.error(`Upload error: ${e.message}`)
    }
    
    uploadProgress.value = Math.round(((i + 1) / fileList.length) * 100)
  }
  
  uploading.value = false
  uploadProgress.value = 0
  
  // Reload file list
  await loadFiles()
  
  // Clear input
  if (fileInput.value) fileInput.value.value = ''
}

async function downloadFile(file) {
  window.open(`/api/files/download/${props.category}/${props.entityId}/${props.subfolder}/${file.filename}`, '_blank')
}

async function deleteFile(file) {
  if (!confirm(`Delete ${file.filename}?`)) return
  
  try {
    const res = await fetch(`/api/files/delete/${props.category}/${props.entityId}/${props.subfolder}/${file.filename}`, {
      method: 'DELETE'
    })
    
    if (res.ok) {
      toast.success(`Deleted ${file.filename}`)
      await loadFiles()
    } else {
      const err = await res.json()
      toast.error(`Failed to delete: ${err.detail}`)
    }
  } catch (e) {
    toast.error(`Delete error: ${e.message}`)
  }
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(timestamp) {
  if (!timestamp) return 'Unknown'
  const date = new Date(parseFloat(timestamp) * 1000)
  return date.toLocaleDateString()
}

onMounted(() => {
  loadFiles()
})
</script>

<style scoped>
.file-upload-widget {
  border: 1px solid #ddd;
  border-radius: 4px;
  padding: 1rem;
  margin: 1rem 0;
}

.upload-zone {
  border: 2px dashed #ccc;
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  background: #f9f9f9;
  cursor: pointer;
  transition: all 0.3s;
}

.upload-zone.drag-over {
  border-color: #007bff;
  background: #e7f3ff;
}

.upload-icon {
  font-size: 3rem;
  display: block;
  margin-bottom: 0.5rem;
}

.upload-hint {
  font-size: 0.85rem;
  color: #666;
  margin-top: 0.5rem;
}

.btn-link {
  background: none;
  border: none;
  color: #007bff;
  text-decoration: underline;
  cursor: pointer;
  padding: 0;
}

.upload-progress {
  margin: 1rem 0;
}

.progress-bar {
  width: 100%;
  height: 20px;
  background: #eee;
  border-radius: 10px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #28a745;
  transition: width 0.3s;
}

.file-list table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
}

.file-list th,
.file-list td {
  padding: 0.5rem;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.file-list th {
  background: #f5f5f5;
  font-weight: bold;
}

.btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.85rem;
  margin-right: 0.25rem;
}

.btn-danger {
  background: #dc3545;
  color: white;
  border: none;
  cursor: pointer;
}

.no-files {
  text-align: center;
  color: #999;
  padding: 2rem;
}
</style>
