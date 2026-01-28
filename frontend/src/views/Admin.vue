<template>
  <div>
    <h1>⚙️ Admin Dashboard</h1>
    
    <!-- Admin Tabs -->
    <div class="admin-tabs">
      <button 
        v-for="tab in tabs" 
        :key="tab.id"
        @click="activeTab = tab.id"
        :class="['tab-button', { active: activeTab === tab.id }]"
      >
        {{ tab.icon }} {{ tab.name }}
      </button>
    </div>

    <!-- System Overview Tab -->
    <div v-if="activeTab === 'overview'" class="tab-content">
      <h2>System Overview</h2>
      
      <!-- System Stats -->
      <div class="system-stats">
        <div class="stat-card">
          <div class="stat-value">{{ systemStats.totalBookings }}</div>
          <div class="stat-label">Total Bookings</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ systemStats.activeCustomers }}</div>
          <div class="stat-label">Active Customers</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ systemStats.totalEmployees }}</div>
          <div class="stat-label">Total Employees</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">${{ systemStats.monthlyRevenue }}</div>
          <div class="stat-label">Monthly Revenue</div>
        </div>
      </div>

      <!-- Recent Activity -->
      <div class="recent-activity">
        <h3>Recent System Activity</h3>
        <div class="activity-list">
          <div v-for="activity in recentActivity" :key="activity.id" class="activity-item">
            <span class="activity-icon">{{ activity.icon }}</span>
            <span class="activity-text">{{ activity.description }}</span>
            <span class="activity-time">{{ activity.timestamp }}</span>
          </div>
        </div>
      </div>

      <!-- System Health -->
      <div class="system-health">
        <h3>System Health</h3>
        <div class="health-metrics">
          <div class="health-item">
            <span class="health-label">Database Status</span>
            <span class="health-status online">Online</span>
          </div>
          <div class="health-item">
            <span class="health-label">API Response Time</span>
            <span class="health-value">125ms</span>
          </div>
          <div class="health-item">
            <span class="health-label">Storage Usage</span>
            <span class="health-value">45% (2.3GB)</span>
          </div>
          <div class="health-item">
            <span class="health-label">Last Backup</span>
            <span class="health-value">2 hours ago</span>
          </div>
        </div>
      </div>
    </div>

    <!-- User Management Tab -->
    <div v-if="activeTab === 'users'" class="tab-content">
      <h2>User Management</h2>
      
      <div class="user-actions">
        <button @click="showAddUserForm = !showAddUserForm" class="btn-primary">
          {{ showAddUserForm ? 'Cancel' : '👤 Add User' }}
        </button>
        <button @click="exportUsers" class="btn-secondary" :disabled="busy.exportUsers">{{ busy.exportUsers ? 'Exporting…' : '📤 Export Users' }}</button>
        <button @click="loadUsers" class="btn-info" :disabled="busy.loadUsers">{{ busy.loadUsers ? 'Refreshing…' : '🔄 Refresh' }}</button>
      </div>

      <!-- Add User Form -->
      <div v-if="showAddUserForm" class="add-user-form">
        <h3>Add New User</h3>
        <form @submit.prevent="addUser">
          <div class="form-row">
            <div class="form-group">
              <label>Username</label>
              <input v-model="newUser.username" type="text" required />
            </div>
            <div class="form-group">
              <label>Email</label>
              <input v-model="newUser.email" type="email" required />
            </div>
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Role</label>
              <select v-model="newUser.role" required>
                <option value="">Select Role</option>
                <option value="admin">Admin</option>
                <option value="manager">Manager</option>
                <option value="dispatcher">Dispatcher</option>
                <option value="driver">Driver</option>
                <option value="accountant">Accountant</option>
              </select>
            </div>
            <div class="form-group">
              <label>Department</label>
              <select v-model="newUser.department">
                <option value="">Select Department</option>
                <option value="operations">Operations</option>
                <option value="dispatch">Dispatch</option>
                <option value="accounting">Accounting</option>
                <option value="maintenance">Maintenance</option>
              </select>
            </div>
          </div>
          <div class="form-actions">
            <button type="submit" class="btn-save" :disabled="busy.addUser">{{ busy.addUser ? 'Adding…' : 'Add User' }}</button>
            <button type="button" @click="cancelAddUser" class="btn-cancel" :disabled="busy.addUser">Cancel</button>
          </div>
        </form>
      </div>

      <!-- Users Table -->
      <table class="users-table">
        <thead>
          <tr>
            <th>Username</th>
            <th>Email</th>
            <th>Role</th>
            <th>Department</th>
            <th>Status</th>
            <th>Last Login</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="user in users" :key="user.id">
            <td>{{ user.username }}</td>
            <td>{{ user.email }}</td>
            <td>
              <span :class="'role-' + user.role">{{ formatRole(user.role) }}</span>
            </td>
            <td>{{ user.department || '-' }}</td>
            <td>
              <span :class="'status-' + user.status">{{ formatStatus(user.status) }}</span>
            </td>
            <td>{{ formatDate(user.last_login) }}</td>
            <td class="actions">
              <button @click="editUser(user)" class="btn-edit">Edit</button>
              <button @click="toggleUserStatus(user)" class="btn-toggle">
                {{ user.status === 'active' ? 'Disable' : 'Enable' }}
              </button>
              <button @click="deleteUser(user)" class="btn-delete">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- System Settings Tab -->
    <div v-if="activeTab === 'settings'" class="tab-content">
      <h2>System Settings</h2>
      
      <div class="settings-sections">
        <!-- General Settings -->
        <div class="settings-section">
          <h3>General Settings</h3>
          <div class="setting-item">
            <label>Company Name</label>
            <input v-model="settings.companyName" type="text" />
          </div>
          <div class="setting-item">
            <label>Default Currency</label>
            <select v-model="settings.currency">
              <option value="CAD">CAD</option>
              <option value="USD">USD</option>
            </select>
          </div>
          <div class="setting-item">
            <label>Time Zone</label>
            <select v-model="settings.timezone">
              <option value="America/Toronto">Eastern Time</option>
              <option value="America/Vancouver">Pacific Time</option>
              <option value="America/Chicago">Central Time</option>
            </select>
          </div>
        </div>

        <!-- Business Settings -->
        <div class="settings-section">
          <h3>Business Settings</h3>
          <div class="setting-item">
            <label>GST Rate (%)</label>
            <input v-model="settings.gstRate" type="number" step="0.01" />
          </div>
          <div class="setting-item">
            <label>Default Booking Duration (hours)</label>
            <input v-model="settings.defaultBookingDuration" type="number" />
          </div>
          <div class="setting-item">
            <label>Minimum Booking Notice (hours)</label>
            <input v-model="settings.minBookingNotice" type="number" />
          </div>
        </div>

        <!-- Notification Settings -->
        <div class="settings-section">
          <h3>Notification Settings</h3>
          <div class="setting-item">
            <label>
              <input v-model="settings.emailNotifications" type="checkbox" />
              Enable Email Notifications
            </label>
          </div>
          <div class="setting-item">
            <label>
              <input v-model="settings.smsNotifications" type="checkbox" />
              Enable SMS Notifications
            </label>
          </div>
          <div class="setting-item">
            <label>Notification Email</label>
            <input v-model="settings.notificationEmail" type="email" />
          </div>
        </div>
      </div>

      <div class="settings-actions">
        <button @click="saveSettings" class="btn-save">Save Settings</button>
        <button @click="resetSettings" class="btn-secondary">Reset to Defaults</button>
      </div>
    </div>

    <!-- Reports Tab -->
    <div v-if="activeTab === 'reports'" class="tab-content">
      <h2>System Reports</h2>
      
      <div class="report-categories">
        <!-- Financial Reports -->
        <div class="report-category">
          <h3>📊 Financial Reports</h3>
          <div class="report-list">
            <div class="report-item">
              <span class="report-name">Monthly Revenue Report</span>
              <button @click="generateReport('monthly-revenue')" class="btn-generate" :disabled="busy['report_monthly-revenue']">{{ busy['report_monthly-revenue'] ? 'Generating…' : 'Generate' }}</button>
            </div>
            <div class="report-item">
              <span class="report-name">GST Summary Report</span>
              <button @click="generateReport('gst-summary')" class="btn-generate" :disabled="busy['report_gst-summary']">{{ busy['report_gst-summary'] ? 'Generating…' : 'Generate' }}</button>
            </div>
            <div class="report-item">
              <span class="report-name">Expense Analysis</span>
              <button @click="generateReport('expense-analysis')" class="btn-generate" :disabled="busy['report_expense-analysis']">{{ busy['report_expense-analysis'] ? 'Generating…' : 'Generate' }}</button>
            </div>
            <div class="report-item">
              <span class="report-name">Profit & Loss Statement</span>
              <button @click="generateReport('profit-loss')" class="btn-generate" :disabled="busy['report_profit-loss']">{{ busy['report_profit-loss'] ? 'Generating…' : 'Generate' }}</button>
            </div>
          </div>
        </div>

        <!-- Operational Reports -->
        <div class="report-category">
          <h3>🚐 Operational Reports</h3>
          <div class="report-list">
            <div class="report-item">
              <span class="report-name">Fleet Utilization Report</span>
              <button @click="generateReport('fleet-utilization')" class="btn-generate" :disabled="busy['report_fleet-utilization']">{{ busy['report_fleet-utilization'] ? 'Generating…' : 'Generate' }}</button>
            </div>
            <div class="report-item">
              <span class="report-name">Driver Performance Report</span>
              <button @click="generateReport('driver-performance')" class="btn-generate" :disabled="busy['report_driver-performance']">{{ busy['report_driver-performance'] ? 'Generating…' : 'Generate' }}</button>
            </div>
            <div class="report-item">
              <span class="report-name">Customer Activity Report</span>
              <button @click="generateReport('customer-activity')" class="btn-generate" :disabled="busy['report_customer-activity']">{{ busy['report_customer-activity'] ? 'Generating…' : 'Generate' }}</button>
            </div>
            <div class="report-item">
              <span class="report-name">Booking Trends Analysis</span>
              <button @click="generateReport('booking-trends')" class="btn-generate" :disabled="busy['report_booking-trends']">{{ busy['report_booking-trends'] ? 'Generating…' : 'Generate' }}</button>
            </div>
          </div>
        </div>

        <!-- Compliance Reports -->
        <div class="report-category">
          <h3>📋 Compliance Reports</h3>
          <div class="report-list">
            <div class="report-item">
              <span class="report-name">WCB Compliance Report</span>
              <button @click="generateReport('wcb-compliance')" class="btn-generate" :disabled="busy['report_wcb-compliance']">{{ busy['report_wcb-compliance'] ? 'Generating…' : 'Generate' }}</button>
            </div>
            <div class="report-item">
              <span class="report-name">Vehicle Inspection Log</span>
              <button @click="generateReport('vehicle-inspection')" class="btn-generate" :disabled="busy['report_vehicle-inspection']">{{ busy['report_vehicle-inspection'] ? 'Generating…' : 'Generate' }}</button>
            </div>
            <div class="report-item">
              <span class="report-name">Driver License Tracking</span>
              <button @click="generateReport('license-tracking')" class="btn-generate" :disabled="busy['report_license-tracking']">{{ busy['report_license-tracking'] ? 'Generating…' : 'Generate' }}</button>
            </div>
            <div class="report-item">
              <span class="report-name">Insurance Coverage Report</span>
              <button @click="generateReport('insurance-coverage')" class="btn-generate" :disabled="busy['report_insurance-coverage']">{{ busy['report_insurance-coverage'] ? 'Generating…' : 'Generate' }}</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Backup Tab -->
    <div v-if="activeTab === 'backup'" class="tab-content">
      <h2>Backup & Maintenance</h2>
      
      <!-- Backup Section -->
      <div class="backup-section">
        <h3>Database Backup</h3>
        <div class="backup-info">
          <div class="backup-status">
            <span class="status-label">Last Backup:</span>
            <span class="status-value">{{ lastBackup }}</span>
          </div>
          <div class="backup-status">
            <span class="status-label">Backup Size:</span>
            <span class="status-value">{{ backupSize }}</span>
          </div>
          <div class="backup-status">
            <span class="status-label">Auto Backup:</span>
            <span class="status-value enabled">Enabled (Daily)</span>
          </div>
        </div>
        <div class="backup-actions">
          <button @click="createBackup" class="btn-primary" :disabled="busy.createBackup">{{ busy.createBackup ? 'Creating Backup…' : '🔄 Create Backup Now' }}</button>
          <button @click="restoreBackup" class="btn-warning" :disabled="busy.restoreBackup">{{ busy.restoreBackup ? 'Restoring…' : '📥 Restore Backup' }}</button>
          <button @click="downloadBackup" class="btn-secondary" :disabled="busy.downloadBackup">{{ busy.downloadBackup ? 'Preparing…' : '💾 Download Latest' }}</button>
        </div>
      </div>

      <!-- Maintenance Section -->
      <div class="maintenance-section">
        <h3>System Maintenance</h3>
        <div class="maintenance-tasks">
          <div class="task-item">
            <span class="task-name">Database Optimization</span>
            <span class="task-status">Last run: 3 days ago</span>
            <button @click="runMaintenance('optimize')" class="btn-task" :disabled="busy.maintenance.optimize">{{ busy.maintenance.optimize ? 'Running…' : 'Run Now' }}</button>
          </div>
          <div class="task-item">
            <span class="task-name">Clear Temporary Files</span>
            <span class="task-status">Last run: 1 day ago</span>
            <button @click="runMaintenance('cleanup')" class="btn-task" :disabled="busy.maintenance.cleanup">{{ busy.maintenance.cleanup ? 'Running…' : 'Run Now' }}</button>
          </div>
          <div class="task-item">
            <span class="task-name">Update System Logs</span>
            <span class="task-status">Last run: 6 hours ago</span>
            <button @click="runMaintenance('logs')" class="btn-task" :disabled="busy.maintenance.logs">{{ busy.maintenance.logs ? 'Running…' : 'Run Now' }}</button>
          </div>
          <div class="task-item">
            <span class="task-name">Verify Data Integrity</span>
            <span class="task-status">Last run: 1 week ago</span>
            <button @click="runMaintenance('verify')" class="btn-task" :disabled="busy.maintenance.verify">{{ busy.maintenance.verify ? 'Running…' : 'Run Now' }}</button>
          </div>
        </div>
      </div>

      <!-- System Logs -->
      <div class="logs-section">
        <h3>System Logs</h3>
        <div class="log-controls">
          <select v-model="selectedLogLevel">
            <option value="">All Levels</option>
            <option value="error">Errors Only</option>
            <option value="warning">Warnings</option>
            <option value="info">Info</option>
          </select>
          <button @click="refreshLogs" class="btn-info" :disabled="busy.refreshLogs">{{ busy.refreshLogs ? 'Refreshing…' : '🔄 Refresh' }}</button>
          <button @click="clearLogs" class="btn-warning" :disabled="busy.clearLogs">{{ busy.clearLogs ? 'Clearing…' : '🗑️ Clear Logs' }}</button>
        </div>
        <div class="log-viewer">
          <div v-for="log in filteredLogs" :key="log.id" :class="'log-entry log-' + log.level">
            <span class="log-time">{{ log.timestamp }}</span>
            <span class="log-level">{{ log.level.toUpperCase() }}</span>
            <span class="log-message">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { toast } from '@/toast/toastStore'

