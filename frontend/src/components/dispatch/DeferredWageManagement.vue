<!--
  Deferred Wage & Owner Equity Management Component
  Purpose: Manage deferred wages, owner expenses, and equity tracking
  Created: October 21, 2025
  
  Features:
  - Deferred wage accounts (Michael Richard, other employees)
  - Owner expense tracking (Paul's CIBC business card)
  - Wage allocation pools and decisions
  - T4 compliance corrections (2013 owner salary issue)
-->
<template>
  <div class="deferred-wage-management">
    <!-- Header Section -->
    <div class="management-header">
      <h2>Deferred Wage & Owner Equity Management</h2>
      <div class="header-actions">
        <button @click="showCreateDeferredAccount = true" class="btn btn-success">
          <i class="fas fa-piggy-bank"></i> New Deferred Account
        </button>
        <button @click="showOwnerExpenseEntry = true" class="btn btn-primary">
          <i class="fas fa-credit-card"></i> Owner Expense Entry
        </button>
        <button @click="showAllocationPool = true" class="btn btn-info">
          <i class="fas fa-coins"></i> Allocation Pool
        </button>
      </div>
    </div>

    <!-- Key Metrics Dashboard -->
    <div class="metrics-grid">
      <div class="metric-card total-deferred">
        <div class="metric-icon">
          <i class="fas fa-clock"></i>
        </div>
        <div class="metric-content">
          <h3>${{ totalDeferredBalance.toLocaleString() }}</h3>
          <p>Total Deferred Wages</p>
          <small>{{ activeDeferredAccounts }} active accounts</small>
        </div>
      </div>
      
      <div class="metric-card owner-equity">
        <div class="metric-icon">
          <i class="fas fa-user-tie"></i>
        </div>
        <div class="metric-content">
          <h3>${{ ownerEquityBalance.toLocaleString() }}</h3>
          <p>Owner Equity Balance</p>
          <small>Business vs Personal</small>
        </div>
      </div>
      
      <div class="metric-card allocation-pool">
        <div class="metric-icon">
          <i class="fas fa-swimming-pool"></i>
        </div>
        <div class="metric-content">
          <h3>${{ availableAllocationFunds.toLocaleString() }}</h3>
          <p>Available Allocation Funds</p>
          <small>{{ activeAllocationPools }} active pools</small>
        </div>
      </div>
      
      <div class="metric-card t4-corrections">
        <div class="metric-icon">
          <i class="fas fa-file-medical"></i>
        </div>
        <div class="metric-content">
          <h3>{{ pendingT4Corrections }}</h3>
          <p>Pending T4 Corrections</p>
          <small>Including 2013 owner salary</small>
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

      <!-- Deferred Wage Accounts Tab -->
      <div v-if="activeTab === 'deferred'" class="tab-content">
        <div class="deferred-accounts-list">
          <div v-for="account in deferredAccounts" :key="account.account_id" class="deferred-account-card">
            <div class="account-header">
              <div class="account-info">
                <h4>{{ account.employee_name }}</h4>
                <span class="account-type">{{ formatAccountType(account.account_type) }}</span>
              </div>
              <div class="account-balance">
                <span class="balance-amount">${{ account.current_balance.toLocaleString() }}</span>
                <span class="balance-label">Current Balance</span>
              </div>
            </div>
            
            <div class="account-details">
              <div class="detail-grid">
                <div class="detail-item">
                  <label>YTD Deferred:</label>
                  <span>${{ account.ytd_deferred_amount.toLocaleString() }}</span>
                </div>
                <div class="detail-item">
                  <label>YTD Paid:</label>
                  <span>${{ account.ytd_paid_amount.toLocaleString() }}</span>
                </div>
                <div class="detail-item">
                  <label>Lifetime Total:</label>
                  <span>${{ account.lifetime_deferred.toLocaleString() }}</span>
                </div>
                <div class="detail-item">
                  <label>Interest:</label>
                  <span>${{ account.accumulated_interest.toLocaleString() }}</span>
                </div>
              </div>
              
              <div class="account-actions">
                <button @click="addDeferredTransaction(account)" class="btn btn-sm btn-primary">
                  <i class="fas fa-plus"></i> Add Transaction
                </button>
                <button @click="makeDeferredPayment(account)" class="btn btn-sm btn-success">
                  <i class="fas fa-dollar-sign"></i> Make Payment
                </button>
                <button @click="viewTransactionHistory(account)" class="btn btn-sm btn-outline-info">
                  <i class="fas fa-history"></i> History
                </button>
                <button @click="editAccount(account)" class="btn btn-sm btn-outline-secondary">
                  <i class="fas fa-edit"></i> Edit
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Owner Equity Tab -->
      <div v-if="activeTab === 'owner'" class="tab-content">
        <div class="owner-equity-dashboard">
          <!-- Paul's Expense Summary -->
          <div class="owner-summary-card">
            <h3>Paul Heffner - Owner Equity Summary</h3>
            <div class="equity-grid">
              <div class="equity-item business">
                <div class="equity-icon">
                  <i class="fas fa-briefcase"></i>
                </div>
                <div class="equity-details">
                  <h4>${{ ownerBusinessExpenses.toLocaleString() }}</h4>
                  <p>Business Expenses (YTD)</p>
                  <small>CIBC Business Card</small>
                </div>
              </div>
              
              <div class="equity-item personal">
                <div class="equity-icon">
                  <i class="fas fa-home"></i>
                </div>
                <div class="equity-details">
                  <h4>${{ ownerPersonalAllocation.toLocaleString() }}</h4>
                  <p>Personal Allocation (YTD)</p>
                  <small>Considered Income</small>
                </div>
              </div>
              
              <div class="equity-item salary">
                <div class="equity-icon">
                  <i class="fas fa-calculator"></i>
                </div>
                <div class="equity-details">
                  <h4>${{ ownerSalaryEquivalent.toLocaleString() }}</h4>
                  <p>Salary Equivalent</p>
                  <small>For T4 Reference</small>
                </div>
              </div>
            </div>
          </div>

          <!-- Recent Owner Transactions -->
          <div class="owner-transactions">
            <div class="section-header">
              <h4>Recent Owner Transactions</h4>
              <button @click="showOwnerExpenseEntry = true" class="btn btn-sm btn-primary">
                <i class="fas fa-plus"></i> Add Expense
              </button>
            </div>
            
            <div class="transactions-table">
              <table class="table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Description</th>
                    <th>Type</th>
                    <th>Business Amount</th>
                    <th>Personal Amount</th>
                    <th>Card Used</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="transaction in ownerTransactions" :key="transaction.transaction_id">
                    <td>{{ formatDate(transaction.transaction_date) }}</td>
                    <td>
                      <div class="transaction-desc">
                        <strong>{{ transaction.description }}</strong>
                        <div class="vendor">{{ transaction.vendor_name }}</div>
                      </div>
                    </td>
                    <td>
                      <span :class="['type-badge', `type-${transaction.transaction_type}`]">
                        {{ formatTransactionType(transaction.transaction_type) }}
                      </span>
                    </td>
                    <td class="amount">${{ transaction.business_portion.toLocaleString() }}</td>
                    <td class="amount">${{ transaction.personal_portion.toLocaleString() }}</td>
                    <td>{{ transaction.card_used || 'N/A' }}</td>
                    <td>
                      <span :class="['status-badge', transaction.approved_by ? 'approved' : 'pending']">
                        {{ transaction.approved_by ? 'Approved' : 'Pending' }}
                      </span>
                    </td>
                    <td>
                      <div class="action-buttons">
                        <button 
                          v-if="!transaction.approved_by"
                          @click="approveOwnerTransaction(transaction)" 
                          class="btn btn-xs btn-success"
                        >
                          <i class="fas fa-check"></i>
                        </button>
                        <button @click="editOwnerTransaction(transaction)" class="btn btn-xs btn-outline-primary">
                          <i class="fas fa-edit"></i>
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>

      <!-- Allocation Pools Tab -->
      <div v-if="activeTab === 'pools'" class="tab-content">
        <div class="allocation-pools">
          <div v-for="pool in allocationPools" :key="pool.pool_id" class="pool-card">
            <div class="pool-header">
              <div class="pool-info">
                <h4>{{ pool.pool_name }}</h4>
                <span class="pool-type">{{ formatPoolType(pool.pool_type) }}</span>
              </div>
              <div class="pool-status">
                <span :class="['status-badge', `status-${pool.pool_status}`]">
                  {{ formatPoolStatus(pool.pool_status) }}
                </span>
              </div>
            </div>
            
            <div class="pool-progress">
              <div class="progress-bar">
                <div 
                  class="progress-fill" 
                  :style="{ width: getPoolProgressPercentage(pool) + '%' }"
                ></div>
              </div>
              <div class="progress-labels">
                <span>Allocated: ${{ pool.allocated_amount.toLocaleString() }}</span>
                <span>Remaining: ${{ pool.remaining_balance.toLocaleString() }}</span>
                <span>Total: ${{ pool.total_available.toLocaleString() }}</span>
              </div>
            </div>
            
            <div class="pool-details">
              <div class="detail-grid">
                <div class="detail-item">
                  <label>Period:</label>
                  <span>{{ formatDate(pool.allocation_period_start) }} - {{ formatDate(pool.allocation_period_end) }}</span>
                </div>
                <div class="detail-item">
                  <label>Frequency:</label>
                  <span>{{ pool.allocation_frequency }}</span>
                </div>
                <div class="detail-item">
                  <label>Employees:</label>
                  <span>{{ pool.employees_allocated }} allocated</span>
                </div>
                <div class="detail-item">
                  <label>Allocations:</label>
                  <span>{{ pool.total_allocations }} decisions</span>
                </div>
              </div>
              
              <div class="pool-actions">
                <button @click="makeAllocation(pool)" class="btn btn-sm btn-primary">
                  <i class="fas fa-hand-holding-usd"></i> Make Allocation
                </button>
                <button @click="viewAllocationHistory(pool)" class="btn btn-sm btn-outline-info">
                  <i class="fas fa-list"></i> View Allocations
                </button>
                <button @click="addFundsToPool(pool)" class="btn btn-sm btn-outline-success">
                  <i class="fas fa-plus-circle"></i> Add Funds
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- T4 Corrections Tab -->
      <div v-if="activeTab === 't4'" class="tab-content">
        <div class="t4-corrections">
          <div class="correction-alert" v-if="has2013Correction">
            <div class="alert alert-warning">
              <i class="fas fa-exclamation-triangle"></i>
              <strong>2013 T4 Correction Required:</strong>
              Paul Heffner received a T4 in 2013 but should not have, as he operates on the salary equity system.
            </div>
          </div>
          
          <div v-for="correction in t4Corrections" :key="correction.correction_id" class="correction-card">
            <div class="correction-header">
              <div class="correction-info">
                <h4>{{ correction.employee_name }} - {{ correction.tax_year }}</h4>
                <span class="correction-type">{{ formatCorrectionType(correction.correction_type) }}</span>
              </div>
              <div class="correction-status">
                <span :class="['status-badge', `status-${correction.correction_status}`]">
                  {{ formatCorrectionStatus(correction.correction_status) }}
                </span>
              </div>
            </div>
            
            <div class="correction-details">
              <div class="amounts-comparison">
                <div class="original-amounts">
                  <h5>Original T4</h5>
                  <div class="amount-grid">
                    <div>Employment Income: ${{ correction.original_employment_income?.toLocaleString() || '0' }}</div>
                    <div>CPP Contributions: ${{ correction.original_cpp_contributions?.toLocaleString() || '0' }}</div>
                    <div>EI Contributions: ${{ correction.original_ei_contributions?.toLocaleString() || '0' }}</div>
                    <div>Income Tax: ${{ correction.original_income_tax?.toLocaleString() || '0' }}</div>
                  </div>
                </div>
                
                <div class="corrected-amounts">
                  <h5>Corrected T4</h5>
                  <div class="amount-grid">
                    <div>Employment Income: ${{ correction.corrected_employment_income?.toLocaleString() || '0' }}</div>
                    <div>CPP Contributions: ${{ correction.corrected_cpp_contributions?.toLocaleString() || '0' }}</div>
                    <div>EI Contributions: ${{ correction.corrected_ei_contributions?.toLocaleString() || '0' }}</div>
                    <div>Income Tax: ${{ correction.corrected_income_tax?.toLocaleString() || '0' }}</div>
                  </div>
                </div>
              </div>
              
              <div class="correction-reason">
                <strong>Reason:</strong> {{ correction.correction_reason }}
              </div>
              
              <div class="correction-actions">
                <button @click="editCorrection(correction)" class="btn btn-sm btn-primary">
                  <i class="fas fa-edit"></i> Edit Correction
                </button>
                <button 
                  v-if="correction.correction_status === 'pending'"
                  @click="fileCorrection(correction)" 
                  class="btn btn-sm btn-success"
                >
                  <i class="fas fa-paper-plane"></i> File with CRA
                </button>
                <button @click="viewCorrectionDetails(correction)" class="btn btn-sm btn-outline-info">
                  <i class="fas fa-eye"></i> Details
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Create Deferred Account Modal -->
    <div v-if="showCreateDeferredAccount" class="modal-overlay" @click="closeModals">
      <div class="modal-content deferred-modal" @click.stop>
        <div class="modal-header">
          <h3>Create Deferred Wage Account</h3>
          <button @click="closeModals" class="close-btn">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <form @submit.prevent="createDeferredAccount" class="deferred-form">
          <div class="form-section">
            <h4>Employee & Account Information</h4>
            <div class="form-row">
              <div class="form-group">
                <label>Employee</label>
                <select v-model="deferredForm.employee_id" required>
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
                <label>Account Name</label>
                <input 
                  type="text" 
                  v-model="deferredForm.account_name" 
                  placeholder="e.g., John Doe Deferred Wages"
                  required
                >
              </div>
            </div>
          </div>

          <div class="form-section">
            <h4>Account Settings</h4>
            <div class="form-row">
              <div class="form-group">
                <label>Maximum Deferred Amount</label>
                <input 
                  type="number" 
                  step="0.01" 
                  v-model="deferredForm.max_deferred_amount"
                  placeholder="50000.00"
                >
              </div>
              
              <div class="form-group">
                <label>Interest Rate (%)</label>
                <input 
                  type="number" 
                  step="0.01" 
                  v-model="deferredForm.interest_rate"
                  placeholder="0.00"
                >
              </div>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label>Payment Frequency</label>
                <select v-model="deferredForm.minimum_payment_frequency">
                  <option value="weekly">Weekly</option>
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                </select>
              </div>
              
              <div class="form-group checkbox-group">
                <label>
                  <input type="checkbox" v-model="deferredForm.auto_payment_enabled">
                  Enable Auto-Payment
                </label>
              </div>
            </div>
            
            <div v-if="deferredForm.auto_payment_enabled" class="form-row">
              <div class="form-group">
                <label>Auto-Payment Amount</label>
                <input 
                  type="number" 
                  step="0.01" 
                  v-model="deferredForm.auto_payment_amount"
                  placeholder="500.00"
                >
              </div>
            </div>
          </div>

          <div class="form-actions">
            <button type="button" @click="closeModals" class="btn btn-secondary">Cancel</button>
            <button type="submit" class="btn btn-primary">Create Account</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Owner Expense Entry Modal -->
    <div v-if="showOwnerExpenseEntry" class="modal-overlay" @click="closeModals">
      <div class="modal-content expense-modal" @click.stop>
        <div class="modal-header">
          <h3>Owner Expense Entry - CIBC Business Card</h3>
          <button @click="closeModals" class="close-btn">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <form @submit.prevent="createOwnerExpense" class="expense-form">
          <div class="form-section">
            <h4>Transaction Details</h4>
            <div class="form-row">
              <div class="form-group">
                <label>Transaction Date</label>
                <input type="date" v-model="expenseForm.transaction_date" required>
              </div>
              
              <div class="form-group">
                <label>Gross Amount</label>
                <input 
                  type="number" 
                  step="0.01" 
                  v-model="expenseForm.gross_amount" 
                  @input="calculatePortions"
                  required
                >
              </div>
            </div>
            
            <div class="form-row">
              <div class="form-group full-width">
                <label>Description</label>
                <input 
                  type="text" 
                  v-model="expenseForm.description" 
                  placeholder="Fuel, meals, equipment, etc."
                  required
                >
              </div>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label>Vendor/Merchant</label>
                <input 
                  type="text" 
                  v-model="expenseForm.vendor_name" 
                  placeholder="Shell, Restaurant, etc."
                >
              </div>
              
              <div class="form-group">
                <label>Expense Category</label>
                <select v-model="expenseForm.expense_category">
                  <option value="fuel">Fuel</option>
                  <option value="meals">Meals & Entertainment</option>
                  <option value="equipment">Equipment</option>
                  <option value="office">Office Supplies</option>
                  <option value="maintenance">Vehicle Maintenance</option>
                  <option value="personal_draw">Personal Draw</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>
          </div>

          <div class="form-section">
            <h4>Business vs Personal Allocation</h4>
            <div class="allocation-slider">
              <div class="slider-container">
                <label>Business Percentage:</label>
                <input 
                  type="range" 
                  min="0" 
                  max="100" 
                  v-model="businessPercentage"
                  @input="calculatePortions"
                  class="slider"
                >
                <span class="percentage-display">{{ businessPercentage }}%</span>
              </div>
              
              <div class="portion-display">
                <div class="business-portion">
                  <label>Business Deductible:</label>
                  <span class="amount">${{ businessAmount.toFixed(2) }}</span>
                </div>
                <div class="personal-portion">
                  <label>Personal Income:</label>
                  <span class="amount">${{ personalAmount.toFixed(2) }}</span>
                </div>
              </div>
            </div>
          </div>

          <div class="form-section">
            <h4>Card & Reference Information</h4>
            <div class="form-row">
              <div class="form-group">
                <label>CIBC Card Used</label>
                <select v-model="expenseForm.card_used">
                  <option value="**** **** **** 1234">Main Business Card (**** 1234)</option>
                  <option value="**** **** **** 5678">Fuel Card (**** 5678)</option>
                  <option value="other">Other</option>
                </select>
              </div>
              
              <div class="form-group">
                <label>Receipt Reference</label>
                <input 
                  type="text" 
                  v-model="expenseForm.receipt_reference" 
                  placeholder="Receipt number or reference"
                >
              </div>
            </div>
          </div>

          <div class="form-actions">
            <button type="button" @click="closeModals" class="btn btn-secondary">Cancel</button>
            <button type="submit" class="btn btn-primary">Record Expense</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DeferredWageManagement',
  data() {
    return {
      activeTab: 'deferred',
      showCreateDeferredAccount: false,
      showOwnerExpenseEntry: false,
      showAllocationPool: false,
      
      // Data
      deferredAccounts: [],
      ownerTransactions: [],
      allocationPools: [],
      t4Corrections: [],
      availableEmployees: [],
      
      // Metrics
      totalDeferredBalance: 0,
      ownerEquityBalance: 0,
      availableAllocationFunds: 0,
      ownerBusinessExpenses: 0,
      ownerPersonalAllocation: 0,
      ownerSalaryEquivalent: 0,
      
      // Forms
      deferredForm: this.getEmptyDeferredForm(),
      expenseForm: this.getEmptyExpenseForm(),
      businessPercentage: 100,
      
      // Quick access for special accounts
      michaelRichardAccount: null,
      paulHeffnerCorrection: null
    }
  },
  computed: {
    tabs() {
      return [
        {
          id: 'deferred',
          label: 'Deferred Wages',
          icon: 'fas fa-clock',
          count: this.activeDeferredAccounts
        },
        {
          id: 'owner',
          label: 'Owner Equity',
          icon: 'fas fa-user-tie',
          count: this.ownerTransactions.filter(t => !t.approved_by).length
        },
        {
          id: 'pools',
          label: 'Allocation Pools',
          icon: 'fas fa-swimming-pool',
          count: this.activeAllocationPools
        },
        {
          id: 't4',
          label: 'T4 Corrections',
          icon: 'fas fa-file-medical',
          count: this.pendingT4Corrections
        }
      ]
    },
    
    activeDeferredAccounts() {
      return this.deferredAccounts.filter(a => a.account_status === 'active').length
    },
    
    activeAllocationPools() {
      return this.allocationPools.filter(p => p.pool_status === 'active').length
    },
    
    pendingT4Corrections() {
      return this.t4Corrections.filter(c => c.correction_status === 'pending').length
    },
    
    has2013Correction() {
      return this.t4Corrections.some(c => c.tax_year === 2013 && c.correction_status === 'pending')
    },
    
    businessAmount() {
      const gross = parseFloat(this.expenseForm.gross_amount) || 0
      return gross * (this.businessPercentage / 100)
    },
    
    personalAmount() {
      const gross = parseFloat(this.expenseForm.gross_amount) || 0
      return gross * ((100 - this.businessPercentage) / 100)
    }
  },
  async mounted() {
    await this.loadData()
  },
  methods: {
    async loadData() {
      try {
        await Promise.all([
          this.loadDeferredAccounts(),
          this.loadOwnerTransactions(),
          this.loadAllocationPools(),
          this.loadT4Corrections(),
          this.loadAvailableEmployees(),
          this.loadMetrics()
        ])
      } catch (error) {
        console.error('Error loading deferred wage data:', error)
        this.$toast.error('Failed to load deferred wage data')
      }
    },
    
    async loadDeferredAccounts() {
      const response = await fetch('/api/deferred-wages/accounts')
      this.deferredAccounts = await response.json()
      
      // Find Michael Richard's account for special handling
      this.michaelRichardAccount = this.deferredAccounts.find(
        a => a.employee_name.toLowerCase().includes('michael') && 
             a.employee_name.toLowerCase().includes('richard')
      )
    },
    
    async loadOwnerTransactions() {
      const response = await fetch('/api/deferred-wages/owner-transactions')
      this.ownerTransactions = await response.json()
    },
    
    async loadAllocationPools() {
      const response = await fetch('/api/deferred-wages/allocation-pools')
      this.allocationPools = await response.json()
    },
    
    async loadT4Corrections() {
      const response = await fetch('/api/deferred-wages/t4-corrections')
      this.t4Corrections = await response.json()
      
      // Find Paul's 2013 correction
      this.paulHeffnerCorrection = this.t4Corrections.find(
        c => c.tax_year === 2013 && c.employee_name.toLowerCase().includes('paul')
      )
    },
    
    async loadAvailableEmployees() {
      const response = await fetch('/api/employees')
      this.availableEmployees = await response.json()
    },
    
    async loadMetrics() {
      const response = await fetch('/api/deferred-wages/metrics')
      const metrics = await response.json()
      
      this.totalDeferredBalance = metrics.total_deferred_balance || 0
      this.ownerEquityBalance = metrics.owner_equity_balance || 0
      this.availableAllocationFunds = metrics.available_allocation_funds || 0
      this.ownerBusinessExpenses = metrics.owner_business_expenses || 0
      this.ownerPersonalAllocation = metrics.owner_personal_allocation || 0
      this.ownerSalaryEquivalent = metrics.owner_salary_equivalent || 0
    },
    
    // Form Management
    getEmptyDeferredForm() {
      return {
        employee_id: '',
        account_name: '',
        max_deferred_amount: '',
        interest_rate: 0,
        minimum_payment_frequency: 'monthly',
        auto_payment_enabled: false,
        auto_payment_amount: ''
      }
    },
    
    getEmptyExpenseForm() {
      return {
        transaction_date: new Date().toISOString().split('T')[0],
        gross_amount: '',
        description: '',
        vendor_name: '',
        expense_category: 'fuel',
        card_used: '**** **** **** 1234',
        receipt_reference: ''
      }
    },
    
    calculatePortions() {
      // Auto-update business/personal portions when amount or percentage changes
      this.expenseForm.business_portion = this.businessAmount
      this.expenseForm.personal_portion = this.personalAmount
    },
    
    // API Actions
    async createDeferredAccount() {
      try {
        const response = await fetch('/api/deferred-wages/accounts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.deferredForm)
        })
        
        if (response.ok) {
          this.$toast.success('Deferred wage account created successfully')
          this.closeModals()
          await this.loadDeferredAccounts()
        } else {
          throw new Error('Failed to create deferred account')
        }
      } catch (error) {
        console.error('Error creating deferred account:', error)
        this.$toast.error('Failed to create deferred account')
      }
    },
    
    async createOwnerExpense() {
      try {
        const response = await fetch('/api/deferred-wages/owner-expenses', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            ...this.expenseForm,
            business_portion: this.businessAmount,
            personal_portion: this.personalAmount
          })
        })
        
        if (response.ok) {
          this.$toast.success('Owner expense recorded successfully')
          this.closeModals()
          await this.loadOwnerTransactions()
          await this.loadMetrics()
        } else {
          throw new Error('Failed to record owner expense')
        }
      } catch (error) {
        console.error('Error recording owner expense:', error)
        this.$toast.error('Failed to record owner expense')
      }
    },
    
    // Helper Methods
    formatAccountType(type) {
      const types = {
        'employee_deferred': 'Employee Deferred',
        'owner_equity': 'Owner Equity',
        'pool_allocation': 'Pool Allocation'
      }
      return types[type] || type
    },
    
    formatTransactionType(type) {
      const types = {
        'business_expense': 'Business Expense',
        'personal_allocation': 'Personal Draw',
        'salary_equivalent': 'Salary Equivalent'
      }
      return types[type] || type
    },
    
    formatPoolType(type) {
      const types = {
        'driver_pool': 'Driver Pool',
        'salary_pool': 'Salary Pool',
        'bonus_pool': 'Bonus Pool'
      }
      return types[type] || type
    },
    
    formatPoolStatus(status) {
      const statuses = {
        'active': 'Active',
        'closed': 'Closed',
        'depleted': 'Depleted'
      }
      return statuses[status] || status
    },
    
    formatCorrectionType(type) {
      const types = {
        'original_filing': 'Original Filing',
        'amendment': 'Amendment',
        'cancellation': 'Cancellation'
      }
      return types[type] || type
    },
    
    formatCorrectionStatus(status) {
      const statuses = {
        'pending': 'Pending',
        'filed': 'Filed',
        'accepted': 'Accepted',
        'rejected': 'Rejected'
      }
      return statuses[status] || status
    },
    
    formatDate(dateString) {
      if (!dateString) return 'N/A'
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    },
    
    getPoolProgressPercentage(pool) {
      if (pool.total_available === 0) return 0
      return (pool.allocated_amount / pool.total_available) * 100
    },
    
    closeModals() {
      this.showCreateDeferredAccount = false
      this.showOwnerExpenseEntry = false
      this.showAllocationPool = false
      this.deferredForm = this.getEmptyDeferredForm()
      this.expenseForm = this.getEmptyExpenseForm()
      this.businessPercentage = 100
    },
    
    // Placeholder methods for future implementation
    addDeferredTransaction(account) {
      console.log('Add deferred transaction for:', account)
    },
    
    makeDeferredPayment(account) {
      console.log('Make deferred payment for:', account)
    },
    
    viewTransactionHistory(account) {
      console.log('View transaction history for:', account)
    },
    
    editAccount(account) {
      console.log('Edit account:', account)
    },
    
    approveOwnerTransaction(transaction) {
      console.log('Approve owner transaction:', transaction)
    },
    
    editOwnerTransaction(transaction) {
      console.log('Edit owner transaction:', transaction)
    },
    
    makeAllocation(pool) {
      console.log('Make allocation from pool:', pool)
    },
    
    viewAllocationHistory(pool) {
      console.log('View allocation history for pool:', pool)
    },
    
    addFundsToPool(pool) {
      console.log('Add funds to pool:', pool)
    },
    
    editCorrection(correction) {
      console.log('Edit T4 correction:', correction)
    },
    
    fileCorrection(correction) {
      console.log('File T4 correction with CRA:', correction)
    },
    
    viewCorrectionDetails(correction) {
      console.log('View T4 correction details:', correction)
    }
  }
}
</script>

