<template>
  <div class="cibc-card-configuration">
    <!-- Header -->
    <div class="page-header">
      <h1 class="page-title">
        <i class="fab fa-cc-visa"></i>
        CIBC Card Management
      </h1>
      <p class="page-subtitle">Paul Heffner's 3 CIBC Business Cards with automated reconciliation</p>
    </div>

    <!-- Card Overview Grid -->
    <div class="cards-overview">
      <div v-for="card in cards" :key="card.card_id" class="card-summary" :class="getRiskClass(card)">
        <div class="card-header">
          <div class="card-title">
            <h3>{{ card.card_name }}</h3>
            <span class="card-type">{{ card.card_type }}</span>
          </div>
          <div class="card-status" :class="{ active: card.is_active }">
            {{ card.is_active ? 'Active' : 'Inactive' }}
          </div>
        </div>
        
        <div class="card-limits">
          <div class="limit-bar">
            <div class="limit-used" :style="{ width: getUtilizationPercentage(card) + '%' }"></div>
          </div>
          <div class="limit-text">
            <span class="current">${{ card.current_balance?.toLocaleString() || '0' }}</span>
            <span class="separator">/</span>
            <span class="total">${{ card.credit_limit?.toLocaleString() }}</span>
          </div>
          <div class="utilization">
            {{ getUtilizationPercentage(card) }}% utilized
          </div>
        </div>

        <div class="card-metrics">
          <div class="metric">
            <span class="label">Available Credit:</span>
            <span class="value">${{ (card.available_credit || (card.credit_limit - card.current_balance))?.toLocaleString() }}</span>
          </div>
          <div class="metric">
            <span class="label">Statement Date:</span>
            <span class="value">{{ formatDate(card.statement_date) }}</span>
          </div>
          <div class="metric">
            <span class="label">Payment Due:</span>
            <span class="value">{{ formatDate(card.payment_due_date) }}</span>
          </div>
        </div>

        <div class="card-actions">
          <button class="btn btn-primary" @click="uploadStatement(card)">
            <i class="fas fa-upload"></i>
            Upload Statement
          </button>
          <button class="btn btn-secondary" @click="viewTransactions(card)">
            <i class="fas fa-list"></i>
            View Transactions
          </button>
        </div>
      </div>
    </div>

    <!-- Monthly Summary Section -->
    <div class="monthly-summary-section">
      <div class="section-header">
        <h2>Monthly Summary</h2>
        <div class="month-selector">
          <button @click="changeMonth(-1)" class="btn btn-sm">
            <i class="fas fa-chevron-left"></i>
          </button>
          <span class="current-month">{{ formatMonth(currentMonth) }}</span>
          <button @click="changeMonth(1)" class="btn btn-sm">
            <i class="fas fa-chevron-right"></i>
          </button>
        </div>
      </div>

      <div class="summary-grid">
        <div v-for="summary in monthlySummaries" :key="summary.card_id" class="summary-card">
          <h4>{{ summary.card_name }}</h4>
          <div class="summary-metrics">
            <div class="metric">
              <span class="label">Transactions:</span>
              <span class="value">{{ summary.transaction_count || 0 }}</span>
            </div>
            <div class="metric">
              <span class="label">Total Amount:</span>
              <span class="value amount">${{ summary.total_amount?.toFixed(2) || '0.00' }}</span>
            </div>
            <div class="metric">
              <span class="label">Auto-Categorized:</span>
              <span class="value">${{ summary.auto_categorized_amount?.toFixed(2) || '0.00' }}</span>
            </div>
            <div class="metric">
              <span class="label">Needs Review:</span>
              <span class="value warning">{{ summary.review_required_count || 0 }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Transaction Processing Section -->
    <div class="processing-section">
      <div class="section-header">
        <h2>Statement Processing</h2>
        <div class="processing-controls">
          <input 
            type="file" 
            ref="fileInput" 
            @change="handleFileSelect" 
            accept=".csv,.xlsx,.pdf"
            style="display: none"
          >
          <button class="btn btn-primary" @click="$refs.fileInput.click()">
            <i class="fas fa-file-upload"></i>
            Upload Statement
          </button>
          <button class="btn btn-secondary" @click="runAutoCategorizationAll">
            <i class="fas fa-robot"></i>
            Auto-Categorize All
          </button>
        </div>
      </div>

      <div v-if="uploadProgress.show" class="upload-progress">
        <div class="progress-bar">
          <div class="progress-fill" :style="{ width: uploadProgress.percent + '%' }"></div>
        </div>
        <div class="progress-text">
          {{ uploadProgress.text }} ({{ uploadProgress.percent }}%)
        </div>
      </div>

      <div v-if="processingResults.length > 0" class="processing-results">
        <h3>Recent Processing Results</h3>
        <div class="results-table">
          <table>
            <thead>
              <tr>
                <th>File</th>
                <th>Card</th>
                <th>Transactions</th>
                <th>Auto-Categorized</th>
                <th>Needs Review</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="result in processingResults" :key="result.id">
                <td>{{ result.filename }}</td>
                <td>{{ result.card_name }}</td>
                <td>{{ result.transactions_processed }}</td>
                <td>{{ result.auto_categorized }}</td>
                <td>{{ result.needs_review }}</td>
                <td>
                  <span class="status-badge" :class="result.status">
                    {{ result.status }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Integration Status Section -->
    <div class="integration-section">
      <div class="section-header">
        <h2>Integration Status</h2>
      </div>

      <div class="integration-grid">
        <div class="integration-item">
          <div class="integration-icon">
            <i class="fas fa-university"></i>
          </div>
          <div class="integration-content">
            <h4>Banking Reconciliation</h4>
            <p>{{ integrationStatus.banking_sync ? 'Connected' : 'Disconnected' }}</p>
            <div class="status-indicator" :class="{ connected: integrationStatus.banking_sync }"></div>
          </div>
        </div>

        <div class="integration-item">
          <div class="integration-icon">
            <i class="fas fa-user-tie"></i>
          </div>
          <div class="integration-content">
            <h4>Owner Equity Accounts</h4>
            <p>{{ integrationStatus.owner_equity ? 'Linked' : 'Not Linked' }}</p>
            <div class="status-indicator" :class="{ connected: integrationStatus.owner_equity }"></div>
          </div>
        </div>

        <div class="integration-item">
          <div class="integration-icon">
            <i class="fas fa-robot"></i>
          </div>
          <div class="integration-content">
            <h4>Auto-Categorization</h4>
            <p>{{ integrationStatus.auto_categorization ? 'Enabled' : 'Disabled' }}</p>
            <div class="status-indicator" :class="{ connected: integrationStatus.auto_categorization }"></div>
          </div>
        </div>

        <div class="integration-item">
          <div class="integration-icon">
            <i class="fas fa-receipt"></i>
          </div>
          <div class="integration-content">
            <h4>Receipt Tracking</h4>
            <p>{{ integrationStatus.receipt_tracking ? 'Active' : 'Inactive' }}</p>
            <div class="status-indicator" :class="{ connected: integrationStatus.receipt_tracking }"></div>
          </div>
        </div>
      </div>
    </div>

    <!-- Statement Upload Modal -->
    <div v-if="showUploadModal" class="modal-overlay" @click="closeUploadModal">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>Upload CIBC Statement</h3>
          <button class="modal-close" @click="closeUploadModal">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <div class="modal-body">
          <div class="upload-form">
            <div class="form-group">
              <label>Select Card:</label>
              <select v-model="uploadForm.selectedCard">
                <option value="">Choose a card...</option>
                <option v-for="card in cards" :key="card.card_id" :value="card.card_id">
                  {{ card.card_name }} ({{ card.card_type }})
                </option>
              </select>
            </div>
            
            <div class="form-group">
              <label>Statement File:</label>
              <input type="file" @change="handleModalFileSelect" accept=".csv,.xlsx,.pdf">
            </div>
            
            <div class="form-group">
              <label>Statement Period:</label>
              <div class="date-range">
                <input type="date" v-model="uploadForm.startDate">
                <span>to</span>
                <input type="date" v-model="uploadForm.endDate">
              </div>
            </div>
            
            <div class="form-group">
              <label>
                <input type="checkbox" v-model="uploadForm.autoCategory">
                Auto-categorize transactions
              </label>
            </div>
          </div>
        </div>
        
        <div class="modal-footer">
          <button class="btn btn-secondary" @click="closeUploadModal">Cancel</button>
          <button class="btn btn-primary" @click="processUpload" :disabled="!uploadForm.selectedCard || !uploadForm.file">
            <i class="fas fa-upload"></i>
            Upload & Process
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'CIBCCardConfiguration',
  data() {
    return {
      loading: false,
      
      // Card data
      cards: [],
      monthlySummaries: [],
      processingResults: [],
      
      // Current month for summary
      currentMonth: new Date(),
      
      // Integration status
      integrationStatus: {
        banking_sync: false,
        owner_equity: false,
        auto_categorization: false,
        receipt_tracking: false
      },
      
      // Upload progress
      uploadProgress: {
        show: false,
        percent: 0,
        text: ''
      },
      
      // Modal state
      showUploadModal: false,
      uploadForm: {
        selectedCard: '',
        file: null,
        startDate: '',
        endDate: '',
        autoCategory: true
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
          this.loadCards(),
          this.loadMonthlySummaries(),
          this.loadIntegrationStatus(),
          this.loadProcessingResults()
        ]);
      } catch (error) {
        console.error('Error loading CIBC data:', error);
        alert('Error loading data. Please refresh the page.');
      } finally {
        this.loading = false;
      }
    },
    
    async loadCards() {
      try {
        const response = await fetch('/api/cibc-cards');
        const data = await response.json();
        this.cards = data;
      } catch (error) {
        console.error('Error loading cards:', error);
      }
    },
    
    async loadMonthlySummaries() {
      try {
        const year = this.currentMonth.getFullYear();
        const month = this.currentMonth.getMonth() + 1;
        
        const response = await fetch(`/api/cibc-cards/monthly-summary?year=${year}&month=${month}`);
        const data = await response.json();
        this.monthlySummaries = data;
      } catch (error) {
        console.error('Error loading monthly summaries:', error);
      }
    },
    
    async loadIntegrationStatus() {
      try {
        const response = await fetch('/api/cibc-cards/integration-status');
        const data = await response.json();
        this.integrationStatus = data;
      } catch (error) {
        console.error('Error loading integration status:', error);
      }
    },
    
    async loadProcessingResults() {
      try {
        const response = await fetch('/api/cibc-cards/processing-results');
        const data = await response.json();
        this.processingResults = data.slice(0, 10); // Last 10 results
      } catch (error) {
        console.error('Error loading processing results:', error);
      }
    },
    
    async uploadStatement(card) {
      this.uploadForm.selectedCard = card.card_id;
      this.showUploadModal = true;
    },
    
    viewTransactions(card) {
      // TODO: Navigate to transactions view or open modal
      alert(`View transactions for ${card.card_name}\nCard ID: ${card.card_id}`);
    },
    
    changeMonth(direction) {
      const newMonth = new Date(this.currentMonth);
      newMonth.setMonth(newMonth.getMonth() + direction);
      this.currentMonth = newMonth;
      this.loadMonthlySummaries();
    },
    
    handleFileSelect(event) {
      // Auto-detect card from file or show selection modal
      this.showUploadModal = true;
    },
    
    handleModalFileSelect(event) {
      this.uploadForm.file = event.target.files[0];
    },
    
    async processUpload() {
      if (!this.uploadForm.selectedCard || !this.uploadForm.file) {
        alert('Please select a card and file');
        return;
      }
      
      this.uploadProgress.show = true;
      this.uploadProgress.percent = 0;
      this.uploadProgress.text = 'Uploading file...';
      
      try {
        const formData = new FormData();
        formData.append('file', this.uploadForm.file);
        formData.append('card_id', this.uploadForm.selectedCard);
        formData.append('start_date', this.uploadForm.startDate);
        formData.append('end_date', this.uploadForm.endDate);
        formData.append('auto_categorize', this.uploadForm.autoCategory);
        
        // Simulate upload progress
        const progressInterval = setInterval(() => {
          if (this.uploadProgress.percent < 90) {
            this.uploadProgress.percent += 10;
            this.uploadProgress.text = `Processing... ${this.uploadProgress.percent}%`;
          }
        }, 200);
        
        const response = await fetch('/api/cibc-cards/upload-statement', {
          method: 'POST',
          body: formData
        });
        
        clearInterval(progressInterval);
        
        if (response.ok) {
          const result = await response.json();
          this.uploadProgress.percent = 100;
          this.uploadProgress.text = 'Upload complete!';
          
          setTimeout(() => {
            this.uploadProgress.show = false;
            this.closeUploadModal();
            this.loadAllData();
            
            alert(`Statement processed successfully!\n` +
                  `Transactions: ${result.transactions_processed}\n` +
                  `Auto-categorized: ${result.auto_categorized}\n` +
                  `Needs review: ${result.needs_review}`);
          }, 1000);
        } else {
          throw new Error('Upload failed');
        }
        
      } catch (error) {
        this.uploadProgress.show = false;
        console.error('Upload error:', error);
        alert('Error uploading statement. Please try again.');
      }
    },
    
    async runAutoCategorizationAll() {
      if (confirm('Run auto-categorization on all uncategorized transactions?')) {
        try {
          const response = await fetch('/api/cibc-cards/auto-categorize-all', {
            method: 'POST'
          });
          
          if (response.ok) {
            const result = await response.json();
            alert(`Auto-categorization complete!\nCategorized: ${result.categorized_count} transactions`);
            this.loadAllData();
          } else {
            alert('Error running auto-categorization');
          }
        } catch (error) {
          console.error('Auto-categorization error:', error);
          alert('Error running auto-categorization');
        }
      }
    },
    
    closeUploadModal() {
      this.showUploadModal = false;
      this.uploadForm = {
        selectedCard: '',
        file: null,
        startDate: '',
        endDate: '',
        autoCategory: true
      };
    },
    
    // Utility methods
    getUtilizationPercentage(card) {
      if (!card.credit_limit || card.credit_limit === 0) return 0;
      return Math.round((card.current_balance / card.credit_limit) * 100);
    },
    
    getRiskClass(card) {
      const utilization = this.getUtilizationPercentage(card);
      if (utilization > 90) return 'high-risk';
      if (utilization > 70) return 'medium-risk';
      return 'low-risk';
    },
    
    formatDate(dateString) {
      if (!dateString) return 'Not set';
      return new Date(dateString).toLocaleDateString();
    },
    
    formatMonth(date) {
      return date.toLocaleDateString('en-US', { year: 'numeric', month: 'long' });
    }
  }
}
</script>

