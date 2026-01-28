<template>
  <div class="receipt-verification-widget">
    <div class="header">
      <h3>📋 Receipt Verification Status</h3>
      <p class="subtitle">Physical receipts matched to banking transactions</p>
    </div>

    <!-- Summary Stats -->
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Total Receipts</div>
        <div class="stat-value">{{ summary.total_receipts?.toLocaleString() || '—' }}</div>
      </div>
      <div class="stat-card verified">
        <div class="stat-label">✅ Verified</div>
        <div class="stat-value">{{ summary.verified_count?.toLocaleString() || '—' }}</div>
      </div>
      <div class="stat-card unverified">
        <div class="stat-label">❌ Unverified</div>
        <div class="stat-value">{{ summary.unverified_count?.toLocaleString() || '—' }}</div>
      </div>
      <div class="stat-card percentage">
        <div class="stat-label">📊 Verification %</div>
        <div class="stat-value">{{ (summary.verification_percentage || 0).toFixed(1) }}%</div>
      </div>
    </div>

    <!-- Verification Progress Bar -->
    <div class="progress-container">
      <div class="progress-bar">
        <div 
          class="progress-fill" 
          :style="{ width: (summary.verification_percentage || 0) + '%' }"
        ></div>
      </div>
      <p class="progress-text">
        {{ summary.verified_count?.toLocaleString() }} of {{ summary.total_receipts?.toLocaleString() }} receipts verified
      </p>
    </div>

    <!-- Year Breakdown -->
    <div class="year-breakdown">
      <h4>By Year</h4>
      <div class="year-list">
        <div v-for="year in yearStats" :key="year.year" class="year-row">
          <span class="year-label">{{ year.year }}</span>
          <div class="year-bar">
            <div 
              class="year-bar-fill"
              :style="{ width: (year.percentage || 0) + '%' }"
            ></div>
          </div>
          <span class="year-stats">
            {{ year.verified }}/{{ year.total }} ({{ (year.percentage || 0).toFixed(0) }}%)
          </span>
        </div>
      </div>
    </div>

    <!-- Tabs: Verified vs Unverified -->
    <div class="tabs">
      <button 
        @click="activeTab = 'verified'" 
        :class="{ active: activeTab === 'verified' }"
        class="tab-button"
      >
        ✅ Verified ({{ verifiedReceipts.length }})
      </button>
      <button 
        @click="activeTab = 'unverified'" 
        :class="{ active: activeTab === 'unverified' }"
        class="tab-button"
      >
        ❌ Unverified ({{ unverifiedReceipts.length }})
      </button>
    </div>

    <!-- Receipts Table -->
    <div class="receipts-table-container" v-if="activeTab === 'verified'">
      <table class="receipts-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Vendor</th>
            <th>Amount</th>
            <th>Category</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="receipt in verifiedReceipts.slice(0, 50)" :key="receipt.receipt_id">
            <td>{{ formatDate(receipt.receipt_date) }}</td>
            <td>{{ receipt.vendor_name }}</td>
            <td class="amount">${{ parseFloat(receipt.gross_amount).toFixed(2) }}</td>
            <td>{{ receipt.category }}</td>
            <td><span class="badge verified">✅ Verified</span></td>
            <td>
              <button 
                @click="unverifyReceipt(receipt.receipt_id)"
                class="btn-small danger"
              >
                Remove
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="table-note" v-if="verifiedReceipts.length > 50">
        Showing 50 of {{ verifiedReceipts.length }} receipts
      </p>
    </div>

    <div class="receipts-table-container" v-if="activeTab === 'unverified'">
      <table class="receipts-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Vendor</th>
            <th>Amount</th>
            <th>Category</th>
            <th>Status</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="receipt in unverifiedReceipts.slice(0, 50)" :key="receipt.receipt_id">
            <td>{{ formatDate(receipt.receipt_date) }}</td>
            <td>{{ receipt.vendor_name }}</td>
            <td class="amount">${{ parseFloat(receipt.gross_amount).toFixed(2) }}</td>
            <td>{{ receipt.category }}</td>
            <td>
              <span class="badge unverified">
                {{ receipt.status }}
              </span>
            </td>
            <td>
              <button 
                @click="verifyReceipt(receipt.receipt_id)"
                class="btn-small success"
              >
                Verify
              </button>
            </td>
          </tr>
        </tbody>
      </table>
      <p class="table-note" v-if="unverifiedReceipts.length > 50">
        Showing 50 of {{ unverifiedReceipts.length }} receipts
      </p>
    </div>

    <!-- Loading/Error States -->
    <div class="loading" v-if="loading">
      <p>Loading verification data...</p>
    </div>
    <div class="error" v-if="error">
      <p>⚠️ {{ error }}</p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ReceiptVerificationWidget',
  data() {
    return {
      summary: {},
      yearStats: [],
      verifiedReceipts: [],
      unverifiedReceipts: [],
      activeTab: 'verified',
      loading: true,
      error: null
    };
  },
  mounted() {
    this.loadData();
  },
  methods: {
    async loadData() {
      try {
        this.loading = true;
        this.error = null;

        // Load summary
        const summaryRes = await fetch('/api/receipts/verification/summary');
        if (!summaryRes.ok) throw new Error('Failed to load summary');
        this.summary = await summaryRes.json();

        // Load year breakdown
        const yearRes = await fetch('/api/receipts/verification/by-year');
        if (!yearRes.ok) throw new Error('Failed to load year stats');
        this.yearStats = await yearRes.json();

        // Load verified receipts
        const verifiedRes = await fetch('/api/receipts/verification/verified?limit=500');
        if (!verifiedRes.ok) throw new Error('Failed to load verified receipts');
        this.verifiedReceipts = await verifiedRes.json();

        // Load unverified receipts
        const unverifiedRes = await fetch('/api/receipts/verification/unverified?limit=500');
        if (!unverifiedRes.ok) throw new Error('Failed to load unverified receipts');
        this.unverifiedReceipts = await unverifiedRes.json();
      } catch (e) {
        this.error = e.message;
        console.error('Error loading verification data:', e);
      } finally {
        this.loading = false;
      }
    },
    async verifyReceipt(receiptId) {
      try {
        const res = await fetch(`/api/receipts/verification/verify/${receiptId}`, {
          method: 'POST'
        });
        if (!res.ok) throw new Error('Failed to verify receipt');
        await this.loadData();
      } catch (e) {
        this.error = e.message;
      }
    },
    async unverifyReceipt(receiptId) {
      if (!confirm('Remove verification from this receipt?')) return;
      try {
        const res = await fetch(`/api/receipts/verification/unverify/${receiptId}`, {
          method: 'POST'
        });
        if (!res.ok) throw new Error('Failed to unverify receipt');
        await this.loadData();
      } catch (e) {
        this.error = e.message;
      }
    },
    formatDate(dateStr) {
      if (!dateStr) return '—';
      return new Date(dateStr).toLocaleDateString('en-CA');
    }
  }
};
</script>

