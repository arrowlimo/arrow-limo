<template>
  <div class="receipt-form-container">
    <h2>{{ editMode ? 'Edit Receipt' : 'Add New Receipt' }}</h2>
    
    <form @submit.prevent="submitReceipt" class="receipt-form">
      <!-- Date -->
      <div class="form-group">
        <label for="receipt_date">Date *</label>
        <input 
          type="date" 
          id="receipt_date" 
          v-model="form.receipt_date" 
          required 
        />
      </div>

      <!-- Vendor with Fuzzy Search -->
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

      <!-- Category -->
      <div class="form-group">
        <label for="category">Category *</label>
        <select id="category" v-model="form.category" @change="onCategoryChange" required>
          <option value="">-- Select Category --</option>
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

      <!-- Conditional Fuel Section -->
      <div v-if="form.category === 'fuel'" class="fuel-section">
        <h3><span class="icon">⛽</span> Fuel Details</h3>
        
        <div class="form-group">
          <label for="vehicle_id">Vehicle</label>
          <select id="vehicle_id" v-model="form.vehicle_id">
            <option value="">-- Select Vehicle --</option>
            <option v-for="vehicle in vehicles" :key="vehicle.vehicle_id" :value="vehicle.vehicle_id">
              {{ vehicle.number }} - {{ vehicle.make }} {{ vehicle.model }}
            </option>
          </select>
        </div>

        <div class="form-group">
          <label for="liters">Liters</label>
          <input 
            type="number" 
            id="liters" 
            v-model.number="form.liters" 
            step="0.01"
            placeholder="e.g., 45.5"
          />
          <span v-if="form.liters && form.gross_amount" class="price-per-liter">
            = ${{ pricePerLiter }} / liter
          </span>
        </div>

        <div class="form-group">
          <label for="charter_number">Charter Number</label>
          <input 
            type="text" 
            id="charter_number" 
            v-model="form.charter_number" 
            placeholder="e.g., RES12345"
          />
        </div>
      </div>

      <!-- Amount -->
      <div class="form-group">
        <label for="gross_amount">Total Amount *</label>
        <input 
          type="number" 
          id="gross_amount" 
          v-model.number="form.gross_amount" 
          step="0.01" 
          @input="autoCalculateGST"
          required 
          placeholder="0.00"
        />
      </div>

      <!-- Tax mode -->
      <div class="form-group">
        <label for="tax_mode">Tax Treatment</label>
        <select id="tax_mode" v-model="taxMode" @change="autoCalculateGST">
          <option value="GST_INCL_5">GST 5% Included (AB)</option>
          <option value="GST_PST_INCL_12">GST+PST 12% Included (BC example)</option>
          <option value="NO_TAX">No Tax / US / Exempt</option>
          <option value="CUSTOM">Custom Rate (included)</option>
        </select>
        <div v-if="taxMode === 'CUSTOM'" class="form-group" style="margin-top:8px;">
          <label for="custom_tax">Custom Tax Rate (%)</label>
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

      <!-- GST (Auto-calculated) -->
      <div class="form-group">
        <label for="gst_amount">GST Amount</label>
        <input 
          type="number" 
          id="gst_amount" 
          v-model.number="form.gst_amount" 
          step="0.01" 
          placeholder="Auto-calculated (5%)"
          readonly
          class="readonly-input"
        />
        <small class="hint">Calculated as 5% GST included in total</small>
      </div>

      <!-- Description -->
      <div class="form-group">
        <label for="description">Description</label>
        <textarea 
          id="description" 
          v-model="form.description" 
          rows="3"
          placeholder="Additional notes..."
        ></textarea>
      </div>

      <!-- Personal / business toggle -->
      <div class="form-group inline">
        <label>
          <input type="checkbox" v-model="form.is_personal" />
          Mark as personal / reimburse driver
        </label>
        <small class="hint">If checked, owner_personal_amount is set to full amount.</small>
      </div>

      <div class="form-group inline" v-if="form.is_personal">
        <label>
          <input type="checkbox" v-model="form.is_driver_personal" />
          Driver personal (exclude from books)
        </label>
        <small class="hint">Marks with DRIVER_PERSONAL code and zero owner draw.</small>
      </div>

      <!-- Action Buttons -->
      <div class="form-actions">
        <button type="submit" class="btn btn-primary">
          {{ editMode ? 'Update Receipt' : 'Save Receipt' }}
        </button>
        <button type="button" @click="resetForm" class="btn btn-secondary">
          Clear
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
      <div v-if="bankingMatches.length > 0" class="message info">
        <h4><span class="icon">🏦</span> Matching Banking Transactions Found</h4>
        <div v-for="match in bankingMatches" :key="match.transaction_id" class="banking-match">
          <div class="match-header">
            <strong>Account {{ match.account_number }}</strong> - {{ formatDate(match.transaction_date) }}
            <span v-if="match.already_matched" class="badge matched">
              ✓ Already Linked (Receipt #{{ match.existing_receipt_id }})
            </span>
            <span v-else class="badge available">○ Available</span>
          </div>
          <div class="match-details">
            {{ match.description }} - 
            <span class="amount">${{ (match.debit_amount || match.credit_amount).toFixed(2) }}</span>
          </div>
          <button 
            v-if="!match.already_matched && editingId" 
            type="button"
            @click="linkToBanking(match.transaction_id)"
            class="btn btn-link"
          >
            Link to This Receipt
          </button>
        </div>
      </div>
    </form>

    <!-- Recent Receipts List -->
    <div class="recent-receipts">
      <h3>Recent Receipts</h3>
      <div v-if="loading" class="loading">Loading...</div>
      <table v-else-if="recentReceipts.length > 0">
        <thead>
          <tr>
            <th>Date</th>
            <th>Vendor</th>
            <th>Category</th>
            <th>Amount</th>
            <th>GST</th>
            <th>Flags</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="receipt in recentReceipts" :key="receipt.receipt_id">
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
          </tr>
        </tbody>
      </table>
      <p v-else class="no-data">No recent receipts</p>
    </div>
  </div>
</template>

<script>
export default {
  name: 'ReceiptForm',
  data() {
    return {
      form: {
        receipt_date: new Date().toISOString().split('T')[0],
        vendor_name: '',
        gross_amount: null,
        gst_amount: null,
        gst_code: null,
        category: '',
        description: '',
        vehicle_id: null,
        liters: null,
        charter_number: '',
        is_personal: false,
        is_driver_personal: false
      },
      allVendors: [],
      vendorSuggestions: [],
      showSuggestions: false,
      vehicles: [],
      recentReceipts: [],
      loading: false,
      editMode: false,
      editingId: null,
      successMessage: '',
      errorMessage: '',
      duplicateReceipts: [],
      bankingMatches: [],
      showDuplicateWarning: false,
      showBankingMatches: false,
      checkingMatches: false,
      taxMode: 'GST_INCL_5',
      customTaxRate: null,
      vendorProfile: null
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
    
    async loadRecentReceipts() {
      this.loading = true;
      try {
        const response = await fetch('http://127.0.0.1:8001/api/receipts-simple/?limit=20');
        if (response.ok) {
          this.recentReceipts = await response.json();
        }
      } catch (error) {
        console.error('Failed to load recent receipts:', error);
      } finally {
        this.loading = false;
      }
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
        this.form.liters = null;
        this.form.charter_number = '';
      }
    },
    
    autoCalculateGST() {
      if (this.form.is_driver_personal) {
        this.form.gst_amount = 0;
        this.form.gst_code = 'DRIVER_PERSONAL';
        return;
      }
      if (this.form.gross_amount) {
        let rate = 0.05;
        if (this.taxMode === 'NO_TAX') {
          rate = 0;
        } else if (this.taxMode === 'GST_PST_INCL_12') {
          rate = 0.12;
        } else if (this.taxMode === 'CUSTOM' && this.customTaxRate !== null) {
          rate = Number(this.customTaxRate) / 100;
        }

        if (rate === 0) {
          this.form.gst_amount = 0;
          this.form.gst_code = 'NO_TAX';
        } else {
          this.form.gst_amount = parseFloat(
            (this.form.gross_amount * rate / (1 + rate)).toFixed(2)
          );
          this.form.gst_code = this.taxMode;
        }
        
        // Check for duplicates and banking matches after amount is entered
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
    
    async submitReceipt() {
      this.successMessage = '';
      this.errorMessage = '';
      
      try {
        // Build fuel description if applicable
        let description = this.form.description || '';
        if (this.form.category === 'fuel') {
          const fuelDetails = [];
          if (this.form.liters) {
            fuelDetails.push(`${this.form.liters}L @ $${this.pricePerLiter}/L`);
          }
          if (this.form.charter_number) {
            fuelDetails.push(`Charter: ${this.form.charter_number}`);
          }
          if (fuelDetails.length > 0) {
            description = description 
              ? `${description} | ${fuelDetails.join(', ')}`
              : fuelDetails.join(', ');
          }
        }
        
        const payload = {
          receipt_date: this.form.receipt_date,
          vendor_name: this.form.vendor_name,
          gross_amount: parseFloat(this.form.gross_amount),
          gst_amount: this.form.is_driver_personal ? 0 : this.form.gst_amount,
          gst_code: this.form.is_driver_personal ? 'DRIVER_PERSONAL' : this.form.gst_code,
          category: this.form.category,
          description: description,
          vehicle_id: this.form.vehicle_id || null,
          is_personal: !!this.form.is_personal,
          is_driver_personal: !!this.form.is_driver_personal
        };
        
        const response = await fetch('http://127.0.0.1:8001/api/receipts-simple/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to save receipt');
        }
        
        const savedReceipt = await response.json();
        this.successMessage = `Receipt #${savedReceipt.receipt_id} saved successfully!`;
        
        // Set editing mode to enable banking linkage
        this.editingId = savedReceipt.receipt_id;
        this.editMode = true;
        
        // Reload vendors and receipts
        this.loadVendors();
        this.loadRecentReceipts();
        
        // Check for banking matches now that receipt is saved
        this.checkForMatches();
        
        // Clear message after 5 seconds
        setTimeout(() => {
          this.successMessage = '';
        }, 5000);
        
      } catch (error) {
        this.errorMessage = error.message || 'An error occurred while saving the receipt';
        console.error('Submit error:', error);
      }
    },
    
    resetForm() {
      this.form = {
        receipt_date: new Date().toISOString().split('T')[0],
        vendor_name: '',
        gross_amount: null,
        gst_amount: null,
        gst_code: null,
        category: '',
        description: '',
        vehicle_id: null,
        liters: null,
        charter_number: '',
        is_personal: false,
        is_driver_personal: false
      };
      this.editMode = false;
      this.editingId = null;
      this.showSuggestions = false;
      this.vendorSuggestions = [];
      this.duplicateReceipts = [];
      this.bankingMatches = [];
      this.successMessage = '';
      this.errorMessage = '';
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
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

h2 {
  color: #2c3e50;
  margin-bottom: 20px;
}

h3 {
  color: #34495e;
  margin-top: 20px;
  margin-bottom: 15px;
}

.receipt-form {
  background: #fff;
  padding: 30px;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.form-group {
  margin-bottom: 20px;
  position: relative;
}

.form-group.inline {
  display: flex;
  align-items: center;
  gap: 10px;
}

label {
  display: block;
  margin-bottom: 5px;
  font-weight: 600;
  color: #34495e;
}

input, select, textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
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
  margin: 25px 0;
  padding: 20px;
  background: #fff8e1;
  border: 2px solid #ffc107;
  border-radius: 8px;
}

.fuel-section h3 {
  margin-top: 0;
  color: #f57c00;
}

.price-per-liter {
  display: inline-block;
  margin-left: 10px;
  padding: 4px 8px;
  background: #e3f2fd;
  border-radius: 4px;
  font-size: 12px;
  color: #1976d2;
  font-weight: 600;
}

/* Buttons */
.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 25px;
}

.btn {
  padding: 12px 24px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.3s;
}

.btn-primary {
  background: #3498db;
  color: white;
}

.btn-primary:hover {
  background: #2980b9;
}

.btn-secondary {
  background: #95a5a6;
  color: white;
}

.btn-secondary:hover {
  background: #7f8c8d;
}

/* Messages */
.message {
  margin-top: 20px;
  padding: 12px 16px;
  border-radius: 4px;
  font-size: 14px;
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

.badge.personal {
  background: #ffeaa7;
  color: #8a6d3b;
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
  background: #17a2b8;
  color: white;
}

.btn-link:hover {
  background: #138496;
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

/* Recent Receipts */
.recent-receipts {
  margin-top: 40px;
  padding: 20px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

.loading {
  text-align: center;
  padding: 20px;
  color: #7f8c8d;
}

.no-data {
  text-align: center;
  padding: 20px;
  color: #95a5a6;
  font-style: italic;
}

table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 15px;
}

thead {
  background: #34495e;
  color: white;
}

th, td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ecf0f1;
}

th {
  font-weight: 600;
  font-size: 13px;
  text-transform: uppercase;
}

td {
  font-size: 14px;
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
</style>
