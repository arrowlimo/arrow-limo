<template>
  <div class="driver-portal">
    <header class="portal-header">
      <div>
        <h1>My Driver Portal</h1>
        <p v-if="profile">{{ profile.name }} · {{ profile.phone || profile.email }}</p>
      </div>
      <button class="secondary" @click="loadPortal">Refresh</button>
    </header>

    <div v-if="error" class="message error">{{ error }}</div>
    <div v-if="notice" class="message success">{{ notice }}</div>
    <div v-if="loading" class="loading">Loading your driver information...</div>

    <template v-else>
      <nav class="tabs" aria-label="Driver portal sections">
        <button v-for="tab in tabs" :key="tab.id" :class="{ active: activeTab === tab.id }" @click="activeTab = tab.id">
          {{ tab.label }}
        </button>
      </nav>

      <section v-if="activeTab === 'personal'" class="panel">
        <div class="section-heading">
          <h2>My Personal Record</h2>
          <button class="secondary print-button" @click="printReport">Print record</button>
        </div>
        <div v-if="profile" class="record-grid">
          <div><span>Name</span><strong>{{ profile.name }}</strong></div>
          <div><span>Email</span><strong>{{ profile.email || 'Not entered' }}</strong></div>
          <div><span>Phone</span><strong>{{ profile.phone || 'Not entered' }}</strong></div>
          <div><span>Employee type</span><strong>{{ profile.employee_type || 'Not entered' }}</strong></div>
          <div><span>Hire date</span><strong>{{ formatDate(profile.hire_date) }}</strong></div>
          <div><span>Status</span><strong>{{ profile.employment_status || 'Not entered' }}</strong></div>
        </div>
      </section>

      <section v-if="activeTab === 'runs'" class="panel">
        <h2>My Runs · {{ calendarStart }} forward</h2>
        <div v-if="calendarItems.length === 0" class="empty-state">No assigned runs from the previous month forward.</div>
        <div v-else class="card-grid">
          <article v-for="trip in calendarItems" :key="trip.charter_id" class="trip-card">
            <div class="trip-heading">
              <strong>{{ formatDate(trip.date) }} · {{ formatTime(trip.pickup_time) }}</strong>
              <span class="status">{{ trip.status || 'Scheduled' }}</span>
            </div>
            <div>Run {{ trip.reserve_number || trip.charter_id }}</div>
            <div>{{ trip.pickup_address || 'Pickup not entered' }}</div>
            <div>to {{ trip.dropoff_address || 'Dropoff not entered' }}</div>
            <button @click="openTrip(trip.charter_id)">Open run</button>
          </article>
        </div>
        <button v-if="calendarHasMore" class="secondary load-more" :disabled="loadingMoreRuns" @click="loadMoreRuns">
          {{ loadingMoreRuns ? 'Loading...' : 'Load more future runs' }}
        </button>
      </section>

      <section v-if="activeTab === 'hos'" class="panel">
        <div class="section-heading">
          <h2>My HOS · Preceding 14 days</h2>
          <button class="secondary print-button" @click="printReport">Print HOS</button>
        </div>
        <p class="hos-scope">
          Alberta provincial · 160 km daily-log exemption · carrier time records retained for at least 6 months
        </p>
        <p class="hos-rule">
          Review limits: 13 driving hours; no driving after 15 consecutive on-duty hours; at least 8 consecutive
          hours off before a shift. Breaks: 10 minutes after up to 4 continuous driving hours, or 30 minutes after
          more than 4 and up to 6 continuous driving hours.
        </p>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Status</th><th>Date</th><th>Off duty</th><th>On duty</th><th>D.A.B.</th><th>Total</th><th>Runs</th></tr></thead>
            <tbody>
              <template v-for="entry in hosEntries" :key="entry.date">
              <tr :class="`hos-${entry.status}`">
                <td><span class="hos-status">{{ hosStatus(entry) }}</span></td>
                <td>{{ formatDate(entry.date) }}</td>
                <td>{{ recorded(entry.total_off_duty) }}</td>
                <td>{{ recorded(entry.total_on_duty) }}</td>
                <td>{{ recorded(entry.total_driving) }}</td>
                <td>{{ recorded(entry.total_hours) }}</td>
                <td>
                  <button class="table-button" @click="toggleHosDay(entry.date)">
                    {{ entry.charters.length }} · {{ expandedHosDay === entry.date ? 'Hide' : 'Details' }}
                  </button>
                </td>
              </tr>
              <tr v-if="expandedHosDay === entry.date" class="hos-detail-row">
                <td colspan="7">
                  <div class="hos-alerts">
                    <strong>Daily review</strong>
                    <ul><li v-for="alert in entry.alerts" :key="alert">{{ alert }}</li></ul>
                    <div>
                      Shift {{ formatTimestamp(entry.workshift_start) }} to {{ formatTimestamp(entry.workshift_end) }}
                      · Elapsed {{ hours(entry.shift_elapsed) }}
                      · Consecutive rest before shift: {{ hours(entry.rest_before_shift) }}
                    </div>
                  </div>
                  <div v-if="entry.charters.length === 0">No assigned charters.</div>
                  <div v-else class="hos-charters">
                    <article v-for="trip in entry.charters" :key="trip.charter_id">
                      <strong>Run {{ trip.reserve_number }}</strong>
                      <span>{{ formatTime(trip.pickup_time) }} to {{ formatTime(trip.dropoff_time) }}</span>
                      <span>
                        Vehicle {{ trip.vehicle_number || 'not assigned' }} ·
                        {{ trip.vehicle_type || 'type not recorded' }} ·
                        {{ trip.passenger_capacity ?? 'unknown' }} seats
                      </span>
                      <span>Passengers {{ trip.passenger_count ?? 'not recorded' }} · Actual run hours {{ recorded(trip.actual_hours) }}</span>
                      <span>D.A.B. {{ hours(trip.bus_driving_hours) }} · Breaks {{ trip.break_minutes ?? 'not recorded' }} minutes</span>
                      <span>
                        {{
                          trip.passenger_capacity === null
                            ? 'Capacity missing · D.A.B. classification needs review'
                            : trip.is_bus
                              ? 'Capacity 11+ · D.A.B. applies'
                              : 'Capacity 10 or fewer · all hours are On Duty; D.A.B. is zero'
                        }}
                      </span>
                      <span v-if="trip.is_out_of_town">Out-of-town run · dispatch must confirm it remained within 160 km</span>
                      <button @click="openTrip(trip.charter_id)">Open run</button>
                    </article>
                  </div>
                  <p class="hos-evidence">
                    Total break hours alone cannot prove Alberta's continuous-driving break rule. Duty-status
                    timestamps must show each required interruption. “Out of town” does not by itself prove travel
                    beyond 160 km; dispatch must confirm exemption eligibility.
                  </p>
                </td>
              </tr>
              </template>
              <tr v-if="hosEntries.length === 0"><td colspan="7">HOS records are unavailable for the preceding 14 days.</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="activeTab === 'run'" class="panel">
        <div class="section-heading">
          <h2>Complete My Run Information</h2>
          <button v-if="selectedTrip" class="secondary print-button" @click="printReport">Print run report</button>
        </div>
        <div v-if="!selectedTrip" class="empty-state">Choose a run from My Runs.</div>
        <form v-else class="form-grid" @submit.prevent="saveTrip">
          <div class="readonly wide">
            <strong>{{ selectedTrip.reserve_number }}</strong>
            <span>{{ formatDate(selectedTrip.date) }} · {{ selectedTrip.pickup_address }} to {{ selectedTrip.dropoff_address }}</span>
          </div>
          <label>
            Starting odometer
            <input v-model.number="tripForm.odometer_start" type="number" min="0" step="0.1">
          </label>
          <label>
            Ending odometer
            <input v-model.number="tripForm.odometer_end" type="number" min="0" step="0.1">
          </label>
          <label>
            Fuel added (litres)
            <input v-model.number="tripForm.fuel_added_liters" type="number" min="0" step="0.01">
          </label>
          <label>
            Actual hours
            <input v-model.number="tripForm.actual_hours" type="number" min="0" max="24" step="0.25">
          </label>
          <label>
            D.A.B. hours
            <input
              v-model.number="tripForm.bus_driving_hours"
              type="number"
              min="0"
              max="24"
              step="0.25"
              :disabled="!selectedTrip.is_bus"
            >
            <small>
              {{
                selectedTrip.passenger_capacity === null
                  ? 'Vehicle capacity is missing; have dispatch correct the vehicle record.'
                  : selectedTrip.is_bus
                    ? 'Vehicle capacity is 11+ including the driver. Enter driving time only.'
                    : 'Vehicle capacity is 10 or fewer; record all work as On Duty. D.A.B. is zero.'
              }}
            </small>
          </label>
          <label>
            Non-driving / off-duty break minutes
            <input v-model.number="tripForm.break_minutes" type="number" min="0" max="1440" step="1">
          </label>
          <label class="wide">
            Driver notes
            <textarea v-model="tripForm.driver_notes" rows="4"></textarea>
          </label>
          <label class="wide">
            Vehicle notes
            <textarea v-model="tripForm.vehicle_notes" rows="3"></textarea>
          </label>
          <label class="checkbox">
            <input v-model="tripForm.mark_completed" type="checkbox" :disabled="selectedTrip.status === 'completed'">
            {{ selectedTrip.status === 'completed' ? 'Run completed' : 'Mark run completed' }}
          </label>
          <div class="actions">
            <button type="submit" :disabled="saving">{{ saving ? 'Saving...' : 'Save run' }}</button>
          </div>
        </form>
      </section>

      <section v-if="activeTab === 'receipts'" class="panel">
        <h2>My Receipts</h2>
        <form class="form-grid receipt-form" @submit.prevent="submitReceipt">
          <label>
            Date
            <input v-model="receiptForm.receipt_date" type="date" required>
          </label>
          <label>
            Vendor
            <input v-model.trim="receiptForm.vendor_name" maxlength="255" required>
          </label>
          <label>
            Amount
            <input v-model.number="receiptForm.gross_amount" type="number" min="0.01" step="0.01" required>
          </label>
          <label>
            Related run
            <select v-model="receiptForm.charter_id">
              <option :value="null">No specific run</option>
              <option v-for="trip in calendarItems" :key="trip.charter_id" :value="trip.charter_id">
                {{ trip.reserve_number }} · {{ formatDate(trip.date) }}
              </option>
            </select>
          </label>
          <label>
            Category
            <input v-model.trim="receiptForm.category" maxlength="100" placeholder="Fuel, parking, supplies">
          </label>
          <label class="checkbox">
            <input v-model="receiptForm.paid_from_float" type="checkbox">
            Paid from company float
          </label>
          <label class="wide">
            Description
            <textarea v-model="receiptForm.description" rows="2"></textarea>
          </label>
          <div class="actions">
            <button type="submit" :disabled="saving">{{ saving ? 'Submitting...' : 'Add receipt' }}</button>
          </div>
        </form>

        <div class="table-wrap">
          <table>
            <thead><tr><th>Date</th><th>Vendor</th><th>Run</th><th>Source</th><th>Amount</th></tr></thead>
            <tbody>
              <tr v-for="receipt in receipts" :key="receipt.receipt_id">
                <td>{{ formatDate(receipt.receipt_date) }}</td>
                <td>{{ receipt.vendor_name }}</td>
                <td>{{ receipt.reserve_number || '—' }}</td>
                <td>{{ receipt.paid_from_float ? 'Company float' : 'Driver paid' }}</td>
                <td>{{ money(receipt.gross_amount) }}</td>
              </tr>
              <tr v-if="receipts.length === 0"><td colspan="5">No receipts submitted.</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="activeTab === 'float'" class="panel">
        <h2>My Float</h2>
        <div class="summary-grid">
          <div><span>Issued</span><strong>{{ money(floatSummary.issued) }}</strong></div>
          <div><span>Float receipts</span><strong>{{ money(floatSummary.receipts) }}</strong></div>
          <div><span>Cash turned in</span><strong>{{ money(floatSummary.returned) }}</strong></div>
          <div :class="{ settled: floatSummary.settled }"><span>Still held</span><strong>{{ money(floatSummary.remaining) }}</strong></div>
          <div><span>Driver paid</span><strong>{{ money(floatSummary.driver_paid) }}</strong></div>
        </div>
        <p v-if="floatSummary.reimbursement_due > 0" class="message">
          Receipts exceed issued float by {{ money(floatSummary.reimbursement_due) }}.
        </p>
        <form class="inline-form" @submit.prevent="submitFloatReturn">
          <label>
            Cash turned in
            <input v-model.number="returnForm.amount" type="number" min="0.01" step="0.01" required>
          </label>
          <label>
            Related run
            <select v-model="returnForm.charter_id">
              <option :value="null">No specific run</option>
              <option v-for="trip in calendarItems" :key="trip.charter_id" :value="trip.charter_id">
                {{ trip.reserve_number }}
              </option>
            </select>
          </label>
          <label>
            Note
            <input v-model.trim="returnForm.notes" maxlength="1000">
          </label>
          <button type="submit" :disabled="saving">Record turn-in</button>
        </form>
      </section>

      <section v-if="activeTab === 'statements'" class="panel">
        <div class="section-heading">
          <h2>My Saved Monthly Pay Statements</h2>
          <div class="statement-actions">
            <label>
              Year
              <input v-model.number="statementYear" type="number" min="2000" max="2100" @change="loadStatements">
            </label>
            <button class="secondary print-button" @click="printReport">Print statements</button>
          </div>
        </div>
        <div class="table-wrap">
          <table>
            <thead><tr><th>Month</th><th>Pay date</th><th>Period</th><th>Total hours</th><th>Overtime</th><th>Gross</th><th>Deductions</th><th>Net</th></tr></thead>
            <tbody>
              <tr v-for="statement in statements" :key="statement.statement_id">
                <td>{{ monthName(statement.month) }}</td>
                <td>{{ formatDate(statement.pay_date) }}</td>
                <td>{{ formatDate(statement.period_start) }} – {{ formatDate(statement.period_end) }}</td>
                <td>{{ statement.total_hours }}</td>
                <td>{{ statement.overtime_hours }}</td>
                <td>{{ money(statement.gross_pay) }}</td>
                <td>{{ money(statement.deductions) }}</td>
                <td><strong>{{ money(statement.net_pay) }}</strong></td>
              </tr>
              <tr v-if="statements.length === 0"><td colspan="8">No saved monthly pay statements found for this year.</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="activeTab === 't4s'" class="panel">
        <div class="section-heading">
          <h2>My Saved T4 Records</h2>
          <button class="secondary print-button" @click="printReport">Print T4 records</button>
        </div>
        <article v-for="year in employmentYears" :key="year" class="t4-record">
          <h3>{{ year }} T4</h3>
          <div v-if="t4ForYear(year)" class="record-grid">
            <div><span>Box 14 · Employment income</span><strong>{{ money(t4ForYear(year).box_14) }}</strong></div>
            <div><span>Box 16 · CPP contributions</span><strong>{{ money(t4ForYear(year).box_16) }}</strong></div>
            <div><span>Box 18 · EI premiums</span><strong>{{ money(t4ForYear(year).box_18) }}</strong></div>
            <div><span>Box 22 · Income tax</span><strong>{{ money(t4ForYear(year).box_22) }}</strong></div>
            <div><span>Box 24 · EI insurable earnings</span><strong>{{ money(t4ForYear(year).box_24) }}</strong></div>
            <div><span>Box 26 · CPP pensionable earnings</span><strong>{{ money(t4ForYear(year).box_26) }}</strong></div>
            <div><span>Box 44 · Union dues</span><strong>{{ money(t4ForYear(year).box_44) }}</strong></div>
            <div><span>Box 46 · Charitable donations</span><strong>{{ money(t4ForYear(year).box_46) }}</strong></div>
            <div><span>Box 52 · Pension adjustment</span><strong>{{ money(t4ForYear(year).box_52) }}</strong></div>
          </div>
          <div v-else class="empty-state">No saved T4 record exists for this employment year.</div>
        </article>
        <div v-if="employmentYears.length === 0" class="empty-state">No employment-year history is available.</div>
      </section>

      <section v-if="activeTab === 'records'" class="panel">
        <div class="section-heading">
          <h2>My Licences, Permits &amp; Certifications</h2>
          <button class="secondary" @click="loadCompliance">Refresh</button>
        </div>
        <p class="records-note">
          Changes you make here are <strong>not applied immediately</strong>. They are sent to the
          office for authorization, and your record only updates once an administrator approves it.
        </p>
        <div v-if="complianceNotice" class="records-notice">{{ complianceNotice }}</div>
        <div v-if="complianceError" class="records-error">{{ complianceError }}</div>

        <div class="table-wrap">
          <table>
            <thead><tr><th>Record</th><th>Current value</th><th>Change to</th><th>Status</th></tr></thead>
            <tbody>
              <tr v-for="field in complianceFields" :key="field.field_key">
                <td>{{ field.label }}</td>
                <td>{{ field.current_value || '—' }}</td>
                <td>
                  <input
                    v-model="complianceDraft[field.field_key]"
                    :type="field.type === 'date' ? 'date' : 'text'"
                  >
                </td>
                <td>
                  <span v-if="field.awaiting_approval" class="pending-flag">
                    Awaiting approval: {{ field.pending_value || '(cleared)' }}
                  </span>
                  <span v-else>—</span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="records-actions">
          <button :disabled="complianceSaving" @click="submitCompliance">
            {{ complianceSaving ? 'Submitting…' : 'Submit changes for approval' }}
          </button>
        </div>

        <h3>Upload a Photo or PDF of a Document</h3>
        <form class="record-upload" @submit.prevent="uploadDocument">
          <label>
            Document type
            <select v-model="documentForm.document_type">
              <option value="DRIVER_LICENCE">Driver Licence</option>
              <option value="CHAUFFEUR_PERMIT">Driver-for-Hire / Chauffeur Permit</option>
              <option value="PROSERVE">ProServe Certificate</option>
              <option value="MEDICAL">Medical Certificate</option>
              <option value="DRIVER_ABSTRACT">Driver Abstract</option>
              <option value="VULNERABLE_SECTOR">Vulnerable Sector Check</option>
              <option value="TRAINING">Training Certificate</option>
              <option value="OTHER">Other</option>
            </select>
          </label>
          <label>
            Document number
            <input v-model="documentForm.document_number" type="text">
          </label>
          <label>
            Expiry date
            <input v-model="documentForm.expiry_date" type="date">
          </label>
          <label>
            File (JPG, PNG or PDF, max 8 MB)
            <input ref="documentInput" type="file" accept="image/*,application/pdf" @change="onDocumentSelected">
          </label>
          <button type="submit" :disabled="documentUploading">
            {{ documentUploading ? 'Uploading…' : 'Upload document' }}
          </button>
        </form>

        <div class="table-wrap">
          <table>
            <thead><tr><th>Document</th><th>Type</th><th>Expiry</th><th>Uploaded</th><th>Status</th></tr></thead>
            <tbody>
              <tr v-for="doc in complianceDocuments" :key="doc.upload_id">
                <td>{{ doc.document_name }}</td>
                <td>{{ doc.document_type }}</td>
                <td>{{ doc.expiry_date ? formatDate(doc.expiry_date) : '—' }}</td>
                <td>{{ formatDate(doc.uploaded_at) }}</td>
                <td>{{ doc.status }}</td>
              </tr>
              <tr v-if="complianceDocuments.length === 0"><td colspan="5">No documents uploaded yet.</td></tr>
            </tbody>
          </table>
        </div>
      </section>

      <section v-if="activeTab === 'training'" class="panel">
        <div class="section-heading">
          <h2>My Training Checklist</h2>
          <button class="secondary" @click="loadTraining">Refresh</button>
        </div>
        <p class="records-note">
          This is a <strong>read-only</strong> view. Training completion is verified and recorded by
          the office &mdash; if something here looks wrong, contact dispatch.
        </p>
        <div v-if="trainingError" class="records-error">{{ trainingError }}</div>

        <div class="training-summary">
          <span class="training-chip done">{{ trainingSummary.completed || 0 }} complete</span>
          <span class="training-chip progress">{{ trainingSummary.in_progress || 0 }} in progress</span>
          <span class="training-chip todo">{{ trainingSummary.not_started || 0 }} not started</span>
          <span v-if="trainingSummary.expired" class="training-chip expired">
            {{ trainingSummary.expired }} expired
          </span>
        </div>

        <article v-for="program in trainingPrograms" :key="program.step_number" class="training-card">
          <header class="training-card-head">
            <div>
              <span class="training-step">Step {{ program.step_number }}</span>
              <strong>{{ program.program_name }}</strong>
              <span class="training-cat">{{ categoryLabel(program.category) }}</span>
              <span v-if="!program.is_mandatory" class="training-cat">optional</span>
            </div>
            <span class="training-status" :class="program.status">
              {{ statusLabel(program.status) }}
            </span>
          </header>
          <div class="training-dates">
            <span>Started: {{ program.started_date ? formatDate(program.started_date) : '—' }}</span>
            <span>Completed: {{ program.completed_date ? formatDate(program.completed_date) : '—' }}</span>
            <span>
              Renews: {{ program.expiry_date ? formatDate(program.expiry_date) : '—' }}
              <template v-if="program.days_until_expiry !== null && program.days_until_expiry !== undefined">
                ({{ program.days_until_expiry }} days)
              </template>
            </span>
          </div>
          <ul v-if="program.items.length" class="training-items">
            <li v-for="item in program.items" :key="item.item_name">
              <span>{{ item.completed ? '☑' : '☐' }}</span>
              {{ item.item_name }}
              <em v-if="!item.is_required">(optional)</em>
              <span v-if="item.completed_date"> &mdash; {{ formatDate(item.completed_date) }}</span>
            </li>
          </ul>
        </article>

        <div v-if="trainingPrograms.length === 0" class="empty-state">
          No training checklist has been assigned to you yet.
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { authFetch } from '@/utils/authFetch'

