<!--
  Driver Float Management Dashboard
  Purpose: Manage $100 e-transfer floats for fuel, oil, and vehicle needs
  Created: October 21, 2025
  
  Features:
  - 17,444+ float transaction management
  - Real-time reconciliation status
  - Receipt return tracking
  - Driver reimbursement workflow
  - Charter run integration
-->
<template>
  <div class="driver-float-management">
    <!-- Header Section -->
    <div class="management-header">
      <h2>Driver Float Management - E-Transfer System</h2>
      <div class="header-actions">
        <button @click="showIssueFloat = true" class="btn btn-success">
          <i class="fas fa-money-bill-wave"></i> Issue $100 Float
        </button>
        <button @click="showReconcileFloat = true" class="btn btn-warning">
          <i class="fas fa-receipt"></i> Reconcile Receipts
        </button>
        <button @click="showReimbursement = true" class="btn btn-info">
          <i class="fas fa-hand-holding-usd"></i> Process Reimbursement
        </button>
        <button @click="refreshData" class="btn btn-outline-primary">
          <i class="fas fa-sync-alt"></i> Refresh
        </button>
      </div>
    </div>

    <!-- Key Metrics Dashboard -->
    <div class="metrics-grid">
      <div class="metric-card outstanding-floats">
        <div class="metric-icon">
          <i class="fas fa-exclamation-circle"></i>
        </div>
        <div class="metric-content">
          <h3>${{ outstandingFloats.toLocaleString() }}</h3>
          <p>Outstanding Floats</p>
          <small>{{ outstandingCount }} active floats</small>
        </div>
      </div>
      
      <div class="metric-card total-issued">
        <div class="metric-icon">
          <i class="fas fa-arrow-up"></i>
        </div>
        <div class="metric-content">
          <h3>${{ totalIssuedToday.toLocaleString() }}</h3>
          <p>Issued Today</p>
          <small>{{ issuedCountToday }} e-transfers</small>
        </div>
      </div>
      
      <div class="metric-card reconciled-today">
        <div class="metric-icon">
          <i class="fas fa-check-circle"></i>
        </div>
        <div class="metric-content">
          <h3>${{ reconciledToday.toLocaleString() }}</h3>
          <p>Reconciled Today</p>
          <small>{{ reconciledCountToday }} receipts</small>
        </div>
      </div>
      
      <div class="metric-card pending-reimbursements">
        <div class="metric-icon">
          <i class="fas fa-clock"></i>
        </div>
        <div class="metric-content">
          <h3>${{ pendingReimbursements.toLocaleString() }}</h3>
          <p>Pending Reimbursements</p>
          <small>{{ pendingReimbursementCount }} drivers</small>
        </div>
      </div>
    </div>

    <!-- Main Content Tabs -->
    <div class="tab-container">
      <div class="tab-headers">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="['tab-header', { 'active': activeTab === tab.id }]"
        >
          <i :class="tab.icon"></i>
          {{ tab.label }}
          <span v-if="tab.count > 0" class="badge">{{ tab.count }}</span>
        </button>
      </div>

      <!-- Active Floats Tab -->
      <div v-if="activeTab === 'active'" class="tab-content">
        <div class="active-floats">
          <div class="filters-bar">
            <div class="filter-group">
              <label>Driver:</label>
              <select v-model="driverFilter">
                <option value="">All Drivers</option>
                <option v-for="driver in uniqueDrivers" :key="driver" :value="driver">
                  {{ driver }}
                </option>
              </select>
            </div>
            <div class="filter-group">
              <label>Status:</label>
              <select v-model="statusFilter">
                <option value="">All Statuses</option>
                <option value="pending">Pending</option>
                <option value="partial">Partial Return</option>
                <option value="overdue">Overdue</option>
              </select>
            </div>
            <div class="filter-group">
              <label>Amount:</label>
              <select v-model="amountFilter">
                <option value="">All Amounts</option>
                <option value="100">$100 Standard</option>
                <option value="over">Over $100</option>
                <option value="under">Under $100</option>
              </select>
            </div>
          </div>

          <div class="floats-table">
            <table class="table">
              <thead>
                <tr>
                  <th>Driver</th>
                  <th>Float Date</th>
                  <th>Amount</th>
                  <th>Type</th>
                  <th>Days Outstanding</th>
                  <th>Charter Runs</th>
                  <th>Receipts</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="float in filteredActiveFloats" :key="float.id" :class="getFloatRowClass(float)">
                  <td>
                    <div class="driver-info">
                      <strong>{{ float.driver_name }}</strong>
                      <div class="driver-id">ID: {{ float.driver_id }}</div>
                    </div>
                  </td>
                  <td>{{ formatDate(float.float_date) }}</td>
                  <td>
                    <span :class="['amount', float.float_amount < 0 ? 'negative' : 'positive']">
                      ${{ Math.abs(float.float_amount).toLocaleString() }}
                    </span>
                  </td>
                  <td>
                    <span class="float-type">{{ formatFloatType(float.float_type) }}</span>
                  </td>
                  <td>
                    <span :class="['days-outstanding', getDaysOutstandingClass(float.days_outstanding)]">
                      {{ float.days_outstanding }} days
                    </span>
                  </td>
                  <td>
                    <div class="charter-info">
                      <span v-if="float.reserve_number">{{ float.reserve_number }}</span>
                      <span v-else class="no-charter">No Charter</span>
                    </div>
                  </td>
                  <td>
                    <div class="receipt-status">
                      <span v-if="float.collection_amount > 0" class="has-receipts">
                        ${{ float.collection_amount.toLocaleString() }}
                      </span>
                      <span v-else class="no-receipts">No Receipts</span>
                    </div>
                  </td>
                  <td>
                    <span :class="['status-badge', `status-${float.reconciliation_status}`]">
                      {{ formatStatus(float.reconciliation_status) }}
                    </span>
                  </td>
                  <td>
                    <div class="action-buttons">
                      <button 
                        @click="addReceipts(float)" 
                        class="btn btn-xs btn-primary"
                        title="Add Receipts"
                      >
                        <i class="fas fa-receipt"></i>
                      </button>
                      <button 
                        @click="processReimbursement(float)" 
                        class="btn btn-xs btn-success"
                        title="Process Reimbursement"
                      >
                        <i class="fas fa-dollar-sign"></i>
                      </button>
                      <button 
                        @click="reconcileFloat(float)" 
                        class="btn btn-xs btn-warning"
                        title="Reconcile"
                      >
                        <i class="fas fa-balance-scale"></i>
                      </button>
                      <button 
                        @click="viewFloatDetails(float)" 
                        class="btn btn-xs btn-outline-info"
                        title="View Details"
                      >
                        <i class="fas fa-eye"></i>
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Recent Activity Tab -->
      <div v-if="activeTab === 'recent'" class="tab-content">
        <div class="recent-activity">
          <div class="activity-filters">
            <div class="date-range">
              <label>Date Range:</label>
              <input type="date" v-model="activityStartDate">
              <span>to</span>
              <input type="date" v-model="activityEndDate">
            </div>
            <div class="activity-type">
              <label>Activity Type:</label>
              <select v-model="activityTypeFilter">
                <option value="">All Activities</option>
                <option value="float_issued">Float Issued</option>
                <option value="receipt_added">Receipt Added</option>
                <option value="reconciled">Reconciled</option>
                <option value="reimbursement">Reimbursement</option>
              </select>
            </div>
          </div>

          <div class="activity-timeline">
            <div v-for="activity in recentActivities" :key="activity.id" class="activity-item">
              <div class="activity-icon">
                <i :class="getActivityIcon(activity.type)"></i>
              </div>
              <div class="activity-content">
                <div class="activity-header">
                  <h4>{{ activity.title }}</h4>
                  <span class="activity-time">{{ formatDateTime(activity.timestamp) }}</span>
                </div>
                <div class="activity-details">
                  <p>{{ activity.description }}</p>
                  <div class="activity-meta">
                    <span class="driver">{{ activity.driver_name }}</span>
                    <span class="amount">${{ activity.amount.toLocaleString() }}</span>
                    <span v-if="activity.charter_id" class="charter">Charter: {{ activity.charter_id }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Driver Summary Tab -->
      <div v-if="activeTab === 'drivers'" class="tab-content">
        <div class="driver-summary">
          <div class="summary-cards">
            <div v-for="driver in driverSummaries" :key="driver.driver_id" class="driver-card">
              <div class="driver-header">
                <div class="driver-info">
                  <h4>{{ driver.driver_name }}</h4>
                  <span class="driver-id">ID: {{ driver.driver_id }}</span>
                </div>
                <div class="driver-status">
                  <span :class="['status-indicator', getDriverStatusClass(driver)]"></span>
                  <span class="status-text">{{ getDriverStatus(driver) }}</span>
                </div>
              </div>
              
              <div class="driver-metrics">
                <div class="metric">
                  <label>Outstanding:</label>
                  <span class="value negative">${{ driver.outstanding_amount.toLocaleString() }}</span>
                </div>
                <div class="metric">
                  <label>This Month:</label>
                  <span class="value">${{ driver.monthly_floats.toLocaleString() }}</span>
                </div>
                <div class="metric">
                  <label>Avg Days:</label>
                  <span class="value">{{ driver.avg_reconciliation_days }}</span>
                </div>
                <div class="metric">
                  <label>Float Count:</label>
                  <span class="value">{{ driver.total_floats }}</span>
                </div>
              </div>
              
              <div class="driver-actions">
                <button @click="issueFloatToDriver(driver)" class="btn btn-sm btn-primary">
                  <i class="fas fa-plus"></i> Issue Float
                </button>
                <button @click="viewDriverHistory(driver)" class="btn btn-sm btn-outline-info">
                  <i class="fas fa-history"></i> History
                </button>
                <button @click="sendReminder(driver)" class="btn btn-sm btn-outline-warning">
                  <i class="fas fa-bell"></i> Remind
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Analytics Tab -->
      <div v-if="activeTab === 'analytics'" class="tab-content">
        <div class="analytics-dashboard">
          <div class="analytics-grid">
            <div class="chart-container">
              <h3>Monthly Float Trends</h3>
              <div class="chart-placeholder">
                <div class="chart-data">
                  <div v-for="month in monthlyTrends" :key="month.month" class="trend-bar">
                    <div class="bar" :style="{ height: getTrendBarHeight(month.amount) + '%' }"></div>
                    <div class="label">{{ month.month }}</div>
                    <div class="amount">${{ month.amount.toLocaleString() }}</div>
                  </div>
                </div>
              </div>
            </div>
            
            <div class="stats-container">
              <h3>Float Statistics</h3>
              <div class="stats-grid">
                <div class="stat-item">
                  <div class="stat-value">{{ floatStats.total_floats.toLocaleString() }}</div>
                  <div class="stat-label">Total Floats</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value">${{ floatStats.total_amount.toLocaleString() }}</div>
                  <div class="stat-label">Total Amount</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value">{{ floatStats.avg_reconciliation_days }}d</div>
                  <div class="stat-label">Avg Reconciliation</div>
                </div>
                <div class="stat-item">
                  <div class="stat-value">{{ floatStats.reconciliation_rate }}%</div>
                  <div class="stat-label">Reconciliation Rate</div>
                </div>
              </div>
            </div>
          </div>
          
          <div class="analytics-insights">
            <h3>Insights & Recommendations</h3>
            <div class="insights-list">
              <div v-for="insight in analyticsInsights" :key="insight.id" class="insight-item">
                <div :class="['insight-icon', insight.type]">
                  <i :class="insight.icon"></i>
                </div>
                <div class="insight-content">
                  <h4>{{ insight.title }}</h4>
                  <p>{{ insight.description }}</p>
                  <div v-if="insight.action" class="insight-action">
                    <button @click="performInsightAction(insight)" class="btn btn-sm btn-outline-primary">
                      {{ insight.action }}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Issue Float Modal -->
    <div v-if="showIssueFloat" class="modal-overlay" @click="closeModals">
      <div class="modal-content float-modal" @click.stop>
        <div class="modal-header">
          <h3>Issue $100 E-Transfer Float</h3>
          <button @click="closeModals" class="close-btn">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <form @submit.prevent="issueFloat" class="float-form">
          <div class="form-section">
            <h4>Driver Information</h4>
            <div class="form-row">
              <div class="form-group">
                <label>Driver</label>
                <select v-model="floatForm.driver_id" required @change="updateDriverInfo">
                  <option value="">Select Driver</option>
                  <option 
                    v-for="driver in availableDrivers" 
                    :key="driver.employee_id"
                    :value="driver.employee_id"
                  >
                    {{ driver.full_name }} ({{ driver.employee_number }})
                  </option>
                </select>
              </div>
              
              <div class="form-group">
                <label>Charter Run (Optional)</label>
                <input 
                  type="text" 
                  v-model="floatForm.reserve_number" 
                  placeholder="e.g., 019708"
                  pattern="[0-9]{6}"
                  title="6-digit reserve number"
                >
              </div>
            </div>
          </div>

          <div class="form-section">
            <h4>Float Details</h4>
            <div class="form-row">
              <div class="form-group">
                <label>Float Amount</label>
                <input 
                  type="number" 
                  step="0.01" 
                  v-model="floatForm.float_amount"
                  placeholder="100.00"
                  required
                >
              </div>
              
              <div class="form-group">
                <label>Float Type</label>
                <select v-model="floatForm.float_type" required>
                  <option value="fuel">Fuel</option>
                  <option value="oil">Oil/Fluids</option>
                  <option value="maintenance">Vehicle Maintenance</option>
                  <option value="general">General Expenses</option>
                </select>
              </div>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label>Payment Method</label>
                <select v-model="floatForm.payment_method" required>
                  <option value="etransfer">E-Transfer</option>
                  <option value="cash">Cash</option>
                  <option value="company_card">Company Card</option>
                </select>
              </div>
              
              <div class="form-group">
                <label>Float Date</label>
                <input type="date" v-model="floatForm.float_date" required>
              </div>
            </div>
            
            <div class="form-row">
              <div class="form-group full-width">
                <label>Notes</label>
                <textarea 
                  v-model="floatForm.notes" 
                  placeholder="Additional notes about this float..."
                  rows="3"
                ></textarea>
              </div>
            </div>
          </div>

          <div class="form-actions">
            <button type="button" @click="closeModals" class="btn btn-secondary">Cancel</button>
            <button type="submit" class="btn btn-success">Issue Float</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Reconcile Receipts Modal -->
    <div v-if="showReconcileFloat" class="modal-overlay" @click="closeModals">
      <div class="modal-content reconcile-modal" @click.stop>
        <div class="modal-header">
          <h3>Reconcile Float with Receipts</h3>
          <button @click="closeModals" class="close-btn">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <form @submit.prevent="reconcileFloatSubmit" class="reconcile-form">
          <div class="form-section">
            <h4>Select Float to Reconcile</h4>
            <div class="float-selection">
              <div v-for="float in unreconciled" :key="float.id" class="float-option">
                <label class="float-radio">
                  <input type="radio" :value="float.id" v-model="reconcileForm.float_id">
                  <div class="float-details">
                    <div class="float-header">
                      <strong>{{ float.driver_name }}</strong>
                      <span class="float-amount">${{ Math.abs(float.float_amount) }}</span>
                    </div>
                    <div class="float-meta">
                      {{ formatDate(float.float_date) }} • {{ formatFloatType(float.float_type) }}
                      <span v-if="float.reserve_number">• Charter: {{ float.reserve_number }}</span>
                    </div>
                  </div>
                </label>
              </div>
            </div>
          </div>

          <div v-if="reconcileForm.float_id" class="form-section">
            <h4>Receipt Information</h4>
            <div class="form-row">
              <div class="form-group">
                <label>Receipt Amount</label>
                <input 
                  type="number" 
                  step="0.01" 
                  v-model="reconcileForm.receipt_amount"
                  placeholder="0.00"
                  required
                >
              </div>
              
              <div class="form-group">
                <label>Receipt Date</label>
                <input type="date" v-model="reconcileForm.receipt_date" required>
              </div>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label>Vendor</label>
                <input 
                  type="text" 
                  v-model="reconcileForm.vendor_name" 
                  placeholder="Shell, Petro-Can, etc."
                >
              </div>
              
              <div class="form-group">
                <label>Receipt Reference</label>
                <input 
                  type="text" 
                  v-model="reconcileForm.receipt_reference" 
                  placeholder="Receipt number or reference"
                >
              </div>
            </div>
            
            <div class="reconciliation-summary">
              <div class="summary-item">
                <label>Original Float:</label>
                <span class="amount">${{ getSelectedFloatAmount() }}</span>
              </div>
              <div class="summary-item">
                <label>Receipt Amount:</label>
                <span class="amount">${{ reconcileForm.receipt_amount || 0 }}</span>
              </div>
              <div class="summary-item total">
                <label>{{ getReconciliationType() }}:</label>
                <span :class="['amount', getReconciliationClass()]">
                  ${{ getReconciliationAmount() }}
                </span>
              </div>
            </div>
          </div>

          <div class="form-actions">
            <button type="button" @click="closeModals" class="btn btn-secondary">Cancel</button>
            <button type="submit" class="btn btn-warning" :disabled="!reconcileForm.float_id">
              Reconcile Float
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DriverFloatManagement',
  data() {
    return {
      activeTab: 'active',
      showIssueFloat: false,
      showReconcileFloat: false,
      showReimbursement: false,
      
      // Data
      activeFloats: [],
      recentActivities: [],
      driverSummaries: [],
      availableDrivers: [],
      unreconciled: [],
      
      // Metrics
      outstandingFloats: 0,
      outstandingCount: 0,
      totalIssuedToday: 0,
      issuedCountToday: 0,
      reconciledToday: 0,
      reconciledCountToday: 0,
      pendingReimbursements: 0,
      pendingReimbursementCount: 0,
      
      // Filters
      driverFilter: '',
      statusFilter: '',
      amountFilter: '',
      activityStartDate: new Date().toISOString().split('T')[0],
      activityEndDate: new Date().toISOString().split('T')[0],
      activityTypeFilter: '',
      
      // Forms
      floatForm: this.getEmptyFloatForm(),
      reconcileForm: this.getEmptyReconcileForm(),
      
      // Analytics
      monthlyTrends: [],
      floatStats: {},
      analyticsInsights: []
    }
  },
  computed: {
    tabs() {
      return [
        {
          id: 'active',
          label: 'Active Floats',
          icon: 'fas fa-exclamation-circle',
          count: this.outstandingCount
        },
        {
          id: 'recent',
          label: 'Recent Activity',
          icon: 'fas fa-clock',
          count: this.recentActivities.length
        },
        {
          id: 'drivers',
          label: 'Driver Summary',
          icon: 'fas fa-users',
          count: this.driverSummaries.length
        },
        {
          id: 'analytics',
          label: 'Analytics',
          icon: 'fas fa-chart-bar',
          count: 0
        }
      ]
    },
    
    uniqueDrivers() {
      return [...new Set(this.activeFloats.map(f => f.driver_name))].sort()
    },
    
    filteredActiveFloats() {
      return this.activeFloats.filter(float => {
        if (this.driverFilter && float.driver_name !== this.driverFilter) return false
        if (this.statusFilter && float.reconciliation_status !== this.statusFilter) return false
        if (this.amountFilter) {
          const amount = Math.abs(float.float_amount)
          if (this.amountFilter === '100' && amount !== 100) return false
          if (this.amountFilter === 'over' && amount <= 100) return false
          if (this.amountFilter === 'under' && amount >= 100) return false
        }
        return true
      })
    }
  },
  async mounted() {
    await this.loadData()
  },
  methods: {
    async loadData() {
      try {
        await Promise.all([
          this.loadActiveFloats(),
          this.loadRecentActivities(),
          this.loadDriverSummaries(),
          this.loadAvailableDrivers(),
          this.loadMetrics(),
          this.loadAnalytics()
        ])
      } catch (error) {
        console.error('Error loading float data:', error)
        this.$toast.error('Failed to load float management data')
      }
    },
    
    async loadActiveFloats() {
      const response = await fetch('/api/floats/active')
      this.activeFloats = await response.json()
    },
    
    async loadRecentActivities() {
      const response = await fetch('/api/floats/activities')
      this.recentActivities = await response.json()
    },
    
    async loadDriverSummaries() {
      const response = await fetch('/api/floats/driver-summaries')
      this.driverSummaries = await response.json()
    },
    
    async loadAvailableDrivers() {
      const response = await fetch('/api/employees?is_chauffeur=true')
      this.availableDrivers = await response.json()
    },
    
    async loadMetrics() {
      const response = await fetch('/api/floats/metrics')
      const metrics = await response.json()
      
      this.outstandingFloats = metrics.outstanding_floats || 0
      this.outstandingCount = metrics.outstanding_count || 0
      this.totalIssuedToday = metrics.total_issued_today || 0
      this.issuedCountToday = metrics.issued_count_today || 0
      this.reconciledToday = metrics.reconciled_today || 0
      this.reconciledCountToday = metrics.reconciled_count_today || 0
      this.pendingReimbursements = metrics.pending_reimbursements || 0
      this.pendingReimbursementCount = metrics.pending_reimbursement_count || 0
    },
    
    async loadAnalytics() {
      const response = await fetch('/api/floats/analytics')
      const analytics = await response.json()
      
      this.monthlyTrends = analytics.monthly_trends || []
      this.floatStats = analytics.stats || {}
      this.analyticsInsights = analytics.insights || []
    },
    
    // Form Management
    getEmptyFloatForm() {
      return {
        driver_id: '',
        reserve_number: '',
        float_amount: 100.00,
        float_type: 'fuel',
        payment_method: 'etransfer',
        float_date: new Date().toISOString().split('T')[0],
        notes: ''
      }
    },
    
    getEmptyReconcileForm() {
      return {
        float_id: '',
        receipt_amount: '',
        receipt_date: new Date().toISOString().split('T')[0],
        vendor_name: '',
        receipt_reference: ''
      }
    },
    
    // Helper Methods
    formatDate(dateString) {
      if (!dateString) return 'N/A'
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    },
    
    formatDateTime(dateString) {
      if (!dateString) return 'N/A'
      return new Date(dateString).toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    },
    
    formatFloatType(type) {
      const types = {
        'fuel': 'Fuel',
        'oil': 'Oil/Fluids',
        'maintenance': 'Maintenance',
        'general': 'General',
        'cash_advance': 'Cash Advance'
      }
      return types[type] || type
    },
    
    formatStatus(status) {
      const statuses = {
        'pending': 'Pending',
        'partial': 'Partial Return',
        'reconciled': 'Reconciled',
        'overdue': 'Overdue'
      }
      return statuses[status] || status
    },
    
    getFloatRowClass(float) {
      if (float.days_outstanding > 7) return 'overdue'
      if (float.days_outstanding > 3) return 'warning'
      return ''
    },
    
    getDaysOutstandingClass(days) {
      if (days > 7) return 'overdue'
      if (days > 3) return 'warning'
      return 'normal'
    },
    
    getDriverStatusClass(driver) {
      if (driver.outstanding_amount > 200) return 'high-risk'
      if (driver.outstanding_amount > 100) return 'medium-risk'
      return 'low-risk'
    },
    
    getDriverStatus(driver) {
      if (driver.outstanding_amount > 200) return 'High Outstanding'
      if (driver.outstanding_amount > 100) return 'Medium Outstanding'
      return 'Good Standing'
    },
    
    getActivityIcon(type) {
      const icons = {
        'float_issued': 'fas fa-arrow-up text-success',
        'receipt_added': 'fas fa-receipt text-info',
        'reconciled': 'fas fa-check-circle text-success',
        'reimbursement': 'fas fa-hand-holding-usd text-warning'
      }
      return icons[type] || 'fas fa-circle'
    },
    
    getTrendBarHeight(amount) {
      const max = Math.max(...this.monthlyTrends.map(t => t.amount))
      return max > 0 ? (amount / max) * 100 : 0
    },
    
    getSelectedFloatAmount() {
      const selectedFloat = this.unreconciled.find(f => f.id === this.reconcileForm.float_id)
      return selectedFloat ? Math.abs(selectedFloat.float_amount) : 0
    },
    
    getReconciliationType() {
      const floatAmount = this.getSelectedFloatAmount()
      const receiptAmount = parseFloat(this.reconcileForm.receipt_amount) || 0
      if (receiptAmount > floatAmount) return 'Driver Owes'
      if (receiptAmount < floatAmount) return 'Refund Due'
      return 'Exact Match'
    },
    
    getReconciliationAmount() {
      const floatAmount = this.getSelectedFloatAmount()
      const receiptAmount = parseFloat(this.reconcileForm.receipt_amount) || 0
      return Math.abs(floatAmount - receiptAmount).toFixed(2)
    },
    
    getReconciliationClass() {
      const floatAmount = this.getSelectedFloatAmount()
      const receiptAmount = parseFloat(this.reconcileForm.receipt_amount) || 0
      if (receiptAmount > floatAmount) return 'negative'
      if (receiptAmount < floatAmount) return 'positive'
      return 'neutral'
    },
    
    // API Actions
    async issueFloat() {
      try {
        const response = await fetch('/api/floats', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.floatForm)
        })
        
        if (response.ok) {
          this.$toast.success('Float issued successfully')
          this.closeModals()
          await this.loadData()
        } else {
          throw new Error('Failed to issue float')
        }
      } catch (error) {
        console.error('Error issuing float:', error)
        this.$toast.error('Failed to issue float')
      }
    },
    
    async reconcileFloatSubmit() {
      try {
        const response = await fetch(`/api/floats/${this.reconcileForm.float_id}/reconcile`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.reconcileForm)
        })
        
        if (response.ok) {
          this.$toast.success('Float reconciled successfully')
          this.closeModals()
          await this.loadData()
        } else {
          throw new Error('Failed to reconcile float')
        }
      } catch (error) {
        console.error('Error reconciling float:', error)
        this.$toast.error('Failed to reconcile float')
      }
    },
    
    async refreshData() {
      await this.loadData()
      this.$toast.success('Data refreshed')
    },
    
    closeModals() {
      this.showIssueFloat = false
      this.showReconcileFloat = false
      this.showReimbursement = false
      this.floatForm = this.getEmptyFloatForm()
      this.reconcileForm = this.getEmptyReconcileForm()
    },
    
    // Placeholder methods for future implementation
    updateDriverInfo() {
      // Auto-populate driver information when selected
    },
    
    addReceipts(float) {
      console.log('Add receipts for float:', float)
    },
    
    processReimbursement(float) {
      console.log('Process reimbursement for float:', float)
    },
    
    reconcileFloat(float) {
      this.reconcileForm.float_id = float.id
      this.showReconcileFloat = true
    },
    
    viewFloatDetails(float) {
      console.log('View float details:', float)
    },
    
    issueFloatToDriver(driver) {
      this.floatForm.driver_id = driver.driver_id
      this.showIssueFloat = true
    },
    
    viewDriverHistory(driver) {
      console.log('View driver history:', driver)
    },
    
    sendReminder(driver) {
      console.log('Send reminder to driver:', driver)
    },
    
    performInsightAction(insight) {
      console.log('Perform insight action:', insight)
    }
  }
}
</script>

