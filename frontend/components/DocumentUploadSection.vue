<template>
  <div class="document-upload-section">
    <h4>{{ sectionTitle }}</h4>
    <div class="upload-area"
         @dragover.prevent
         @drop.prevent="onDrop"
         @click="fileInput.click()">
      <span v-if="!uploading">Drag & drop or click to upload</span>
      <span v-if="uploading">Uploading...</span>
      <input ref="fileInput" type="file" multiple style="display:none" @change="onFileChange" />
    </div>
    <div class="doc-list">
      <div v-for="doc in docs" :key="doc.id" class="doc-item">
        <span>{{ doc.name }}</span>
        <span :class="expiryClass(doc)">{{ expiryText(doc) }}</span>
        <button @click="preview(doc)">Preview</button>
        <button @click="$emit('delete', doc)">Delete</button>
      </div>
    </div>
    <div v-if="previewDoc" class="doc-preview-modal" @click="previewDoc=null">
      <iframe v-if="isPdf(previewDoc)" :src="previewDoc.url" width="600" height="800"></iframe>
      <img v-else :src="previewDoc.url" style="max-width:600px;max-height:800px;" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
const props = defineProps({
  docs: Array,
  docType: String
})
const emit = defineEmits(['upload', 'delete'])
const fileInput = ref(null)
const uploading = ref(false)
const previewDoc = ref(null)

const sectionTitle = computed(() => {
  switch (props.docType) {
    case 'core': return 'Core Business Documents';
    case 'vehicle': return 'Vehicle & Fleet Compliance';
    case 'driver': return 'Driver & Staff Requirements';
    case 'operational': return 'Operational & Municipal Compliance';
    default: return 'Documents';
  }
})

function onDrop(e) {
  handleFiles(e.dataTransfer.files)
}
function onFileChange(e) {
  handleFiles(e.target.files)
}
function handleFiles(files) {
  uploading.value = true
  emit('upload', props.docType, files)
  uploading.value = false
}
function expiryClass(doc) {
  if (!doc.expiry) return ''
  const now = new Date()
  const exp = new Date(doc.expiry)
  if (exp < now) return 'expired'
  if ((exp - now) / (1000*60*60*24) < 30) return 'expiring'
  return ''
}
function expiryText(doc) {
  if (!doc.expiry) return ''
  const exp = new Date(doc.expiry)
  const now = new Date()
  if (exp < now) return 'Expired'
  if ((exp - now) / (1000*60*60*24) < 30) return 'Expiring soon'
  return 'Valid'
}
function preview(doc) {
  previewDoc.value = doc
}
function isPdf(doc) {
  return doc.name.endsWith('.pdf')
}
</script>

<style scoped>
.document-upload-section { margin-bottom: 2rem; }
.upload-area {
  border: 2px dashed #888;
  padding: 1.5rem;
  text-align: center;
  margin-bottom: 1rem;
  cursor: pointer;
  background: #fafbfc;
}
.doc-list { margin-top: 1rem; }
.doc-item { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem; }
.expired { color: #c00; font-weight: bold; }
.expiring { color: #e67e22; font-weight: bold; }
.doc-preview-modal {
  position: fixed; top: 10%; left: 50%; transform: translateX(-50%);
  background: #fff; border: 1px solid #ccc; box-shadow: 0 2px 8px #0002;
  padding: 1rem; z-index: 1000;
}
</style>
