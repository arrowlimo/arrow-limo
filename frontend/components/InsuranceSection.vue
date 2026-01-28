<template>
  <div class="insurance-section">
    <h4>Insurance & Licensing</h4>
    <div style="margin-bottom:1rem;">
      <label>Upload Insurance/Licence Document:</label>
      <input type="file" @change="onUpload" />
    </div>
    <ul>
      <li v-for="doc in insuranceDocs" :key="doc.name">
        <a :href="doc.url" target="_blank">{{ doc.name }}</a>
        <span :class="expiryClass(doc)">{{ expiryText(doc) }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
const insuranceDocs = ref([])

async function fetchInsuranceDocs() {
  const res = await fetch('/api/business/documents')
  const data = await res.json()
  insuranceDocs.value = data.documents.filter(d => d.doc_type === 'insurance' || d.doc_type === 'licence')
}

async function onUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  // Prompt for type
  let docType = 'insurance'
  if (confirm('Is this a licence document?')) docType = 'licence'
  formData.append('doc_type', docType)
  let expiry = ''
  if (confirm('Add expiry date for this document?')) {
    expiry = prompt('Enter expiry date (YYYY-MM-DD) or leave blank:') || ''
  }
  formData.append('expiry', expiry)
  await fetch('/api/business/upload_document', { method: 'POST', body: formData })
  await fetchInsuranceDocs()
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

onMounted(fetchInsuranceDocs)
</script>

<style scoped>
.insurance-section { margin-bottom: 2rem; background: #fff8f8; padding: 1rem; border-radius: 6px; }
.expired { color: #c00; font-weight: bold; }
.expiring { color: #e67e22; font-weight: bold; }
</style>