<style scoped>
.driver-float-management {
  padding: 20px;
  background-color: #f8f9fa;
  min-height: 100vh;
}

.management-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.management-header h2 {
  margin: 0;
  color: #2c3e50;
}

.header-actions {
  display: flex;
  gap: 15px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.metric-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  display: flex;
  align-items: center;
  gap: 15px;
}

.metric-card.outstanding-floats .metric-icon {
  background: #dc3545;
}

.metric-card.total-issued .metric-icon {
  background: #28a745;
}

.metric-card.reconciled-today .metric-icon {
  background: #17a2b8;
}

.metric-card.pending-reimbursements .metric-icon {
  background: #ffc107;
}

.metric-icon {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 1.5rem;
}

.metric-content h3 {
  margin: 0;
  font-size: 1.8rem;
  color: #2c3e50;
}

.metric-content p {
  margin: 5px 0 0 0;
  color: #6c757d;
  font-weight: 600;
}

.metric-content small {
  color: #adb5bd;
  font-size: 0.8rem;
}

.tab-container {
  background: white;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  overflow: hidden;
}

.tab-headers {
  display: flex;
  background: #f8f9fa;
  border-bottom: 1px solid #dee2e6;
}

.tab-header {
  padding: 15px 20px;
  border: none;
  background: none;
  color: #495057;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab-header:hover {
  background: #e9ecef;
  color: #007bff;
}

