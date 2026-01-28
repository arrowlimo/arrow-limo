<!--
  Paul's CIBC Business Card Configuration
  Purpose: Configure Paul Heffner's 3 CIBC business cards for owner equity tracking
  Created: October 21, 2025
  
  Features:
  - Business Expenses Card (5434 **** **** 1234)
  - Personal Allocation Card (5434 **** **** 5678) 
  - Salary Equity Card (5434 **** **** 9012)
  - Real-time balance tracking
  - Expense categorization
  - Monthly statements integration
-->
<template>
  <div class="cibc-card-configuration">
    <!-- Header Section -->
    <div class="config-header">
      <h2>Paul's CIBC Business Cards - Owner Equity System</h2>
      <div class="header-actions">
        <button @click="showAddCard = true" class="btn btn-success">
          <i class="fas fa-credit-card"></i> Add Card
        </button>
        <button @click="showStatementUpload = true" class="btn btn-warning">
          <i class="fas fa-file-upload"></i> Upload Statement
        </button>
        <button @click="syncWithBanking" class="btn btn-info">
          <i class="fas fa-sync-alt"></i> Sync Banking
        </button>
        <button @click="refreshData" class="btn btn-outline-primary">
          <i class="fas fa-refresh"></i> Refresh
        </button>
      </div>
    </div>

    <!-- Card Overview Grid -->
    <div class="cards-grid">
      <div v-for="card in cibcCards" :key="card.card_id" class="cibc-card" :class="getCardClass(card)">
        <div class="card-header">
          <div class="card-info">
            <h3>{{ card.card_name }}</h3>
            <div class="card-number">
              <i class="fab fa-cc-visa"></i>
              **** **** **** {{ card.last_four_digits }}
            </div>
            <div class="card-type">{{ formatCardType(card.card_type) }}</div>
          </div>
          <div class="card-status">
            <span :class="['status-indicator', card.is_active ? 'active' : 'inactive']"></span>
            <span class="status-text">{{ card.is_active ? 'Active' : 'Inactive' }}</span>
          </div>
        </div>

        <div class="card-metrics">
          <div class="metric-row">
            <div class="metric">
              <label>Current Balance:</label>
              <span :class="['balance', getBalanceClass(card.current_balance)]">
                ${{ formatCurrency(card.current_balance) }}
              </span>
            </div>
            <div class="metric">
              <label>Credit Limit:</label>
              <span class="limit">${{ formatCurrency(card.credit_limit) }}</span>
            </div>
          </div>
          
          <div class="metric-row">
            <div class="metric">
              <label>This Month:</label>
              <span class="monthly">${{ formatCurrency(card.monthly_spending) }}</span>
            </div>
            <div class="metric">
              <label>Available:</label>
              <span class="available">${{ formatCurrency(card.credit_limit - card.current_balance) }}</span>
            </div>
          </div>
        </div>

        <div class="card-actions">
          <button @click="viewTransactions(card)" class="btn btn-sm btn-primary">
            <i class="fas fa-list"></i> Transactions
          </button>
          <button @click="addExpense(card)" class="btn btn-sm btn-success">
            <i class="fas fa-plus"></i> Add Expense
          </button>
          <button @click="editCard(card)" class="btn btn-sm btn-outline-secondary">
            <i class="fas fa-edit"></i> Edit
          </button>
          <button @click="generateStatement(card)" class="btn btn-sm btn-outline-info">
            <i class="fas fa-file-alt"></i> Statement
          </button>
        </div>

        <!-- Recent Transactions Preview -->
        <div class="recent-transactions">
          <h5>Recent Transactions</h5>
          <div v-if="card.recent_transactions && card.recent_transactions.length > 0" class="transaction-list">
            <div v-for="txn in card.recent_transactions.slice(0, 3)" :key="txn.id" class="transaction-item">
              <div class="transaction-details">
                <div class="vendor">{{ txn.vendor_name }}</div>
                <div class="date">{{ formatDate(txn.transaction_date) }}</div>
              </div>
              <div class="amount">${{ formatCurrency(txn.amount) }}</div>
              <div class="category">{{ txn.category }}</div>
            </div>
          </div>
          <div v-else class="no-transactions">
            No recent transactions
          </div>
        </div>
      </div>
    </div>

    <!-- Monthly Summary Section -->
    <div class="monthly-summary">
      <h3>Monthly Summary - {{ currentMonth }}</h3>
      <div class="summary-grid">
        <div class="summary-card business">
          <div class="summary-header">
            <h4>Business Expenses</h4>
            <i class="fas fa-briefcase"></i>
          </div>
          <div class="summary-metrics">
            <div class="metric">
              <label>Total Spent:</label>
              <span class="value">${{ formatCurrency(monthlyTotals.business_expenses) }}</span>
            </div>
            <div class="metric">
              <label>Transactions:</label>
              <span class="value">{{ monthlyTotals.business_count }}</span>
            </div>
            <div class="metric">
              <label>Avg Transaction:</label>
              <span class="value">${{ formatCurrency(monthlyTotals.business_avg) }}</span>
            </div>
          </div>
        </div>

        <div class="summary-card personal">
          <div class="summary-header">
            <h4>Personal Allocation</h4>
            <i class="fas fa-user"></i>
          </div>
          <div class="summary-metrics">
            <div class="metric">
              <label>Total Spent:</label>
              <span class="value">${{ formatCurrency(monthlyTotals.personal_allocation) }}</span>
            </div>
            <div class="metric">
              <label>Transactions:</label>
              <span class="value">{{ monthlyTotals.personal_count }}</span>
            </div>
            <div class="metric">
              <label>Avg Transaction:</label>
              <span class="value">${{ formatCurrency(monthlyTotals.personal_avg) }}</span>
            </div>
          </div>
        </div>

        <div class="summary-card salary">
          <div class="summary-header">
            <h4>Salary Equity</h4>
            <i class="fas fa-chart-line"></i>
          </div>
          <div class="summary-metrics">
            <div class="metric">
              <label>Total Spent:</label>
              <span class="value">${{ formatCurrency(monthlyTotals.salary_equity) }}</span>
            </div>
            <div class="metric">
              <label>Transactions:</label>
              <span class="value">{{ monthlyTotals.salary_count }}</span>
            </div>
            <div class="metric">
              <label>Avg Transaction:</label>
              <span class="value">${{ formatCurrency(monthlyTotals.salary_avg) }}</span>
            </div>
          </div>
        </div>

        <div class="summary-card total">
          <div class="summary-header">
            <h4>Total Equity Usage</h4>
            <i class="fas fa-calculator"></i>
          </div>
          <div class="summary-metrics">
            <div class="metric">
              <label>Combined Total:</label>
              <span class="value total-amount">
                ${{ formatCurrency(monthlyTotals.total_spending) }}
              </span>
            </div>
            <div class="metric">
              <label>All Transactions:</label>
              <span class="value">{{ monthlyTotals.total_count }}</span>
            </div>
            <div class="metric">
              <label>Owner Equity Impact:</label>
              <span :class="['value', getEquityClass(monthlyTotals.equity_impact)]">
                ${{ formatCurrency(monthlyTotals.equity_impact) }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Banking Integration Status -->
    <div class="banking-integration">
      <h3>Banking Integration Status</h3>
      <div class="integration-grid">
        <div class="integration-item">
          <div class="integration-icon">
            <i class="fas fa-university"></i>
          </div>
          <div class="integration-details">
            <h4>CIBC Banking Connection</h4>
            <div class="status">
              <span :class="['indicator', bankingStatus.cibc_connected ? 'connected' : 'disconnected']"></span>
              {{ bankingStatus.cibc_connected ? 'Connected' : 'Disconnected' }}
            </div>
            <div class="last-sync">
              Last Sync: {{ formatDateTime(bankingStatus.last_sync) }}
            </div>
          </div>
          <div class="integration-actions">
            <button @click="connectCIBC" class="btn btn-sm btn-primary">
              <i class="fas fa-link"></i> Connect
            </button>
          </div>
        </div>

        <div class="integration-item">
          <div class="integration-icon">
            <i class="fas fa-file-excel"></i>
          </div>
          <div class="integration-details">
            <h4>Statement Processing</h4>
            <div class="status">
              <span class="indicator processed"></span>
              {{ bankingStatus.statements_processed }} statements processed
            </div>
            <div class="last-sync">
              Latest: {{ formatDate(bankingStatus.latest_statement_date) }}
            </div>
          </div>
          <div class="integration-actions">
            <button @click="showStatementUpload = true" class="btn btn-sm btn-success">
              <i class="fas fa-upload"></i> Upload
            </button>
          </div>
        </div>

        <div class="integration-item">
          <div class="integration-icon">
            <i class="fas fa-robot"></i>
          </div>
          <div class="integration-details">
            <h4>Auto-Categorization</h4>
            <div class="status">
              <span class="indicator active"></span>
              {{ bankingStatus.auto_categorization_rate }}% auto-categorized
            </div>
            <div class="last-sync">
              Rules: {{ bankingStatus.categorization_rules }} active
            </div>
          </div>
          <div class="integration-actions">
            <button @click="manageRules" class="btn btn-sm btn-warning">
              <i class="fas fa-cogs"></i> Rules
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Add Card Modal -->
    <div v-if="showAddCard" class="modal-overlay" @click="closeModals">
      <div class="modal-content add-card-modal" @click.stop>
        <div class="modal-header">
          <h3>Add CIBC Business Card</h3>
          <button @click="closeModals" class="close-btn">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <form @submit.prevent="addCard" class="card-form">
          <div class="form-section">
            <h4>Card Information</h4>
            <div class="form-row">
              <div class="form-group">
                <label>Card Name</label>
                <input 
                  type="text" 
                  v-model="cardForm.card_name"
                  placeholder="e.g., Business Expenses Card"
                  required
                >
              </div>
              
              <div class="form-group">
                <label>Card Type</label>
                <select v-model="cardForm.card_type" required>
                  <option value="business_expenses">Business Expenses</option>
                  <option value="personal_allocation">Personal Allocation</option>
                  <option value="salary_equity">Salary Equity</option>
                </select>
              </div>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label>Card Number (Last 4 Digits)</label>
                <input 
                  type="text" 
                  v-model="cardForm.last_four_digits"
                  placeholder="1234"
                  pattern="[0-9]{4}"
                  maxlength="4"
                  required
                >
              </div>
              
              <div class="form-group">
                <label>Credit Limit</label>
                <input 
                  type="number" 
                  step="0.01" 
                  v-model="cardForm.credit_limit"
                  placeholder="25000.00"
                  required
                >
              </div>
            </div>
          </div>

          <div class="form-section">
            <h4>Owner Equity Integration</h4>
            <div class="form-row">
              <div class="form-group">
                <label>Owner Equity Account</label>
                <select v-model="cardForm.owner_equity_account_id" required>
                  <option value="">Select Account</option>
                  <option 
                    v-for="account in ownerEquityAccounts" 
                    :key="account.account_id"
                    :value="account.account_id"
                  >
                    {{ account.account_name }} ({{ account.account_type }})
                  </option>
                </select>
              </div>
              
              <div class="form-group">
                <label>Default Category</label>
                <select v-model="cardForm.default_category">
                  <option value="">Auto-categorize</option>
                  <option value="office_supplies">Office Supplies</option>
                  <option value="meals_entertainment">Meals & Entertainment</option>
                  <option value="travel">Travel</option>
                  <option value="vehicle_expenses">Vehicle Expenses</option>
                  <option value="professional_services">Professional Services</option>
                  <option value="insurance">Insurance</option>
                  <option value="utilities">Utilities</option>
                  <option value="personal">Personal</option>
                </select>
              </div>
            </div>
          </div>

          <div class="form-actions">
            <button type="button" @click="closeModals" class="btn btn-secondary">Cancel</button>
            <button type="submit" class="btn btn-success">Add Card</button>
          </div>
        </form>
      </div>
    </div>

    <!-- Statement Upload Modal -->
    <div v-if="showStatementUpload" class="modal-overlay" @click="closeModals">
      <div class="modal-content statement-modal" @click.stop>
        <div class="modal-header">
          <h3>Upload CIBC Statement</h3>
          <button @click="closeModals" class="close-btn">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <form @submit.prevent="uploadStatement" class="statement-form">
          <div class="upload-section">
            <div class="file-upload">
              <input 
                type="file" 
                ref="statementFile"
                @change="handleFileSelect"
                accept=".pdf,.csv,.xlsx"
                style="display: none"
              >
              <button 
                type="button" 
                @click="$refs.statementFile.click()" 
                class="btn btn-outline-primary file-select-btn"
              >
                <i class="fas fa-file-upload"></i>
                Select Statement File
              </button>
              <div v-if="selectedFile" class="selected-file">
                <i class="fas fa-file"></i>
                {{ selectedFile.name }}
                <span class="file-size">({{ formatFileSize(selectedFile.size) }})</span>
              </div>
            </div>
            
            <div class="form-row">
              <div class="form-group">
                <label>Card</label>
                <select v-model="statementForm.card_id" required>
                  <option value="">Select Card</option>
                  <option 
                    v-for="card in cibcCards" 
                    :key="card.card_id"
                    :value="card.card_id"
                  >
                    {{ card.card_name }} (**** {{ card.last_four_digits }})
                  </option>
                </select>
              </div>
              
              <div class="form-group">
                <label>Statement Period</label>
                <input 
                  type="month" 
                  v-model="statementForm.statement_period"
                  required
                >
              </div>
            </div>
          </div>

          <div class="processing-options">
            <h4>Processing Options</h4>
            <div class="option-group">
              <label class="checkbox-label">
                <input type="checkbox" v-model="statementForm.auto_categorize">
                Auto-categorize transactions
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="statementForm.match_existing">
                Match with existing transactions
              </label>
              <label class="checkbox-label">
                <input type="checkbox" v-model="statementForm.update_balances">
                Update card balances
              </label>
            </div>
          </div>

          <div class="form-actions">
            <button type="button" @click="closeModals" class="btn btn-secondary">Cancel</button>
            <button type="submit" class="btn btn-warning" :disabled="!selectedFile">
              Upload & Process
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'CIBCCardConfiguration',
  data() {
    return {
      showAddCard: false,
      showStatementUpload: false,
      selectedFile: null,
      
      // Data
      cibcCards: [],
      ownerEquityAccounts: [],
      monthlyTotals: {},
      bankingStatus: {},
      
      // Forms
      cardForm: this.getEmptyCardForm(),
      statementForm: this.getEmptyStatementForm()
    }
  },
  computed: {
    currentMonth() {
      return new Date().toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long' 
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
          this.loadCIBCCards(),
          this.loadOwnerEquityAccounts(),
          this.loadMonthlyTotals(),
          this.loadBankingStatus()
        ])
      } catch (error) {
        console.error('Error loading CIBC card data:', error)
        this.$toast.error('Failed to load card configuration data')
      }
    },
    
    async loadCIBCCards() {
      const response = await fetch('/api/deferred-wages/cibc-cards')
      this.cibcCards = await response.json()
    },
    
    async loadOwnerEquityAccounts() {
      const response = await fetch('/api/deferred-wages/accounts?type=owner_equity')
      this.ownerEquityAccounts = await response.json()
    },
    
    async loadMonthlyTotals() {
      const currentDate = new Date()
      const year = currentDate.getFullYear()
      const month = currentDate.getMonth() + 1
      
      const response = await fetch(`/api/deferred-wages/cibc-monthly-summary/${year}/${month}`)
      this.monthlyTotals = await response.json()
    },
    
    async loadBankingStatus() {
      const response = await fetch('/api/deferred-wages/banking-status')
      this.bankingStatus = await response.json()
    },
    
    // Form Management
    getEmptyCardForm() {
      return {
        card_name: '',
        card_type: 'business_expenses',
        last_four_digits: '',
        credit_limit: 25000.00,
        owner_equity_account_id: '',
        default_category: '',
        is_active: true
      }
    },
    
    getEmptyStatementForm() {
      return {
        card_id: '',
        statement_period: new Date().toISOString().slice(0, 7),
        auto_categorize: true,
        match_existing: true,
        update_balances: true
      }
    },
    
    // Helper Methods
    formatCurrency(amount) {
      if (!amount) return '0.00'
      return Math.abs(parseFloat(amount)).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      })
    },
    
    formatDate(dateString) {
      if (!dateString) return 'N/A'
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      })
    },
    
    formatDateTime(dateString) {
      if (!dateString) return 'Never'
      return new Date(dateString).toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    },
    
    formatFileSize(bytes) {
      if (bytes === 0) return '0 Bytes'
      const k = 1024
      const sizes = ['Bytes', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    },
    
    formatCardType(cardType) {
      const types = {
        'business_expenses': 'Business Expenses',
        'personal_allocation': 'Personal Allocation',
        'salary_equity': 'Salary Equity'
      }
      return types[cardType] || cardType
    },
    
    getCardClass(card) {
      return `card-type-${card.card_type}`
    },
    
    getBalanceClass(balance) {
      if (balance < 0) return 'negative'
      if (balance > 10000) return 'high'
      if (balance > 5000) return 'medium'
      return 'low'
    },
    
    getEquityClass(impact) {
      if (impact < 0) return 'negative'
      if (impact > 5000) return 'high'
      return 'normal'
    },
    
    // API Actions
    async addCard() {
      try {
        const response = await fetch('/api/deferred-wages/cibc-cards', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.cardForm)
        })
        
        if (response.ok) {
          this.$toast.success('CIBC card added successfully')
          this.closeModals()
          await this.loadData()
        } else {
          throw new Error('Failed to add card')
        }
      } catch (error) {
        console.error('Error adding card:', error)
        this.$toast.error('Failed to add CIBC card')
      }
    },
    
    async uploadStatement() {
      try {
        const formData = new FormData()
        formData.append('statement_file', this.selectedFile)
        formData.append('card_id', this.statementForm.card_id)
        formData.append('statement_period', this.statementForm.statement_period)
        formData.append('auto_categorize', this.statementForm.auto_categorize)
        formData.append('match_existing', this.statementForm.match_existing)
        formData.append('update_balances', this.statementForm.update_balances)
        
        const response = await fetch('/api/deferred-wages/cibc-statement-upload', {
          method: 'POST',
          body: formData
        })
        
        if (response.ok) {
          const result = await response.json()
          this.$toast.success(`Statement processed: ${result.transactions_processed} transactions`)
          this.closeModals()
          await this.loadData()
        } else {
          throw new Error('Failed to upload statement')
        }
      } catch (error) {
        console.error('Error uploading statement:', error)
        this.$toast.error('Failed to upload statement')
      }
    },
    
    async syncWithBanking() {
      try {
        const response = await fetch('/api/deferred-wages/cibc-banking-sync', {
          method: 'POST'
        })
        
        if (response.ok) {
          const result = await response.json()
          this.$toast.success(`Banking sync complete: ${result.synced_transactions} transactions`)
          await this.loadData()
        } else {
          throw new Error('Failed to sync with banking')
        }
      } catch (error) {
        console.error('Error syncing with banking:', error)
        this.$toast.error('Failed to sync with banking')
      }
    },
    
    handleFileSelect(event) {
      this.selectedFile = event.target.files[0]
    },
    
    closeModals() {
      this.showAddCard = false
      this.showStatementUpload = false
      this.selectedFile = null
      this.cardForm = this.getEmptyCardForm()
      this.statementForm = this.getEmptyStatementForm()
    },
    
    async refreshData() {
      await this.loadData()
      this.$toast.success('Data refreshed')
    },
    
    // Placeholder methods for future implementation
    viewTransactions(card) {
      console.log('View transactions for card:', card)
    },
    
    addExpense(card) {
      console.log('Add expense for card:', card)
    },
    
    editCard(card) {
      console.log('Edit card:', card)
    },
    
    generateStatement(card) {
      console.log('Generate statement for card:', card)
    },
    
    connectCIBC() {
      console.log('Connect to CIBC banking')
    },
    
    manageRules() {
      console.log('Manage categorization rules')
    }
  }
}
</script>

