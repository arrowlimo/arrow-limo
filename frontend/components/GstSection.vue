<template>
  <div class="gst-section">
    <h4>GST Reports & Reconciliation</h4>
    <button @click="downloadReport('gst_extraction_report')">GST Extraction Report</button>
    <button @click="downloadReport('gst_year_end_reconciliation_report')">Year-End GST Reconciliation</button>
    <button @click="downloadReport('gst_paid_input_tax_report')">GST Paid Input Tax Report</button>
    <div style="margin-top:1rem;">
      <label>Upload GST Document:</label>
      <input type="file" @change="onUpload" />
    </div>
    <ul>
      <li v-for="doc in gstDocs" :key="doc.name">
        <a :href="doc.url" target="_blank">{{ doc.name }}</a>
        <span :class="expiryClass(doc)">{{ expiryText(doc) }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
const gstDocs = ref([])

function downloadReport(name) {
  window.open(`/reports/${name}.txt`, '_blank')
}

async function fetchGstDocs() {
  const res = await fetch('/api/business/documents')
  const data = await res.json()
  gstDocs.value = data.documents.filter(d => d.doc_type === 'gst')
}

async function onUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  formData.append('doc_type', 'gst')
  await fetch('/api/business/upload_document', { method: 'POST', body: formData })
  await fetchGstDocs()
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

onMounted(fetchGstDocs)
</script>

<style scoped>
.gst-section { margin-bottom: 2rem; background: #f8f8ff; padding: 1rem; border-radius: 6px; }
.expired { color: #c00; font-weight: bold; }
.expiring { color: #e67e22; font-weight: bold; }
</style>