<style scoped>
.receipt-verification-widget {
  padding: 20px;
  background: #f5f5f5;
  border-radius: 8px;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.header {
  margin-bottom: 20px;
}

.header h3 {
  margin: 0 0 5px 0;
  font-size: 20px;
  color: #333;
}

.subtitle {
  margin: 0;
  color: #666;
  font-size: 13px;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  background: white;
  padding: 15px;
  border-radius: 6px;
  border-left: 4px solid #999;
}

.stat-card.verified {
  border-left-color: #4caf50;
}

.stat-card.unverified {
  border-left-color: #f44336;
}

.stat-card.percentage {
  border-left-color: #2196f3;
}

.stat-label {
  font-size: 12px;
  color: #666;
  margin-bottom: 5px;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
  color: #333;
}

/* Progress Bar */
.progress-container {
  margin-bottom: 20px;
}

.progress-bar {
  width: 100%;
  height: 20px;
  background: #ddd;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #4caf50, #81c784);
  transition: width 0.3s ease;
}

.progress-text {
  margin: 0;
  font-size: 12px;
  color: #666;
}

/* Year Breakdown */
.year-breakdown {
  background: white;
  padding: 15px;
  border-radius: 6px;
  margin-bottom: 20px;
}

.year-breakdown h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: #333;
}

.year-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.year-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.year-label {
  width: 40px;
  font-weight: bold;
  color: #333;
}

.year-bar {
  flex: 1;
  height: 20px;
  background: #eee;
  border-radius: 4px;
  overflow: hidden;
}

.year-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #4caf50, #81c784);
}

.year-stats {
  width: 100px;
  text-align: right;
  font-size: 12px;
  color: #666;
}

/* Tabs */
.tabs {
  display: flex;
  gap: 10px;
  margin-bottom: 15px;
  border-bottom: 1px solid #ddd;
}

.tab-button {
  padding: 10px 15px;
  border: none;
  background: transparent;
  color: #666;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  font-weight: 500;
  transition: all 0.3s ease;
}

.tab-button.active {
  color: #2196f3;
  border-bottom-color: #2196f3;
}

/* Table */
.receipts-table-container {
  background: white;
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 15px;
}

.receipts-table {
  width: 100%;
  border-collapse: collapse;
}

.receipts-table th {
  background: #f5f5f5;
  padding: 12px;
  text-align: left;
  font-weight: 600;
  color: #333;
  border-bottom: 1px solid #ddd;
  font-size: 12px;
}

.receipts-table td {
  padding: 10px 12px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 13px;
}

.receipts-table tbody tr:hover {
  background: #fafafa;
}

.amount {
  font-weight: 500;
  color: #2196f3;
}

.badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 3px;
  font-size: 11px;
  font-weight: 500;
}

.badge.verified {
  background: #e8f5e9;
  color: #2e7d32;
}

.badge.unverified {
  background: #ffebee;
  color: #c62828;
}

/* Buttons */
.btn-small {
  padding: 5px 10px;
  border: none;
  border-radius: 4px;
  font-size: 11px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s ease;
}

.btn-small.success {
  background: #4caf50;
  color: white;
}

.btn-small.success:hover {
  background: #388e3c;
}

.btn-small.danger {
  background: #f44336;
  color: white;
}

.btn-small.danger:hover {
  background: #d32f2f;
}

.table-note {
  padding: 10px 12px;
  margin: 0;
  background: #f5f5f5;
  font-size: 12px;
  color: #666;
  border-top: 1px solid #ddd;
}

/* Loading/Error */
.loading,
.error {
  padding: 20px;
  text-align: center;
  background: white;
  border-radius: 6px;
  margin-bottom: 15px;
}

.loading {
  color: #2196f3;
}

.error {
  background: #ffebee;
  color: #c62828;
}
</style>