<style scoped>
.cibc-card-configuration {
  padding: 20px;
  background-color: #f8f9fa;
  min-height: 100vh;
}

.config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.config-header h2 {
  margin: 0;
  color: #2c3e50;
}

.header-actions {
  display: flex;
  gap: 15px;
}

/* CIBC Cards Grid */
.cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
  gap: 25px;
  margin-bottom: 40px;
}

.cibc-card {
  background: white;
  border-radius: 12px;
  padding: 25px;
  box-shadow: 0 4px 8px rgba(0,0,0,0.1);
  border-left: 5px solid #007bff;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.cibc-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(0,0,0,0.15);
}

.cibc-card.card-type-business_expenses {
  border-left-color: #28a745;
}

.cibc-card.card-type-personal_allocation {
  border-left-color: #17a2b8;
}

.cibc-card.card-type-salary_equity {
  border-left-color: #ffc107;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.card-info h3 {
  margin: 0 0 8px 0;
  color: #2c3e50;
  font-size: 1.3rem;
}

.card-number {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #6c757d;
  font-family: 'Courier New', monospace;
  font-size: 1.1rem;
  margin-bottom: 5px;
}

.card-number i {
  color: #007bff;
  font-size: 1.5rem;
}

.card-type {
  background: #e9ecef;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
  text-transform: uppercase;
  font-weight: 600;
  color: #495057;
}

