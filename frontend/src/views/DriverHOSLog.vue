<template>
  <div class="hos-log-container">
    <h2>Driver HOS Duty Log (Last 14 Days)</h2>
    <div class="legal-info">
      <strong>Cycle: 1</strong> &mdash; Alberta 160km Radius Exemption<br>
      <span>
        This log is maintained under Cycle 1. The driver operates within 160km of the home terminal, returns to the home terminal each day, and receives at least 8 consecutive hours off duty. No emergency, adverse driving, or split sleeper exemptions are claimed unless noted below.
      </span>
      <ul style="margin-top:0.5em;">
        <li>Maximum 13 hours driving in a workshift</li>
        <li>Maximum 16 hours on duty in a workshift (if 2 hours break taken)</li>
        <li>Minimum 8 consecutive hours off duty before/after each shift</li>
        <li>All times recorded in 15-minute increments</li>
        <li>Carrier: Arrow Limousine, Home Terminal: 123 Main St, Red Deer, AB</li>
      </ul>
    </div>
    <div v-if="loading">Loading...</div>
    <div v-else>
      <div class="print-section">
        <button @click="printLog">Print HOS Log & Inspection Report</button>
      </div>
      <table class="hos-log-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Workshift Start</th>
            <th>Workshift End</th>
            <th>Duty Status Changes</th>
            <th>Total On Duty</th>
            <th>Total Driving</th>
            <th>Total Off Duty</th>
            <th>Breaks</th>
            <th v-if="isAdmin">Deferral</th>
            <th v-if="isAdmin">Emergency</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in hosLog" :key="entry.date">
            <td>{{ entry.date }}</td>
            <td>{{ entry.workshift_start }}</td>
            <td>{{ entry.workshift_end }}</td>
            <td>
              <ul>
                <li v-for="change in entry.duty_log" :key="change.start">
                  {{ change.status }}: {{ change.start }} - {{ change.end }} ({{ change.duration }})
                  <span v-if="change.emergency || change.adverse">&nbsp;<strong>*</strong></span>
                </li>
              </ul>
            </td>
            <td>{{ entry.total_on_duty }}</td>
            <td>{{ entry.total_driving }}</td>
            <td>{{ entry.total_off_duty }}</td>
            <td>{{ entry.breaks }}</td>
            <td v-if="isAdmin">
              <input type="checkbox" v-model="entry.deferral" />
              <span v-if="entry.deferral">Deferred {{ entry.deferral_hours || 0 }}h to next day</span>
            </td>
            <td v-if="isAdmin">
              <input type="checkbox" v-model="entry.emergency" />
              <input v-if="entry.emergency" v-model="entry.emergency_reason" placeholder="Reason (required)" style="width:120px;" />
            </td>
          </tr>
        </tbody>
      </table>
      <div class="footer-print">
        <div style="margin-top:2em;">
          <strong>Home Terminal:</strong> 123 Main St, Red Deer, AB<br>
          <strong>Carrier:</strong> Arrow Limousine<br>
          <strong>Driver Signature:</strong> ____________________________ &nbsp; <strong>Date:</strong> ____________
        </div>
        <div style="margin-top:1em;font-size:0.95em;color:#555;">
          * If any duty status is marked with <strong>*</strong>, an emergency or adverse driving exemption was claimed for that period.<br>
          <span v-if="isAdmin">Deferral and emergency fields are admin-only and must be completed for compliance if used.</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
// Set this to true for admin users only
const isAdmin = true
import { ref, onMounted } from 'vue'
const hosLog = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
  const res = await fetch('/api/driver_hos_log?days=14')
    if (res.ok) {
      hosLog.value = await res.json()
    } else {
      hosLog.value = []
    }
  } catch (e) {
    hosLog.value = []
  } finally {
    loading.value = false
  }
})

function printLog() {
  window.print()
}
</script>

<style scoped>
.hos-log-container {
  padding: 2rem;
}
.hos-log-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1.5rem;
}
.hos-log-table th, .hos-log-table td {
  border: 1px solid #1976d2;
  padding: 0.5rem 1rem;
  text-align: left;
}
.print-section {
  margin-bottom: 1rem;
}
</style>