.tab-header.active {
  background: white;
  color: #007bff;
  border-bottom: 2px solid #007bff;
}

.badge {
  background: #dc3545;
  color: white;
  border-radius: 12px;
  padding: 2px 8px;
  font-size: 0.75rem;
  font-weight: bold;
}

.tab-content {
  padding: 30px;
  min-height: 500px;
}

/* Filters Bar */
.filters-bar {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 6px;
  align-items: end;
}

.filter-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.filter-group label {
  font-weight: 600;
  color: #495057;
  font-size: 0.9rem;
}

.filter-group select {
  padding: 8px 12px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  background: white;
}

/* Floats Table */
.table {
  width: 100%;
  border-collapse: collapse;
  background: white;
}

.table th,
.table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #dee2e6;
}

.table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #495057;
  position: sticky;
  top: 0;
}

.table tr.overdue {
  background: #fff5f5;
  border-left: 4px solid #dc3545;
}

.table tr.warning {
  background: #fffbf0;
  border-left: 4px solid #ffc107;
}

.driver-info strong {
  color: #2c3e50;
}

.driver-id {
  font-size: 0.8rem;
  color: #6c757d;
}

.amount.negative {
  color: #dc3545;
  font-weight: bold;
}

.amount.positive {
  color: #28a745;
  font-weight: bold;
}