const tabs = [
  { id: 'personal', label: 'Personal Record' },
  { id: 'runs', label: 'My Runs' },
  { id: 'run', label: 'Run Details' },
  { id: 'hos', label: 'HOS' },
  { id: 'receipts', label: 'Receipts' },
  { id: 'float', label: 'Float' },
  { id: 'statements', label: 'Pay Statements' },
  { id: 't4s', label: 'T4 Records' },
  { id: 'records', label: 'My Records' },
  { id: 'training', label: 'My Training' }
]
const activeTab = ref('runs')
const loading = ref(true)
const loadingMoreRuns = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const profile = ref(null)
const calendarItems = ref([])
const calendarStart = ref('')
const calendarHasMore = ref(false)
const calendarNextOffset = ref(null)
const hosEntries = ref([])
const expandedHosDay = ref(null)
const selectedTrip = ref(null)
const receipts = ref([])
const statements = ref([])
const t4Records = ref([])
const employmentYears = computed(() => {
  const savedYears = t4Records.value.map(record => Number(record.tax_year)).filter(Boolean)
  const hireYear = Number(String(profile.value?.hire_date || '').slice(0, 4))
  if (!hireYear) return [...new Set(savedYears)].sort((a, b) => b - a)
  const currentYear = new Date().getFullYear()
  const employedYears = Array.from(
    { length: Math.max(0, currentYear - hireYear + 1) },
    (_, index) => currentYear - index
  )
  return [...new Set([...savedYears, ...employedYears])].sort((a, b) => b - a)
})
const statementYear = ref(new Date().getFullYear())
const floatSummary = reactive({ issued: null, receipts: null, driver_paid: null, returned: null, remaining: null, reimbursement_due: null, settled: null })
const tripForm = reactive({})
const receiptForm = reactive({
  receipt_date: new Date().toISOString().slice(0, 10),
  vendor_name: '',
  gross_amount: null,
  category: '',
  description: '',
  charter_id: null,
  paid_from_float: false
})
const returnForm = reactive({ amount: null, charter_id: null, notes: '' })
const complianceFields = ref([])
const trainingPrograms = ref([])
const trainingSummary = ref({})
const trainingError = ref('')
const complianceDocuments = ref([])
const complianceDraft = reactive({})
const complianceSaving = ref(false)
const documentUploading = ref(false)
const complianceNotice = ref('')
const complianceError = ref('')
const documentInput = ref(null)
const documentForm = reactive({
  document_type: 'DRIVER_LICENCE',
  document_number: '',
  expiry_date: '',
  file_base64: '',
  file_name: '',
  mime_type: ''
})