<style scoped>
.cibc-card-configuration {
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
  color: #e74c3c;
}

.page-subtitle {
  color: #7f8c8d;
  font-size: 1.1em;
}

/* Cards Overview */
.cards-overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
  gap: 20px;
  margin-bottom: 40px;
}

.card-summary {
  background: white;
  border-radius: 12px;
  padding: 25px;
  box-shadow: 0 4px 15px rgba(0,0,0,0.1);
  border-left: 5px solid #3498db;
  transition: transform 0.3s;
}

.card-summary:hover {
  transform: translateY(-5px);
}

.card-summary.high-risk {
  border-left-color: #e74c3c;
}

.card-summary.medium-risk {
  border-left-color: #f39c12;
}

.card-summary.low-risk {
  border-left-color: #27ae60;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.card-title h3 {
  margin: 0 0 5px 0;
  color: #2c3e50;
  font-size: 1.3em;
}

.card-type {
  background: #ecf0f1;
  color: #7f8c8d;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;
  font-weight: 600;
}

.card-status {
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.9em;
  font-weight: 600;
  background: #e74c3c;
  color: white;
}

.card-status.active {
  background: #27ae60;
}

.card-limits {
  margin-bottom: 20px;
}

.limit-bar {
  height: 8px;
  background: #ecf0f1;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 10px;
}

