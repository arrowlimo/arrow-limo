<template>
  <div class="driver-float-management">
    <!-- Header -->
    <div class="page-header">
      <h1 class="page-title">
        <i class="fas fa-money-bill-wave"></i>
        Driver Float Management
      </h1>
      <p class="page-subtitle">Manage $100 e-transfer float system with real-time reconciliation</p>
    </div>

    <!-- Key Metrics Dashboard -->
    <div class="metrics-grid">
      <div class="metric-card">
        <div class="metric-icon">
          <i class="fas fa-wallet"></i>
        </div>
        <div class="metric-content">
          <div class="metric-value">${{ metrics.totalActiveFloats?.toLocaleString() || '0' }}</div>
          <div class="metric-label">Total Active Floats</div>
        </div>
      </div>
      
      <div class="metric-card">
        <div class="metric-icon">
          <i class="fas fa-users"></i>
        </div>
        <div class="metric-content">
          <div class="metric-value">{{ metrics.driversWithFloats || 0 }}</div>
          <div class="metric-label">Drivers with Floats</div>
        </div>
      </div>
      
      <div class="metric-card">
        <div class="metric-icon">
          <i class="fas fa-check-circle"></i>
        </div>
        <div class="metric-content">
          <div class="metric-value">{{ metrics.reconciledPercentage || 0 }}%</div>
          <div class="metric-label">Reconciled</div>
        </div>
      </div>
      
      <div class="metric-card">
        <div class="metric-icon">
          <i class="fas fa-exclamation-triangle"></i>
        </div>
        <div class="metric-content">
          <div class="metric-value">{{ metrics.unreconciledCount || 0 }}</div>
          <div class="metric-label">Unreconciled</div>
        </div>
      </div>
    </div>

    <!-- Tab Navigation -->
    <div class="tab-container">
      <div class="tab-navigation">
        <button 
          class="tab-button" 
          :class="{ active: activeTab === 'active' }"
          @click="activeTab = 'active'"
        >
          <i class="fas fa-clock"></i>
          Active Floats
        </button>
        <button 
          class="tab-button" 
          :class="{ active: activeTab === 'recent' }"
          @click="activeTab = 'recent'"
        >
          <i class="fas fa-history"></i>
          Recent Activity
        </button>
        <button 
          class="tab-button" 
          :class="{ active: activeTab === 'drivers' }"
          @click="activeTab = 'drivers'"
        >
          <i class="fas fa-user-tie"></i>
          Driver Summary
        </button>
        <button 
          class="tab-button" 
          :class="{ active: activeTab === 'analytics' }"
          @click="activeTab = 'analytics'"
        >
          <i class="fas fa-chart-line"></i>
          Analytics
        </button>
      </div>

      <!-- Active Floats Tab -->
      <div v-show="activeTab === 'active'" class="tab-content">
        <div class="content-header">
          <h2>Active Float Transactions</h2>
          <div class="filters">
            <select v-model="filters.status" @change="loadActiveFloats">
              <option value="">All Statuses</option>
              <option value="active">Active</option>
              <option value="pending_reconciliation">Pending Reconciliation</option>
              <option value="reconciled">Reconciled</option>
            </select>
            <input 
              type="text" 
              v-model="filters.driverSearch" 
              placeholder="Search driver..."
              @input="loadActiveFloats"
            >
          </div>
        </div>

        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Float ID</th>
                <th>Driver</th>
                <th>Amount</th>
                <th>Issue Date</th>
                <th>Charter</th>
                <th>Status</th>
                <th>Banking Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="float in activeFloats" :key="float.float_id">
                <td>{{ float.float_id }}</td>
                <td>{{ float.driver_name }}</td>
                <td class="amount">${{ float.float_amount?.toFixed(2) }}</td>
                <td>{{ formatDate(float.issue_date) }}</td>
                <td>
                  <span v-if="float.reserve_number" class="charter-link">
                    {{ float.reserve_number }}
                  </span>
                  <span v-else class="no-charter">No charter</span>
                </td>
                <td>
                  <span class="status-badge" :class="float.float_status">
                    {{ formatStatus(float.float_status) }}
                  </span>
                </td>
                <td>
                  <span class="status-badge" :class="float.reconciliation_status">
                    {{ formatStatus(float.reconciliation_status) }}
                  </span>
                </td>
                <td>
                  <div class="action-buttons">
                    <button 
                      class="btn btn-sm btn-primary"
                      @click="viewFloatDetails(float)"
                    >
                      <i class="fas fa-eye"></i>
                    </button>
                    <button 
                      class="btn btn-sm btn-success"
                      v-if="float.float_status === 'active'"
                      @click="reconcileFloat(float)"
                    >
                      <i class="fas fa-check"></i>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Recent Activity Tab -->
      <div v-show="activeTab === 'recent'" class="tab-content">
        <div class="content-header">
          <h2>Recent Float Activity</h2>
          <div class="date-range-picker">
            <input type="date" v-model="dateRange.start" @change="loadRecentActivity">
            <span>to</span>
            <input type="date" v-model="dateRange.end" @change="loadRecentActivity">
          </div>
        </div>

        <div class="activity-timeline">
          <div v-for="activity in recentActivity" :key="activity.id" class="activity-item">
            <div class="activity-icon" :class="activity.activity_type">
              <i :class="getActivityIcon(activity.activity_type)"></i>
            </div>
            <div class="activity-content">
              <div class="activity-header">
                <span class="activity-title">{{ activity.activity_description }}</span>
                <span class="activity-time">{{ formatDateTime(activity.created_at) }}</span>
              </div>
              <div class="activity-details">
                <span class="driver">{{ activity.driver_name }}</span>
                <span class="amount">${{ activity.amount?.toFixed(2) }}</span>
                <span v-if="activity.reserve_number" class="charter">Charter: {{ activity.reserve_number }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Driver Summary Tab -->
      <div v-show="activeTab === 'drivers'" class="tab-content">
        <div class="content-header">
          <h2>Driver Float Summary</h2>
        </div>

        <div class="driver-grid">
          <div v-for="driver in driverSummary" :key="driver.driver_name" class="driver-card">
            <div class="driver-header">
              <h3>{{ driver.driver_name }}</h3>
              <span class="float-count">{{ driver.active_float_count }} active</span>
            </div>
            <div class="driver-metrics">
              <div class="metric">
                <label>Total Active:</label>
                <span class="value">${{ driver.total_active_amount?.toFixed(2) }}</span>
              </div>
              <div class="metric">
                <label>Lifetime Total:</label>
                <span class="value">${{ driver.lifetime_total?.toFixed(2) }}</span>
              </div>
              <div class="metric">
                <label>Last Float:</label>
                <span class="value">{{ formatDate(driver.last_float_date) }}</span>
              </div>
              <div class="metric">
                <label>Reconciliation Rate:</label>
                <span class="value">{{ driver.reconciliation_rate || 0 }}%</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Analytics Tab -->
      <div v-show="activeTab === 'analytics'" class="tab-content">
        <div class="content-header">
          <h2>Float Analytics</h2>
        </div>

        <div class="analytics-grid">
          <div class="chart-container">
            <h3>Monthly Float Trends</h3>
            <div class="chart-placeholder">
              <p>Chart showing monthly float issuance and reconciliation trends</p>
              <div class="trend-data">
                <div v-for="trend in monthlyTrends" :key="trend.month" class="trend-item">
                  <span class="month">{{ trend.month }}</span>
                  <span class="issued">${{ trend.total_issued?.toLocaleString() }}</span>
                  <span class="reconciled">${{ trend.total_reconciled?.toLocaleString() }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="summary-stats">
            <h3>System Statistics</h3>
            <div class="stat-list">
              <div class="stat-item">
                <label>Total Float Records:</label>
                <span>{{ analytics.totalRecords?.toLocaleString() }}</span>
              </div>
              <div class="stat-item">
                <label>Average Float Amount:</label>
                <span>${{ analytics.averageAmount?.toFixed(2) }}</span>
              </div>
              <div class="stat-item">
                <label>Average Reconciliation Time:</label>
                <span>{{ analytics.averageReconciliationDays }} days</span>
              </div>
              <div class="stat-item">
                <label>System Health Score:</label>
                <span class="health-score" :class="analytics.healthScore >= 90 ? 'excellent' : analytics.healthScore >= 70 ? 'good' : 'needs-attention'">
                  {{ analytics.healthScore }}%
                </span>
              </div>
            </div>
          </div>
        </div>
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
      loading: false,
      
      // Metrics
      metrics: {
        totalActiveFloats: 0,
        driversWithFloats: 0,
        reconciledPercentage: 0,
        unreconciledCount: 0
      },
      
      // Data arrays
      activeFloats: [],
      recentActivity: [],
      driverSummary: [],
      monthlyTrends: [],
      
      // Analytics
      analytics: {
        totalRecords: 0,
        averageAmount: 0,
        averageReconciliationDays: 0,
        healthScore: 0
      },
      
      // Filters
      filters: {
        status: '',
        driverSearch: ''
      },
      
      // Date range
      dateRange: {
        start: this.getDateDaysAgo(30),
        end: this.getTodayDate()
      }
    }
  },
  
  mounted() {
    this.loadAllData();
  },
  
  methods: {
    async loadAllData() {
      this.loading = true;
      try {
        await Promise.all([
          this.loadMetrics(),
          this.loadActiveFloats(),
          this.loadRecentActivity(),
          this.loadDriverSummary(),
          this.loadAnalytics()
        ]);
      } catch (error) {
        console.error('Error loading float data:', error);
      } finally {
        this.loading = false;
      }
    },
    
    async loadMetrics() {
      try {
        const response = await fetch('/api/floats/metrics');
        const data = await response.json();
        this.metrics = data;
      } catch (error) {
        console.error('Error loading metrics:', error);
      }
    },
    
    async loadActiveFloats() {
      try {
        const params = new URLSearchParams();
        if (this.filters.status) params.append('status', this.filters.status);
        if (this.filters.driverSearch) params.append('driver', this.filters.driverSearch);
        
        const response = await fetch(`/api/floats/active?${params}`);
        const data = await response.json();
        this.activeFloats = data;
      } catch (error) {
        console.error('Error loading active floats:', error);
      }
    },
    
    async loadRecentActivity() {
      try {
        const params = new URLSearchParams({
          start_date: this.dateRange.start,
          end_date: this.dateRange.end
        });
        
        const response = await fetch(`/api/floats/activity?${params}`);
        const data = await response.json();
        this.recentActivity = data;
      } catch (error) {
        console.error('Error loading recent activity:', error);
      }
    },
    
    async loadDriverSummary() {
      try {
        const response = await fetch('/api/floats/drivers');
        const data = await response.json();
        this.driverSummary = data;
      } catch (error) {
        console.error('Error loading driver summary:', error);
      }
    },
    
    async loadAnalytics() {
      try {
        const response = await fetch('/api/floats/analytics');
        const data = await response.json();
        this.analytics = data.analytics || {};
        this.monthlyTrends = data.trends || [];
      } catch (error) {
        console.error('Error loading analytics:', error);
      }
    },
    
    async reconcileFloat(float) {
      if (confirm(`Reconcile float ${float.float_id} for ${float.driver_name}?`)) {
        try {
          const response = await fetch(`/api/floats/${float.float_id}/reconcile`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
          });
          
          if (response.ok) {
            alert('Float reconciled successfully');
            this.loadAllData();
          } else {
            alert('Error reconciling float');
          }
        } catch (error) {
          console.error('Error reconciling float:', error);
        }
      }
    },
    
    viewFloatDetails(float) {
      // TODO: Implement float details modal
      alert(`Float Details: ${float.float_id}\nDriver: ${float.driver_name}\nAmount: $${float.float_amount}`);
    },
    
    // Utility methods
    formatDate(dateString) {
      if (!dateString) return 'N/A';
      return new Date(dateString).toLocaleDateString();
    },
    
    formatDateTime(dateString) {
      if (!dateString) return 'N/A';
      return new Date(dateString).toLocaleString();
    },
    
    formatStatus(status) {
      if (!status) return 'Unknown';
      return status.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    },
    
    getActivityIcon(activityType) {
      const icons = {
        'float_issued': 'fas fa-plus-circle',
        'float_reconciled': 'fas fa-check-circle',
        'banking_matched': 'fas fa-link',
        'charter_assigned': 'fas fa-car',
        'receipt_uploaded': 'fas fa-receipt'
      };
      return icons[activityType] || 'fas fa-circle';
    },
    
    getDateDaysAgo(days) {
      const date = new Date();
      date.setDate(date.getDate() - days);
      return date.toISOString().split('T')[0];
    },
    
    getTodayDate() {
      return new Date().toISOString().split('T')[0];
    }
  }
}
</script>