const requestJson = async (url, options) => {
  const response = await authFetch(url, options)
  if (!response) throw new Error('Your session has expired')
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(payload.detail || 'Request failed')
  return payload
}

const loadTraining = async () => {
  trainingError.value = ''
  try {
    const payload = await requestJson('/api/chauffeur/me/training')
    trainingPrograms.value = payload.programs || []
    trainingSummary.value = payload.summary || {}
  } catch (err) {
    trainingError.value = err.message
  }
}

const loadCompliance = async () => {
  complianceError.value = ''
  try {
    const payload = await requestJson('/api/chauffeur/me/compliance')
    complianceFields.value = payload.fields || []
    complianceDocuments.value = payload.documents || []
    complianceFields.value.forEach(field => {
      complianceDraft[field.field_key] = field.pending_value ?? field.current_value ?? ''
    })
  } catch (err) {
    complianceError.value = err.message
  }
}

const submitCompliance = async () => {
  complianceError.value = ''
  complianceNotice.value = ''
  const changes = complianceFields.value
    .filter(field => (complianceDraft[field.field_key] ?? '') !== (field.pending_value ?? field.current_value ?? ''))
    .map(field => ({ field_key: field.field_key, new_value: complianceDraft[field.field_key] || null }))

  if (changes.length === 0) {
    complianceNotice.value = 'Nothing has been changed yet.'
    return
  }

  complianceSaving.value = true
  try {
    const payload = await requestJson('/api/chauffeur/me/compliance', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ changes })
    })
    complianceNotice.value = payload.message || 'Submitted for approval.'
    await loadCompliance()
  } catch (err) {
    complianceError.value = err.message
  } finally {
    complianceSaving.value = false
  }
}