const activeTab = ref('overview')
const showAddUserForm = ref(false)
const selectedLogLevel = ref('')

const tabs = [
  { id: 'overview', name: 'Overview', icon: '📊' },
  { id: 'users', name: 'Users', icon: '👥' },
  { id: 'settings', name: 'Settings', icon: '⚙️' },
  { id: 'reports', name: 'Reports', icon: '📋' },
  { id: 'backup', name: 'Backup', icon: '💾' }
]

const systemStats = ref({
  totalBookings: 0,
  activeCustomers: 0,
  totalEmployees: 0,
  monthlyRevenue: 0
})

const recentActivity = ref([])
const users = ref([])
const logs = ref([])
const busy = ref({
  addUser: false,
  loadUsers: false,
  exportUsers: false,
  createBackup: false,
  restoreBackup: false,
  downloadBackup: false,
  refreshLogs: false,
  clearLogs: false,
  maintenance: { optimize: false, cleanup: false, logs: false, verify: false }
})
const busyRow = ref({})

const newUser = ref({
  username: '',
  email: '',
  role: '',
  department: ''
})

const settings = ref({
  companyName: 'Limo Services',
  currency: 'CAD',
  timezone: 'America/Toronto',
  gstRate: 5.0,
  defaultBookingDuration: 3,
  minBookingNotice: 2,
  emailNotifications: true,
  smsNotifications: false,
  notificationEmail: 'admin@limoservice.com'
})