<style scoped>
.driver-float-management {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  text-align: center;
  margin-bottom: 30px;
}

.page-title {
  color: #2c3e50;
  margin-bottom: 10px;
  font-size: 2.2em;
}

.page-title i {
  margin-right: 15px;
  color: #27ae60;
}

.page-subtitle {
  color: #7f8c8d;
  font-size: 1.1em;
}

/* Metrics Grid */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.metric-card {
  background: white;
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  display: flex;
  align-items: center;
  gap: 15px;
}

.metric-icon {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5em;
  color: white;
  background: linear-gradient(45deg, #3498db, #2980b9);
}

.metric-value {
  font-size: 1.8em;
  font-weight: bold;
  color: #2c3e50;
}

.metric-label {
  color: #7f8c8d;
  font-size: 0.9em;
}

/* Tab Container */
.tab-container {
  background: white;
  border-radius: 10px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  overflow: hidden;
}

.tab-navigation {
  display: flex;
  background: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

.tab-button {
  flex: 1;
  padding: 15px 20px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 1em;
  color: #6c757d;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.tab-button:hover {
  background: #e9ecef;
  color: #495057;
}

.tab-button.active {
  background: white;
  color: #007bff;
  border-bottom: 3px solid #007bff;
}

.tab-content {
  padding: 20px;
}

.content-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.content-header h2 {
  margin: 0;
  color: #2c3e50;
}

.filters {
  display: flex;
  gap: 10px;
}

.filters select,
.filters input {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 5px;
  font-size: 0.9em;
}

/* Table Styles */
.table-container {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.9em;
}

.data-table th,
.data-table td {
  text-align: left;
  padding: 12px;
  border-bottom: 1px solid #e9ecef;
}

.data-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #495057;
}

.data-table .amount {
  font-weight: 600;
  color: #27ae60;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;
  font-weight: 600;
  text-transform: uppercase;
}

.status-badge.active {
  background: #d4edda;
  color: #155724;
}

.status-badge.reconciled {
  background: #cce5ff;
  color: #004085;
}

.status-badge.pending_reconciliation {
  background: #fff3cd;
  color: #856404;
}

.charter-link {
  color: #007bff;
  font-weight: 600;
}

.no-charter {
  color: #6c757d;
  font-style: italic;
}

.action-buttons {
  display: flex;
  gap: 5px;
}

.btn {
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8em;
  transition: all 0.3s;
}

.btn-sm {
  padding: 4px 8px;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-success {
  background: #28a745;
  color: white;
}

.btn:hover {
  opacity: 0.8;
  transform: translateY(-1px);
}

/* Activity Timeline */
.activity-timeline {
  max-height: 600px;
  overflow-y: auto;
}

.activity-item {
  display: flex;
  gap: 15px;
  padding: 15px 0;
  border-bottom: 1px solid #f0f0f0;
}

.activity-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  background: #3498db;
}

.activity-icon.float_issued {
  background: #27ae60;
}

.activity-icon.float_reconciled {
  background: #3498db;
}

.activity-icon.banking_matched {
  background: #f39c12;
}

.activity-content {
  flex: 1;
}

.activity-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 5px;
}