const onDocumentSelected = event => {
  const file = event.target.files && event.target.files[0]
  if (!file) {
    documentForm.file_base64 = ''
    return
  }
  documentForm.file_name = file.name
  documentForm.mime_type = file.type || 'application/octet-stream'
  const reader = new FileReader()
  reader.onload = () => {
    documentForm.file_base64 = String(reader.result).split(',')[1] || ''
  }
  reader.readAsDataURL(file)
}

const uploadDocument = async () => {
  complianceError.value = ''
  complianceNotice.value = ''
  if (!documentForm.file_base64) {
    complianceError.value = 'Choose a file to upload first.'
    return
  }
  documentUploading.value = true
  try {
    const payload = await requestJson('/api/chauffeur/me/documents', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        document_type: documentForm.document_type,
        document_name: documentForm.file_name,
        mime_type: documentForm.mime_type,
        file_base64: documentForm.file_base64,
        expiry_date: documentForm.expiry_date || null,
        document_number: documentForm.document_number || null
      })
    })
    complianceNotice.value = payload.message || 'Document uploaded.'
    documentForm.file_base64 = ''
    documentForm.file_name = ''
    documentForm.document_number = ''
    documentForm.expiry_date = ''
    if (documentInput.value) documentInput.value.value = ''
    await loadCompliance()
  } catch (err) {
    complianceError.value = err.message
  } finally {
    documentUploading.value = false
  }
}