const lastBackup = ref('2025-09-17 14:30')
const backupSize = ref('2.3 GB')

const filteredLogs = computed(() => {
  if (!selectedLogLevel.value) return logs.value
  return logs.value.filter(log => log.level === selectedLogLevel.value)
})

async function loadSystemData() {
  try {
    // Load system stats - mock data for now
    systemStats.value = {
      totalBookings: 1247,
      activeCustomers: 89,
      totalEmployees: 12,
      monthlyRevenue: 45280
    }

    // Load recent activity
    recentActivity.value = [
      { id: 1, icon: '📅', description: 'New booking created by customer #123', timestamp: '2 minutes ago' },
      { id: 2, icon: '👤', description: 'New employee added: John Doe', timestamp: '15 minutes ago' },
      { id: 3, icon: '💰', description: 'Payment received from customer #456', timestamp: '1 hour ago' },
      { id: 4, icon: '🚐', description: 'Vehicle #3 completed maintenance', timestamp: '2 hours ago' },
      { id: 5, icon: '📊', description: 'Monthly report generated', timestamp: '4 hours ago' }
    ]

    // Load users
    users.value = [
      { id: 1, username: 'admin', email: 'admin@limo.com', role: 'admin', department: 'operations', status: 'active', last_login: '2025-09-17' },
      { id: 2, username: 'dispatcher1', email: 'dispatch@limo.com', role: 'dispatcher', department: 'dispatch', status: 'active', last_login: '2025-09-17' },
      { id: 3, username: 'accountant1', email: 'accounting@limo.com', role: 'accountant', department: 'accounting', status: 'active', last_login: '2025-09-16' },
      { id: 4, username: 'driver1', email: 'driver1@limo.com', role: 'driver', department: 'operations', status: 'active', last_login: '2025-09-17' }
    ]

    // Load logs
    logs.value = [
      { id: 1, timestamp: '2025-09-17 14:30:15', level: 'info', message: 'System backup completed successfully' },
      { id: 2, timestamp: '2025-09-17 14:25:10', level: 'warning', message: 'Low disk space warning: 85% used' },
      { id: 3, timestamp: '2025-09-17 14:20:05', level: 'error', message: 'Failed to send email notification to customer #789' },
      { id: 4, timestamp: '2025-09-17 14:15:00', level: 'info', message: 'Database optimization completed' },
      { id: 5, timestamp: '2025-09-17 14:10:30', level: 'info', message: 'User login: dispatcher1' }
    ]
  } catch (error) {
    console.error('Error loading system data:', error)
  }
}

