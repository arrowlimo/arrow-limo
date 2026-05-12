<template>
  <section class="audit-center">
    <header class="hero">
      <h1>Audit Center</h1>
      <p>Run automated checks, inspect audit trails, and generate year-end package bundles.</p>
    </header>

    <div class="panels">
      <article class="panel controls">
        <h2>Run Audit Checks</h2>
        <div class="grid two">
          <label>
            Fiscal Year
            <input v-model.number="checksForm.fiscal_year" type="number" min="2000" max="2100" />
          </label>
          <label>
            Package Mode
            <select v-model="checksForm.package_mode">
              <option value="standard">standard</option>
              <option value="print">print</option>
              <option value="email">email</option>
            </select>
          </label>
          <label>
            Date From
            <input v-model="checksForm.date_from" type="date" />
          </label>
          <label>
            Date To
            <input v-model="checksForm.date_to" type="date" />
          </label>
        </div>

        <div class="actions">
          <button class="btn primary" :disabled="busyChecks" @click="runChecks">
            {{ busyChecks ? 'Running...' : 'Run Checks' }}
          </button>
          <button class="btn" :disabled="busyPackage" @click="generatePackage">
            {{ busyPackage ? 'Generating...' : 'Generate Year-End Package' }}
          </button>
        </div>

        <p v-if="lastManifest" class="result-line">
          Package ready: <strong>{{ lastManifest.package_id }}</strong>
          <button class="link-btn" @click="downloadPackage(lastManifest.package_id)">Download ZIP</button>
        </p>
      </article>

      <article class="panel controls">
        <h2>Result Filters</h2>
        <div class="grid two">
          <label>
            Severity
            <select v-model="filters.severity">
              <option value="">All</option>
              <option value="critical">critical</option>
              <option value="high">high</option>
              <option value="medium">medium</option>
              <option value="low">low</option>
            </select>
          </label>
          <label>
            Module
            <input v-model.trim="filters.module" type="text" placeholder="invoices, payments, receipts" />
          </label>
          <label>
            User
            <input v-model.trim="filters.user" type="text" placeholder="username" />
          </label>
          <label>
            Date
            <input v-model="filters.date" type="date" />
          </label>
        </div>
        <div class="actions">
          <button class="btn" :disabled="busyEvents" @click="loadEvents">Refresh Events</button>
          <button class="btn" :disabled="busyPackages" @click="loadPackages">Refresh Packages</button>
        </div>
      </article>
    </div>

    <article class="panel checks">
      <h2>Check Results</h2>
      <div v-if="!lastReport" class="empty">No report yet. Click "Run Checks".</div>
      <div v-else>
        <div class="status-bar">
          <span class="pill" :class="statusClass(lastReport.overall_status)">Overall {{ lastReport.overall_status }}</span>
          <span>PASS {{ lastReport.summary.PASS || 0 }}</span>
          <span>WARN {{ lastReport.summary.WARN || 0 }}</span>
          <span>FAIL {{ lastReport.summary.FAIL || 0 }}</span>
        </div>

        <table class="table">
          <thead>
            <tr>
              <th>Status</th>
              <th>Severity</th>
              <th>Check</th>
              <th>Message</th>
              <th>Links</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="finding in filteredFindings" :key="finding.check_id + finding.message">
              <td><span class="pill" :class="statusClass(finding.status)">{{ finding.status }}</span></td>
              <td>{{ finding.severity }}</td>
              <td>{{ finding.check_id }}</td>
              <td>{{ finding.message }}</td>
              <td>
                <div class="deep-links" v-if="finding.affected_record_ids && finding.affected_record_ids.length">
                  <router-link
                    v-for="rid in finding.affected_record_ids.slice(0, 5)"
                    :key="rid"
                    :to="recordLink(finding.check_id, rid)"
                  >
                    {{ rid }}
                  </router-link>
                </div>
                <span v-else>-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>

    <article class="panel events">
      <h2>Audit Events</h2>
      <table class="table compact">
        <thead>
          <tr>
            <th>Time</th>
            <th>Module</th>
            <th>Action</th>
            <th>Entity</th>
            <th>User</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="event in filteredEvents" :key="event.event_id">
            <td>{{ formatTs(event.occurred_at) }}</td>
            <td>{{ event.module }}</td>
            <td>{{ event.action }}</td>
            <td>{{ event.entity_type }} #{{ event.entity_id }}</td>
            <td>{{ event.actor?.username || '-' }}</td>
          </tr>
          <tr v-if="!filteredEvents.length">
            <td colspan="5" class="empty">No events matching current filters.</td>
          </tr>
        </tbody>
      </table>
    </article>

    <article class="panel packages">
      <h2>Generated Packages</h2>
      <table class="table compact">
        <thead>
          <tr>
            <th>Package</th>
            <th>Year</th>
            <th>Status</th>
            <th>Generated</th>
            <th>Download</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="pkg in packages" :key="pkg.package_id">
            <td>{{ pkg.package_name }} ({{ pkg.package_id }})</td>
            <td>{{ pkg.fiscal_year }}</td>
            <td><span class="pill" :class="statusClass(pkg.overall_status)">{{ pkg.overall_status }}</span></td>
            <td>{{ formatTs(pkg.generated_at) }}</td>
            <td><button class="link-btn" @click="downloadPackage(pkg.package_id)">ZIP</button></td>
          </tr>
          <tr v-if="!packages.length">
            <td colspan="5" class="empty">No package runs yet.</td>
          </tr>
        </tbody>
      </table>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { authFetch } from '@/utils/authFetch'