.float-type {
  background: #e9ecef;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  text-transform: uppercase;
}

.days-outstanding.normal {
  color: #28a745;
}

.days-outstanding.warning {
  color: #ffc107;
}

.days-outstanding.overdue {
  color: #dc3545;
  font-weight: bold;
}

.charter-info .no-charter {
  color: #6c757d;
  font-style: italic;
}

.receipt-status .has-receipts {
  color: #28a745;
  font-weight: 600;
}

.receipt-status .no-receipts {
  color: #6c757d;
  font-style: italic;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.status-badge.status-pending {
  background: #fff3cd;
  color: #856404;
}

.status-badge.status-partial {
  background: #cce5ff;
  color: #004085;
}

.status-badge.status-reconciled {
  background: #d4edda;
  color: #155724;
}

.status-badge.status-overdue {
  background: #f8d7da;
  color: #721c24;
}

.action-buttons {
  display: flex;
  gap: 5px;
}

/* Driver Summary Cards */
.summary-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
  gap: 20px;
}

.driver-card {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
}

.driver-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.driver-info h4 {
  margin: 0;
  color: #2c3e50;
}

.driver-id {
  font-size: 0.8rem;
  color: #6c757d;
}

.driver-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.status-indicator.low-risk {
  background: #28a745;
}

