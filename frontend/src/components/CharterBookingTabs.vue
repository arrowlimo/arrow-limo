<template>
  <div class="charter-booking-container">
    <!-- Header -->
    <div class="booking-header">
      <h1>{{ isNewBooking ? '🆕 New Charter Booking' : `📝 Edit Charter #${currentCharter?.reserve_number}` }}</h1>
      <button v-if="!isNewBooking" @click="closeBooking" class="close-btn">✕ Close</button>
    </div>

    <!-- Tab Navigation -->
    <div class="tab-nav">
      <button 
        v-for="tab in tabs" 
        :key="tab.id"
        @click="activeTab = tab.id"
        :class="['tab-button', { active: activeTab === tab.id }]"
      >
        {{ tab.icon }} {{ tab.label }}
      </button>
    </div>

    <!-- Tab Content -->
    <div class="tab-content">
      <!-- Run Charter Tab -->
      <div v-show="activeTab === 'run-charter'" class="tab-pane">
        <RunCharterTab 
          @save="saveCharter" 
          @quote-generated="handleQuoteGenerated"
        />
      </div>

      <!-- Invoice/Payments Tab -->
      <div v-show="activeTab === 'invoice'" class="tab-pane">
        <div class="coming-soon">
          <h3>💳 Invoice & Payment History</h3>
          <p>View all invoices, payments, receipts, and refunds</p>
        </div>
      </div>

      <!-- Routing Map Tab -->
      <div v-show="activeTab === 'routing'" class="tab-pane">
        <div class="coming-soon">
          <h3>🗺️ Routing Map View</h3>
          <p>Visual route map with Google Maps integration</p>
        </div>
      </div>

      <!-- Documents Tab -->
      <div v-show="activeTab === 'documents'" class="tab-pane">
        <div class="coming-soon">
          <h3>📄 Documents & Contracts</h3>
          <p>Contracts, waivers, and customer documents</p>
        </div>
      </div>

      <!-- History Tab -->
      <div v-show="activeTab === 'history'" class="tab-pane">
        <div class="coming-soon">
          <h3>📊 Charter History</h3>
          <p>Changes log and audit trail</p>
        </div>
      </div>
    </div>

    <!-- Quote Modal -->
    <div v-if="showQuoteModal" class="modal-overlay" @click="showQuoteModal = false">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h2>📊 Generated Quote</h2>
          <button @click="showQuoteModal = false" class="close-btn">✕</button>
        </div>
        
        <div class="modal-body">
          <div class="quote-display">
            <div class="quote-header-info">
              <p><strong>Customer:</strong> {{ generatedQuote?.charter?.clientName }}</p>
              <p><strong>Date:</strong> {{ generatedQuote?.charter?.charterDate }}</p>
              <p><strong>Pickup:</strong> {{ generatedQuote?.charter?.pickupTime }}</p>
              <p><strong>Passengers:</strong> {{ generatedQuote?.charter?.passengerCount }}</p>
            </div>

            <h3>Route Summary</h3>
            <div class="route-summary">
              <div v-if="generatedQuote?.charter?.isOutOfTown" class="route-list">
                <div class="route-item primary">
                  <span class="route-label">Primary A</span>
                  <span>Leave Red Deer For {{ generatedQuote?.charter?.primaryA?.address }}</span>
                  <span class="route-time">{{ generatedQuote?.charter?.primaryA?.time }}</span>
                </div>
                <div class="route-item primary">
                  <span class="route-label">Primary B</span>
                  <span>Pickup In {{ generatedQuote?.charter?.primaryB?.address }}</span>
                  <span class="route-time">{{ generatedQuote?.charter?.primaryB?.time }}</span>
                </div>
                <div v-for="(stop, idx) in generatedQuote?.charter?.routingStops" :key="idx" class="route-item">
                  <span class="route-label">{{ idx + 1 }}</span>
                  <span>{{ stop.type }} {{ stop.address }}</span>
                  <span class="route-time">{{ stop.time }}</span>
                </div>
                <div class="route-item secondary">
                  <span class="route-label">Secondary B</span>
                  <span>Drop Off At {{ generatedQuote?.charter?.secondaryB?.address }}</span>
                  <span class="route-time">{{ generatedQuote?.charter?.secondaryB?.time }}</span>
                </div>
                <div class="route-item secondary">
                  <span class="route-label">Secondary A</span>
                  <span>Returned to Red Deer {{ generatedQuote?.charter?.secondaryA?.address }}</span>
                  <span class="route-time">{{ generatedQuote?.charter?.secondaryA?.time }}</span>
                </div>
              </div>
            </div>

            <h3>Vehicle Options</h3>
            <div class="vehicle-quotes">
              <div v-for="(vehicle, idx) in generatedQuote?.vehicles" :key="idx" class="vehicle-quote-card">
                <div class="vehicle-header">
                  <h4>{{ formatVehicleType(vehicle.type) }}</h4>
                  <span class="vehicle-qty">Quantity: {{ vehicle.quantity }}</span>
                </div>
                <p class="vehicle-purpose">{{ vehicle.purpose }}</p>
                <div class="vehicle-pricing">
                  <div class="price-line">
                    <span>Base Rate:</span>
                    <span>${{ calculateVehicleRate(vehicle.type) }}</span>
                  </div>
                  <div class="price-line">
                    <span>× {{ vehicle.quantity }} vehicle(s)</span>
                    <span>${{ (calculateVehicleRate(vehicle.type) * vehicle.quantity).toFixed(2) }}</span>
                  </div>
                  <div class="price-line total">
                    <span>Subtotal:</span>
                    <span>${{ (calculateVehicleRate(vehicle.type) * vehicle.quantity).toFixed(2) }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div class="quote-total">
              <h3>Grand Total: ${{ calculateGrandTotal() }}</h3>
              <p class="gst-note">*Includes 5% GST</p>
            </div>
          </div>
        </div>

        <div class="modal-footer">
          <button @click="emailQuote" class="btn-primary">📧 Email Quote</button>
          <button @click="printQuote" class="btn-secondary">🖨️ Print Quote</button>
          <button @click="convertToBooking" class="btn-success">✅ Convert to Booking</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import RunCharterTab from './charter/RunCharterTab.vue'

const route = useRoute()
const router = useRouter()

// State
const activeTab = ref('run-charter') // Default to Run Charter tab
const currentCharter = ref(null)
const isNewBooking = computed(() => !currentCharter.value)
const showQuoteModal = ref(false)
const generatedQuote = ref(null)

// Tabs configuration
const tabs = [
  { id: 'run-charter', label: 'Run Charter', icon: '🚗' },
  { id: 'invoice', label: 'Invoice/Payments', icon: '💳' },
  { id: 'routing', label: 'Route Map', icon: '🗺️' },
  { id: 'documents', label: 'Documents', icon: '📄' },
  { id: 'history', label: 'History', icon: '📊' }
]

// Vehicle pricing lookup (would come from API in production)
const vehicleRates = {
  sedan: 150,
  suv: 200,
  stretch: 350,
  shuttle: 400,
  party_bus: 600,
  coach: 800
}

// Methods
function saveCharter(charterData) {
  console.log('Saving charter:', charterData)
  // TODO: API call to save charter
}

function handleQuoteGenerated(quoteData) {
  generatedQuote.value = quoteData
  showQuoteModal.value = true
}

function formatVehicleType(type) {
  const names = {
    sedan: 'Sedan (1-4 passengers)',
    suv: 'SUV (1-6 passengers)',
    stretch: 'Stretch Limousine (1-8 passengers)',
    shuttle: 'Shuttle Bus (8-15 passengers)',
    party_bus: 'Party Bus (16-26 passengers)',
    coach: 'Coach Bus (27-56 passengers)'
  }
  return names[type] || type
}

function calculateVehicleRate(type) {
  return vehicleRates[type] || 0
}

function calculateGrandTotal() {
  if (!generatedQuote.value?.vehicles) return '0.00'
  
  const total = generatedQuote.value.vehicles.reduce((sum, v) => {
    return sum + (calculateVehicleRate(v.type) * v.quantity)
  }, 0)
  
  return total.toFixed(2)
}

function emailQuote() {
  console.log('Emailing quote...')
  // TODO: Implement email functionality
}

function printQuote() {
  console.log('Printing quote...')
  window.print()
}

function convertToBooking() {
  showQuoteModal.value = false
  // Set status to Confirmed and save
  console.log('Converting quote to confirmed booking...')
}

function closeBooking() {
  router.push('/dispatch')
}

onMounted(() => {
  // Load charter if editing existing
  const charterId = route.params.id
  if (charterId) {
    // TODO: Load charter data
    console.log('Loading charter:', charterId)
  }
})
</script>

<style scoped>
.charter-booking-container {
  min-height: 100vh;
  background: #f5f7fa;
}

.booking-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.booking-header h1 {
  margin: 0;
  font-size: 1.8rem;
}

.close-btn {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 1rem;
  transition: all 0.3s;
}

.close-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.tab-nav {
  background: white;
  border-bottom: 2px solid #e2e8f0;
  display: flex;
  padding: 0 2rem;
  gap: 0.5rem;
}

.tab-button {
  padding: 1rem 1.5rem;
  background: transparent;
  border: none;
  border-bottom: 3px solid transparent;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 600;
  color: #718096;
  transition: all 0.3s;
}

.tab-button:hover {
  color: #2d3748;
  background: #f7fafc;
}

.tab-button.active {
  color: #667eea;
  border-bottom-color: #667eea;
  background: #f8f9ff;
}

.tab-content {
  padding: 2rem;
}

.tab-pane {
  animation: fadeIn 0.3s;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.coming-soon {
  background: white;
  padding: 4rem;
  border-radius: 8px;
  text-align: center;
  color: #a0aec0;
}

.coming-soon h3 {
  color: #2d3748;
  margin-bottom: 1rem;
}

/* Quote Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 2rem;
}

.modal-content {
  background: white;
  border-radius: 12px;
  max-width: 900px;
  width: 100%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
  padding: 1.5rem 2rem;
  border-bottom: 2px solid #e2e8f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: white;
  border-radius: 12px 12px 0 0;
}

.modal-header h2 {
  margin: 0;
}

.modal-body {
  padding: 2rem;
}

.quote-display {
  
}

.quote-header-info {
  background: #f7fafc;
  padding: 1rem;
  border-radius: 6px;
  margin-bottom: 1.5rem;
}

.quote-header-info p {
  margin: 0.5rem 0;
}

.route-summary {
  background: #f7fafc;
  padding: 1rem;
  border-radius: 6px;
  margin-bottom: 1.5rem;
}

.route-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.route-item {
  display: grid;
  grid-template-columns: 100px 1fr 80px;
  gap: 1rem;
  padding: 0.75rem;
  background: white;
  border-radius: 4px;
  border-left: 4px solid #cbd5e0;
}

.route-item.primary {
  border-left-color: #667eea;
}

.route-item.secondary {
  border-left-color: #48bb78;
}

.route-label {
  font-weight: 700;
  color: #2d3748;
}

.route-time {
  color: #718096;
  text-align: right;
}

.vehicle-quotes {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.vehicle-quote-card {
  background: #f8f9ff;
  padding: 1.5rem;
  border-radius: 8px;
  border: 2px solid #667eea;
}

.vehicle-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.vehicle-header h4 {
  margin: 0;
  color: #2d3748;
}

.vehicle-qty {
  background: #667eea;
  color: white;
  padding: 0.25rem 0.75rem;
  border-radius: 12px;
  font-size: 0.85rem;
  font-weight: 600;
}

.vehicle-purpose {
  color: #718096;
  font-style: italic;
  margin-bottom: 1rem;
}

.vehicle-pricing {
  border-top: 1px solid #cbd5e0;
  padding-top: 1rem;
}

.price-line {
  display: flex;
  justify-content: space-between;
  margin-bottom: 0.5rem;
}

.price-line.total {
  font-weight: 700;
  font-size: 1.1rem;
  color: #667eea;
  margin-top: 0.5rem;
  padding-top: 0.5rem;
  border-top: 2px solid #cbd5e0;
}

.quote-total {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 1.5rem;
  border-radius: 8px;
  text-align: center;
}

.quote-total h3 {
  margin: 0;
  font-size: 2rem;
}

.gst-note {
  margin: 0.5rem 0 0 0;
  opacity: 0.9;
  font-size: 0.9rem;
}

.modal-footer {
  padding: 1.5rem 2rem;
  border-top: 2px solid #e2e8f0;
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
}

.btn-primary, .btn-secondary, .btn-success {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-primary {
  background: #667eea;
  color: white;
}

.btn-primary:hover {
  background: #5568d3;
}

.btn-secondary {
  background: #e2e8f0;
  color: #2d3748;
}

.btn-secondary:hover {
  background: #cbd5e0;
}

.btn-success {
  background: #48bb78;
  color: white;
}

.btn-success:hover {
  background: #38a169;
}
</style>
