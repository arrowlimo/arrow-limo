<template>
  <div class="payroll-section">
    <h4>Payroll Reports & Documents</h4>
    <button @click="downloadReport('printable_pay_report_by_driver_with_charters_and_wcb')">Printable Pay Report (Drivers/Charters/WCB)</button>
    <button @click="downloadReport('printable_pay_report_by_driver_with_charters')">Printable Pay Report (Drivers/Charters)</button>
    <button @click="downloadReport('printable_pay_report_by_driver')">Printable Pay Report (Drivers Only)</button>
    <div style="margin-top:1rem;">
      <label>Upload Payroll Document:</label>
      <input type="file" @change="onUpload" />
    </div>
    <ul>
      <li v-for="doc in payrollDocs" :key="doc.name">
        <a :href="doc.url" target="_blank">{{ doc.name }}</a>
        <span :class="expiryClass(doc)">{{ expiryText(doc) }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
const payrollDocs = ref([])

function downloadReport(name) {
  window.open(`/reports/${name}.txt`, '_blank')
}

async function fetchPayrollDocs() {
  const res = await fetch('/api/business/documents')
  const data = await res.json()
  payrollDocs.value = data.documents.filter(d => d.doc_type === 'payroll')
}

async function onUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  const formData = new FormData()
  formData.append('file', file)
  formData.append('doc_type', 'payroll')
  await fetch('/api/business/upload_document', { method: 'POST', body: formData })
  await fetchPayrollDocs()
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

onMounted(fetchPayrollDocs)
</script>

<style scoped>
.payroll-section { margin-bottom: 2rem; background: #f8fff8; padding: 1rem; border-radius: 6px; }
.expired { color: #c00; font-weight: bold; }
.expiring { color: #e67e22; font-weight: bold; }
</style>