const loadPortal = async () => {
  loading.value = true
  error.value = ''
  try {
    profile.value = await requestJson('/api/chauffeur/me/profile')
    const [calendarData, hosData, receiptData, floatData, statementData, t4Data] = await Promise.all([
      requestJson('/api/chauffeur/me/calendar'),
      requestJson('/api/chauffeur/me/hos'),
      requestJson('/api/chauffeur/me/receipts'),
      requestJson('/api/chauffeur/me/float'),
      requestJson(`/api/chauffeur/me/pay-statements?year=${statementYear.value}`),
      requestJson('/api/chauffeur/me/t4s')
    ])
    calendarItems.value = calendarData.items || []
    calendarStart.value = formatDate(calendarData.start_date)
    calendarHasMore.value = Boolean(calendarData.has_more)
    calendarNextOffset.value = calendarData.next_offset
    hosEntries.value = hosData.items || []
    receipts.value = receiptData.items || []
    Object.assign(floatSummary, floatData)
    statements.value = statementData.items || []
    t4Records.value = t4Data.items || []
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

const loadMoreRuns = async () => {
  if (!calendarHasMore.value || calendarNextOffset.value === null) return
  loadingMoreRuns.value = true
  error.value = ''
  try {
    const data = await requestJson(`/api/chauffeur/me/calendar?offset=${calendarNextOffset.value}`)
    calendarItems.value.push(...(data.items || []))
    calendarHasMore.value = Boolean(data.has_more)
    calendarNextOffset.value = data.next_offset
  } catch (err) {
    error.value = err.message
  } finally {
    loadingMoreRuns.value = false
  }
}

const loadStatements = async () => {
  try {
    const data = await requestJson(`/api/chauffeur/me/pay-statements?year=${statementYear.value}`)
    statements.value = data.items || []
  } catch (err) {
    error.value = err.message
  }
}

const openTrip = async (charterId) => {
  error.value = ''
  try {
    selectedTrip.value = await requestJson(`/api/chauffeur/me/trips/${charterId}`)
    Object.assign(tripForm, {
      driver_notes: selectedTrip.value.driver_notes,
      vehicle_notes: selectedTrip.value.vehicle_notes,
      odometer_start: selectedTrip.value.odometer_start,
      odometer_end: selectedTrip.value.odometer_end,
      fuel_added_liters: selectedTrip.value.fuel_added_liters,
      actual_hours: selectedTrip.value.actual_hours,
      bus_driving_hours: selectedTrip.value.passenger_capacity === null
        ? selectedTrip.value.bus_driving_hours
        : selectedTrip.value.is_bus
          ? selectedTrip.value.bus_driving_hours
          : 0,
      break_minutes: selectedTrip.value.break_minutes,
      mark_completed: selectedTrip.value.status === 'completed'
    })
    activeTab.value = 'run'
  } catch (err) {
    error.value = err.message
  }
}

const saveTrip = async () => {
  saving.value = true
  error.value = ''
  try {
    const payload = { ...tripForm }
    delete payload.mark_completed
    if (selectedTrip.value.passenger_capacity === null) {
      delete payload.bus_driving_hours
    }
    for (const field of ['bus_driving_hours', 'break_minutes']) {
      if (payload[field] === '') payload[field] = null
    }
    if (tripForm.mark_completed && selectedTrip.value.status !== 'completed') {
      payload.status = 'completed'
    }
    selectedTrip.value = await requestJson(`/api/chauffeur/me/trips/${selectedTrip.value.charter_id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
    notice.value = 'Run information saved.'
    await loadPortal()
    activeTab.value = 'run'
  } catch (err) {
    error.value = err.message
  } finally {
    saving.value = false
  }
}

const submitReceipt = async () => {
  saving.value = true
  error.value = ''
  try {
    await requestJson('/api/chauffeur/me/receipts', {
      method: 'POST',
      body: JSON.stringify(receiptForm)
    })
    Object.assign(receiptForm, {
      receipt_date: new Date().toISOString().slice(0, 10),
      vendor_name: '',
      gross_amount: null,
      category: '',
      description: '',
      charter_id: null,
      paid_from_float: false
    })
    notice.value = 'Receipt submitted.'
    await loadPortal()
    activeTab.value = 'receipts'
  } catch (err) {
    error.value = err.message
  } finally {
    saving.value = false
  }
}

const submitFloatReturn = async () => {
  saving.value = true
  error.value = ''
  try {
    await requestJson('/api/chauffeur/me/float/returns', {
      method: 'POST',
      body: JSON.stringify(returnForm)
    })
    Object.assign(returnForm, { amount: null, charter_id: null, notes: '' })
    notice.value = 'Float turn-in recorded.'
    await loadPortal()
    activeTab.value = 'float'
  } catch (err) {
    error.value = err.message
  } finally {
    saving.value = false
  }
}

const money = value => value === null || value === undefined
  ? 'Not recorded'
  : new Intl.NumberFormat('en-CA', { style: 'currency', currency: 'CAD' }).format(Number(value))
const formatDate = value => value ? new Date(`${String(value).slice(0, 10)}T12:00:00`).toLocaleDateString('en-CA') : '—'
const formatTime = value => value ? String(value).slice(0, 5) : 'Time not set'
const formatTimestamp = value => value
  ? new Date(value).toLocaleString('en-CA', { dateStyle: 'medium', timeStyle: 'short' })
  : 'not recorded'
const recorded = value => value === null || value === undefined || value === '' ? 'Not recorded' : value
const hours = value => value === null || value === undefined ? 'Not verified' : `${value} hours`
const hosStatus = entry => ({
  green: 'OK',
  yellow: 'Review',
  red: 'Alert'
}[entry.status] || 'Review')
const toggleHosDay = day => {
  expandedHosDay.value = expandedHosDay.value === day ? null : day
}
const monthName = value => value ? new Intl.DateTimeFormat('en-CA', { month: 'long' }).format(new Date(2000, Number(value) - 1, 1)) : '—'
const t4ForYear = year => t4Records.value.find(record => Number(record.tax_year) === Number(year))
const categoryLabel = value => ({
  municipal: 'Municipal / Bylaw',
  provincial: 'Provincial',
  federal: 'Federal',
  company: 'Company'
}[value] || value || '')

const statusLabel = value => ({
  completed: 'Completed',
  in_progress: 'In progress',
  expired: 'Expired',
  waived: 'Waived',
  not_started: 'Not started'
}[value] || value || '')

const printReport = () => window.print()

watch(activeTab, tab => {
  if (tab === 'records' && complianceFields.value.length === 0) {
    loadCompliance()
  }
  if (tab === 'training' && trainingPrograms.value.length === 0) {
    loadTraining()
  }
})

onMounted(loadPortal)
</script>

<style scoped>
.driver-portal { max-width: 1200px; margin: 0 auto; }
.portal-header, .section-heading { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }
.portal-header h1, .section-heading h2 { margin-bottom: .25rem; }
.portal-header p { margin: 0; color: #64748b; }
.tabs { display: flex; flex-wrap: wrap; gap: .5rem; margin: 1.25rem 0; }
button { border: 0; border-radius: 6px; padding: .65rem 1rem; background: #2563eb; color: white; cursor: pointer; }
button:disabled { opacity: .6; cursor: wait; }
button.secondary, .tabs button { background: #e2e8f0; color: #1e293b; }
.tabs button.active { background: #2563eb; color: white; }
.panel { background: white; border: 1px solid #dbe3ee; border-radius: 10px; padding: 1.25rem; }
.card-grid, .summary-grid, .record-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 1rem; }
.trip-card, .summary-grid > div { border: 1px solid #dbe3ee; border-radius: 8px; padding: 1rem; display: grid; gap: .6rem; }
.trip-heading { display: flex; justify-content: space-between; gap: .75rem; }
.status { background: #e0f2fe; border-radius: 99px; padding: .15rem .55rem; font-size: .8rem; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
label { display: grid; gap: .35rem; font-weight: 600; }
input, select, textarea { box-sizing: border-box; width: 100%; padding: .65rem; border: 1px solid #cbd5e1; border-radius: 6px; font: inherit; }
.wide, .actions { grid-column: 1 / -1; }
.readonly { display: grid; gap: .25rem; padding: .75rem; background: #f8fafc; }
.checkbox { display: flex; align-items: center; gap: .5rem; }
.checkbox input { width: auto; }
.receipt-form { margin-bottom: 1.5rem; }
.inline-form { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)) auto; align-items: end; gap: 1rem; margin-top: 1.25rem; }
.summary-grid span { color: #64748b; }
.record-grid > div { display: grid; gap: .25rem; border: 1px solid #dbe3ee; border-radius: 8px; padding: .85rem; }
.record-grid span { color: #64748b; font-size: .85rem; }
.t4-record { margin-top: 1rem; padding-top: 1rem; border-top: 2px solid #dbe3ee; break-inside: avoid; }
.hos-scope { margin-bottom: .35rem; font-weight: 700; }
.hos-rule, .hos-evidence { color: #475569; }
.hos-green { background: #f0fdf4; }
.hos-yellow { background: #fefce8; }
.hos-red { background: #fef2f2; }
.hos-status { font-weight: 700; }
.hos-alerts ul { margin: .4rem 0 .75rem; }
.hos-detail-row td { white-space: normal; padding: 1rem; }
.hos-charters { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: .75rem; margin-top: .75rem; }
.hos-charters article { display: grid; gap: .35rem; border: 1px solid #cbd5e1; border-radius: 6px; padding: .75rem; }
.table-button { padding: .35rem .6rem; }
.load-more { margin-top: 1rem; }
.summary-grid strong { font-size: 1.5rem; }
.summary-grid .settled { border-color: #16a34a; background: #f0fdf4; }
.table-wrap { overflow-x: auto; margin-top: 1rem; }
.statement-actions { display: flex; align-items: end; gap: .75rem; }
table { width: 100%; border-collapse: collapse; }
th, td { border-bottom: 1px solid #e2e8f0; padding: .7rem; text-align: left; white-space: nowrap; }
.message { padding: .75rem; margin: .75rem 0; border-radius: 6px; background: #eff6ff; }
.message.error { background: #fef2f2; color: #991b1b; }
.message.success { background: #f0fdf4; color: #166534; }
.empty-state, .loading { padding: 2rem; text-align: center; color: #64748b; }
.records-note { background: #fef9c3; border: 1px solid #fde047; border-radius: 8px; padding: 0.75rem; color: #713f12; }
.records-notice { background: #dcfce7; border: 1px solid #86efac; border-radius: 8px; padding: 0.75rem; color: #14532d; margin-bottom: 0.75rem; }
.records-error { background: #fee2e2; border: 1px solid #fca5a5; border-radius: 8px; padding: 0.75rem; color: #7f1d1d; margin-bottom: 0.75rem; }
.pending-flag { color: #b45309; font-weight: 600; }
.records-actions { margin: 1rem 0; }
.record-upload { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.75rem; align-items: end; margin-bottom: 1rem; }
.training-summary { display: flex; flex-wrap: wrap; gap: 0.5rem; margin: 1rem 0; }
.training-chip { border-radius: 999px; padding: 0.25rem 0.75rem; font-size: 0.85rem; font-weight: 600; }
.training-chip.done { background: #dcfce7; color: #14532d; }
.training-chip.progress { background: #fef9c3; color: #713f12; }
.training-chip.todo { background: #e5e7eb; color: #374151; }
.training-chip.expired { background: #fee2e2; color: #7f1d1d; }
.training-card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 0.85rem; margin-bottom: 0.75rem; background: #fff; }
.training-card-head { display: flex; justify-content: space-between; align-items: center; gap: 0.75rem; flex-wrap: wrap; }
.training-step { background: #1f2937; color: #fff; border-radius: 6px; padding: 0.1rem 0.5rem; font-size: 0.75rem; margin-right: 0.5rem; }
.training-cat { color: #6b7280; font-size: 0.8rem; margin-left: 0.5rem; }
.training-status { border-radius: 999px; padding: 0.2rem 0.7rem; font-size: 0.8rem; font-weight: 600; background: #e5e7eb; color: #374151; }
.training-status.completed { background: #dcfce7; color: #14532d; }
.training-status.in_progress { background: #fef9c3; color: #713f12; }
.training-status.expired { background: #fee2e2; color: #7f1d1d; }
.training-dates { display: flex; flex-wrap: wrap; gap: 1rem; color: #4b5563; font-size: 0.85rem; margin-top: 0.5rem; }
.training-items { margin: 0.6rem 0 0; padding-left: 1rem; color: #374151; font-size: 0.85rem; }
.training-items li { margin-bottom: 0.2rem; list-style: none; }
@media (max-width: 720px) {
  .form-grid, .inline-form { grid-template-columns: 1fr; }
  .wide, .actions { grid-column: auto; }
  .portal-header { align-items: flex-start; }
  .statement-actions { align-items: stretch; flex-direction: column; }
}
@media print {
  .portal-header, .tabs, .message, .print-button, .actions, .receipt-form, .inline-form { display: none !important; }
  .driver-portal, .panel { max-width: none; border: 0; padding: 0; }
  .panel { color: #000; }
  input, select, textarea { border: 0; padding: .15rem; color: #000; background: transparent; }
  .table-wrap { overflow: visible; }
}
</style>