function addUser() {
  if (busy.value.addUser) return
  busy.value.addUser = true
  console.log('Add user:', newUser.value)
  
  const user = {
    id: users.value.length + 1,
    username: newUser.value.username,
    email: newUser.value.email,
    role: newUser.value.role,
    department: newUser.value.department,
    status: 'active',
    last_login: null
  }
  
  users.value.push(user)
  cancelAddUser()
  toast.success('User added successfully!')
  busy.value.addUser = false
}

function cancelAddUser() {
  showAddUserForm.value = false
  newUser.value = {
    username: '',
    email: '',
    role: '',
    department: ''
  }
}

function editUser(user) {
  console.log('Edit user:', user)
  // TODO: Implement user editing
  toast.info('User editing not yet implemented')
}

function toggleUserStatus(user) {
  if (busyRow.value[user.id]) return
  busyRow.value[user.id] = true
  setTimeout(() => {
    user.status = user.status === 'active' ? 'inactive' : 'active'
    toast.success(`User ${user.username} ${user.status === 'active' ? 'enabled' : 'disabled'}`)
    busyRow.value[user.id] = false
  }, 400)
}

function deleteUser(user) {
  if (confirm(`Are you sure you want to delete user ${user.username}?`)) {
    busyRow.value[user.id] = true
    setTimeout(() => {
      users.value = users.value.filter(u => u.id !== user.id)
      toast.success('User deleted successfully!')
      busyRow.value[user.id] = false
    }, 400)
  }
}

