<template>
  <div class="receipt-form-container">
    <h2>{{ editMode ? 'Edit Receipt' : 'Add New Receipt' }}</h2>
    
    <form @submit.prevent="submitReceipt" class="receipt-form">
      <!-- Row 1: Amount and Date -->
      <div class="form-row">
        <div class="form-group">
          <label for="gross_amount">Total Amount *</label>
          <input 
            type="number" 
            id="gross_amount" 
            v-model.number="form.gross_amount" 
            step="0.01" 
            @input="autoCalculateGST"
            @keyup.enter="submitReceipt"
            required 
            placeholder="0.00"
            autofocus
          />
        </div>

        <div class="form-group">
          <label for="receipt_date">Date *</label>
          <input 
            type="date" 
            id="receipt_date" 
            v-model="form.receipt_date" 
            required 
          />
        </div>

        <div class="form-group">
          <label for="category">Category *</label>
          <select id="category" v-model="form.category" @change="onCategoryChange" required>
            <option value="">-- Select --</option>
            <option value="fuel">Fuel</option>
            <option value="maintenance">Vehicle Maintenance</option>
            <option value="insurance">Insurance</option>
            <option value="office">Office Supplies</option>
            <option value="meals">Meals & Entertainment</option>
            <option value="client_beverages">Client Beverages</option>
            <option value="client_supplies">Client Supplies</option>
            <option value="client_food">Client Food</option>
            <option value="professional">Professional Services</option>
            <option value="utilities">Utilities</option>
            <option value="rent">Rent</option>
            <option value="wages">Wages</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>

      <!-- Row 2: Invoice #, Description, Bank Transaction ID -->
      <div class="form-row">
        <div class="form-group" style="max-width: 120px;">
          <label for="invoice_number">Invoice #</label>
          <input 
            type="text" 
            id="invoice_number" 
            v-model="form.invoice_number" 
            maxlength="10"
            placeholder="e.g., 12345"
          />
        </div>

        <div class="form-group" style="flex: 1;">
          <label for="description">Description</label>
          <input
            type="text" 
            id="description" 
            v-model="form.description" 
            placeholder="Additional notes..."
          />
        </div>

        <div class="form-group" style="max-width: 150px;">
          <label for="banking_transaction_id">Bank Trans ID</label>
          <input 
            type="text" 
            id="banking_transaction_id" 
            v-model="form.banking_transaction_id" 
            readonly
            class="readonly-input"
            placeholder="(linked)"
            title="Linked banking transaction ID"
          />
        </div>
      </div>

      <!-- Row 3: Vendor with Fuzzy Search -->
      <div class="form-group">
        <label for="vendor_name">Vendor *</label>
        <input 
          type="text" 
          id="vendor_name" 
          v-model="form.vendor_name" 
          @input="searchVendors"
          @focus="showSuggestions = true"
          @blur="loadVendorProfile"
          placeholder="Type to search vendors..."
          required 
          autocomplete="off"
        />
        
        <!-- Vendor Suggestions Dropdown -->
        <div v-if="showSuggestions && vendorSuggestions.length > 0" class="suggestions-dropdown">
          <div 
            v-for="vendor in vendorSuggestions" 
            :key="typeof vendor === 'string' ? vendor : vendor.name"
            @click="selectVendor(vendor)"
            class="suggestion-item"
          >
            <div class="vendor-main">{{ typeof vendor === 'string' ? vendor : vendor.name }}</div>
            <div v-if="typeof vendor === 'object' && vendor.canonical !== vendor.name" class="vendor-canonical">
              → Standardized: {{ vendor.canonical }}
            </div>
          </div>
        </div>

        <!-- Add New Vendor Hint -->
        <div v-if="form.vendor_name && !isExistingVendor" class="new-vendor-hint">
          <span class="icon">✨</span> Add "{{ form.vendor_name }}" as new vendor
        </div>
      </div>

      <!-- Row 4: Charter + Driver Reimburse checkbox (for fuel category) -->
      <div v-if="form.category === 'fuel' || form.is_personal" class="form-row">
        <div class="form-group" style="flex: 1;">
          <label for="charter_number">Charter/Reserve #</label>
          <input 
            type="text" 
            id="charter_number" 
            v-model="form.charter_number" 
            placeholder="e.g., RES12345"
          />
          <small class="hint">For reference only</small>
        </div>

        <div class="form-group inline" style="align-self: center;">
          <label>
            <input type="checkbox" v-model="form.is_personal" />
            Driver Reimburse
          </label>
        </div>

        <div v-if="form.is_personal" class="form-group inline" style="align-self: center;">
          <label>
            <input type="checkbox" v-model="form.is_driver_personal" />
            Driver Personal (exclude)
          </label>
        </div>
      </div>

      <!-- Row 5: Driver, Vehicle, Fuel (for fuel or reimbursements) -->
      <div v-if="form.category === 'fuel' || form.is_personal" class="form-row">
        <div class="form-group" style="flex: 2;">
          <label for="employee_id">Driver</label>
          <select id="employee_id" v-model="form.employee_id">
            <option value="">-- Select Driver --</option>
            <option v-for="driver in drivers" :key="driver.employee_id" :value="driver.employee_id">
              {{ driver.first_name }} {{ driver.last_name }}
            </option>
          </select>
        </div>

        <div v-if="form.category === 'fuel'" class="form-group" style="flex: 2;">
          <label for="vehicle_id">Vehicle</label>
          <select id="vehicle_id" v-model="form.vehicle_id">
            <option value="">-- Select --</option>
            <option v-for="vehicle in vehicles" :key="vehicle.vehicle_id" :value="vehicle.vehicle_id">
              {{ vehicle.number }} - {{ vehicle.make }} {{ vehicle.model }}
            </option>
          </select>
        </div>

        <div v-if="form.category === 'fuel'" class="form-group" style="max-width: 130px;">
          <label for="liters">Fuel (L)</label>
          <input 
            type="number" 
            id="liters" 
            v-model.number="form.liters" 
            step="0.01"
            placeholder="45.5"
          />
          <span v-if="form.liters && form.gross_amount" class="price-per-liter">
            ${{ pricePerLiter }}/L
          </span>
        </div>
      </div>

      <!-- Banking Transaction Link -->
      <div v-if="editingId && (bankingMatches.length > 0 || bankingSearchPerformed)" class="banking-section">
        <h4><span class="icon">🏬</span> Banking Transaction</h4>
        
        <!-- Show matches found -->
        <div v-if="bankingMatches.length > 0">
          <div 
            v-for="match in bankingMatches" 
            :key="match.transaction_id" 
            class="banking-match-compact clickable"
            @dblclick="!match.already_matched && linkToBanking(match.transaction_id)"
            :title="match.already_matched ? 'Already linked' : 'Double-click to link'"
          >
            <div class="match-info">
              <strong>{{ match.account_number }}</strong> - {{ formatDate(match.transaction_date) }} -
              ${{ (match.debit_amount || match.credit_amount).toFixed(2) }}
              <span v-if="match.already_matched" class="badge matched">✓ Linked</span>
            </div>
            <button 
              v-if="!match.already_matched" 
              type="button"
              @click="linkToBanking(match.transaction_id)"
              class="btn btn-link-small"
            >
              Link
            </button>
          </div>
        </div>
        
        <!-- Banking search results -->
        <div v-if="bankingSearchResults.length > 0">
          <div 
            v-for="result in bankingSearchResults.slice(0, 5)" 
            :key="result.transaction_id" 
            class="banking-match-compact clickable"
            @dblclick="!result.receipt_id && linkToBanking(result.transaction_id)"
            :title="result.receipt_id ? 'Already linked' : 'Double-click to link'"
          >
            <div class="match-info">
              <strong>{{ result.account_number }}</strong> - {{ formatDate(result.transaction_date) }} -
              ${{ (result.debit_amount || result.credit_amount || 0).toFixed(2) }}
              <span v-if="result.receipt_id" class="badge matched">✓ Linked</span>
              <span v-else-if="isExactMatch(result)" class="badge exact">💰</span>
            </div>
            <button
              v-if="!result.receipt_id"
              type="button"
              @click="linkToBanking(result.transaction_id)"
              class="btn btn-link-small"
            >
              Link
            </button>
          </div>
          <p v-if="bankingSearchResults.length > 5" class="more-results">+ {{ bankingSearchResults.length - 5 }} more</p>
        </div>
      </div>

      <!-- Row 6: Tax Mode and GST -->
      <div class="form-row">
        <div class="form-group">
          <label for="tax_mode">Tax Treatment</label>
          <select id="tax_mode" v-model="taxMode" @change="autoCalculateGST">
            <option value="GST_INCL_5">GST 5% Included (AB)</option>
            <option value="GST_PST_INCL_12">GST+PST 12% Included (BC)</option>
            <option value="NO_TAX">No Tax / US / Exempt</option>
            <option value="CUSTOM">Custom Rate</option>
          </select>
        </div>

        <div class="form-group" style="max-width: 150px;">
          <label for="gst_amount">GST/Tax Amount</label>
          <input 
            type="number" 
            id="gst_amount" 
            v-model.number="form.gst_amount" 
            step="0.01" 
            placeholder="0.00"
            readonly
            class="readonly-input"
          />
        </div>

        <div v-if="taxMode === 'CUSTOM'" class="form-group" style="max-width: 120px;">
          <label for="custom_tax">Rate (%)</label>
          <input 
            type="number"
            id="custom_tax"
            v-model.number="customTaxRate"
            step="0.01"
            placeholder="e.g. 12"
            @input="autoCalculateGST"
          />
        </div>
      </div>

      <!-- Paper Verification Status -->
      <div class="form-row verification-row">
        <div class="form-group inline-checkbox">
          <label class="checkbox-label">
            <input type="checkbox" v-model="form.is_paper_verified" />
            <span class="checkbox-text">
              ✅ Physical receipt verified
            </span>
          </label>
          <small class="hint">Check this box when you've physically verified the paper receipt</small>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="form-actions">
        <button type="submit" class="btn btn-primary">
          {{ editMode ? 'Update Receipt' : 'Save Receipt' }}
        </button>
        <button type="button" @click="resetForm" class="btn btn-secondary">
          Clear
        </button>
        <button type="button" @click="refreshData" class="btn btn-info">
          Refresh
        </button>
        <button 
          v-if="editingId" 
          type="button" 
          @click="toggleBankingSearch" 
          class="btn btn-info"
        >
          {{ showBankingSearch ? 'Hide' : 'Search' }} Banking
        </button>
      </div>

      <!-- Messages -->
      <div v-if="successMessage" class="message success">
        <span class="icon">✓</span> {{ successMessage }}
      </div>
      <div v-if="errorMessage" class="message error">
        <span class="icon">✗</span> {{ errorMessage }}
      </div>

      <!-- Duplicate Receipt Warning -->
      <div v-if="duplicateReceipts.length > 0" class="message warning">
        <h4><span class="icon">⚠️</span> Potential Duplicate Receipts Found</h4>
        <div v-for="dup in duplicateReceipts" :key="dup.receipt_id" class="duplicate-item">
          <strong>Receipt #{{ dup.receipt_id }}</strong> - {{ formatDate(dup.receipt_date) }} - 
          {{ dup.vendor_name }} - ${{ dup.gross_amount.toFixed(2) }}
          <span v-if="dup.is_matched" class="badge matched">✓ Matched to Banking</span>
          <span v-else class="badge unmatched">○ Not Matched</span>
        </div>
      </div>

      <!-- Banking Transaction Matches -->
      <div v-if="bankingMatches.length > 0" class="banking-section compact">
        <h4><span class="icon">🏦</span> Banking Matches</h4>
        <div v-for="match in bankingMatches" :key="match.transaction_id" class="banking-match-compact">
          <div class="match-info">
            <strong>{{ match.account_number }}</strong> - {{ formatDate(match.transaction_date) }} -
            ${{ (match.debit_amount || match.credit_amount).toFixed(2) }}
            <span v-if="match.already_matched" class="badge matched">✓ Linked</span>
          </div>
          <button 
            v-if="!match.already_matched && editingId" 
            type="button"
            @click="linkToBanking(match.transaction_id)"
            class="btn btn-link-small"
          >
            Link
          </button>
        </div>
      </div>

      <!-- Collapsible Banking Search -->
      <div v-if="showBankingSearch" class="banking-search">
        <h4><span class="icon">🏦</span> Search Banking Transactions</h4>
        <div class="banking-search-controls">
          <input
            v-model.number="bankingSearchAmount"
            type="number"
            step="0.01"
            placeholder="Amount (optional)"
          />
          <input
            v-model="bankingSearchVendor"
            type="text"
            placeholder="Vendor or description (optional)"
          />
          <input
            v-model="bankingSearchStartDate"
            type="date"
            placeholder="Start Date"
            title="Start Date"
          />
          <input
            v-model="bankingSearchEndDate"
            type="date"
            placeholder="End Date"
            title="End Date"
          />
          <select v-model="bankingSearchAccountFilter" class="account-filter">
            <option value="">All Accounts</option>
            <option v-for="account in bankingAccounts" :key="account" :value="account">
              {{ account }}
            </option>
          </select>
          <button type="button" class="btn btn-secondary" @click="searchBankingTransactions">
            Search
          </button>
          <button type="button" class="btn btn-link" @click="clearBankingSearch">
            Clear
          </button>
        </div>
        <small class="hint">Search by amount, vendor, date range, and/or account. Results show exact amount matches highlighted.</small>

        <div v-if="bankingSearchError" class="message error">
          <span class="icon">✗</span> {{ bankingSearchError }}
        </div>
        <div v-else-if="bankingSearchLoading" class="loading">Searching...</div>
        <div v-else-if="bankingSearchPerformed && bankingSearchResults.length === 0" class="message warning">
          No banking transactions found.
        </div>

        <div v-if="bankingSearchResults.length > 0" class="banking-search-results">
          <p class="results-count">{{ bankingSearchResults.length }} transaction(s) found</p>
          <div 
            v-for="result in bankingSearchResults" 
            :key="result.transaction_id" 
            class="banking-match clickable"
            @dblclick="!result.receipt_id && editingId && linkToBanking(result.transaction_id)"
            :title="result.receipt_id ? 'Already linked' : 'Double-click to link'"
          >
            <div class="match-header">
              <strong>Account {{ result.account_number }}</strong> - {{ formatDate(result.transaction_date) }}
              <span v-if="result.receipt_id" class="badge matched">
                ✓ Linked (Receipt #{{ result.receipt_id }})
              </span>
              <span v-else-if="isExactMatch(result)" class="badge exact-match">
                💰 Exact Match
              </span>
              <span v-else class="badge available">○ Available</span>
            </div>
            <div class="match-details">
              {{ result.description || result.vendor_extracted || '(no description)' }} -
              <span class="amount" :class="{ 'exact-amount': isExactMatch(result) }">
                ${{ (result.debit_amount || result.credit_amount || 0).toFixed(2) }}
              </span>
            </div>
            <button
              v-if="!result.receipt_id && editingId"
              type="button"
              @click="linkToBanking(result.transaction_id)"
              class="btn btn-link"
            >
              Link to This Receipt
            </button>
          </div>
        </div>
      </div>
    </form>

    <!-- Recent Receipts List -->
    <div class="recent-receipts">
      <div class="receipts-header">
        <h3>Recent Receipts (Last 40)</h3>
        <div class="verification-filter">
          <label for="verificationFilter">Filter:</label>
          <select id="verificationFilter" v-model="verificationFilter" class="filter-select">
            <option value="all">All Receipts</option>
            <option value="verified">✅ Verified Only</option>
            <option value="unverified">❌ Unverified Only</option>
          </select>
        </div>
      </div>
      <div v-if="loading" class="loading">Loading...</div>
      <table v-else-if="filteredRecentReceipts.length > 0">
        <thead>
          <tr>
            <th>Date</th>
            <th>Vendor</th>
            <th>Category</th>
            <th>Amount</th>
            <th>GST</th>
            <th>Flags</th>
            <th>Verified</th>
          </tr>
        </thead>
        <tbody>
          <tr 
            v-for="receipt in filteredRecentReceipts" 
            :key="receipt.receipt_id"
            @click="loadReceiptForEdit(receipt.receipt_id)"
            class="clickable-row"
            :class="{ 'active-row': editingId === receipt.receipt_id }"
          >
            <td>{{ formatDate(receipt.receipt_date) }}</td>
            <td>{{ receipt.vendor_name }}</td>
            <td>{{ receipt.category || '-' }}</td>
            <td class="amount">${{ receipt.gross_amount.toFixed(2) }}</td>
            <td class="amount">${{ receipt.gst_amount.toFixed(2) }}</td>
            <td>
              <span v-if="receipt.is_driver_personal" class="badge driver">Driver personal</span>
              <span v-else-if="receipt.is_personal" class="badge personal">Personal</span>
              <span v-else class="badge neutral">Business</span>
            </td>
            <td class="verification-cell">
              <span v-if="receipt.is_paper_verified" class="verified-badge" :title="'Verified: ' + (receipt.paper_verification_date || 'N/A')">✅</span>
              <span v-else class="unverified-badge">❌</span>
            </td>
          </tr>
          <!-- Placeholder rows to maintain consistent height -->
          <tr v-for="i in Math.max(0, 40 - filteredRecentReceipts.length)" :key="'placeholder-' + i" class="placeholder-row">
            <td colspan="7" class="placeholder-cell">—</td>
          </tr>
        </tbody>
      </table>
      <table v-else class="empty-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Vendor</th>
            <th>Category</th>
            <th>Amount</th>
            <th>GST</th>
            <th>Flags</th>
            <th>Verified</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="i in 40" :key="'empty-' + i" class="placeholder-row">
            <td colspan="7" class="placeholder-cell">— No receipts yet —</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>
// GL accounts that should NEVER have GST calculated
// Includes: Liability accounts (loans), bank charges, interest, financial services
const GST_EXEMPT_GL_CODES = new Set([
  '2795', '2800', '2802', '2804', '2806', '2807', '2808', '2810', '2910',
  '6100', '6101', '6280', '5450', '1135', '1099'
]);

export default {
  name: 'ReceiptForm',
  data() {
    return {
      form: {
        receipt_date: new Date().toISOString().split('T')[0],
        vendor_name: '',
        invoice_number: '',
        gross_amount: null,
        gst_amount: null,
        gst_code: null,
        category: '',
        description: '',
        vehicle_id: null,
        charter_id: null,
        charter_number: '',
        employee_id: null,
        liters: null,
        is_personal: false,
        is_driver_personal: false,
        gl_account_code: null,
        banking_transaction_id: null,
        is_paper_verified: false  // Track if physical paper receipt has been checked
      },
      allVendors: [],
      vendorSuggestions: [],
      showSuggestions: false,
      showBankingSearch: false,
      vehicles: [],
      drivers: [],
      recentReceipts: [],
      loading: false,
      editMode: false,
      editingId: null,
      successMessage: '',
      errorMessage: '',
      duplicateReceipts: [],
      bankingMatches: [],
      bankingSearchAmount: null,
      bankingSearchVendor: '',
      bankingSearchStartDate: '',
      bankingSearchEndDate: '',
      bankingSearchAccountFilter: '',
      bankingSearchResults: [],
      bankingSearchLoading: false,
      bankingSearchError: '',
      bankingSearchPerformed: false,
      bankingAccounts: [],
      showDuplicateWarning: false,
      showBankingMatches: false,
      checkingMatches: false,
      taxMode: 'GST_INCL_5',
      customTaxRate: null,
      vendorProfile: null,
      verificationFilter: 'all'  // For filtering verified/unverified receipts
    };
  },
  computed: {
    isExistingVendor() {
      return this.allVendors.some(v => {
        const name = typeof v === 'string' ? v : v.name;
        return name.toLowerCase() === this.form.vendor_name.toLowerCase();
      });
    },
    pricePerLiter() {
      if (!this.form.liters || !this.form.gross_amount) return '0.00';
      return (this.form.gross_amount / this.form.liters).toFixed(2);
    },
    filteredRecentReceipts() {
      if (this.verificationFilter === 'all') {
        return this.recentReceipts;
      } else if (this.verificationFilter === 'verified') {
        return this.recentReceipts.filter(r => r.is_paper_verified === true);
      } else if (this.verificationFilter === 'unverified') {
        return this.recentReceipts.filter(r => r.is_paper_verified !== true);
      }
      return this.recentReceipts;
    }
  },
  watch: {
    'form.is_personal'(val) {
      if (!val) {
        this.form.is_driver_personal = false;
        this.autoCalculateGST();
      }
    },
    'form.is_driver_personal'(val) {
      if (val && !this.form.is_personal) {
        this.form.is_personal = true;
      }
      this.autoCalculateGST();
    }
  },
  mounted() {
    this.loadVendors();
    this.loadVehicles();
    this.loadDrivers();
    this.loadRecentReceipts();
    
    // Click outside to close suggestions
    document.addEventListener('click', this.handleClickOutside);
  },
  beforeUnmount() {
    document.removeEventListener('click', this.handleClickOutside);
  },
  methods: {
    async loadVendors() {
      try {
        const response = await fetch('http://127.0.0.1:8001/api/receipts-simple/vendors');
        if (response.ok) {
          const vendorData = await response.json();
          // Support both old format (strings) and new format (objects)
          this.allVendors = vendorData.map(v => 
            typeof v === 'string' ? { name: v, canonical: v } : v
          );
        }
      } catch (error) {
        console.error('Failed to load vendors:', error);
      }
    },

    async loadVendorProfile() {
      if (!this.form.vendor_name) return;
      try {
        const response = await fetch(
          `http://127.0.0.1:8001/api/receipts-simple/vendor-profile?vendor=${encodeURIComponent(this.form.vendor_name)}`
        );
        if (response.ok) {
          const profile = await response.json();
          this.vendorProfile = profile;
          // Auto-set category if empty
          if (!this.form.category && profile.suggested_category) {
            this.form.category = profile.suggested_category;
          }
          // Auto-set tax mode based on gst_code
          if (profile.suggested_gst_code) {
            if (profile.suggested_gst_code === 'NO_TAX') {
              this.taxMode = 'NO_TAX';
            } else if (profile.suggested_gst_code === 'GST_PST_INCL_12') {
              this.taxMode = 'GST_PST_INCL_12';
            } else {
              this.taxMode = 'GST_INCL_5';
            }
            this.autoCalculateGST();
          }
        }
      } catch (error) {
        console.error('Failed to load vendor profile:', error);
      }
    },
    
    async loadVehicles() {
      try {
        const response = await fetch('http://127.0.0.1:8001/api/vehicles');
        if (response.ok) {
          this.vehicles = await response.json();
        }
      } catch (error) {
        console.error('Failed to load vehicles:', error);
      }
    },
    
    async loadDrivers() {
      try {
        const response = await fetch('http://127.0.0.1:8001/api/employees?role=driver');
        if (response.ok) {
          this.drivers = await response.json();
        }
      } catch (error) {
        console.error('Failed to load drivers:', error);
      }
    },
    
    async loadRecentReceipts() {
      this.loading = true;
      try {
        const response = await fetch('http://127.0.0.1:8001/api/receipts-simple/?limit=40');
        if (response.ok) {
          this.recentReceipts = await response.json();
        }
      } catch (error) {
        console.error('Failed to load recent receipts:', error);
      } finally {
        this.loading = false;
      }
    },
    
    refreshData() {
      this.loadRecentReceipts();
      this.loadVendors();
      this.successMessage = 'Data refreshed';
      setTimeout(() => { this.successMessage = ''; }, 2000);
    },
    
    searchVendors() {
      if (!this.form.vendor_name) {
        this.vendorSuggestions = [];
        return;
      }
      
      const searchTerm = this.form.vendor_name.toLowerCase();
      this.vendorSuggestions = this.allVendors
        .filter(vendor => {
          const name = typeof vendor === 'string' ? vendor : vendor.name;
          return name.toLowerCase().includes(searchTerm);
        })
        .sort((a, b) => {
          const aName = typeof a === 'string' ? a : a.name;
          const bName = typeof b === 'string' ? b : b.name;
          // Prioritize vendors that START with the search term
          const aStarts = aName.toLowerCase().startsWith(searchTerm);
          const bStarts = bName.toLowerCase().startsWith(searchTerm);
          if (aStarts && !bStarts) return -1;
          if (!aStarts && bStarts) return 1;
          return aName.localeCompare(bName);
        })
        .slice(0, 10); // Top 10 matches
    },
    
    selectVendor(vendor) {
      const vendorName = typeof vendor === 'string' ? vendor : vendor.name;
      this.form.vendor_name = vendorName;
      this.showSuggestions = false;
      this.vendorSuggestions = [];
      this.loadVendorProfile();
    },
    
    handleClickOutside(event) {
      const container = this.$el.querySelector('.form-group');
      if (!container || !container.contains(event.target)) {
        this.showSuggestions = false;
      }
    },
    
    onCategoryChange() {
      // Reset fuel-specific fields when category changes
      if (this.form.category !== 'fuel') {
        this.form.vehicle_id = null;
        this.form.charter_id = null;
        this.form.charter_number = '';
        this.form.employee_id = null;
        this.form.liters = null;
        this.charterLookupResult = null;
      }
    },
    
    async loadReceiptForEdit(receiptId) {
      try {
        const response = await fetch(`http://127.0.0.1:8001/api/receipts-simple/${receiptId}`);
        if (!response.ok) {
          throw new Error('Failed to load receipt');
        }
        
        const receipt = await response.json();
        
        // Populate form with receipt data - use explicit boolean conversion
        this.form = {
          receipt_date: receipt.receipt_date,
          vendor_name: receipt.vendor_name,
          invoice_number: receipt.invoice_number || '',
          gross_amount: receipt.gross_amount,
          gst_amount: receipt.gst_amount,
          gst_code: receipt.gst_code,
          category: receipt.category || '',
          description: receipt.description || '',
          vehicle_id: receipt.vehicle_id || null,
          charter_id: receipt.charter_id || null,
          charter_number: receipt.reserve_number || '',
          employee_id: receipt.employee_id || null,
          liters: receipt.fuel_amount || null,
          is_personal: receipt.is_personal === true,
          is_driver_personal: receipt.is_driver_personal === true,
          banking_transaction_id: receipt.banking_transaction_id || null,
          gl_account_code: receipt.gl_account_code || null,
          is_paper_verified: receipt.is_paper_verified === true
        };
        
        // Set edit mode
        this.editMode = true;
        this.editingId = receiptId;
        
      } catch (error) {
        console.error('Failed to load receipt for editing:', error);
        this.errorMessage = 'Failed to load receipt: ' + error.message;
      }
    },
    
    // Helper: Check if tax should be skipped
    shouldSkipTax() {
      if (this.form.is_driver_personal) return true;
      if (this.form.gl_account_code && GST_EXEMPT_GL_CODES.has(this.form.gl_account_code)) return true;
      return false;
    },
    
    // Helper: Get tax rate from current mode
    getTaxRate() {
      if (this.taxMode === 'NO_TAX') return 0;
      if (this.taxMode === 'GST_PST_INCL_12') return 0.12;
      if (this.taxMode === 'CUSTOM' && this.customTaxRate !== null) {
        return Number(this.customTaxRate) / 100;
      }
      return 0.05; // Default AB GST
    },
    
    // Helper: Calculate tax from gross amount
    calculateTaxFromGross(grossAmount, rate) {
      if (rate === 0) return 0;
      return Number.parseFloat((grossAmount * rate / (1 + rate)).toFixed(2));
    },
    
    // Simplified GST calculation
    autoCalculateGST() {
      if (this.shouldSkipTax()) {
        this.form.gst_amount = 0;
        this.form.gst_code = this.form.is_driver_personal ? 'DRIVER_PERSONAL' : 'GST_EXEMPT';
        return;
      }
      
      if (this.form.gross_amount) {
        const rate = this.getTaxRate();
        this.form.gst_amount = this.calculateTaxFromGross(this.form.gross_amount, rate);
        this.form.gst_code = rate === 0 ? 'NO_TAX' : this.taxMode;
        
        // Check for duplicates and banking matches
        if (this.form.vendor_name && this.form.receipt_date) {
          this.checkForMatches();
        }
      } else {
        this.form.gst_amount = null;
      }
    },
    
    async checkForMatches() {
      if (!this.form.gross_amount || !this.form.receipt_date) return;
      
      this.checkingMatches = true;
      
      try {
        // Check for duplicate receipts
        if (this.form.vendor_name) {
          const dupResponse = await fetch(
            `http://127.0.0.1:8001/api/receipts-simple/check-duplicates?` +
            `vendor=${encodeURIComponent(this.form.vendor_name)}&` +
            `amount=${this.form.gross_amount}&` +
            `date=${this.form.receipt_date}&` +
            `days_window=7`
          );
          if (dupResponse.ok) {
            this.duplicateReceipts = await dupResponse.json();
          }
        }
        
        // Check for banking transaction matches
        const bankResponse = await fetch(
          `http://127.0.0.1:8001/api/receipts-simple/match-banking?` +
          `amount=${this.form.gross_amount}&` +
          `date=${this.form.receipt_date}&` +
          `days_window=7` +
          (this.form.vendor_name ? `&vendor=${encodeURIComponent(this.form.vendor_name)}` : '')
        );
        if (bankResponse.ok) {
          this.bankingMatches = await bankResponse.json();
        }
        
      } catch (error) {
        console.error('Failed to check matches:', error);
      } finally {
        this.checkingMatches = false;
      }
    },
    
    async linkToBanking(transactionId) {
      if (!this.editingId) {
        this.errorMessage = 'Receipt must be saved before linking to banking';
        return;
      }
      
      try {
        const response = await fetch(
          `http://127.0.0.1:8001/api/receipts-simple/${this.editingId}/link-banking/${transactionId}`,
          { method: 'POST' }
        );
        
        if (response.ok) {
          this.successMessage = 'Receipt linked to banking transaction successfully!';
          // Refresh banking matches to show updated status
          this.checkForMatches();
        } else {
          const error = await response.json();
          this.errorMessage = error.detail || 'Failed to link to banking';
        }
      } catch (error) {
        this.errorMessage = 'Error linking to banking: ' + error.message;
      }
    },

    async searchBankingTransactions() {
      const vendor = (this.bankingSearchVendor || '').trim();
      const hasAmount = this.bankingSearchAmount !== null && this.bankingSearchAmount !== '';

      this.bankingSearchError = '';
      this.bankingSearchPerformed = true;
      this.bankingSearchResults = [];

      if (!hasAmount && !vendor) {
        this.bankingSearchError = 'Enter an amount or vendor to search.';
        return;
      }

      const params = new URLSearchParams();
      if (hasAmount) {
        params.set('amount', this.bankingSearchAmount);
      }
      if (vendor) {
        params.set('vendor', vendor);
      }
      if (this.bankingSearchStartDate) {
        params.set('start_date', this.bankingSearchStartDate);
      }
      if (this.bankingSearchEndDate) {
        params.set('end_date', this.bankingSearchEndDate);
      }
      params.set('limit', '1000');

      this.bankingSearchLoading = true;
      try {
        const response = await fetch(
          `http://127.0.0.1:8001/api/banking/search?${params.toString()}`
        );
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to search banking transactions');
        }
        let results = await response.json();
        
        // Filter by account if selected
        if (this.bankingSearchAccountFilter) {
          results = results.filter(r => r.account_number === this.bankingSearchAccountFilter);
        }
        
        // Extract unique accounts for the account filter
        this.bankingAccounts = [...new Set(results.map(r => r.account_number).filter(Boolean))];
        
        this.bankingSearchResults = results;
      } catch (error) {
        this.bankingSearchError = error.message || 'Failed to search banking transactions';
      } finally {
        this.bankingSearchLoading = false;
      }
    },

    clearBankingSearch() {
      this.bankingSearchAmount = null;
      this.bankingSearchVendor = '';
      this.bankingSearchStartDate = '';
      this.bankingSearchEndDate = '';
      this.bankingSearchAccountFilter = '';
      this.bankingSearchResults = [];
      this.bankingSearchError = '';
      this.bankingSearchPerformed = false;
      this.bankingAccounts = [];
    },

    isExactMatch(result) {
      // Check if the banking transaction amount exactly matches the receipt amount
      if (!this.bankingSearchAmount) return false;
      const transactionAmount = result.debit_amount || result.credit_amount || 0;
      return Math.abs(transactionAmount - this.bankingSearchAmount) < 0.01;
    },
    
    // Helper: Build fuel-specific description
    buildFuelDescription() {
      let description = this.form.description || '';
      if (this.form.category !== 'fuel') return description;
      
      const fuelDetails = [];
      if (this.form.liters) {
        fuelDetails.push(`${this.form.liters}L @ $${this.pricePerLiter}/L`);
      }
      if (this.form.charter_number) {
        fuelDetails.push(`Charter: ${this.form.charter_number}`);
      }
      
      if (fuelDetails.length > 0) {
        return description ? `${description} | ${fuelDetails.join(', ')}` : fuelDetails.join(', ');
      }
      return description;
    },
    
    // Helper: Build receipt payload for API
    buildReceiptPayload() {
      return {
        receipt_date: this.form.receipt_date,
        vendor_name: this.form.vendor_name,
        invoice_number: this.form.invoice_number || null,
        gross_amount: Number.parseFloat(this.form.gross_amount),
        gst_amount: this.form.is_driver_personal ? 0 : this.form.gst_amount,
        gst_code: this.form.is_driver_personal ? 'DRIVER_PERSONAL' : this.form.gst_code,
        category: this.form.category,
        description: this.buildFuelDescription(),
        vehicle_id: this.form.vehicle_id || null,
        charter_id: this.form.charter_id || null,
        reserve_number: this.form.charter_number || null,
        employee_id: this.form.employee_id || null,
        fuel_amount: this.form.liters || null,
        is_personal: !!this.form.is_personal,
        is_driver_personal: !!this.form.is_driver_personal,
        is_paper_verified: this.form.is_paper_verified || false
      };
    },
    
    // Helper: API call to save/update receipt
    async saveReceiptAPI(payload, isUpdate) {
      const url = isUpdate 
        ? `http://127.0.0.1:8001/api/receipts-simple/${this.editingId}` 
        : 'http://127.0.0.1:8001/api/receipts-simple/';
      const method = isUpdate ? 'PUT' : 'POST';
      
      const response = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `Failed to ${isUpdate ? 'update' : 'save'} receipt`);
      }
      
      return await response.json();
    },
    
    // Simplified submit function
    async submitReceipt() {
      this.successMessage = '';
      this.errorMessage = '';
      
      try {
        const isUpdate = this.editMode && this.editingId;
        const payload = this.buildReceiptPayload();
        const savedReceipt = await this.saveReceiptAPI(payload, isUpdate);
        
        this.successMessage = `Receipt #${savedReceipt.receipt_id} ${isUpdate ? 'updated' : 'saved'} successfully!`;
        this.editingId = savedReceipt.receipt_id;
        this.editMode = true;
        
        // Reload data
        await this.loadReceiptForEdit(savedReceipt.receipt_id);
        this.loadVendors();
        this.loadRecentReceipts();
        this.checkForMatches();
        
        setTimeout(() => { this.successMessage = ''; }, 5000);
      } catch (error) {
        this.errorMessage = error.message || 'An error occurred while saving the receipt';
        console.error('Submit error:', error);
      }
    },
    
    resetForm() {
      this.form = {
        receipt_date: new Date().toISOString().split('T')[0],
        vendor_name: '',
        invoice_number: '',
        gross_amount: null,
        gst_amount: null,
        gst_code: null,
        category: '',
        description: '',
        vehicle_id: null,
        charter_id: null,
        charter_number: '',
        employee_id: null,
        liters: null,
        is_personal: false,
        is_driver_personal: false,
        is_paper_verified: false
      };
      this.editMode = false;
      this.editingId = null;
      this.showSuggestions = false;
      this.showBankingSearch = false;
      this.vendorSuggestions = [];
      this.duplicateReceipts = [];
      this.bankingMatches = [];
      this.clearBankingSearch();
      this.charterLookupResult = null;
      this.successMessage = '';
      this.errorMessage = '';
    },
    
    toggleBankingSearch() {
      this.showBankingSearch = !this.showBankingSearch;
      if (this.showBankingSearch) {
        // Pre-populate search with receipt values
        this.bankingSearchAmount = this.form.gross_amount;
        this.bankingSearchVendor = this.form.vendor_name;
        this.bankingSearchStartDate = this.form.receipt_date;
      }
    },
    
    formatDate(dateStr) {
      if (!dateStr) return '-';
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-CA'); // YYYY-MM-DD format
    }
  }
};
</script>

