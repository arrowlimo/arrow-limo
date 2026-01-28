<!--
  Continuous Salary Employment Management Component
  Purpose: Manage ongoing salary employees with automatic monthly booking,
           ROE calculations, and end-of-employment processing
  Created: October 21, 2025
-->
<template>
  <div class="continuous-employment-management">
    <!-- Header Section -->
    <div class="management-header">
      <h2>Continuous Salary Employment</h2>
      <div class="header-actions">
        <button @click="showCreateContract = true" class="btn btn-success">
          <i class="fas fa-user-plus"></i> New Salary Employee
        </button>
        <button @click="runMonthlyPayroll" class="btn btn-primary" :disabled="processingPayroll">
          <i class="fas fa-calendar-check"></i> 
          {{ processingPayroll ? 'Processing...' : 'Generate Monthly Payroll' }}
        </button>
      </div>
    </div>

    <!-- Quick Stats -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-icon">
          <i class="fas fa-users"></i>
        </div>
        <div class="stat-content">
          <h3>{{ activeContracts.length }}</h3>
          <p>Active Salary Employees</p>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon">
          <i class="fas fa-dollar-sign"></i>
        </div>
        <div class="stat-content">
          <h3>${{ totalMonthlySalaries.toLocaleString() }}</h3>
          <p>Total Monthly Salaries</p>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon">
          <i class="fas fa-clock"></i>
        </div>
        <div class="stat-content">
          <h3>{{ pendingPayrollApprovals }}</h3>
          <p>Pending Payroll Approvals</p>
        </div>
      </div>
      
      <div class="stat-card">
        <div class="stat-icon">
          <i class="fas fa-file-alt"></i>
        </div>
        <div class="stat-content">
          <h3>{{ pendingROEs }}</h3>
          <p>Pending ROEs</p>
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

      <!-- Active Contracts Tab -->
      <div v-if="activeTab === 'contracts'" class="tab-content">
        <div class="contracts-table">
          <table class="table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Position</th>
                <th>Start Date</th>
                <th>Monthly Salary</th>
                <th>Auto Booking</th>
                <th>Contract Type</th>
                <th>Next Payroll</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="contract in activeContracts" :key="contract.contract_id">
                <td>
                  <div class="employee-info">
                    <strong>{{ contract.employee_name }}</strong>
                    <div class="employee-details">ID: {{ contract.employee_id }}</div>
                  </div>
                </td>
                <td>{{ contract.classification_type || 'General' }}</td>
                <td>{{ formatDate(contract.employment_start_date) }}</td>
                <td class="salary-amount">${{ contract.monthly_salary.toLocaleString() }}</td>
                <td>
                  <span :class="['status-badge', contract.auto_book_enabled ? 'enabled' : 'disabled']">
                    {{ contract.auto_book_enabled ? 'Enabled' : 'Disabled' }}
                  </span>
                </td>
                <td>{{ formatContractType(contract.contract_type) }}</td>
                <td>{{ getNextPayrollDate(contract) }}</td>
                <td>
                  <div class="action-buttons">
                    <button @click="editContract(contract)" class="btn btn-sm btn-outline-primary">
                      <i class="fas fa-edit"></i>
                    </button>
                    <button @click="viewPayrollHistory(contract)" class="btn btn-sm btn-outline-info">
                      <i class="fas fa-history"></i>
                    </button>
                    <button @click="terminateEmployment(contract)" class="btn btn-sm btn-outline-danger">
                      <i class="fas fa-user-times"></i>
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Monthly Payroll Tab -->
      <div v-if="activeTab === 'payroll'" class="tab-content">
        <div class="payroll-controls">
          <div class="period-selector">
            <label>Pay Period:</label>
            <select v-model="selectedPayPeriod" @change="loadPayrollData">
              <option v-for="period in payPeriods" :key="period.value" :value="period.value">
                {{ period.label }}
              </option>
            </select>
          </div>
          
          <button @click="approveAllPayroll" class="btn btn-success" :disabled="!hasUnapprovedPayroll">
            <i class="fas fa-check-double"></i> Approve All
          </button>
        </div>

        <div class="payroll-table">
          <table class="table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Gross Salary</th>
                <th>Deductions</th>
                <th>Net Pay</th>
                <th>Status</th>
                <th>Generated</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="payroll in monthlyPayroll" :key="payroll.payroll_id">
                <td>{{ payroll.employee_name }}</td>
                <td class="amount">${{ payroll.total_gross_pay.toLocaleString() }}</td>
                <td class="amount">${{ payroll.total_deductions.toLocaleString() }}</td>
                <td class="amount">${{ payroll.net_pay.toLocaleString() }}</td>
                <td>
                  <span :class="['status-badge', `status-${payroll.payroll_status}`]">
                    {{ formatPayrollStatus(payroll.payroll_status) }}
                  </span>
                </td>
                <td>{{ formatDateTime(payroll.generated_at) }}</td>
                <td>
                  <div class="action-buttons">
                    <button 
                      v-if="payroll.payroll_status === 'generated'"
                      @click="approvePayroll(payroll.payroll_id)" 
                      class="btn btn-sm btn-success"
                    >
                      <i class="fas fa-check"></i> Approve
                    </button>
                    <button @click="viewPayrollDetails(payroll)" class="btn btn-sm btn-outline-info">
                      <i class="fas fa-eye"></i> Details
                    </button>
                    <button 
                      v-if="payroll.payroll_status === 'generated'"
                      @click="editPayroll(payroll)" 
                      class="btn btn-sm btn-outline-warning"
                    >
                      <i class="fas fa-edit"></i> Edit
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ROE Management Tab -->
      <div v-if="activeTab === 'roe'" class="tab-content">
        <div class="roe-controls">
          <button @click="showCreateROE = true" class="btn btn-success">
            <i class="fas fa-file-medical"></i> Create ROE for Any Employee
          </button>
        </div>
        
        <div class="roe-list">
          <div v-for="roe in roeRecords" :key="roe.roe_id" class="roe-card">
            <div class="roe-header">
              <div class="roe-number">
                <strong>{{ roe.roe_number }}</strong>
                <span :class="['status-badge', `status-${roe.roe_status}`]">
                  {{ formatROEStatus(roe.roe_status) }}
                </span>
              </div>
              <div class="roe-dates">
                Last Day Paid: {{ formatDate(roe.last_day_paid) }}
              </div>
            </div>
            
            <div class="roe-details">
              <div class="roe-info">
                <h4>{{ roe.employee_name }}</h4>
                <p><strong>Reason:</strong> {{ roe.reason_description }}</p>
                <p><strong>Insurable Hours:</strong> {{ roe.total_insurable_hours }}</p>
                <p><strong>Insurable Earnings:</strong> ${{ roe.total_insurable_earnings?.toLocaleString() }}</p>
              </div>
              
              <div class="roe-actions">
                <button @click="editROE(roe)" class="btn btn-sm btn-outline-primary">
                  <i class="fas fa-edit"></i> Edit
                </button>
                <button 
                  v-if="roe.roe_status === 'completed'"
                  @click="submitROE(roe.roe_id)" 
                  class="btn btn-sm btn-success"
                >
                  <i class="fas fa-paper-plane"></i> Submit to CRA
                </button>
                <button @click="printROE(roe.roe_id)" class="btn btn-sm btn-outline-secondary">
                  <i class="fas fa-print"></i> Print
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- End of Employment Tab -->
      <div v-if="activeTab === 'termination'" class="tab-content">
        <div class="termination-list">
          <div v-for="termination in endOfEmploymentCases" :key="termination.processing_id" class="termination-card">
            <div class="termination-header">
              <h4>{{ termination.employee_name }}</h4>
              <span :class="['status-badge', `status-${termination.processing_status}`]">
                {{ formatTerminationStatus(termination.processing_status) }}
              </span>
            </div>
            
            <div class="termination-details">
              <div class="termination-info">
                <p><strong>Termination Date:</strong> {{ formatDate(termination.termination_date) }}</p>
                <p><strong>Type:</strong> {{ formatTerminationType(termination.termination_type) }}</p>
                <p><strong>Final Pay:</strong> ${{ termination.total_net_final_pay?.toLocaleString() }}</p>
                <p><strong>Vacation Payout:</strong> ${{ termination.vacation_payout_amount?.toLocaleString() }}</p>
              </div>
              
              <div class="termination-checklist">
                <div class="checklist-item">
                  <i :class="['fas', termination.final_pay_processed ? 'fa-check-circle text-success' : 'fa-clock text-warning']"></i>
                  Final Pay
                </div>
                <div class="checklist-item">
                  <i :class="['fas', termination.roe_generated ? 'fa-check-circle text-success' : 'fa-clock text-warning']"></i>
                  ROE Generated
                </div>
                <div class="checklist-item">
                  <i :class="['fas', termination.t4_generated ? 'fa-check-circle text-success' : 'fa-clock text-warning']"></i>
                  T4 Slip
                </div>
                <div class="checklist-item">
                  <i :class="['fas', termination.benefits_terminated ? 'fa-check-circle text-success' : 'fa-clock text-warning']"></i>
                  Benefits Terminated
                </div>
              </div>
              
              <div class="termination-actions">
                <button @click="processTermination(termination)" class="btn btn-sm btn-primary">
                  <i class="fas fa-cog"></i> Process
                </button>
                <button @click="viewTerminationDetails(termination)" class="btn btn-sm btn-outline-info">
                  <i class="fas fa-eye"></i> Details
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Create ROE Modal -->
    <div v-if="showCreateROE" class="modal-overlay" @click="closeModals">
      <div class="modal-content roe-modal" @click.stop>
        <div class="modal-header">
          <h3>Create ROE for Employee</h3>
          <button @click="closeModals" class="close-btn">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <form @submit.prevent="createROEForEmployee" class="roe-form">
          <div class="form-section">
            <h4>Employee Selection</h4>
            <div class="form-row">
              <div class="form-group full-width">
                <label>Employee (All Types: Salary, Charter Drivers, Part-time)</label>
                <select v-model="roeForm.employee_id" required @change="loadEmployeeDetails">
                  <option value="">Select Employee</option>
                  <option 
                    v-for="employee in allEmployees" 
                    :key="employee.employee_id"
                    :value="employee.employee_id"
                  >
                    {{ employee.full_name }} - {{ employee.employment_type }} ({{ employee.position }})
                  </option>
                </select>
              </div>
            </div>
            
            <div v-if="selectedEmployeeDetails" class="employee-preview">
              <h5>Employee Details:</h5>
              <div class="detail-grid">
                <div><strong>Name:</strong> {{ selectedEmployeeDetails.full_name }}</div>
                <div><strong>Position:</strong> {{ selectedEmployeeDetails.position }}</div>
                <div><strong>Employment Type:</strong> {{ selectedEmployeeDetails.employment_type }}</div>
                <div><strong>Hire Date:</strong> {{ formatDate(selectedEmployeeDetails.hire_date) }}</div>
                <div><strong>Status:</strong> {{ selectedEmployeeDetails.status }}</div>
                <div><strong>Avg Earnings:</strong> ${{ selectedEmployeeDetails.avg_earnings?.toLocaleString() }}</div>
              </div>
            </div>
          </div>

          <div class="form-section">
            <h4>Termination Information</h4>
            <div class="form-row">
              <div class="form-group">
                <label>Termination Date</label>
                <input type="date" v-model="roeForm.termination_date" required>
              </div>
              
              <div class="form-group">
                <label>Reason Code</label>
                <select v-model="roeForm.reason_code" required>
                  <option value="A">A - Shortage of work (layoff)</option>
                  <option value="E">E - Quit</option>
                  <option value="M">M - Dismissal</option>
                  <option value="N">N - Leave of absence</option>
                  <option value="G">G - Retirement</option>
                  <option value="K">K - Other</option>
                </select>
              </div>
            </div>
            
            <div class="form-row">
              <div class="form-group full-width">
                <label>Reason Description</label>
                <textarea v-model="roeForm.reason_description" rows="3" placeholder="Detailed reason for employment termination..."></textarea>
              </div>
            </div>
          </div>

          <div class="form-actions">
            <button type="button" @click="closeModals" class="btn btn-secondary">Cancel</button>
            <button type="submit" class="btn btn-primary" :disabled="creatingROE">
              {{ creatingROE ? 'Creating...' : 'Create ROE' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Create Contract Modal -->
    <div v-if="showCreateContract" class="modal-overlay" @click="closeModals">
      <div class="modal-content contract-modal" @click.stop>
        <div class="modal-header">
          <h3>{{ editingContract ? 'Edit Employment Contract' : 'New Salary Employee Contract' }}</h3>
          <button @click="closeModals" class="close-btn">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <form @submit.prevent="saveContract" class="contract-form">
          <div class="form-section">
            <h4>Employee Information</h4>
            <div class="form-row">
              <div class="form-group">
                <label>Employee</label>
                <select v-model="contractForm.employee_id" required>
                  <option value="">Select Employee</option>
                  <option 
                    v-for="employee in availableEmployees" 
                    :key="employee.employee_id"
                    :value="employee.employee_id"
                  >
                    {{ employee.full_name }} - {{ employee.position }}
                  </option>
                </select>
              </div>
              
              <div class="form-group">
                <label>Position/Classification</label>
                <select v-model="contractForm.classification_type" required>
                  <option value="accountant">Accountant</option>
                  <option value="dispatcher">Dispatcher</option>
                  <option value="bookkeeper">Bookkeeper</option>
                  <option value="manager">Manager</option>
                  <option value="administrator">Administrator</option>
                </select>
              </div>
            </div>
          </div>

          <div class="form-section">
            <h4>Employment Period</h4>
            <div class="form-row">
              <div class="form-group">
                <label>Start Date</label>
                <input type="date" v-model="contractForm.employment_start_date" required>
              </div>
              
              <div class="form-group">
                <label>End Date (Optional)</label>
                <input type="date" v-model="contractForm.employment_end_date">
              </div>
              
              <div class="form-group">
                <label>Contract Type</label>
                <select v-model="contractForm.contract_type" required>
                  <option value="permanent">Permanent</option>
                  <option value="contract">Contract</option>
                  <option value="probation">Probation</option>
                  <option value="seasonal">Seasonal</option>
                </select>
              </div>
            </div>
          </div>

          <div class="form-section">
            <h4>Salary Information</h4>
            <div class="form-row">
              <div class="form-group">
                <label>Monthly Salary</label>
                <input 
                  type="number" 
                  step="0.01" 
                  v-model="contractForm.monthly_salary" 
                  required
                  @input="calculateAnnualSalary"
                >
              </div>
              
              <div class="form-group">
                <label>Annual Salary</label>
                <input 
                  type="number" 
                  step="0.01" 
                  v-model="contractForm.annual_salary" 
                  readonly
                >
              </div>
              
              <div class="form-group">
                <label>Pay Frequency</label>
                <select v-model="contractForm.pay_frequency">
                  <option value="monthly">Monthly</option>
                  <option value="bi_weekly">Bi-Weekly</option>
                  <option value="semi_monthly">Semi-Monthly</option>
                </select>
              </div>
            </div>
          </div>

          <div class="form-section">
            <h4>Benefits & Time Off</h4>
            <div class="form-row">
              <div class="form-group">
                <label>Vacation Days/Year</label>
                <input type="number" v-model="contractForm.vacation_days_per_year" min="0" max="30">
              </div>
              
              <div class="form-group">
                <label>Sick Days/Year</label>
                <input type="number" v-model="contractForm.sick_days_per_year" min="0" max="20">
              </div>
            </div>
            
            <div class="form-row">
              <div class="form-group checkbox-group">
                <label>
                  <input type="checkbox" v-model="contractForm.health_benefits">
                  Health Benefits
                </label>
              </div>
              
              <div class="form-group checkbox-group">
                <label>
                  <input type="checkbox" v-model="contractForm.dental_benefits">
                  Dental Benefits
                </label>
              </div>
            </div>
          </div>

          <div class="form-section">
            <h4>Payroll Settings</h4>
            <div class="form-row">
              <div class="form-group checkbox-group">
                <label>
                  <input type="checkbox" v-model="contractForm.auto_book_enabled">
                  Enable Automatic Monthly Payroll Generation
                </label>
              </div>
              
              <div class="form-group">
                <label>Booking Day of Month</label>
                <input 
                  type="number" 
                  v-model="contractForm.booking_day_of_month" 
                  min="1" 
                  max="28"
                  :disabled="!contractForm.auto_book_enabled"
                >
              </div>
            </div>
          </div>

          <div class="form-actions">
            <button type="button" @click="closeModals" class="btn btn-secondary">Cancel</button>
            <button type="submit" class="btn btn-primary">
              {{ editingContract ? 'Update Contract' : 'Create Contract' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ContinuousEmploymentManagement',
  data() {
    return {
      activeTab: 'contracts',
      showCreateContract: false,
      showCreateROE: false,
      editingContract: null,
      processingPayroll: false,
      creatingROE: false,
      
      // Data
      activeContracts: [],
      monthlyPayroll: [],
      roeRecords: [],
      endOfEmploymentCases: [],
      availableEmployees: [],
      allEmployees: [],
      selectedEmployeeDetails: null,
      
      // Form
      contractForm: this.getEmptyContractForm(),
      roeForm: this.getEmptyROEForm(),
      
      // Filters
      selectedPayPeriod: this.getCurrentPayPeriod(),
      payPeriods: this.generatePayPeriods()
    }
  },
  computed: {
    tabs() {
      return [
        {
          id: 'contracts',
          label: 'Active Contracts',
          icon: 'fas fa-file-contract',
          count: this.activeContracts.length
        },
        {
          id: 'payroll',
          label: 'Monthly Payroll',
          icon: 'fas fa-money-check',
          count: this.pendingPayrollApprovals
        },
        {
          id: 'roe',
          label: 'ROE Records',
          icon: 'fas fa-file-medical',
          count: this.pendingROEs
        },
        {
          id: 'termination',
          label: 'End of Employment',
          icon: 'fas fa-user-times',
          count: this.endOfEmploymentCases.length
        }
      ]
    },
    
    totalMonthlySalaries() {
      return this.activeContracts.reduce((total, contract) => {
        return total + parseFloat(contract.monthly_salary || 0)
      }, 0)
    },
    
    pendingPayrollApprovals() {
      return this.monthlyPayroll.filter(p => p.payroll_status === 'generated').length
    },
    
    pendingROEs() {
      return this.roeRecords.filter(r => r.roe_status === 'draft').length
    },
    
    hasUnapprovedPayroll() {
      return this.pendingPayrollApprovals > 0
    }
  },
  async mounted() {
    await this.loadData()
  },
  methods: {
    async loadData() {
      try {
        await Promise.all([
          this.loadActiveContracts(),
          this.loadPayrollData(),
          this.loadROERecords(),
          this.loadEndOfEmploymentCases(),
          this.loadAvailableEmployees(),
          this.loadAllEmployeesForROE()
        ])
      } catch (error) {
        console.error('Error loading data:', error)
        this.$toast.error('Failed to load employment data')
      }
    },
    
    async loadActiveContracts() {
      const response = await fetch('/api/continuous-employment/contracts/active')
      this.activeContracts = await response.json()
    },
    
    async loadPayrollData() {
      const response = await fetch(`/api/continuous-employment/payroll?period=${this.selectedPayPeriod}`)
      this.monthlyPayroll = await response.json()
    },
    
    async loadROERecords() {
      const response = await fetch('/api/continuous-employment/roe')
      this.roeRecords = await response.json()
    },
    
    async loadEndOfEmploymentCases() {
      const response = await fetch('/api/continuous-employment/terminations')
      this.endOfEmploymentCases = await response.json()
    },
    
    async loadAvailableEmployees() {
      const response = await fetch('/api/continuous-employment/employees/available-for-salary')
      this.availableEmployees = await response.json()
    },
    
    async loadAllEmployeesForROE() {
      const response = await fetch('/api/continuous-employment/employees/all-for-roe')
      this.allEmployees = await response.json()
    },
    
    // Contract Management
    editContract(contract) {
      this.editingContract = contract
      this.contractForm = { ...contract }
      this.showCreateContract = true
    },
    
    async saveContract() {
      try {
        const url = this.editingContract 
          ? `/api/continuous-employment/contracts/${this.editingContract.contract_id}`
          : '/api/continuous-employment/contracts'
        
        const method = this.editingContract ? 'PUT' : 'POST'
        
        const response = await fetch(url, {
          method: method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.contractForm)
        })
        
        if (response.ok) {
          this.$toast.success(`Contract ${this.editingContract ? 'updated' : 'created'} successfully`)
          this.closeModals()
          await this.loadActiveContracts()
        } else {
          throw new Error('Failed to save contract')
        }
      } catch (error) {
        console.error('Error saving contract:', error)
        this.$toast.error('Failed to save contract')
      }
    },
    
    // Payroll Management
    async runMonthlyPayroll() {
      if (!confirm('Generate monthly payroll for all active salary employees?')) return
      
      this.processingPayroll = true
      try {
        const response = await fetch('/api/continuous-employment/payroll/generate-monthly', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
        
        if (response.ok) {
          const result = await response.json()
          this.$toast.success(`Generated payroll for ${result.count} employees`)
          await this.loadPayrollData()
        } else {
          throw new Error('Failed to generate payroll')
        }
      } catch (error) {
        console.error('Error generating payroll:', error)
        this.$toast.error('Failed to generate monthly payroll')
      } finally {
        this.processingPayroll = false
      }
    },
    
    async approvePayroll(payrollId) {
      try {
        const response = await fetch(`/api/continuous-employment/payroll/${payrollId}/approve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
        
        if (response.ok) {
          this.$toast.success('Payroll approved')
          await this.loadPayrollData()
        } else {
          throw new Error('Failed to approve payroll')
        }
      } catch (error) {
        console.error('Error approving payroll:', error)
        this.$toast.error('Failed to approve payroll')
      }
    },
    
    async approveAllPayroll() {
      if (!confirm('Approve all pending payroll entries?')) return
      
      try {
        const response = await fetch('/api/continuous-employment/payroll/approve-all', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ period: this.selectedPayPeriod })
        })
        
        if (response.ok) {
          const result = await response.json()
          this.$toast.success(`Approved ${result.count} payroll entries`)
          await this.loadPayrollData()
        } else {
          throw new Error('Failed to approve all payroll')
        }
      } catch (error) {
        console.error('Error approving all payroll:', error)
        this.$toast.error('Failed to approve all payroll')
      }
    },
    
    // ROE Management
    async createROEForEmployee() {
      if (!this.roeForm.employee_id || !this.roeForm.termination_date) {
        this.$toast.error('Please select employee and termination date')
        return
      }
      
      this.creatingROE = true
      try {
        const response = await fetch('/api/continuous-employment/roe/create-for-any-employee', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.roeForm)
        })
        
        if (response.ok) {
          const result = await response.json()
          this.$toast.success(`ROE ${result.roe_number} created successfully`)
          this.closeModals()
          await this.loadROERecords()
        } else {
          const error = await response.json()
          throw new Error(error.error || 'Failed to create ROE')
        }
      } catch (error) {
        console.error('Error creating ROE:', error)
        this.$toast.error('Failed to create ROE: ' + error.message)
      } finally {
        this.creatingROE = false
      }
    },
    
    async loadEmployeeDetails() {
      if (this.roeForm.employee_id) {
        this.selectedEmployeeDetails = this.allEmployees.find(
          emp => emp.employee_id == this.roeForm.employee_id
        )
      } else {
        this.selectedEmployeeDetails = null
      }
    },

    // Employment Termination
    async terminateEmployment(contract) {
      if (!confirm(`Terminate employment for ${contract.employee_name}?`)) return
      
      try {
        const response = await fetch(`/api/continuous-employment/contracts/${contract.contract_id}/terminate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
        
        if (response.ok) {
          this.$toast.success('Employment termination process started')
          await this.loadData()
        } else {
          throw new Error('Failed to start termination process')
        }
      } catch (error) {
        console.error('Error terminating employment:', error)
        this.$toast.error('Failed to start termination process')
      }
    },
    
    // Helper Methods
    getEmptyContractForm() {
      return {
        employee_id: '',
        classification_type: '',
        employment_start_date: '',
        employment_end_date: '',
        contract_type: 'permanent',
        monthly_salary: '',
        annual_salary: '',
        pay_frequency: 'monthly',
        vacation_days_per_year: 10,
        sick_days_per_year: 5,
        health_benefits: false,
        dental_benefits: false,
        auto_book_enabled: true,
        booking_day_of_month: 1
      }
    },
    
    getEmptyROEForm() {
      return {
        employee_id: '',
        termination_date: '',
        reason_code: 'E',
        reason_description: ''
      }
    },
    
    calculateAnnualSalary() {
      if (this.contractForm.monthly_salary) {
        this.contractForm.annual_salary = (parseFloat(this.contractForm.monthly_salary) * 12).toFixed(2)
      }
    },
    
    getCurrentPayPeriod() {
      const now = new Date()
      return `${now.getFullYear()}-${(now.getMonth() + 1).toString().padStart(2, '0')}`
    },
    
    generatePayPeriods() {
      const periods = []
      const now = new Date()
      
      for (let i = 0; i < 12; i++) {
        const date = new Date(now.getFullYear(), now.getMonth() - i, 1)
        const value = `${date.getFullYear()}-${(date.getMonth() + 1).toString().padStart(2, '0')}`
        const label = date.toLocaleDateString('en-US', { year: 'numeric', month: 'long' })
        periods.push({ value, label })
      }
      
      return periods
    },
    
    formatDate(dateString) {
      if (!dateString) return 'N/A'
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    },
    
    formatDateTime(dateTimeString) {
      if (!dateTimeString) return 'N/A'
      return new Date(dateTimeString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    },
    
    formatContractType(type) {
      const types = {
        'permanent': 'Permanent',
        'contract': 'Contract',
        'probation': 'Probation',
        'seasonal': 'Seasonal'
      }
      return types[type] || type
    },
    
    formatPayrollStatus(status) {
      const statuses = {
        'generated': 'Pending Approval',
        'approved': 'Approved',
        'processed': 'Processed',
        'paid': 'Paid',
        'cancelled': 'Cancelled'
      }
      return statuses[status] || status
    },
    
    formatROEStatus(status) {
      const statuses = {
        'draft': 'Draft',
        'completed': 'Completed',
        'submitted': 'Submitted',
        'amended': 'Amended'
      }
      return statuses[status] || status
    },
    
    formatTerminationStatus(status) {
      const statuses = {
        'pending': 'Pending',
        'in_progress': 'In Progress',
        'completed': 'Completed'
      }
      return statuses[status] || status
    },
    
    formatTerminationType(type) {
      const types = {
        'voluntary': 'Voluntary Resignation',
        'involuntary': 'Involuntary Termination',
        'layoff': 'Layoff',
        'retirement': 'Retirement'
      }
      return types[type] || type
    },
    
    getNextPayrollDate(contract) {
      if (!contract.auto_book_enabled) return 'Manual'
      
      const now = new Date()
      const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, contract.booking_day_of_month)
      return this.formatDate(nextMonth.toISOString().split('T')[0])
    },
    
    closeModals() {
      this.showCreateContract = false
      this.showCreateROE = false
      this.editingContract = null
      this.selectedEmployeeDetails = null
      this.contractForm = this.getEmptyContractForm()
      this.roeForm = this.getEmptyROEForm()
    },
    
    // Placeholder methods for future implementation
    viewPayrollHistory(contract) {
      console.log('View payroll history for:', contract)
    },
    
    viewPayrollDetails(payroll) {
      console.log('View payroll details:', payroll)
    },
    
    editPayroll(payroll) {
      console.log('Edit payroll:', payroll)
    },
    
    editROE(roe) {
      console.log('Edit ROE:', roe)
    },
    
    submitROE(roeId) {
      console.log('Submit ROE to CRA:', roeId)
    },
    
    async printROE(roeId) {
      try {
        // Fetch detailed ROE data
        const response = await fetch(`/api/continuous-employment/roe/${roeId}`)
        if (!response.ok) {
          throw new Error('Failed to fetch ROE data')
        }
        
        const roeData = await response.json()
        
        // Open ROE print template in new window
        const printWindow = window.open('', '_blank', 'width=800,height=1000')
        
        // Create ROE print template component dynamically
        const roeTemplate = this.$vueApp.component('ROEPrintTemplate', () => import('./components/ROEPrintTemplate.vue'))
        
        // Generate the ROE HTML
        const roeHtml = this.generateROEHtml(roeData)
        
        printWindow.document.write(roeHtml)
        printWindow.document.close()
        
        // Auto-print after content loads
        printWindow.onload = () => {
          setTimeout(() => {
            printWindow.print()
          }, 500)
        }
        
      } catch (error) {
        console.error('Error printing ROE:', error)
        this.$toast.error('Failed to print ROE')
      }
    },
    
    generateROEHtml(roeData) {
      // Generate static HTML for ROE printing
      return `
        <!DOCTYPE html>
        <html>
        <head>
          <title>Record of Employment - ${roeData.roe_number}</title>
          <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; }
            .roe-container { max-width: 8.5in; margin: 0 auto; }
            .roe-header { border-bottom: 2px solid #000; padding-bottom: 15px; margin-bottom: 20px; }
            .roe-title { text-align: center; margin-bottom: 20px; }
            .roe-section { border: 1px solid #000; margin-bottom: 20px; }
            .section-title { background: #000; color: white; padding: 8px 12px; font-weight: bold; }
            .field-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; padding: 15px; }
            .field-group { display: flex; flex-direction: column; }
            .field-label { font-size: 9px; font-weight: bold; margin-bottom: 3px; color: #333; }
            .field-value { border: 1px solid #666; padding: 6px 8px; min-height: 20px; }
            .full-width { grid-column: 1 / -1; }
            .currency { text-align: right; font-weight: bold; }
            .date { text-align: center; font-family: monospace; }
            .sin { text-align: center; font-family: monospace; font-weight: bold; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; }
            th, td { border: 1px solid #666; padding: 6px 8px; text-align: left; font-size: 10px; }
            th { background: #f0f0f0; font-weight: bold; text-align: center; }
            .text-right { text-align: right; }
            @media print { body { margin: 0; } }
          </style>
        </head>
        <body>
          <div class="roe-container">
            <!-- ROE Header -->
            <div class="roe-header">
              <div class="roe-title">
                <h1>RECORD OF EMPLOYMENT</h1>
                <h2>RELEVÉ D'EMPLOI</h2>
                <div style="text-align: right; margin-top: 10px;">
                  <strong>ROE Number: ${roeData.roe_number}</strong>
                </div>
              </div>
            </div>

            <!-- Employer Information -->
            <div class="roe-section">
              <div class="section-title">EMPLOYER INFORMATION / RENSEIGNEMENTS SUR L'EMPLOYEUR</div>
              <div class="field-grid">
                <div class="field-group">
                  <div class="field-label">1. Business Number / Numéro d'entreprise</div>
                  <div class="field-value">123456789RC0001</div>
                </div>
                <div class="field-group">
                  <div class="field-label">2. Employer Name / Nom de l'employeur</div>
                  <div class="field-value">Arrow Limousine Service</div>
                </div>
                <div class="field-group full-width">
                  <div class="field-label">3. Address / Adresse</div>
                  <div class="field-value">1234 Business Street<br>Red Deer, AB T4N 1A1</div>
                </div>
                <div class="field-group">
                  <div class="field-label">4. Telephone / Téléphone</div>
                  <div class="field-value">(403) 555-0123</div>
                </div>
                <div class="field-group">
                  <div class="field-label">5. Email / Courriel</div>
                  <div class="field-value">info@arrowlimo.ca</div>
                </div>
              </div>
            </div>

            <!-- Employee Information -->
            <div class="roe-section">
              <div class="section-title">EMPLOYEE INFORMATION / RENSEIGNEMENTS SUR L'EMPLOYÉ(E)</div>
              <div class="field-grid">
                <div class="field-group">
                  <div class="field-label">6. Social Insurance Number / Numéro d'assurance sociale</div>
                  <div class="field-value sin">${this.formatSIN(roeData.employee_sin)}</div>
                </div>
                <div class="field-group">
                  <div class="field-label">7. Employee Number / Numéro d'employé(e)</div>
                  <div class="field-value">${roeData.employee_number || roeData.employee_id}</div>
                </div>
                <div class="field-group full-width">
                  <div class="field-label">8. Employee Name / Nom de l'employé(e)</div>
                  <div class="field-value">${roeData.employee_name}</div>
                </div>
                <div class="field-group full-width">
                  <div class="field-label">9. Employee Address / Adresse de l'employé(e)</div>
                  <div class="field-value">${roeData.employee_address || 'Address on File'}</div>
                </div>
              </div>
            </div>

            <!-- Employment Information -->
            <div class="roe-section">
              <div class="section-title">EMPLOYMENT INFORMATION / RENSEIGNEMENTS SUR L'EMPLOI</div>
              <div class="field-grid">
                <div class="field-group">
                  <div class="field-label">10. First Day Worked / Premier jour travaillé</div>
                  <div class="field-value date">${this.formatDateForPrint(roeData.first_day_worked)}</div>
                </div>
                <div class="field-group">
                  <div class="field-label">11. Last Day for Which Paid / Dernier jour payé</div>
                  <div class="field-value date">${this.formatDateForPrint(roeData.last_day_paid)}</div>
                </div>
                <div class="field-group">
                  <div class="field-label">12. Final Pay Period Ending Date / Date de fin de la dernière période de paie</div>
                  <div class="field-value date">${this.formatDateForPrint(roeData.final_pay_period_end)}</div>
                </div>
                <div class="field-group">
                  <div class="field-label">13. Pay Period Type / Type de période de paie</div>
                  <div class="field-value">${this.formatPayPeriodTypeForPrint(roeData.pay_period_type)}</div>
                </div>
              </div>
            </div>

            <!-- Reason for Issuing ROE -->
            <div class="roe-section">
              <div class="section-title">REASON FOR ISSUING THIS ROE / RAISON DE LA PRODUCTION DE CE RELEVÉ</div>
              <div class="field-grid">
                <div class="field-group">
                  <div class="field-label">14. Reason Code / Code de raison</div>
                  <div class="field-value" style="text-align: center; font-weight: bold; font-size: 14px; background: #f0f0f0;">${roeData.reason_code}</div>
                </div>
                <div class="field-group full-width">
                  <div class="field-label">15. Comments / Commentaires</div>
                  <div class="field-value">${roeData.reason_description}</div>
                </div>
              </div>
            </div>

            <!-- Earnings and Hours -->
            <div class="roe-section">
              <div class="section-title">EARNINGS AND HOURS / GAINS ET HEURES</div>
              <div class="field-grid">
                <div class="field-group">
                  <div class="field-label">16. Total Insurable Hours / Total des heures assurables</div>
                  <div class="field-value" style="text-align: right;">${roeData.total_insurable_hours || 0}</div>
                </div>
                <div class="field-group">
                  <div class="field-label">17. Total Insurable Earnings / Total des gains assurables</div>
                  <div class="field-value currency">$${this.formatCurrencyForPrint(roeData.total_insurable_earnings)}</div>
                </div>
              </div>

              <!-- Pay Periods Table -->
              <div style="margin-top: 20px;">
                <div style="background: #333; color: white; padding: 6px 12px; font-weight: bold; text-align: center;">
                  PAY PERIOD DETAILS / DÉTAILS DES PÉRIODES DE PAIE
                </div>
                <table>
                  <thead>
                    <tr>
                      <th>Period / Période</th>
                      <th>From / Du</th>
                      <th>To / Au</th>
                      <th>Insurable Hours / Heures assurables</th>
                      <th>Insurable Earnings / Gains assurables</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${this.generatePayPeriodsTable(roeData.pay_periods)}
                  </tbody>
                </table>
              </div>
            </div>

            <!-- Additional Information -->
            <div class="roe-section">
              <div class="section-title">ADDITIONAL INFORMATION / RENSEIGNEMENTS SUPPLÉMENTAIRES</div>
              <div class="field-grid">
                <div class="field-group">
                  <div class="field-label">18. Vacation Pay / Paie de vacances</div>
                  <div class="field-value currency">$${this.formatCurrencyForPrint(roeData.vacation_pay)}</div>
                </div>
                <div class="field-group">
                  <div class="field-label">19. Statutory Holiday Pay / Paie de congé férié</div>
                  <div class="field-value currency">$${this.formatCurrencyForPrint(roeData.statutory_holiday_pay)}</div>
                </div>
                <div class="field-group">
                  <div class="field-label">20. Other Monies / Autres sommes</div>
                  <div class="field-value currency">$${this.formatCurrencyForPrint(roeData.other_monies)}</div>
                </div>
                <div class="field-group full-width">
                  <div class="field-label">21. Expected Date of Recall / Date prévue de rappel</div>
                  <div class="field-value date">${this.formatDateForPrint(roeData.expected_recall_date)}</div>
                </div>
              </div>
            </div>

            <!-- Certification -->
            <div class="roe-section">
              <div class="section-title">CERTIFICATION / ATTESTATION</div>
              <div class="field-grid">
                <div class="field-group">
                  <div class="field-label">22. Name of Person Completing ROE / Nom de la personne qui remplit le relevé</div>
                  <div class="field-value">${roeData.completed_by_name || 'Human Resources'}</div>
                </div>
                <div class="field-group">
                  <div class="field-label">23. Title / Titre</div>
                  <div class="field-value">${roeData.completed_by_title || 'HR Manager'}</div>
                </div>
                <div class="field-group">
                  <div class="field-label">24. Telephone / Téléphone</div>
                  <div class="field-value">(403) 555-0123</div>
                </div>
                <div class="field-group">
                  <div class="field-label">25. Date Completed / Date de production</div>
                  <div class="field-value date">${this.formatDateForPrint(roeData.completed_date || new Date())}</div>
                </div>
                <div class="field-group full-width">
                  <div class="field-label">26. Signature</div>
                  <div class="field-value" style="height: 40px; border-bottom: 1px solid #000; border-left: none; border-right: none; border-top: none;"></div>
                </div>
              </div>
            </div>

            <!-- Footer -->
            <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #ccc;">
              <div style="background: #fff3cd; border: 1px solid #ffc107; padding: 10px; margin-bottom: 15px; font-size: 10px;">
                <p><strong>IMPORTANT:</strong> This Record of Employment must be given to the employee immediately upon interruption of earnings.</p>
                <p><strong>IMPORTANT :</strong> Ce relevé d'emploi doit être remis à l'employé(e) immédiatement dès l'interruption de rémunération.</p>
              </div>
              <div style="display: flex; justify-content: space-between; font-size: 10px; color: #666;">
                <div><strong>Status:</strong> ${this.formatROEStatusForPrint(roeData.roe_status)}</div>
                <div>ROE Form Version: ${new Date().getFullYear()}.1</div>
              </div>
            </div>
          </div>
        </body>
        </html>
      `
    },
    
    formatSIN(sin) {
      if (!sin) return '___-___-___'
      const digits = sin.replace(/\D/g, '')
      if (digits.length !== 9) return '___-___-___'
      return `${digits.slice(0,3)}-${digits.slice(3,6)}-${digits.slice(6,9)}`
    },
    
    formatDateForPrint(dateString) {
      if (!dateString) return ''
      const date = new Date(dateString)
      return date.toLocaleDateString('en-CA', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      })
    },
    
    formatCurrencyForPrint(amount) {
      if (!amount) return '0.00'
      return parseFloat(amount).toLocaleString('en-CA', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })
    },
    
    formatPayPeriodTypeForPrint(type) {
      const types = {
        'weekly': 'Weekly / Hebdomadaire',
        'bi_weekly': 'Bi-weekly / Aux deux semaines',
        'semi_monthly': 'Semi-monthly / Bimensuel',
        'monthly': 'Monthly / Mensuel'
      }
      return types[type] || type
    },
    
    formatROEStatusForPrint(status) {
      const statuses = {
        'draft': 'Draft',
        'completed': 'Completed',
        'submitted': 'Submitted to Service Canada',
        'amended': 'Amended'
      }
      return statuses[status] || status
    },
    
    generatePayPeriodsTable(payPeriods) {
      let tableRows = ''
      const periods = payPeriods || []
      
      // Show up to 6 pay periods (standard ROE requirement)
      for (let i = 0; i < 6; i++) {
        if (i < periods.length) {
          const period = periods[i]
          tableRows += `
            <tr>
              <td>${i + 1}</td>
              <td>${this.formatDateForPrint(period.period_start)}</td>
              <td>${this.formatDateForPrint(period.period_end)}</td>
              <td class="text-right">${period.insurable_hours || 0}</td>
              <td class="text-right">$${this.formatCurrencyForPrint(period.insurable_earnings)}</td>
            </tr>
          `
        } else {
          tableRows += `
            <tr style="height: 25px; background: #fafafa;">
              <td>${i + 1}</td>
              <td></td>
              <td></td>
              <td></td>
              <td></td>
            </tr>
          `
        }
      }
      
      return tableRows
    },
    
    processTermination(termination) {
      console.log('Process termination:', termination)
    },
    
    viewTerminationDetails(termination) {
      console.log('View termination details:', termination)
    }
  }
}
</script>

<style scoped>
.continuous-employment-management {
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  display: flex;
  align-items: center;
  gap: 15px;
}

.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: #007bff;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 1.5rem;
}

.stat-content h3 {
  margin: 0;
  font-size: 1.8rem;
  color: #2c3e50;
}

.stat-content p {
  margin: 5px 0 0 0;
  color: #6c757d;
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

.table {
  width: 100%;
  border-collapse: collapse;
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
}

.employee-info strong {
  color: #2c3e50;
}

.employee-details {
  font-size: 0.8rem;
  color: #6c757d;
}

.salary-amount {
  font-weight: 600;
  color: #28a745;
}

.amount {
  font-weight: 600;
  text-align: right;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.status-badge.enabled {
  background: #d4edda;
  color: #155724;
}

.status-badge.disabled {
  background: #f8d7da;
  color: #721c24;
}

.status-badge.status-generated {
  background: #fff3cd;
  color: #856404;
}

.status-badge.status-approved {
  background: #d4edda;
  color: #155724;
}

.status-badge.status-processed {
  background: #cce7ff;
  color: #004085;
}

.status-badge.status-paid {
  background: #d1ecf1;
  color: #0c5460;
}

.action-buttons {
  display: flex;
  gap: 5px;
}

.payroll-controls,
.roe-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 6px;
}

.period-selector {
  display: flex;
  align-items: center;
  gap: 10px;
}

.period-selector label {
  font-weight: 600;
  color: #495057;
}

.period-selector select {
  padding: 8px 12px;
  border: 1px solid #ced4da;
  border-radius: 4px;
}

.roe-card,
.termination-card {
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  background: #f8f9fa;
}

.roe-header,
.termination-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.roe-number strong {
  font-size: 1.2rem;
  color: #2c3e50;
}

.roe-details,
.termination-details {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 20px;
  align-items: start;
}

.roe-info h4,
.termination-info {
  margin: 0 0 10px 0;
  color: #2c3e50;
}

.termination-checklist {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.checklist-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.9rem;
}

.roe-actions,
.termination-actions {
  display: flex;
  flex-direction: column;
  gap: 10px;
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

.modal-content.contract-modal,
.modal-content.roe-modal {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 800px;
  max-height: 90vh;
  overflow-y: auto;
}

.employee-preview {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 15px;
  margin-top: 15px;
}

.employee-preview h5 {
  margin: 0 0 10px 0;
  color: #495057;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 10px;
  font-size: 0.9rem;
}

.detail-grid div {
  padding: 5px 0;
}

.detail-grid strong {
  color: #2c3e50;
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

.contract-form {
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

.form-group label {
  font-weight: 600;
  margin-bottom: 5px;
  color: #495057;
}

.form-group input,
.form-group select {
  padding: 8px 12px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 0.9rem;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 2px rgba(0,123,255,0.25);
}

.checkbox-group {
  flex-direction: row;
  align-items: center;
}

.checkbox-group label {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 0;
  cursor: pointer;
}

.checkbox-group input[type="checkbox"] {
  width: auto;
  margin: 0;
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
  }
  
  .stats-grid {
    grid-template-columns: 1fr;
  }
  
  .tab-headers {
    flex-wrap: wrap;
  }
  
  .form-row {
    grid-template-columns: 1fr;
  }
  
  .roe-details,
  .termination-details {
    grid-template-columns: 1fr;
  }
  
  .roe-actions,
  .termination-actions {
    flex-direction: row;
    justify-content: center;
  }
}
</style>