function saveSettings() {
  console.log('Save settings:', settings.value)
  // TODO: Save to backend
  toast.success('Settings saved successfully!')
}

function resetSettings() {
  if (confirm('Are you sure you want to reset all settings to defaults?')) {
    // Reset to default values
    settings.value = {
      companyName: 'Limo Services',
      currency: 'CAD',
      timezone: 'America/Toronto',
      gstRate: 5.0,
      defaultBookingDuration: 3,
      minBookingNotice: 2,
      emailNotifications: true,
      smsNotifications: false,
      notificationEmail: 'admin@limoservice.com'
    }
    toast.success('Settings reset to defaults!')
  }
}

function generateReport(reportType) {
  const key = `report_${reportType}`
  if (busy.value[key]) return
  busy.value[key] = true
  console.log('Generate report:', reportType)
  setTimeout(() => {
    toast.info(`${reportType} report generation not yet implemented`)
    busy.value[key] = false
  }, 600)
}

function createBackup() {
  if (busy.value.createBackup) return
  busy.value.createBackup = true
  console.log('Creating backup...')
  setTimeout(() => {
    toast.info('Backup creation not yet implemented')
    busy.value.createBackup = false
  }, 1000)
}

function restoreBackup() {
  if (confirm('Are you sure you want to restore from backup? This will overwrite current data.')) {
    if (busy.value.restoreBackup) return
    busy.value.restoreBackup = true
    console.log('Restoring backup...')
    setTimeout(() => {
      toast.info('Backup restoration not yet implemented')
      busy.value.restoreBackup = false
    }, 1200)
  }
}