.limit-used {
  height: 100%;
  background: linear-gradient(45deg, #3498db, #2980b9);
  transition: width 0.5s;
}

.high-risk .limit-used {
  background: linear-gradient(45deg, #e74c3c, #c0392b);
}

.medium-risk .limit-used {
  background: linear-gradient(45deg, #f39c12, #e67e22);
}

.limit-text {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 1.1em;
  margin-bottom: 5px;
}

.limit-text .current {
  font-weight: bold;
  color: #2c3e50;
}

.limit-text .separator {
  color: #bdc3c7;
}

.limit-text .total {
  color: #7f8c8d;
}

.utilization {
  font-size: 0.9em;
  color: #7f8c8d;
}

.card-metrics {
  margin-bottom: 20px;
}

.metric {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid #f8f9fa;
}

.metric .label {
  color: #7f8c8d;
  font-size: 0.9em;
}

.metric .value {
  font-weight: 600;
  color: #2c3e50;
}

.metric .amount {
  color: #e74c3c;
}

.metric .warning {
  color: #f39c12;
}

.card-actions {
  display: flex;
  gap: 10px;
}

.btn {
  padding: 10px 15px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9em;
  font-weight: 600;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-primary {
  background: #3498db;
  color: white;
}

.btn-secondary {
  background: #95a5a6;
  color: white;
}

.btn-sm {
  padding: 5px 10px;
  font-size: 0.8em;
}

.btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

/* Monthly Summary */
.monthly-summary-section,
.processing-section,
.integration-section {
  margin-bottom: 40px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 2px solid #ecf0f1;
}

.section-header h2 {
  margin: 0;
  color: #2c3e50;
}

.month-selector {
  display: flex;
  align-items: center;
  gap: 15px;
}

.current-month {
  font-weight: 600;
  color: #2c3e50;
  min-width: 150px;
  text-align: center;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.summary-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  border-left: 4px solid #3498db;
}

.summary-card h4 {
  margin: 0 0 15px 0;
  color: #2c3e50;
}

.summary-metrics {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Processing Section */
.processing-controls {
  display: flex;
  gap: 10px;
}

.upload-progress {
  margin: 20px 0;
  background: #f8f9fa;
  border-radius: 8px;
  padding: 15px;
}

.progress-bar {
  height: 8px;
  background: #ecf0f1;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 10px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(45deg, #27ae60, #2ecc71);
  transition: width 0.3s;
}

.progress-text {
  color: #7f8c8d;
  font-size: 0.9em;
}

.processing-results {
  margin-top: 20px;
}

.results-table table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

.results-table th,
.results-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #f0f0f0;
}

.results-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #495057;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 0.8em;
  font-weight: 600;
  text-transform: uppercase;
}

.status-badge.completed {
  background: #d4edda;
  color: #155724;
}

.status-badge.processing {
  background: #fff3cd;
  color: #856404;
}

.status-badge.error {
  background: #f8d7da;
  color: #721c24;
}

/* Integration Status */
.integration-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
}

.integration-item {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 10px rgba(0,0,0,0.1);
  display: flex;
  align-items: center;
  gap: 15px;
}

.integration-icon {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ecf0f1;
  color: #7f8c8d;
  font-size: 1.5em;
}

.integration-content {
  flex: 1;
}

.integration-content h4 {
  margin: 0 0 5px 0;
  color: #2c3e50;
}

.integration-content p {
  margin: 0;
  color: #7f8c8d;
  font-size: 0.9em;
}

.status-indicator {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #e74c3c;
  margin-top: 5px;
}

.status-indicator.connected {
  background: #27ae60;
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
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 12px;
  width: 90%;
  max-width: 500px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #f0f0f0;
}

.modal-header h3 {
  margin: 0;
  color: #2c3e50;
}

.modal-close {
  background: none;
  border: none;
  font-size: 1.2em;
  cursor: pointer;
  color: #7f8c8d;
  padding: 5px;
  border-radius: 4px;
}

.modal-close:hover {
  background: #f8f9fa;
}

.modal-body {
  padding: 20px;
}

.upload-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  font-weight: 600;
  color: #2c3e50;
}

.form-group select,
.form-group input[type="file"],
.form-group input[type="date"] {
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 0.9em;
}

.date-range {
  display: flex;
  align-items: center;
  gap: 10px;
}

.date-range span {
  color: #7f8c8d;
}

.form-group input[type="checkbox"] {
  margin-right: 8px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 20px;
  border-top: 1px solid #f0f0f0;
}
</style>