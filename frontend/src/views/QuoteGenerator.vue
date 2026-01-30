<template>
  <div class="quote-generator-container">
    <h1>📋 Charter Quote Generator</h1>
    
    <!-- Quote Details Section -->
    <div class="quote-details-section">
      <h2>Quote Details</h2>
      
      <div class="form-grid">
        <!-- Basic Info -->
        <div class="form-group">
          <label>Client Name:</label>
          <input v-model="form.clientName" type="text" placeholder="Enter client name" />
        </div>
        
        <div class="form-group">
          <label>Pickup Location:</label>
          <input v-model="form.pickupLocation" type="text" value="Red Deer" />
        </div>
        
        <div class="form-group">
          <label>Dropoff Location:</label>
          <input v-model="form.dropoffLocation" type="text" value="Red Deer" />
        </div>
        
        <div class="form-group">
          <label>Passengers:</label>
          <input v-model.number="form.passengers" type="number" min="1" max="50" value="20" />
        </div>
        
        <!-- Vehicle Type Selection -->
        <div class="form-group">
          <label>Vehicle Type: <span class="required">*</span></label>
          <select v-model="form.vehicleType">
            <option value="">-- Select Vehicle Type --</option>
            <option value="Luxury Sedan (4 pax)">Luxury Sedan (4 pax)</option>
            <option value="Luxury SUV (3-4 pax)">Luxury SUV (3-4 pax)</option>
            <option value="Sedan (3-4 pax)">Sedan (3-4 pax)</option>
            <option value="Sedan Stretch (6 Pax)">Sedan Stretch (6 Pax)</option>
            <option value="Party Bus (20 pax)">Party Bus (20 pax)</option>
            <option value="Party Bus (27 pax)">Party Bus (27 pax)</option>
            <option value="Shuttle Bus (18 pax)">Shuttle Bus (18 pax)</option>
            <option value="SUV Stretch (13 pax)">SUV Stretch (13 pax)</option>
          </select>
        </div>
        
        <!-- Gratuity Rate -->
        <div class="form-group">
          <label>Gratuity Rate:</label>
          <div class="input-with-suffix">
            <input v-model.number="form.gratuityRate" type="number" min="0" max="100" value="18" />
            <span>%</span>
          </div>
        </div>
      </div>
      
      <!-- Booking Type Choices -->
      <div class="booking-types-section">
        <h3>Booking Types: <span class="required">*</span></h3>
        <div class="checkbox-grid">
          <label class="checkbox-label">
            <input v-model="form.bookingTypes.flatRate" type="checkbox" />
            Flat Rate
          </label>
          <label class="checkbox-label">
            <input v-model="form.bookingTypes.hourly" type="checkbox" checked />
            Hourly
          </label>
          <label class="checkbox-label">
            <input v-model="form.bookingTypes.splitRun" type="checkbox" checked />
            Split Run
          </label>
          <label class="checkbox-label">
            <input v-model="form.bookingTypes.splitStandby" type="checkbox" />
            Split + Standby
          </label>
          <label class="checkbox-label">
            <input v-model="form.bookingTypes.tradeServices" type="checkbox" />
            Trade of Services
          </label>
          <label class="checkbox-label">
            <input v-model="form.bookingTypes.baseRate" type="checkbox" />
            Base Rate
          </label>
        </div>
      </div>
      
      <div class="form-options">
        <label class="checkbox-label">
          <input v-model="form.includeGST" type="checkbox" checked />
          Include GST (5%)
        </label>
      </div>
    </div>
    
    <!-- Tabs for Quote Methods -->
    <div class="tabs-section">
      <div class="tab-buttons">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          :class="['tab-button', { active: activeTab === tab.id }]"
          @click="activeTab = tab.id"
        >
          {{ tab.label }}
        </button>
      </div>
      
      <!-- Tab 1: Hourly Rate -->
      <div v-if="activeTab === 'hourly'" class="tab-content">
        <h3>Hourly Rate Quote</h3>
        <div class="form-grid">
          <div class="form-group">
            <label>Hours:</label>
            <div class="input-with-suffix">
              <input v-model.number="pricing.hourly.hours" type="number" min="0.5" max="24" step="0.5" value="8" />
              <span>hours</span>
            </div>
          </div>
          <div class="form-group">
            <label>Rate per Hour:</label>
            <div class="input-with-prefix">
              <span>$</span>
              <input v-model.number="pricing.hourly.rate" type="number" min="50" max="1000" step="10" value="300" />
            </div>
          </div>
        </div>
      </div>
      
      <!-- Tab 2: Package -->
      <div v-if="activeTab === 'package'" class="tab-content">
        <h3>Fixed Package Pricing</h3>
        <div class="form-grid">
          <div class="form-group">
            <label>Package Description:</label>
            <input v-model="pricing.package.description" type="text" placeholder="e.g., 8 hours" value="8 hours" />
          </div>
          <div class="form-group">
            <label>Package Price:</label>
            <div class="input-with-prefix">
              <span>$</span>
              <input v-model.number="pricing.package.price" type="number" min="100" max="5000" step="50" value="1550" />
            </div>
          </div>
          <div class="form-group full-width">
            <label>Package Includes:</label>
            <textarea 
              v-model="pricing.package.includes" 
              placeholder="e.g., Includes up to 3 stops, up to 2 hours wait time, etc."
              rows="3"
            ></textarea>
          </div>
        </div>
      </div>
      
      <!-- Tab 3: Split Run -->
      <div v-if="activeTab === 'splitRun'" class="tab-content">
        <h3>Split Run with Multiple Segments</h3>
        <div class="split-table">
          <table>
            <thead>
              <tr>
                <th>Segment Description</th>
                <th>Hours</th>
                <th>Rate/Hour</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(segment, idx) in pricing.splitRun" :key="idx">
                <td>
                  <input v-model="segment.description" type="text" placeholder="e.g., From Hotel to Airport" />
                </td>
                <td>
                  <input v-model.number="segment.hours" type="number" min="0.5" max="24" step="0.5" />
                </td>
                <td>
                  <div class="input-with-prefix">
                    <span>$</span>
                    <input v-model.number="segment.rate" type="number" min="50" max="1000" step="10" />
                  </div>
                </td>
                <td>
                  <button @click="removeSplitSegment(idx)" class="btn-remove">Remove</button>
                </td>
              </tr>
            </tbody>
          </table>
          <button @click="addSplitSegment" class="btn-add">+ Add Segment</button>
        </div>
      </div>
      
      <!-- Tab 4: Extra Charges -->
      <div v-if="activeTab === 'extras'" class="tab-content">
        <h3>Extra Charges & Adjustments</h3>
        <div class="form-grid">
          <div class="form-group">
            <label>Extra Stops:</label>
            <input v-model.number="pricing.extras.extraStops" type="number" min="0" value="0" />
            <small>@ $25/stop</small>
          </div>
          <div class="form-group">
            <label>Wait Time (Hours):</label>
            <input v-model.number="pricing.extras.waitTime" type="number" min="0" max="24" step="0.5" value="0" />
            <small>@ $50/hour</small>
          </div>
          <div class="form-group">
            <label>
              <input v-model="pricing.extras.cleaning" type="checkbox" />
              Interior Cleaning ($150)
            </label>
          </div>
          <div class="form-group">
            <label>Fuel Surcharge:</label>
            <div class="input-with-prefix">
              <span>$</span>
              <input v-model.number="pricing.extras.fuelSurcharge" type="number" min="0" step="5" value="0" />
            </div>
          </div>
          <div class="form-group full-width">
            <label>Custom Charges:</label>
            <textarea 
              v-model="pricing.extras.customCharges" 
              placeholder="Custom charges (one per line): Description: Amount"
              rows="4"
            ></textarea>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Results Section -->
    <div class="results-section">
      <h2>Quote Comparison Results</h2>
      
      <div v-if="quoteResults" class="results-display">
        <div class="results-header">
          <h3>{{ quoteResults.header }}</h3>
        </div>
        
        <table class="results-table">
          <thead>
            <tr>
              <th>Quote Method</th>
              <th>Subtotal</th>
              <th>GST</th>
              <th>Gratuity</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="quote in quoteResults.quotes" :key="quote.method">
              <td>{{ quote.name }}</td>
              <td>${{ quote.subtotal.toFixed(2) }}</td>
              <td>${{ quote.gst.toFixed(2) }}</td>
              <td>${{ quote.gratuity.toFixed(2) }}</td>
              <td class="total">${{ quote.total.toFixed(2) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    
    <!-- Charter Terms -->
    <div class="terms-section">
      <h2>Charter Agreement & Terms</h2>
      <div class="terms-display">
        <ol>
          <li><strong>Cancellation Policy:</strong> Cancellations must be made 48 hours in advance for full refund</li>
          <li><strong>Payment Terms:</strong> 50% deposit required to confirm, balance due 7 days before service</li>
          <li><strong>No-Show:</strong> No-show charges: 50% of quoted total</li>
          <li><strong>Extra Stops:</strong> Additional stops beyond agreed route: $25.00 per stop</li>
          <li><strong>Wait Time:</strong> Wait time beyond 15 minutes: $50.00 per hour</li>
          <li><strong>Fuel Surcharge:</strong> Fuel surcharge of 10% applies if diesel exceeds $1.50/liter</li>
          <li><strong>Cleaning:</strong> Interior cleaning if required: $150.00</li>
          <li><strong>Vehicle Change:</strong> Vehicle substitution permitted only with client approval</li>
          <li><strong>Gratuity:</strong> Gratuity not included; 18% recommended based on service quality</li>
        </ol>
      </div>
    </div>
    
    <!-- Action Buttons -->
    <div class="action-buttons">
      <button @click="calculateQuotes" class="btn-primary">🔄 Calculate All Quotes</button>
      <button v-if="quoteResults" @click="printQuote" class="btn-secondary">🖨️ Print Quote</button>
      <button v-if="quoteResults" @click="saveQuote" class="btn-secondary">💾 Save Quote</button>
      <button @click="resetForm" class="btn-secondary">Reset</button>
    </div>
    
    <!-- Toast Messages -->
    <div v-if="toast.message" :class="['toast', toast.type]">
      {{ toast.message }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const activeTab = ref('hourly')
const quoteResults = ref(null)
const toast = ref({ message: '', type: 'success' })

const tabs = [
  { id: 'hourly', label: '💰 Step 1: Hourly Rate' },
  { id: 'package', label: '📦 Step 2: Package' },
  { id: 'splitRun', label: '🔄 Step 3: Split Run' },
  { id: 'extras', label: '➕ Extra Charges' }
]

const form = ref({
  clientName: '',
  pickupLocation: 'Red Deer',
  dropoffLocation: 'Red Deer',
  passengers: 20,
  vehicleType: '',
  gratuityRate: 18,
  includeGST: true,
  bookingTypes: {
    flatRate: false,
    hourly: true,
    splitRun: true,
    splitStandby: false,
    tradeServices: false,
    baseRate: false
  }
})

const pricing = ref({
  hourly: {
    hours: 8,
    rate: 300
  },
  package: {
    description: '8 hours',
    price: 1550,
    includes: 'Includes up to 3 stops, up to 2 hours wait time'
  },
  splitRun: [
    { description: 'Segment 1', hours: 2, rate: 300 },
    { description: 'Segment 2', hours: 1.5, rate: 250 }
  ],
  extras: {
    extraStops: 0,
    waitTime: 0,
    cleaning: false,
    fuelSurcharge: 0,
    customCharges: ''
  }
})

const getSelectedBookingTypes = () => {
  const selected = []
  if (form.value.bookingTypes.flatRate) selected.push('Flat Rate')
  if (form.value.bookingTypes.hourly) selected.push('Hourly')
  if (form.value.bookingTypes.splitRun) selected.push('Split Run')
  if (form.value.bookingTypes.splitStandby) selected.push('Split + Standby')
  if (form.value.bookingTypes.tradeServices) selected.push('Trade of Services')
  if (form.value.bookingTypes.baseRate) selected.push('Base Rate')
  return selected
}

const calculateGST = (amount) => {
  if (!form.value.includeGST) return { gst: 0, net: amount }
  const gst = amount * 0.05 / 1.05
  const net = amount - gst
  return { gst: Math.round(gst * 100) / 100, net: Math.round(net * 100) / 100 }
}

const calculateQuotes = () => {
  // Validation
  if (!form.value.vehicleType) {
    showToast('Please select a vehicle type', 'error')
    return
  }
  
  const selectedBookings = getSelectedBookingTypes()
  if (selectedBookings.length === 0) {
    showToast('Please select at least one booking type', 'error')
    return
  }
  
  const gstRate = form.value.gratuityRate / 100
  const header = `Quote Results - ${form.value.vehicleType} - Booking Types: ${selectedBookings.join(', ')}`
  
  // Quote 1: Hourly
  const hourlySubtotal = pricing.value.hourly.hours * pricing.value.hourly.rate
  const hourlyGST = calculateGST(hourlySubtotal)
  const hourlyGratuity = hourlySubtotal * gstRate
  const hourlyTotal = hourlySubtotal + hourlyGratuity
  
  // Quote 2: Package
  const packageGST = calculateGST(pricing.value.package.price)
  const packageGratuity = pricing.value.package.price * gstRate
  const packageTotal = pricing.value.package.price + packageGratuity
  
  // Quote 3: Split Run
  let splitSubtotal = 0
  for (const seg of pricing.value.splitRun) {
    splitSubtotal += seg.hours * seg.rate
  }
  const splitGST = calculateGST(splitSubtotal)
  const splitGratuity = splitSubtotal * gstRate
  const splitTotal = splitSubtotal + splitGratuity
  
  quoteResults.value = {
    header,
    quotes: [
      {
        method: 'hourly',
        name: 'Hourly Rate',
        subtotal: hourlySubtotal,
        gst: hourlyGST.gst,
        gratuity: hourlyGratuity,
        total: hourlyTotal
      },
      {
        method: 'package',
        name: 'Package',
        subtotal: pricing.value.package.price,
        gst: packageGST.gst,
        gratuity: packageGratuity,
        total: packageTotal
      },
      {
        method: 'splitRun',
        name: 'Split Run',
        subtotal: splitSubtotal,
        gst: splitGST.gst,
        gratuity: splitGratuity,
        total: splitTotal
      }
    ]
  }
  
  showToast('Quotes calculated successfully', 'success')
}

const printQuote = () => {
  if (!quoteResults.value) return
  
  const doc = document.createElement('div')
  doc.innerHTML = `
    <h2>${quoteResults.value.header}</h2>
    <p><strong>Client:</strong> ${form.value.clientName}</p>
    <p><strong>Pickup:</strong> ${form.value.pickupLocation}</p>
    <p><strong>Dropoff:</strong> ${form.value.dropoffLocation}</p>
    <p><strong>Passengers:</strong> ${form.value.passengers}</p>
    <table border="1" cellpadding="8">
      <tr><th>Quote Method</th><th>Subtotal</th><th>GST</th><th>Gratuity</th><th>Total</th></tr>
      ${quoteResults.value.quotes.map(q => 
        `<tr><td>${q.name}</td><td>$${q.subtotal.toFixed(2)}</td><td>$${q.gst.toFixed(2)}</td><td>$${q.gratuity.toFixed(2)}</td><td>$${q.total.toFixed(2)}</td></tr>`
      ).join('')}
    </table>
  `
  
  const printWindow = window.open('', '', 'width=800,height=600')
  printWindow.document.write(doc.innerHTML)
  printWindow.document.close()
  printWindow.print()
}

const saveQuote = () => {
  if (!quoteResults.value) return
  showToast('Quote saved successfully (database integration pending)', 'success')
}

const addSplitSegment = () => {
  pricing.value.splitRun.push({ description: '', hours: 1, rate: 300 })
}

const removeSplitSegment = (idx) => {
  pricing.value.splitRun.splice(idx, 1)
}

const resetForm = () => {
  form.value = {
    clientName: '',
    pickupLocation: 'Red Deer',
    dropoffLocation: 'Red Deer',
    passengers: 20,
    vehicleType: '',
    gratuityRate: 18,
    includeGST: true,
    bookingTypes: {
      flatRate: false,
      hourly: true,
      splitRun: true,
      splitStandby: false,
      tradeServices: false,
      baseRate: false
    }
  }
  quoteResults.value = null
}

const showToast = (message, type = 'success') => {
  toast.value = { message, type }
  setTimeout(() => {
    toast.value = { message: '', type: 'success' }
  }, 3000)
}
</script>

<style scoped>
.quote-generator-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

h1 {
  color: #2c3e50;
  margin-bottom: 2rem;
}

h2 {
  color: #34495e;
  margin-top: 2rem;
  margin-bottom: 1rem;
  border-bottom: 2px solid #3498db;
  padding-bottom: 0.5rem;
}

h3 {
  color: #34495e;
  margin-bottom: 1rem;
}

/* Sections */
.quote-details-section,
.results-section,
.terms-section {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 2rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

/* Forms */
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
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
  margin-bottom: 0.5rem;
  color: #2c3e50;
}

.form-group input,
.form-group select,
.form-group textarea {
  padding: 0.75rem;
  border: 1px solid #bdc3c7;
  border-radius: 4px;
  font-size: 1rem;
  font-family: inherit;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #3498db;
  box-shadow: 0 0 5px rgba(52, 152, 219, 0.3);
}

.form-group small {
  color: #7f8c8d;
  margin-top: 0.25rem;
}

.input-with-prefix,
.input-with-suffix {
  display: flex;
  align-items: center;
  border: 1px solid #bdc3c7;
  border-radius: 4px;
  overflow: hidden;
}

.input-with-prefix span {
  padding: 0 0.75rem;
  background: #ecf0f1;
  font-weight: 600;
  color: #2c3e50;
}

.input-with-prefix input,
.input-with-suffix input {
  border: none;
  flex: 1;
  padding: 0.75rem;
}

.input-with-suffix span {
  padding: 0 0.75rem;
  color: #7f8c8d;
}

.required {
  color: #e74c3c;
}

/* Booking Types */
.booking-types-section {
  margin-bottom: 1.5rem;
}

.checkbox-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  cursor: pointer;
  font-weight: 500;
  color: #2c3e50;
}

.checkbox-label input {
  margin-right: 0.5rem;
  cursor: pointer;
  width: 18px;
  height: 18px;
}

.form-options {
  margin-top: 1rem;
}

/* Tabs */
.tabs-section {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  margin-bottom: 2rem;
  overflow: hidden;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.tab-buttons {
  display: flex;
  background: #f8f9fa;
  border-bottom: 2px solid #ddd;
}

.tab-button {
  flex: 1;
  padding: 1rem;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.95rem;
  font-weight: 600;
  color: #7f8c8d;
  border-bottom: 3px solid transparent;
  transition: all 0.3s ease;
}

.tab-button:hover {
  background: #ecf0f1;
  color: #34495e;
}

.tab-button.active {
  color: #3498db;
  border-bottom-color: #3498db;
  background: #fff;
}

.tab-content {
  padding: 1.5rem;
}

/* Split Run Table */
.split-table {
  margin-top: 1rem;
}

.split-table table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1rem;
}

.split-table thead {
  background: #ecf0f1;
}

.split-table th {
  padding: 0.75rem;
  text-align: left;
  font-weight: 600;
  color: #2c3e50;
  border: 1px solid #bdc3c7;
}

.split-table td {
  padding: 0.75rem;
  border: 1px solid #bdc3c7;
}

.split-table input {
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #bdc3c7;
  border-radius: 4px;
}

.btn-remove {
  padding: 0.5rem 1rem;
  background: #e74c3c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
}

.btn-remove:hover {
  background: #c0392b;
}

.btn-add {
  padding: 0.75rem 1.5rem;
  background: #27ae60;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
}

.btn-add:hover {
  background: #229954;
}

/* Results */
.results-section {
  background: #fff;
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 2rem;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.results-display {
  margin-top: 1rem;
}

.results-header {
  padding: 1rem;
  background: #ecf0f1;
  border-radius: 4px;
  margin-bottom: 1rem;
}

.results-header h3 {
  margin: 0;
  color: #2c3e50;
}

.results-table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 1rem;
}

.results-table thead {
  background: #34495e;
  color: white;
}

.results-table th {
  padding: 1rem;
  text-align: right;
  font-weight: 600;
}

.results-table th:first-child {
  text-align: left;
}

.results-table td {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #ddd;
  text-align: right;
}

.results-table td:first-child {
  text-align: left;
  font-weight: 600;
  color: #2c3e50;
}

.results-table td.total {
  font-weight: 700;
  color: #27ae60;
  background: #f0fff4;
  border-top: 2px solid #27ae60;
}

/* Terms */
.terms-display {
  background: #f8f9fa;
  padding: 1.5rem;
  border-radius: 4px;
}

.terms-display ol {
  margin: 0;
  padding-left: 1.5rem;
}

.terms-display li {
  margin-bottom: 0.75rem;
  line-height: 1.6;
  color: #34495e;
}

.terms-display strong {
  color: #2c3e50;
}

/* Action Buttons */
.action-buttons {
  display: flex;
  gap: 1rem;
  justify-content: center;
  margin-top: 2rem;
  flex-wrap: wrap;
}

.btn-primary,
.btn-secondary {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  font-size: 1rem;
  transition: all 0.3s ease;
}

.btn-primary {
  background: #3498db;
  color: white;
}

.btn-primary:hover {
  background: #2980b9;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

.btn-secondary {
  background: #95a5a6;
  color: white;
}

.btn-secondary:hover {
  background: #7f8c8d;
}

/* Toast */
.toast {
  position: fixed;
  top: 20px;
  right: 20px;
  padding: 1rem 1.5rem;
  border-radius: 4px;
  color: white;
  font-weight: 600;
  z-index: 1000;
  animation: slideIn 0.3s ease, slideOut 2.7s ease forwards;
}

.toast.success {
  background: #27ae60;
}

.toast.error {
  background: #e74c3c;
}

@keyframes slideIn {
  from {
    transform: translateX(400px);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

@keyframes slideOut {
  0% {
    transform: translateX(0);
    opacity: 1;
  }
  90% {
    transform: translateX(0);
    opacity: 1;
  }
  100% {
    transform: translateX(400px);
    opacity: 0;
  }
}

/* Responsive */
@media (max-width: 768px) {
  .quote-generator-container {
    padding: 1rem;
  }
  
  .form-grid {
    grid-template-columns: 1fr;
  }
  
  .checkbox-grid {
    grid-template-columns: 1fr;
  }
  
  .tab-buttons {
    flex-wrap: wrap;
  }
  
  .tab-button {
    flex: 1;
    min-width: 150px;
    padding: 0.75rem 0.5rem;
    font-size: 0.85rem;
  }
  
  .action-buttons {
    flex-direction: column;
  }
  
  .btn-primary,
  .btn-secondary {
    width: 100%;
  }
}
</style>