function downloadBackup() {
  if (busy.value.downloadBackup) return
  busy.value.downloadBackup = true
  console.log('Downloading backup...')
  setTimeout(() => {
    toast.info('Backup download not yet implemented')
    busy.value.downloadBackup = false
  }, 800)
}

function runMaintenance(taskType) {
  if (busy.value.maintenance[taskType]) return
  busy.value.maintenance[taskType] = true
  console.log('Running maintenance task:', taskType)
  setTimeout(() => {
    toast.info(`${taskType} maintenance task not yet implemented`)
    busy.value.maintenance[taskType] = false
  }, 900)
}

function refreshLogs() {
  if (busy.value.refreshLogs) return
  busy.value.refreshLogs = true
  console.log('Refreshing logs...')
  setTimeout(() => {
    loadSystemData()
    busy.value.refreshLogs = false
  }, 400)
}

function clearLogs() {
  if (confirm('Are you sure you want to clear all logs?')) {
    if (busy.value.clearLogs) return
    busy.value.clearLogs = true
    setTimeout(() => {
      logs.value = []
      toast.success('Logs cleared!')
      busy.value.clearLogs = false
    }, 300)
  }
}

function exportUsers() {
  if (busy.value.exportUsers) return
  busy.value.exportUsers = true
  console.log('Exporting users...')
  setTimeout(() => {
    toast.info('User export not yet implemented')
    busy.value.exportUsers = false
  }, 700)
}

