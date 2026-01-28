<template>
  <div class="business-dashboard">
    <h2>Business Compliance Dashboard</h2>
    <section>
      <h3>Core Business Documents</h3>
  <DocumentUploadSection :docs="coreBusinessDocs" doc-type="core" @upload="onUpload" @delete="onDelete" />
    </section>
    <section>
      <h3>Vehicle & Fleet Compliance</h3>
  <DocumentUploadSection :docs="vehicleDocs" doc-type="vehicle" @upload="onUpload" @delete="onDelete" />
    </section>
    <section>
      <h3>Driver & Staff Requirements</h3>
  <DocumentUploadSection :docs="driverDocs" doc-type="driver" @upload="onUpload" @delete="onDelete" />
    </section>
    <section>
      <h3>Operational & Municipal Compliance</h3>
  <DocumentUploadSection :docs="operationalDocs" doc-type="operational" @upload="onUpload" @delete="onDelete" />
    </section>
    <section>
      <h3>GST Compliance</h3>
      <GstSection />
    </section>
    <section>
      <h3>Payroll Compliance</h3>
      <PayrollSection />
    </section>
    <section>
      <h3>Insurance & Licensing Compliance</h3>
      <InsuranceSection />
    </section>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import DocumentUploadSection from './DocumentUploadSection.vue'
import GstSection from './GstSection.vue'
import PayrollSection from './PayrollSection.vue'
import InsuranceSection from './InsuranceSection.vue'

const coreBusinessDocs = ref([])
const vehicleDocs = ref([])
const driverDocs = ref([])
const operationalDocs = ref([])

async function fetchBusinessDocuments() {
  const res = await fetch('/api/business/documents')
  const data = await res.json()
  // Partition by doc_type
  coreBusinessDocs.value = data.documents.filter(d => d.doc_type === 'core')
  vehicleDocs.value = data.documents.filter(d => d.doc_type === 'vehicle')
  driverDocs.value = data.documents.filter(d => d.doc_type === 'driver')
  operationalDocs.value = data.documents.filter(d => d.doc_type === 'operational')
}

async function onUpload(type, files) {
  for (const file of files) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('doc_type', type)
    // Prompt for expiry if needed (simple prompt for demo)
    let expiry = ''
    if (confirm('Add expiry date for this document?')) {
      expiry = prompt('Enter expiry date (YYYY-MM-DD) or leave blank:') || ''
    }
    formData.append('expiry', expiry)
    await fetch('/api/business/upload_document', {
      method: 'POST',
      body: formData
    })
  }
  await fetchBusinessDocuments()
}

async function onDelete(doc) {
  await fetch(`/api/business/document/${encodeURIComponent(doc.name)}`, { method: 'DELETE' })
  await fetchBusinessDocuments()
}

onMounted(() => {
  fetchBusinessDocuments()
})
</script>

<style scoped>
.business-dashboard {
  max-width: 900px;
  margin: 2rem auto;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 8px #0001;
  padding: 2rem;
}
section {
  margin-bottom: 2rem;
}
</style>
