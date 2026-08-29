<template>
  <section class="support-panel">
    <header>
      <div>
        <h1>Admin Driver Access</h1>
        <p>Open a driver account to verify access or assist with their records. Every switch is audited.</p>
      </div>
      <button class="secondary" :disabled="loading" @click="loadAdminData">Refresh</button>
    </header>

    <div v-if="error" class="message error">{{ error }}</div>
    <section class="notifications" aria-labelledby="security-notifications">
      <div class="section-heading">
        <h2 id="security-notifications">Security Notifications</h2>
        <span>{{ notifications.length }} recent events</span>
      </div>
      <p v-if="!notifications.length" class="empty">No recent password or security events.</p>
      <ul v-else>
        <li v-for="notification in notifications" :key="`${notification.occurred_at}-${notification.action}`" :class="notification.severity">
          <div>
            <strong>{{ notification.message }}</strong>
            <span v-if="notification.detail">{{ notification.detail }}</span>
          </div>
          <time :datetime="notification.occurred_at">{{ formatDate(notification.occurred_at) }}</time>
        </li>
      </ul>
    </section>

    <div class="selector">
      <label for="driver-account">Driver account</label>
      <select id="driver-account" v-model.number="selectedEmployeeId" :disabled="loading">
        <option :value="null">Select an active driver</option>
        <option v-for="employee in employees" :key="employee.employee_id" :value="employee.employee_id">
          {{ employee.name }} · {{ employee.username }} · {{ employee.employee_type }}
        </option>
      </select>
      <button class="primary" :disabled="loading || !selectedEmployeeId" @click="openDriver">
        {{ loading ? 'Opening...' : 'Open Selected Driver Account' }}
      </button>
      <label for="temporary-password">Pending first-login password reset</label>
      <input
        id="temporary-password"
        v-model="temporaryPassword"
        type="password"
        minlength="12"
        autocomplete="new-password"
        placeholder="Enter a temporary password"
      >
      <button class="warning" :disabled="loading || !selectedEmployeeId || temporaryPassword.length < 12" @click="resetPendingPassword">
        Reset Pending Login
      </button>
    </div>

    <div class="account-list">
      <button
        v-for="employee in employees"
        :key="employee.employee_id"
        class="account"
        :class="{ selected: selectedEmployeeId === employee.employee_id }"
        @click="selectedEmployeeId = employee.employee_id"
      >
        <strong>{{ employee.name }}</strong>
        <span>{{ employee.username }} · {{ employee.employee_type }}</span>
      </button>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authFetch } from '@/utils/authFetch'

const router = useRouter()
const employees = ref([])
const notifications = ref([])
const selectedEmployeeId = ref(null)
const loading = ref(false)
const error = ref('')
const temporaryPassword = ref('')

const readResponse = async (response, fallback) => {
  const payload = await response?.json().catch(() => ({}))
  if (!response?.ok) throw new Error(payload?.detail || fallback)
  return payload
}

const formatDate = value => new Intl.DateTimeFormat(undefined, {
  dateStyle: 'medium',
  timeStyle: 'short'
}).format(new Date(value))

const loadAdminData = async () => {
  loading.value = true
  error.value = ''
  try {
    const [employeeResponse, notificationResponse] = await Promise.all([
      authFetch('/auth/support/employees'),
      authFetch('/auth/support/notifications')
    ])
    const employeePayload = await readResponse(employeeResponse, 'Unable to load driver accounts')
    const notificationPayload = await readResponse(notificationResponse, 'Unable to load security notifications')
    employees.value = employeePayload.items || []
    notifications.value = notificationPayload.items || []
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

const openDriver = async () => {
  if (!selectedEmployeeId.value) return
  loading.value = true
  error.value = ''
  try {
    const response = await authFetch('/auth/support/impersonate', {
      method: 'POST',
      body: JSON.stringify({ employee_id: selectedEmployeeId.value })
    })
    const payload = await response?.json().catch(() => ({}))
    if (!response?.ok) throw new Error(payload.detail || 'Unable to open driver account')
    localStorage.setItem('auth_token', payload.access_token)
    localStorage.setItem('user', JSON.stringify(payload.user))
    localStorage.setItem('user_role', payload.user.role)
    localStorage.setItem('user_permissions', JSON.stringify(payload.user.permissions || {}))
    await router.push('/')
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

const resetPendingPassword = async () => {
  if (!selectedEmployeeId.value || temporaryPassword.value.length < 12) return
  loading.value = true
  error.value = ''
  try {
    const response = await authFetch('/auth/support/reset-pending-password', {
      method: 'POST',
      body: JSON.stringify({
        employee_id: selectedEmployeeId.value,
        temporary_password: temporaryPassword.value
      })
    })
    const payload = await response?.json().catch(() => ({}))
    if (!response?.ok) throw new Error(payload.detail || 'Unable to reset pending login')
    temporaryPassword.value = ''
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

onMounted(loadAdminData)
</script>

<style scoped>
.support-panel { max-width: 1000px; margin: 0 auto; background: white; border: 1px solid #dbe3ee; border-radius: 10px; padding: 1.25rem; }
header { display: flex; justify-content: space-between; align-items: start; gap: 1rem; }
h1 { margin: 0 0 .35rem; }
header p { margin: 0; color: #475569; }
.notifications { margin-top: 1.5rem; border: 1px solid #dbe3ee; border-radius: 8px; overflow: hidden; }
.section-heading { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: .8rem 1rem; background: #f8fafc; }
.section-heading h2 { margin: 0; font-size: 1.05rem; }
.section-heading span, .empty { color: #64748b; }
.notifications ul { list-style: none; padding: 0; margin: 0; max-height: 280px; overflow: auto; }
.notifications li { display: flex; justify-content: space-between; gap: 1rem; padding: .8rem 1rem; border-top: 1px solid #e2e8f0; }
.notifications li.warning { border-left: 4px solid #dc2626; background: #fff7f7; }
.notifications li div { display: grid; gap: .2rem; }
.notifications li div span, .notifications time { color: #64748b; font-size: .85rem; }
.notifications time { white-space: nowrap; }
.empty { margin: 0; padding: 1rem; border-top: 1px solid #e2e8f0; }
.selector { display: grid; grid-template-columns: minmax(240px, 1fr) auto; gap: .75rem; align-items: end; margin: 1.5rem 0; }
.selector label { grid-column: 1 / -1; font-weight: 700; }
select, input, button { padding: .75rem; border-radius: 6px; font: inherit; }
select, input { border: 1px solid #cbd5e1; }
button { border: 0; cursor: pointer; }
button:disabled { opacity: .6; cursor: wait; }
.primary { background: #2563eb; color: white; font-weight: 700; }
.secondary { background: #e2e8f0; color: #1e293b; }
.warning { background: #f59e0b; color: #422006; font-weight: 700; }
.account-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: .75rem; }
.account { display: grid; gap: .3rem; text-align: left; background: #f8fafc; border: 1px solid #dbe3ee; color: #1e293b; }
.account.selected { border-color: #2563eb; background: #eff6ff; }
.account span { color: #64748b; }
.message { padding: .75rem; margin-top: 1rem; border-radius: 6px; }
.message.error { background: #fef2f2; color: #991b1b; }
@media (max-width: 680px) {
  .selector { grid-template-columns: 1fr; }
  header { flex-direction: column; }
  .notifications li { flex-direction: column; }
}
</style>