function loadUsers() {
  if (busy.value.loadUsers) return
  busy.value.loadUsers = true
  console.log('Loading users...')
  setTimeout(() => {
    loadSystemData()
    busy.value.loadUsers = false
  }, 400)
}

function formatRole(role) {
  const roles = {
    admin: 'Administrator',
    manager: 'Manager',
    dispatcher: 'Dispatcher',
    driver: 'Driver',
    accountant: 'Accountant'
  }
  return roles[role] || role
}

function formatStatus(status) {
  return status.charAt(0).toUpperCase() + status.slice(1)
}

function formatDate(dateString) {
  if (!dateString) return 'Never'
  return new Date(dateString).toLocaleDateString()
}

onMounted(() => {
  loadSystemData()
})
</script>

<style scoped>
.admin-tabs {
  display: flex;
  gap: 5px;
  margin-bottom: 30px;
  border-bottom: 2px solid #e9ecef;
}

.tab-button {
  padding: 12px 24px;
  background: none;
  border: none;
  border-bottom: 3px solid transparent;
  cursor: pointer;
  font-weight: 500;
  color: #666;
  transition: all 0.3s;
}

.tab-button:hover {
  color: #007bff;
  background: #f8f9fa;
}

.tab-button.active {
  color: #007bff;
  border-bottom-color: #007bff;
  background: white;
}

.tab-content {
  padding: 20px 0;
}

.system-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.stat-value {
  font-size: 2rem;
  font-weight: bold;
  color: #007bff;
  margin-bottom: 5px;
}

.stat-label {
  color: #666;
  font-size: 0.9rem;
}

.recent-activity, .system-health {
  background: white;
  border-radius: 8px;
  padding: 25px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.activity-list {
  max-height: 300px;
  overflow-y: auto;
}

.activity-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 12px 0;
  border-bottom: 1px solid #eee;
}

.activity-icon {
  font-size: 1.2rem;
}

.activity-text {
  flex: 1;
  color: #333;
}

.activity-time {
  color: #666;
  font-size: 0.85rem;
}

.health-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 15px;
}

.health-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 6px;
}

.health-label {
  font-weight: 500;
  color: #333;
}

.health-status.online {
  color: #28a745;
  font-weight: bold;
}

.health-value {
  color: #007bff;
  font-weight: bold;
}

.user-actions {
  display: flex;
  gap: 15px;
  margin-bottom: 25px;
  flex-wrap: wrap;
}

.add-user-form {
  background: white;
  border-radius: 8px;
  padding: 25px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.form-row {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
}

.form-group {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.form-group label {
  margin-bottom: 5px;
  font-weight: 500;
  color: #333;
}

.form-group input, .form-group select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.users-table {
  width: 100%;
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  border-collapse: collapse;
}

.users-table th,
.users-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #eee;
}

.users-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #333;
}

.users-table tr:hover {
  background-color: #f5f5f5;
}