.status-indicator.medium-risk {
  background: #ffc107;
}

.status-indicator.high-risk {
  background: #dc3545;
}

.driver-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 15px;
}

.metric {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #e9ecef;
}

.metric label {
  font-weight: 600;
  color: #495057;
}

.metric .value {
  color: #2c3e50;
  font-weight: 600;
}

.metric .value.negative {
  color: #dc3545;
}

.driver-actions {
  display: flex;
  gap: 10px;
}

/* Activity Timeline */
.activity-timeline {
  max-height: 600px;
  overflow-y: auto;
}

.activity-item {
  display: flex;
  gap: 15px;
  padding: 15px;
  border-bottom: 1px solid #e9ecef;
}

.activity-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #f8f9fa;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.activity-content {
  flex: 1;
}

.activity-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
}

.activity-header h4 {
  margin: 0;
  color: #2c3e50;
  font-size: 1rem;
}

.activity-time {
  color: #6c757d;
  font-size: 0.8rem;
}

.activity-details p {
  margin: 0 0 8px 0;
  color: #495057;
}

.activity-meta {
  display: flex;
  gap: 15px;
  font-size: 0.8rem;
  color: #6c757d;
}

/* Analytics Dashboard */
.analytics-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 30px;
  margin-bottom: 30px;
}