.card-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.status-indicator.active {
  background: #28a745;
}

.status-indicator.inactive {
  background: #dc3545;
}

.status-text {
  font-size: 0.9rem;
  color: #6c757d;
}

/* Card Metrics */
.card-metrics {
  margin-bottom: 20px;
}

.metric-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
  margin-bottom: 12px;
}

.metric {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #e9ecef;
}

.metric label {
  font-weight: 600;
  color: #495057;
  font-size: 0.9rem;
}

.metric .balance.negative {
  color: #dc3545;
  font-weight: bold;
}

.metric .balance.high {
  color: #dc3545;
}

.metric .balance.medium {
  color: #ffc107;
}

.metric .balance.low {
  color: #28a745;
}

.metric .limit,
.metric .monthly,
.metric .available {
  color: #2c3e50;
  font-weight: 600;
}

/* Card Actions */
.card-actions {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

/* Recent Transactions */
.recent-transactions h5 {
  margin: 0 0 15px 0;
  color: #495057;
  font-size: 1rem;
  border-bottom: 1px solid #dee2e6;
  padding-bottom: 8px;
}

.transaction-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.transaction-item {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 10px;
  align-items: center;
  padding: 8px;
  background: #f8f9fa;
  border-radius: 4px;
  font-size: 0.85rem;
}

.transaction-details {
  display: flex;
  flex-direction: column;
}

.vendor {
  font-weight: 600;
  color: #2c3e50;
}

.date {
  color: #6c757d;
  font-size: 0.8rem;
}

.amount {
  font-weight: 600;
  color: #2c3e50;
}

.category {
  font-size: 0.8rem;
  color: #6c757d;
  text-align: right;
}

.no-transactions {
  color: #6c757d;
  font-style: italic;
  text-align: center;
  padding: 20px;
}

/* Monthly Summary */
.monthly-summary {
  background: white;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  margin-bottom: 30px;
}

.monthly-summary h3 {
  margin: 0 0 25px 0;
  color: #2c3e50;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
}

.summary-card {
  padding: 20px;
  border-radius: 8px;
  border-left: 4px solid #007bff;
}

.summary-card.business {
  background: linear-gradient(135deg, #d4edda, #c3e6cb);
  border-left-color: #28a745;
}

.summary-card.personal {
  background: linear-gradient(135deg, #cce5ff, #b3d9ff);
  border-left-color: #17a2b8;
}

.summary-card.salary {
  background: linear-gradient(135deg, #fff3cd, #ffeaa7);
  border-left-color: #ffc107;
}

.summary-card.total {
  background: linear-gradient(135deg, #f8d7da, #f5c6cb);
  border-left-color: #dc3545;
}

.summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.summary-header h4 {
  margin: 0;
  color: #2c3e50;
  font-size: 1.1rem;
}

.summary-header i {
  font-size: 1.5rem;
  opacity: 0.7;
}

.summary-metrics {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.summary-metrics .metric {
  border-bottom: none;
  padding: 4px 0;
}

.summary-metrics .value {
  color: #2c3e50;
  font-weight: bold;
}

.summary-metrics .total-amount {
  font-size: 1.2rem;
  color: #dc3545;
}

.summary-metrics .value.negative {
  color: #dc3545;
}

.summary-metrics .value.high {
  color: #dc3545;
}

/* Banking Integration */
.banking-integration {
  background: white;
  padding: 25px;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  margin-bottom: 30px;
}

.banking-integration h3 {
  margin: 0 0 25px 0;
  color: #2c3e50;
}

.integration-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.integration-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #dee2e6;
}

.integration-icon {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: #007bff;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 1.5rem;
  flex-shrink: 0;
}

.integration-details {
  flex: 1;
}

.integration-details h4 {
  margin: 0 0 5px 0;
  color: #2c3e50;
  font-size: 1rem;
}

.integration-details .status {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
}

.integration-details .indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.indicator.connected,
.indicator.active,
.indicator.processed {
  background: #28a745;
}

.indicator.disconnected {
  background: #dc3545;
}

.integration-details .last-sync {
  color: #6c757d;
  font-size: 0.8rem;
}

.integration-actions {
  flex-shrink: 0;
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
  max-width: 700px;
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

.card-form,
.statement-form {
  padding: 20px;
}

.form-section {
  margin-bottom: 25px;
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

/* File Upload */
.file-upload {
  margin-bottom: 20px;
}

.file-select-btn {
  width: 100%;
  padding: 15px;
  border: 2px dashed #007bff;
  background: #f8f9fa;
  color: #007bff;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s ease;
}

.file-select-btn:hover {
  background: #e3f2fd;
  border-color: #0056b3;
}

.selected-file {
  margin-top: 10px;
  padding: 10px;
  background: #d4edda;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: #155724;
}

.file-size {
  color: #6c757d;
  font-size: 0.8rem;
}

/* Processing Options */
.processing-options {
  margin-bottom: 25px;
}

.option-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #495057;
  cursor: pointer;
}

.checkbox-label input[type="checkbox"] {
  margin: 0;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 15px;
  margin-top: 25px;
  padding-top: 20px;
  border-top: 1px solid #dee2e6;
}

/* Responsive Design */
@media (max-width: 768px) {
  .config-header {
    flex-direction: column;
    gap: 15px;
    align-items: stretch;
  }
  
  .header-actions {
    justify-content: center;
    flex-wrap: wrap;
  }
  
  .cards-grid {
    grid-template-columns: 1fr;
  }
  
  .form-row {
    grid-template-columns: 1fr;
  }
  
  .summary-grid {
    grid-template-columns: 1fr;
  }
  
  .integration-grid {
    grid-template-columns: 1fr;
  }
  
  .integration-item {
    flex-direction: column;
    text-align: center;
  }
  
  .metric-row {
    grid-template-columns: 1fr;
  }
  
  .card-actions {
    justify-content: center;
  }
}
</style>