.role-admin { color: #dc3545; font-weight: bold; }
.role-manager { color: #fd7e14; font-weight: bold; }
.role-dispatcher { color: #007bff; font-weight: bold; }
.role-driver { color: #28a745; font-weight: bold; }
.role-accountant { color: #6f42c1; font-weight: bold; }

.status-active { color: #28a745; font-weight: bold; }
.status-inactive { color: #dc3545; font-weight: bold; }

.actions {
  display: flex;
  gap: 8px;
}

.settings-sections {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 30px;
  margin-bottom: 30px;
}

.settings-section {
  background: white;
  border-radius: 8px;
  padding: 25px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.setting-item {
  margin-bottom: 20px;
}

.setting-item label {
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
  color: #333;
}

.setting-item input, .setting-item select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.setting-item input[type="checkbox"] {
  width: auto;
  margin-right: 8px;
}

.settings-actions {
  text-align: center;
}

.report-categories {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 30px;
}

.report-category {
  background: white;
  border-radius: 8px;
  padding: 25px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.report-list {
  margin-top: 15px;
}

.report-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #eee;
}

.report-name {
  font-weight: 500;
  color: #333;
}

.backup-section, .maintenance-section, .logs-section {
  background: white;
  border-radius: 8px;
  padding: 25px;
  margin-bottom: 30px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.backup-info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.backup-status {
  display: flex;
  justify-content: space-between;
  padding: 10px;
  background: #f8f9fa;
  border-radius: 6px;
}

.status-label {
  font-weight: 500;
  color: #333;
}

.status-value.enabled {
  color: #28a745;
  font-weight: bold;
}

.backup-actions, .maintenance-tasks {
  display: flex;
  gap: 15px;
  flex-wrap: wrap;
}

.task-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 6px;
  margin-bottom: 10px;
  width: 100%;
}

.task-name {
  font-weight: 500;
  color: #333;
}

.task-status {
  color: #666;
  font-size: 0.9rem;
}

.log-controls {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
  align-items: center;
}

.log-viewer {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 15px;
  border-radius: 6px;
  font-family: 'Courier New', monospace;
  font-size: 0.9rem;
  max-height: 400px;
  overflow-y: auto;
}

.log-entry {
  margin-bottom: 8px;
  padding: 5px;
  border-radius: 3px;
}

.log-time {
  color: #569cd6;
  margin-right: 10px;
}

.log-level {
  margin-right: 10px;
  padding: 2px 6px;
  border-radius: 3px;
  font-weight: bold;
  font-size: 0.8rem;
}

.log-error .log-level {
  background: #f14c4c;
  color: white;
}

.log-warning .log-level {
  background: #ffb86c;
  color: black;
}

.log-info .log-level {
  background: #50fa7b;
  color: black;
}

.log-message {
  color: #f8f8f2;
}

/* Button Styles */
.btn-primary, .btn-secondary, .btn-info, .btn-success, .btn-warning {
  padding: 10px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s;
}

.btn-primary { background: #007bff; color: white; }
.btn-secondary { background: #6c757d; color: white; }
.btn-info { background: #17a2b8; color: white; }
.btn-success { background: #28a745; color: white; }
.btn-warning { background: #ffc107; color: black; }

.btn-save { background: #28a745; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; }
.btn-cancel { background: #dc3545; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; }
.btn-edit { background: #007bff; color: white; padding: 4px 8px; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85rem; }
.btn-delete { background: #dc3545; color: white; padding: 4px 8px; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85rem; }
.btn-toggle { background: #ffc107; color: black; padding: 4px 8px; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85rem; }
.btn-generate { background: #28a745; color: white; padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9rem; }
.btn-task { background: #007bff; color: white; padding: 6px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 0.9rem; }

.btn-primary:disabled,
.btn-secondary:disabled,
.btn-info:disabled,
.btn-success:disabled,
.btn-warning:disabled,
.btn-save:disabled,
.btn-edit:disabled,
.btn-delete:disabled,
.btn-toggle:disabled,
.btn-generate:disabled,
.btn-task:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

h1, h2, h3 {
  color: #333;
  margin-bottom: 1rem;
}
</style>