.activity-title {
  font-weight: 600;
  color: #2c3e50;
}

.activity-time {
  color: #7f8c8d;
  font-size: 0.9em;
}

.activity-details {
  display: flex;
  gap: 15px;
  font-size: 0.9em;
  color: #7f8c8d;
}

/* Driver Grid */
.driver-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.driver-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  border-left: 4px solid #007bff;
}

.driver-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.driver-header h3 {
  margin: 0;
  color: #2c3e50;
}

.float-count {
  background: #007bff;
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;
}

.driver-metrics {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.metric {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #e9ecef;
}

.metric label {
  color: #6c757d;
  font-size: 0.9em;
}

.metric .value {
  font-weight: 600;
  color: #2c3e50;
}

/* Analytics */
.analytics-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 30px;
}

.chart-container,
.summary-stats {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
}

.chart-placeholder {
  height: 300px;
  border: 2px dashed #ddd;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #6c757d;
}

.trend-data {
  margin-top: 20px;
  width: 100%;
}

.trend-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #e9ecef;
}

.stat-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid #e9ecef;
}

.health-score.excellent {
  color: #27ae60;
  font-weight: bold;
}

.health-score.good {
  color: #f39c12;
  font-weight: bold;
}

.health-score.needs-attention {
  color: #e74c3c;
  font-weight: bold;
}

.date-range-picker {
  display: flex;
  align-items: center;
  gap: 10px;
}

.date-range-picker input {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 5px;
}

.date-range-picker span {
  color: #6c757d;
}
</style>