.chart-container,
.stats-container {
  background: #f8f9fa;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #dee2e6;
}

.chart-container h3,
.stats-container h3 {
  margin: 0 0 20px 0;
  color: #2c3e50;
}

.chart-data {
  display: flex;
  align-items: end;
  gap: 10px;
  height: 200px;
}

.trend-bar {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
}

.bar {
  background: linear-gradient(180deg, #007bff, #0056b3);
  width: 30px;
  min-height: 5px;
  border-radius: 2px 2px 0 0;
  margin-bottom: 5px;
}

.trend-bar .label {
  font-size: 0.7rem;
  color: #6c757d;
  margin-bottom: 2px;
}

.trend-bar .amount {
  font-size: 0.8rem;
  color: #2c3e50;
  font-weight: 600;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
}

.stat-item {
  text-align: center;
  padding: 15px;
  background: white;
  border-radius: 6px;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: bold;
  color: #2c3e50;
  margin-bottom: 5px;
}

.stat-label {
  font-size: 0.8rem;
  color: #6c757d;
  text-transform: uppercase;
}

/* Insights */
.insights-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.insight-item {
  display: flex;
  gap: 15px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 6px;
  border-left: 4px solid #007bff;
}

.insight-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  flex-shrink: 0;
}

.insight-icon.info {
  background: #17a2b8;
}