const yearNow = new Date().getFullYear()

const checksForm = ref({
  fiscal_year: yearNow,
  date_from: `${yearNow}-01-01`,
  date_to: `${yearNow}-12-31`,
  package_mode: 'standard'
})

const filters = ref({
  severity: '',
  module: '',
  user: '',
  date: ''
})

const busyChecks = ref(false)
const busyEvents = ref(false)
const busyPackage = ref(false)
const busyPackages = ref(false)

const lastReport = ref(null)
const lastManifest = ref(null)
const events = ref([])
const packages = ref([])

function statusClass(status) {
  if (status === 'FAIL') return 'fail'
  if (status === 'WARN') return 'warn'
  return 'pass'
}

function recordLink(checkId, recordId) {
  if (checkId.includes('invoice')) return `/accounting?invoice=${encodeURIComponent(recordId)}`
  if (checkId.includes('trip')) return `/charter/${encodeURIComponent(recordId)}`
  if (checkId.includes('pd7a') || checkId.includes('t4') || checkId.includes('payroll')) return `/payroll-compliance?record=${encodeURIComponent(recordId)}`
  if (checkId.includes('receipt')) return `/receipts?receipt=${encodeURIComponent(recordId)}`
  if (checkId.includes('payment')) return `/received-payments?payment=${encodeURIComponent(recordId)}`
  return '/reports'
}

function formatTs(value) {
  if (!value) return '-'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return String(value)
  return dt.toLocaleString()
}

const filteredFindings = computed(() => {
  const report = lastReport.value
  if (!report?.findings) return []
  return report.findings.filter((f) => {
    const matchSeverity = !filters.value.severity || f.severity === filters.value.severity
    const moduleHint = (f.data_sources || []).join(',').toLowerCase()
    const matchModule = !filters.value.module || moduleHint.includes(filters.value.module.toLowerCase())
    return matchSeverity && matchModule
  })
})

const filteredEvents = computed(() => {
  return events.value.filter((event) => {
    const eventDate = event.occurred_at ? String(event.occurred_at).slice(0, 10) : ''
    const matchDate = !filters.value.date || eventDate === filters.value.date
    const matchModule = !filters.value.module || String(event.module || '').toLowerCase().includes(filters.value.module.toLowerCase())
    const actor = event.actor?.username || ''
    const matchUser = !filters.value.user || String(actor).toLowerCase().includes(filters.value.user.toLowerCase())
    return matchDate && matchModule && matchUser
  })
})

async function runChecks() {
  busyChecks.value = true
  try {
    const res = await authFetch('/api/audit/checks', {
      method: 'POST',
      body: JSON.stringify(checksForm.value)
    })
    if (!res || !res.ok) throw new Error('Failed to run checks')
    lastReport.value = await res.json()
    await loadEvents()
  } finally {
    busyChecks.value = false
  }
}