<style scoped>
.deferred-wage-management {
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

.metric-card.total-deferred .metric-icon {
  background: #ffc107;
}

.metric-card.owner-equity .metric-icon {
  background: #6f42c1;
}

.metric-card.allocation-pool .metric-icon {
  background: #20c997;
}

.metric-card.t4-corrections .metric-icon {
  background: #dc3545;
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

/* Deferred Account Cards */
.deferred-account-card {
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  background: #f8f9fa;
}

.account-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.account-info h4 {
  margin: 0;
  color: #2c3e50;
}

.account-type {
  font-size: 0.8rem;
  color: #6c757d;
  text-transform: uppercase;
  font-weight: 600;
}

.account-balance {
  text-align: right;
}

.balance-amount {
  font-size: 1.5rem;
  font-weight: bold;
  color: #ffc107;
}

.balance-label {
  display: block;
  font-size: 0.8rem;
  color: #6c757d;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.detail-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #e9ecef;
}

.detail-item label {
  font-weight: 600;
  color: #495057;
}

.detail-item span {
  color: #2c3e50;
}

.account-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

/* Owner Equity Dashboard */
.owner-summary-card {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 25px;
  margin-bottom: 30px;
}

.owner-summary-card h3 {
  margin: 0 0 20px 0;
  color: #2c3e50;
}

.equity-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
}

.equity-item {
  background: white;
  border-radius: 6px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 15px;
}

.equity-item.business .equity-icon {
  background: #28a745;
}

.equity-item.personal .equity-icon {
  background: #dc3545;
}

.equity-item.salary .equity-icon {
  background: #007bff;
}

.equity-icon {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 1.3rem;
}

.equity-details h4 {
  margin: 0;
  font-size: 1.5rem;
  color: #2c3e50;
}

.equity-details p {
  margin: 5px 0 0 0;
  color: #495057;
  font-weight: 600;
}

.equity-details small {
  color: #6c757d;
  font-size: 0.8rem;
}

/* Owner Transactions Table */
.owner-transactions {
  background: white;
  border-radius: 6px;
  padding: 20px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.section-header h4 {
  margin: 0;
  color: #2c3e50;
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

.transaction-desc strong {
  color: #2c3e50;
}

.transaction-desc .vendor {
  font-size: 0.8rem;
  color: #6c757d;
}

.amount {
  text-align: right;
  font-weight: 600;
}

.type-badge,
.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.type-badge.type-business_expense {
  background: #d4edda;
  color: #155724;
}

.type-badge.type-personal_allocation {
  background: #f8d7da;
  color: #721c24;
}

.status-badge.approved {
  background: #d4edda;
  color: #155724;
}

.status-badge.pending {
  background: #fff3cd;
  color: #856404;
}

.action-buttons {
  display: flex;
  gap: 5px;
}

/* Allocation Pools */
.pool-card {
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  background: #f8f9fa;
}

.pool-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.pool-info h4 {
  margin: 0;
  color: #2c3e50;
}

.pool-type {
  font-size: 0.8rem;
  color: #6c757d;
  text-transform: uppercase;
}

.pool-progress {
  margin-bottom: 20px;
}

.progress-bar {
  width: 100%;
  height: 20px;
  background: #e9ecef;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 10px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #28a745, #20c997);
  transition: width 0.3s ease;
}

.progress-labels {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: #6c757d;
}

.pool-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

/* T4 Corrections */
.correction-alert {
  margin-bottom: 20px;
}

.alert {
  padding: 15px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.alert-warning {
  background: #fff3cd;
  border: 1px solid #ffc107;
  color: #856404;
}

.correction-card {
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  background: #f8f9fa;
}

.correction-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.correction-info h4 {
  margin: 0;
  color: #2c3e50;
}

.correction-type {
  font-size: 0.8rem;
  color: #6c757d;
  text-transform: uppercase;
}

.amounts-comparison {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 15px;
}

.original-amounts,
.corrected-amounts {
  background: white;
  padding: 15px;
  border-radius: 6px;
}

.original-amounts h5,
.corrected-amounts h5 {
  margin: 0 0 10px 0;
  color: #495057;
}

.amount-grid {
  display: grid;
  gap: 8px;
  font-size: 0.9rem;
}

.amount-grid div {
  display: flex;
  justify-content: space-between;
  padding: 5px 0;
  border-bottom: 1px solid #f1f3f4;
}

.correction-reason {
  background: white;
  padding: 15px;
  border-radius: 6px;
  margin-bottom: 15px;
  font-size: 0.9rem;
  color: #495057;
}

.correction-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
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

.deferred-form,
.expense-form {
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

/* Allocation Slider */
.allocation-slider {
  background: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 20px;
}

.slider-container {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 20px;
}

.slider-container label {
  font-weight: 600;
  color: #495057;
  min-width: 140px;
}

.slider {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: #dee2e6;
  outline: none;
  -webkit-appearance: none;
}

.slider::-webkit-slider-thumb {
  -webkit-appearance: none;
  appearance: none;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #007bff;
  cursor: pointer;
}

.slider::-moz-range-thumb {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #007bff;
  cursor: pointer;
  border: none;
}

.percentage-display {
  font-weight: bold;
  color: #007bff;
  min-width: 50px;
  text-align: right;
}

.portion-display {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.business-portion,
.personal-portion {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px;
  border-radius: 6px;
}

.business-portion {
  background: #d4edda;
  border: 1px solid #c3e6cb;
}

.personal-portion {
  background: #f8d7da;
  border: 1px solid #f5c6cb;
}

.business-portion label,
.personal-portion label {
  font-weight: 600;
  margin: 0;
}

.business-portion .amount {
  font-weight: bold;
  color: #155724;
}

.personal-portion .amount {
  font-weight: bold;
  color: #721c24;
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
  
  .metrics-grid {
    grid-template-columns: 1fr;
  }
  
  .tab-headers {
    flex-wrap: wrap;
  }
  
  .form-row {
    grid-template-columns: 1fr;
  }
  
  .amounts-comparison {
    grid-template-columns: 1fr;
  }
  
  .portion-display {
    grid-template-columns: 1fr;
  }
  
  .slider-container {
    flex-direction: column;
    align-items: stretch;
  }
  
  .slider-container label {
    min-width: auto;
  }
}
</style>