.insight-icon.warning {
  background: #ffc107;
}

.insight-icon.success {
  background: #28a745;
}

.insight-content h4 {
  margin: 0 0 8px 0;
  color: #2c3e50;
}

.insight-content p {
  margin: 0 0 10px 0;
  color: #495057;
  font-size: 0.9rem;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #dee2e6;
}

.modal-header h3 {
  margin: 0;
  color: #2c3e50;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: #6c757d;
  cursor: pointer;
}

.float-form,
.reconcile-form {
  padding: 20px;
}

.form-section {
  margin-bottom: 30px;
}

.form-section h4 {
  margin: 0 0 15px 0;
  color: #495057;
  font-size: 1.1rem;
  border-bottom: 1px solid #dee2e6;
  padding-bottom: 8px;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 15px;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group.full-width {
  grid-column: 1 / -1;
}

.form-group label {
  font-weight: 600;
  margin-bottom: 5px;
  color: #495057;
}

.form-group input,
.form-group select,
.form-group textarea {
  padding: 8px 12px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 0.9rem;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 2px rgba(0,123,255,0.25);
}

/* Float Selection */
.float-selection {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 300px;
  overflow-y: auto;
}

.float-option {
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 15px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.float-option:hover {
  background: #f8f9fa;
}

.float-radio {
  display: flex;
  align-items: center;
  gap: 15px;
  cursor: pointer;
}

.float-radio input[type="radio"] {
  margin: 0;
}

.float-details {
  flex: 1;
}

.float-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 5px;
}

.float-header strong {
  color: #2c3e50;
}

.float-amount {
  font-weight: bold;
  color: #007bff;
}

.float-meta {
  font-size: 0.8rem;
  color: #6c757d;
}

/* Reconciliation Summary */
.reconciliation-summary {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 15px;
  margin-top: 20px;
}

.summary-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #e9ecef;
}

.summary-item.total {
  border-bottom: none;
  font-weight: bold;
  padding-top: 15px;
  border-top: 2px solid #dee2e6;
}

.summary-item label {
  color: #495057;
}

.summary-item .amount.neutral {
  color: #28a745;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 15px;
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid #dee2e6;
}

/* Responsive Design */
@media (max-width: 768px) {
  .management-header {
    flex-direction: column;
    gap: 15px;
    align-items: stretch;
  }
  
  .header-actions {
    justify-content: center;
    flex-wrap: wrap;
  }
  
  .metrics-grid {
    grid-template-columns: 1fr;
  }
  
  .tab-headers {
    flex-wrap: wrap;
  }
  
  .filters-bar {
    flex-direction: column;
    align-items: stretch;
  }
  
  .form-row {
    grid-template-columns: 1fr;
  }
  
  .analytics-grid {
    grid-template-columns: 1fr;
  }
  
  .summary-cards {
    grid-template-columns: 1fr;
  }
  
  .driver-metrics {
    grid-template-columns: 1fr;
  }
  
  .chart-data {
    height: 150px;
  }
}
</style>