async function loadEvents() {
  busyEvents.value = true
  try {
    const params = new URLSearchParams({ limit: '500', offset: '0' })
    if (checksForm.value.date_from) params.set('date_from', checksForm.value.date_from)
    if (checksForm.value.date_to) params.set('date_to', checksForm.value.date_to)
    if (filters.value.module) params.set('module', filters.value.module)
    if (filters.value.user) params.set('username', filters.value.user)
    const res = await authFetch(`/api/audit/events?${params.toString()}`)
    if (!res || !res.ok) throw new Error('Failed to fetch events')
    const data = await res.json()
    events.value = data.items || []
  } finally {
    busyEvents.value = false
  }
}

async function generatePackage() {
  busyPackage.value = true
  try {
    const res = await authFetch('/api/audit/package/year-end', {
      method: 'POST',
      body: JSON.stringify(checksForm.value)
    })
    if (!res || !res.ok) throw new Error('Failed to generate package')
    lastManifest.value = await res.json()
    await loadPackages()
  } finally {
    busyPackage.value = false
  }
}

async function loadPackages() {
  busyPackages.value = true
  try {
    const params = new URLSearchParams({
      limit: '100',
      offset: '0',
      fiscal_year: String(checksForm.value.fiscal_year)
    })
    const res = await authFetch(`/api/audit/packages?${params.toString()}`)
    if (!res || !res.ok) throw new Error('Failed to fetch package runs')
    const data = await res.json()
    packages.value = data.items || []
  } finally {
    busyPackages.value = false
  }
}

async function downloadPackage(packageId) {
  const res = await authFetch(`/api/audit/package/${encodeURIComponent(packageId)}/download`)
  if (!res || !res.ok) {
    throw new Error('Failed to download package ZIP')
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `${packageId}.zip`
  anchor.click()
  URL.revokeObjectURL(url)
}

onMounted(async () => {
  await Promise.all([loadEvents(), loadPackages()])
})
</script>

<style scoped>
.audit-center {
  display: grid;
  gap: 1rem;
}
.hero {
  border: 1px solid #d1d5db;
  background: linear-gradient(120deg, #fef7e7 0%, #eef6ff 100%);
  padding: 1rem 1.2rem;
  border-radius: 10px;
}
.hero h1 {
  margin: 0;
}
.hero p {
  margin: 0.35rem 0 0;
}
.panels {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 1rem;
}
.panel {
  background: #ffffff;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  padding: 1rem;
}
.panel h2 {
  margin-top: 0;
}
.grid.two {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}
label {
  display: grid;
  gap: 0.35rem;
  font-size: 0.9rem;
}
input,
select {
  border: 1px solid #cbd5e1;
  border-radius: 6px;
  padding: 0.45rem 0.55rem;
}
.actions {
  margin-top: 0.8rem;
  display: flex;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.btn {
  border: 1px solid #334155;
  background: #ffffff;
  color: #1e293b;
  border-radius: 6px;
  padding: 0.45rem 0.75rem;
  cursor: pointer;
}
.btn.primary {
  background: #0f766e;
  border-color: #0f766e;
  color: #ffffff;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.link-btn {
  border: none;
  background: transparent;
  color: #0b61d8;
  cursor: pointer;
  text-decoration: underline;
  padding: 0;
}
.result-line {
  margin-top: 0.8rem;
}
.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9rem;
}
.table th,
.table td {
  border-bottom: 1px solid #e2e8f0;
  text-align: left;
  padding: 0.45rem;
  vertical-align: top;
}
.table.compact {
  font-size: 0.85rem;
}
.status-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.65rem;
}
.pill {
  border-radius: 999px;
  padding: 0.15rem 0.55rem;
  font-size: 0.78rem;
  font-weight: 600;
}
.pill.pass {
  background: #dcfce7;
  color: #166534;
}
.pill.warn {
  background: #fef9c3;
  color: #854d0e;
}
.pill.fail {
  background: #fee2e2;
  color: #991b1b;
}
.deep-links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}
.empty {
  color: #64748b;
}
@media (max-width: 900px) {
  .grid.two {
    grid-template-columns: 1fr;
  }
}
</style>