<style scoped>
.receipt-form-container {
  max-width: 900px;
  margin: 0 auto;
  padding: 10px;
  max-height: calc(100vh - 60px);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

h2 {
  color: #2c3e50;
  margin-bottom: 10px;
  font-size: 1.3rem;
}

h3 {
  color: #34495e;
  margin-top: 10px;
  margin-bottom: 8px;
  font-size: 1.1rem;
}

.receipt-form {
  background: #fff;
  padding: 15px;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.form-group {
  margin-bottom: 12px;
  position: relative;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.form-group.inline {
  display: flex;
  align-items: center;
  gap: 10px;
}

/* Paper Verification Checkbox */
.verification-row {
  background: #f0f9ff;
  border: 2px solid #0891b2;
  border-radius: 6px;
  padding: 12px;
  margin: 16px 0;
}

.form-group.inline-checkbox {
  margin-bottom: 0;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  font-weight: 500;
  color: #0e7490;
}

.checkbox-label input[type="checkbox"] {
  width: auto;
  cursor: pointer;
  transform: scale(1.3);
}

.checkbox-text {
  font-size: 14px;
  font-weight: 600;
}

.verification-row .hint {
  margin-left: 32px;
  margin-top: 5px;
  font-style: italic;
  color: #0e7490;
}

label {
  display: block;
  margin-bottom: 3px;
  font-weight: 600;
  color: #34495e;
  font-size: 0.85rem;
}

input, select, textarea {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 13px;
  box-sizing: border-box;
}

input:focus, select:focus, textarea:focus {
  outline: none;
  border-color: #3498db;
  box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
}

.readonly-input {
  background-color: #f8f9fa;
  cursor: not-allowed;
}

.hint {
  display: block;
  margin-top: 5px;
  font-size: 12px;
  color: #7f8c8d;
}

/* Vendor Suggestions Dropdown */
.suggestions-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  right: 0;
  background: white;
  border: 1px solid #ddd;
  border-top: none;
  border-radius: 0 0 4px 4px;
  max-height: 200px;
  overflow-y: auto;
  z-index: 1000;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.suggestion-item {
  padding: 10px;
  cursor: pointer;
  transition: background 0.2s;
}

.suggestion-item:hover {
  background: #ecf0f1;
}

.new-vendor-hint {
  margin-top: 8px;
  padding: 8px 12px;
  background: #d4edda;
  border: 1px solid #c3e6cb;
  border-radius: 4px;
  font-size: 13px;
  color: #155724;
}

/* Fuel Section */
.fuel-section {
  background: #fff8e1;
  border: 1px solid #ffc107;
  border-radius: 4px;
  padding: 4px 8px;
}

.price-per-liter {
  display: block;
  margin-top: 3px;
  font-size: 11px;
  color: #1976d2;
  font-weight: 600;
}

/* Banking Section */
.banking-section {
  margin: 12px 0;
  padding: 10px;
  background: #e8f5e9;
  border: 1px solid #4caf50;
  border-radius: 4px;
}

.banking-section h4 {
  margin: 0 0 8px 0;
  font-size: 13px;
  color: #2e7d32;
}

.banking-match-compact {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px;
  margin: 4px 0;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 3px;
  font-size: 12px;
}

.banking-match-compact.clickable {
  cursor: pointer;
  transition: background 0.2s;
}

.banking-match-compact.clickable:hover {
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.banking-match.clickable {
  cursor: pointer;
  transition: all 0.2s;
}

.banking-match.clickable:hover {
  background: #f0f7ff;
  box-shadow: 0 2px 4px rgba(0,0,0,0.08);
}

.match-info {
  flex: 1;
}

.more-results {
  margin-top: 8px;
  font-size: 12px;
  color: #666;
  font-style: italic;
}

/* Buttons */
.form-actions {
  display: flex;
  gap: 8px;
  margin-top: 15px;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.3s;
}

.btn-primary {
  background: #1a5a7f;
  color: #ffffff;
}

.btn-primary:hover {
  background: #144a6b;
}

.btn-secondary {
  background: #5a6769;
  color: #ffffff;
}

.btn-secondary:hover {
  background: #4a5557;
}

.btn-info {
  background: #0e6574;
  color: #ffffff;
}

.btn-info:hover {
  background: #0b5461;
}

.btn-link-small {
  padding: 3px 10px;
  font-size: 11px;
  background: #0e6574;
  color: #ffffff;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  transition: background 0.3s;
}

.btn-link-small:hover {
  background: #0b5461;
}

/* Messages */
.message {
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
}

.message.success {
  background: #d4edda;
  border: 1px solid #c3e6cb;
  color: #155724;
}

.message.error {
  background: #f8d7da;
  border: 1px solid #f5c6cb;
  color: #721c24;
}

.message.warning {
  background: #fff3cd;
  border: 1px solid #ffeaa7;
  color: #856404;
}

.message.info {
  background: #d1ecf1;
  border: 1px solid #bee5eb;
  color: #0c5460;
}

.message h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  font-weight: 600;
}

.banking-search {
  margin-top: 12px;
  padding: 10px;
  background: #f7f9fc;
  border: 1px solid #e1e5ee;
  border-radius: 6px;
}

.banking-search-controls {
  display: grid;
  grid-template-columns: 1fr 1.5fr 1fr 1fr 1.2fr auto auto;
  gap: 8px;
  align-items: center;
}

.banking-search-results {
  margin-top: 8px;
}

.duplicate-item, .banking-match {
  padding: 8px;
  margin: 5px 0;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 4px;
  font-size: 13px;
}

.match-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.match-details {
  font-size: 12px;
  color: #666;
}

.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
  margin-left: 8px;
}

.badge.matched {
  background: #d4edda;
  color: #155724;
}

.badge.unmatched {
  background: #f8d7da;
  color: #721c24;
}

.badge.available {
  background: #d1ecf1;
  color: #0c5460;
}

.badge.exact-match {
  background: #d4f1d4;
  color: #155724;
  font-weight: 700;
}

.badge.personal {
  background: #ffeaa7;
  color: #6d5a2e;
}

.badge.driver {
  background: #f8d7da;
  color: #721c24;
}

.badge.neutral {
  background: #e2e3e5;
  color: #555;
}

.btn-link {
  padding: 4px 12px;
  margin-top: 4px;
  font-size: 12px;
  background: #0e6574;
  color: #ffffff;
}

.btn-link:hover {
  background: #0b5461;
}

.exact-amount {
  font-weight: 700;
  color: #155724;
}

.results-count {
  font-size: 13px;
  color: #666;
  margin-bottom: 8px;
  font-weight: 600;
}

.account-filter {
  padding: 4px 8px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 14px;
}

.vendor-main {
  font-weight: 600;
}

.vendor-canonical {
  font-size: 11px;
  color: #6c757d;
  margin-top: 2px;
  font-style: italic;
}

.icon {
  margin-right: 8px;
}

@media (max-width: 768px) {
  .banking-search-controls {
    grid-template-columns: 1fr;
  }
  
  .account-filter {
    width: 100%;
  }
}

/* Recent Receipts */
.recent-receipts {
  margin-top: 15px;
  padding: 12px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  max-height: 600px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

.loading {
  text-align: center;
  padding: 20px;
  color: #7f8c8d;
}

.empty-table tbody {
  max-height: 550px;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
  display: block;
  overflow-x: auto;
  font-size: 12px;
}

thead {
  background: #34495e;
  color: white;
  display: table;
  width: 100%;
  table-layout: fixed;
  position: sticky;
  top: 0;
  z-index: 10;
}

tbody {
  display: block;
  max-height: 550px;
  overflow-y: auto;
  width: 100%;
}

tbody tr {
  display: table;
  width: 100%;
  table-layout: fixed;
}

tbody tr.clickable-row {
  cursor: pointer;
  transition: background-color 0.2s;
}

tbody tr.clickable-row:hover {
  background-color: #f0f8ff;
}

tbody tr.active-row {
  background-color: #e3f2fd;
  border-left: 4px solid #2196f3;
}

th, td {
  padding: 6px 8px;
  text-align: left;
  border-bottom: 1px solid #ecf0f1;
}

th {
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
}

td {
  font-size: 12px;
  color: #2c3e50;
}

td.amount {
  text-align: right;
  font-weight: 600;
  font-family: 'Courier New', monospace;
}

tbody tr:hover {
  background: #f8f9fa;
  cursor: pointer;
}

.placeholder-row {
  opacity: 0.3;
  pointer-events: none;
}

.placeholder-row:hover {
  background: transparent;
  cursor: default;
}

.placeholder-cell {
  text-align: center;
  color: #bdc3c7;
  font-style: italic;
  padding: 8px;
}

/* Verification Filter Styles */
.receipts-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.receipts-header h3 {
  margin: 0;
}

.verification-filter {
  display: flex;
  align-items: center;
  gap: 8px;
}

.verification-filter label {
  font-size: 13px;
  font-weight: 500;
  color: #34495e;
}

.filter-select {
  padding: 6px 10px;
  border: 1px solid #dfe6e9;
  border-radius: 4px;
  font-size: 13px;
  background-color: white;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-select:hover {
  border-color: #74b9ff;
}

.filter-select:focus {
  outline: none;
  border-color: #0984e3;
  box-shadow: 0 0 0 3px rgba(9, 132, 227, 0.1);
}

.verification-cell {
  text-align: center;
  font-size: 16px;
}

.verified-badge {
  cursor: help;
}

.unverified-badge {
  opacity: 0.5;
}
</style>
