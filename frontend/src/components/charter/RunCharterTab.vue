<template>
  <div class="run-charter-tab">
    <!-- Search/Clone Header -->
    <div class="charter-search-header">
      <div class="search-bar">
        <input 
          v-model="searchQuery"
          @keyup.enter="searchCharters"
          type="text"
          placeholder="🔍 Search charter by reserve#, client name, date, or phone..."
          class="search-input"
        />
        <button @click="searchCharters" class="btn-search">Search</button>
        <button @click="clearForm" class="btn-new">➕ New Charter</button>
      </div>
      
      <!-- Search Results Dropdown -->
      <div v-if="searchResults.length > 0" class="search-results">
        <div class="results-header">
          <h4>Found {{ searchResults.length }} charter(s)</h4>
          <button @click="searchResults = []" class="close-results">✕</button>
        </div>
        <div class="results-list">
          <div 
            v-for="charter in searchResults" 
            :key="charter.id"
            @click="loadCharter(charter)"
            class="result-item"
          >
            <div class="result-main">
              <strong>{{ charter.reserve_number }}</strong> - {{ charter.client_name }}
            </div>
            <div class="result-details">
              {{ charter.charter_date }} | {{ charter.pickup_time }} | {{ charter.vehicle_type }}
            </div>
            <div class="result-actions">
              <button @click.stop="cloneCharter(charter)" class="btn-clone">📋 Clone</button>
              <button @click.stop="linkCharter(charter)" class="btn-link">🔗 Link</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Main Form Content -->
    <div class="charter-form-sections">
      <!-- RESERVATION INFORMATION -->
      <div class="form-section">
        <h2 class="section-header">📋 RESERVATION INFORMATION</h2>
        <ClientDetailsSection
          v-model:customerSearch="charterForm.client_name"
          v-model:charterDate="charterForm.charter_date"
          v-model:pickupTime="charterForm.pickup_time"
          v-model:dropoffTime="charterForm.dropoff_time"
          v-model:dispatchNotes="charterForm.dispatcher_notes"
          v-model:passengerCount="charterForm.passenger_count"
          v-model:vehicleType="charterForm.vehicle_type"
          v-model:runType="charterForm.run_type"
          v-model:airportLocation="charterForm.airport_location"
          v-model:outOfTown="charterForm.out_of_town"
          v-model:clientNotes="charterForm.client_notes"
          @extend-time="handleExtendTime"
          @vehicle-type-changed="handleVehicleTypeChange"
          @run-type-changed="handleRunTypeChange"
          @airport-changed="handleAirportChange"
        />
      </div>

      <!-- VEHICLE ASSIGNMENT -->
      <div class="form-section">
        <h2 class="section-header">🚐 VEHICLE ASSIGNMENT</h2>
        <DispatchSection
          v-model:vehicleId="charterForm.vehicle_id"
          v-model:chauffeurId="charterForm.chauffeur_id"
          @vehicle-selected="handleVehicleSelected"
          @chauffeur-selected="handleChauffeurSelected"
        />
      </div>

      <!-- ROUTING & CHARGES -->
      <div class="form-section routing-billing-section">
        <h2 class="section-header">🗺️ ROUTING & CHARGES</h2>
        <div class="routing-billing-layout">
          <div class="routing-column">
            <RoutingTable
              v-model:routes="charterForm.routes"
              :isLocked="routingLocked"
              @toggle-lock="routingLocked = !routingLocked"
              @add-route="addRoute"
              @delete-route="deleteRoute"
              @move-up="moveRouteUp"
              @move-down="moveRouteDown"
              @calculate-billed-time="updateRouteBilledTime"
            />
          </div>

          <div class="billing-column">
            <BillingPanel
              v-model:charterFeeType="charterForm.charter_fee_type"
              v-model:charterFeeAmount="charterForm.charter_fee_amount"
              :hourlyRate="charterForm.hourly_rate"
              v-model:gratuityPercent="charterForm.gratuity_percent"
              :gratuityAmount="charterForm.gratuity_amount"
              v-model:extraGratuity="charterForm.extra_gratuity"
              v-model:beverageCartIds="charterForm.beverage_cart_ids"
              v-model:beverageTotal="charterForm.beverage_total"
              v-model:fuelLitres="charterForm.fuel_litres"
              v-model:fuelPrice="charterForm.fuel_price"
              :customCharges="charterForm.custom_charges"
              v-model:gstExempt="charterForm.gst_exempt"
              v-model:gstPermitNumber="charterForm.gst_permit_number"
              :subtotal="charterSubtotal"
              :gstAmount="charterGstAmount"
              :grandTotal="charterGrandTotal"
              @add-custom-charge="addCustomCharge"
              @remove-custom-charge="removeCustomCharge"
              @update-custom-charge="updateCustomCharge"
              @calculate-gratuity="calculateGratuity"
            />

            <SplitRunControls
              v-model:enabled="charterForm.split_run_enabled"
              v-model:routingType="charterForm.routing_type"
              v-model:timeBefore="charterForm.split_time_before"
              v-model:timeAfter="charterForm.split_time_after"
              v-model:doTime="charterForm.do_time"
              v-model:pickupTime="charterForm.split_run_pickup_time"
              v-model:waitTimeRate="charterForm.wait_time_rate"
              @quick-split="handleQuickSplit"
            />
          </div>
        </div>
      </div>

      <!-- Two Column Layout for Additional Sections -->
      <div class="additional-sections">
        <div class="left-column">
          <!-- HOS & Driver -->
          <HOSDriverSection
            v-model:hosStartTime="form.hos_start_time"
            v-model:hosEndTime="form.hos_end_time"
            v-model:mealBreak1Start="form.meal_break_1_start"
            v-model:mealBreak1End="form.meal_break_1_end"
            v-model:mealBreak2Start="form.meal_break_2_start"
            v-model:mealBreak2End="form.meal_break_2_end"
            v-model:driverHourlyRate="form.driver_hourly_rate"
            v-model:driverTotalPay="form.driver_total_pay"
            v-model:driverNotes="form.driver_notes"
            v-model:preInspectionComplete="form.pre_inspection_complete"
            v-model:postInspectionComplete="form.post_inspection_complete"
            v-model:logbookSubmitted="form.logbook_submitted"
          />

          <!-- Vehicle & Odometer -->
          <VehicleOdometerSection
            v-model:odometerStart="form.odometer_start"
            v-model:odometerEnd="form.odometer_end"
            v-model:fuelAdded="form.fuel_added"
            v-model:fuelCost="form.fuel_cost"
            v-model:exteriorCondition="form.exterior_condition"
            v-model:interiorCondition="form.interior_condition"
            v-model:cleanliness="form.cleanliness"
            v-model:damageNotes="form.damage_notes"
            v-model:needsWash="form.needs_wash"
            v-model:needsDetail="form.needs_detail"
            v-model:needsService="form.needs_service"
          />
        </div>

        <div class="right-column">
          <!-- Accounting Details -->
          <AccountingDetailsSection
            v-model:paymentStatus="form.payment_status"
            v-model:invoiceNumber="form.invoice_number"
            v-model:invoiceDate="form.invoice_date"
            :amountDue="grandTotal"
            v-model:amountPaid="form.amount_paid"
            v-model:paymentMethod="form.payment_method"
            v-model:chequeNumber="form.cheque_number"
            v-model:cardLast4="form.card_last_4"
            v-model:eTransferRef="form.etransfer_ref"
            v-model:depositAmount="form.deposit_amount"
            v-model:depositDate="form.deposit_date"
            v-model:depositMethod="form.deposit_method"
            v-model:gratuityAmount="form.gratuity_cash_amount"
            v-model:gratuityOnCard="form.gratuity_on_card"
            v-model:revenueAccount="form.revenue_account"
            v-model:expenseAccount="form.expense_account"
            v-model:taxCode="form.tax_code"
            v-model:accountingNotes="form.accounting_notes"
            :subtotal="subtotal"
            :gstAmount="gstAmount"
          />
        </div>
      </div>

      <!-- Save Actions -->
      <div class="save-actions">
        <button @click="saveCharter" class="btn-save">💾 Save Charter</button>
        <button @click="saveAndInvoice" class="btn-invoice">📄 Save & Generate Invoice</button>
        <button @click="saveAndPrint" class="btn-print">🖨️ Save & Print</button>
        <button v-if="currentCharter" @click="deleteCharter" class="btn-delete">🗑️ Delete Charter</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import ClientDetailsSection from './ClientDetailsSection.vue'
import DispatchSection from './DispatchSection.vue'
import RoutingTable from './RoutingTable.vue'
import BillingPanel from './BillingPanel.vue'
import SplitRunControls from './SplitRunControls.vue'
import HOSDriverSection from './HOSDriverSection.vue'
import VehicleOdometerSection from './VehicleOdometerSection.vue'
import AccountingDetailsSection from './AccountingDetailsSection.vue'

// Composables - will need to create simplified versions or inline the logic
// For now, we'll inline the necessary logic

// State
const searchQuery = ref('')
const searchResults = ref([])
const currentCharter = ref(null)

// Charter Form State (combines all charter detail fields)
const charterForm = ref({
  // Client Details
  client_name: '',
  charter_date: '',
  pickup_time: '',
  dropoff_time: '',
  dispatcher_notes: '',
  passenger_count: 1,
  vehicle_type: '',
  run_type: '',
  airport_location: '',
  out_of_town: false,
  client_notes: '',
  
  // Dispatch
  vehicle_id: null,
  chauffeur_id: null,
  
  // Routing
  routes: [],
  
  // Billing
  charter_fee_type: 'hourly',
  charter_fee_amount: 0,
  hourly_rate: 0,
  gratuity_percent: 15,
  gratuity_amount: 0,
  extra_gratuity: 0,
  beverage_cart_ids: [],
  beverage_total: 0,
  fuel_litres: 0,
  fuel_price: 0,
  custom_charges: [],
  gst_exempt: false,
  gst_permit_number: '',
  
  // Split Run
  split_run_enabled: false,
  routing_type: 'normal',
  split_time_before: 0,
  split_time_after: 0,
  do_time: '',
  split_run_pickup_time: '',
  wait_time_rate: 0
})

// Routing State
const routingLocked = ref(false)

// Run Charter Form data (HOS, Vehicle, Accounting)
const form = ref({
  // Charter details are handled by inline sections above
  // HOS Driver
  hos_start_time: '',
  hos_end_time: '',
  meal_break_1_start: '',
  meal_break_1_end: '',
  meal_break_2_start: '',
  meal_break_2_end: '',
  driver_hourly_rate: 0,
  driver_total_pay: 0,
  driver_notes: '',
  pre_inspection_complete: false,
  post_inspection_complete: false,
  logbook_submitted: false,
  
  // Vehicle Odometer
  odometer_start: 0,
  odometer_end: 0,
  fuel_added: 0,
  fuel_cost: 0,
  exterior_condition: '',
  interior_condition: '',
  cleanliness: '',
  damage_notes: '',
  needs_wash: false,
  needs_detail: false,
  needs_service: false,
  
  // Accounting
  payment_status: 'pending',
  invoice_number: '',
  invoice_date: '',
  amount_paid: 0,
  payment_method: '',
  cheque_number: '',
  card_last_4: '',
  etransfer_ref: '',
  deposit_amount: 0,
  deposit_date: '',
  deposit_method: '',
  gratuity_cash_amount: 0,
  gratuity_on_card: false,
  revenue_account: '4000',
  expense_account: '5100',
  tax_code: 'GST',
  accounting_notes: ''
})

// Initialize routes if empty
if (charterForm.value.routes.length === 0) {
  charterForm.value.routes = [
    { type: 'Pickup', location: '', time: charterForm.value.pickup_time, notes: '' }
  ]
}

// Computed values for billing
const charterSubtotal = computed(() => {
  let total = charterForm.value.charter_fee_amount || 0
  total += charterForm.value.beverage_total || 0
  total += (charterForm.value.fuel_litres || 0) * (charterForm.value.fuel_price || 0)
  charterForm.value.custom_charges.forEach(charge => {
    total += charge.amount || 0
  })
  return total
})

const charterGstAmount = computed(() => {
  return charterForm.value.gst_exempt ? 0 : charterSubtotal.value * 0.05
})

const charterGrandTotal = computed(() => {
  return charterSubtotal.value + charterGstAmount.value + (charterForm.value.gratuity_amount || 0) + (charterForm.value.extra_gratuity || 0)
})

// Compatible computed values (for compatibility with existing code)
const subtotal = computed(() => charterSubtotal.value)
const gstAmount = computed(() => charterGstAmount.value)
const grandTotal = computed(() => charterGrandTotal.value)

// Charter Detail Event Handlers
const handleExtendTime = (hours) => {
  if (!charterForm.value.pickup_time) return
  const [h, m] = charterForm.value.pickup_time.split(':').map(Number)
  const newTime = new Date()
  newTime.setHours(h + hours, m)
  charterForm.value.dropoff_time = newTime.toTimeString().slice(0, 5)
}

const handleQuickSplit = (hours) => {
  charterForm.value.split_time_before = hours
  charterForm.value.split_time_after = hours
}

const handleVehicleTypeChange = () => {
  // TODO: Load vehicle pricing based on type
  console.log('Vehicle type changed:', charterForm.value.vehicle_type)
}

const handleRunTypeChange = () => {
  // TODO: Load pricing based on run type
  console.log('Run type changed:', charterForm.value.run_type)
}

const handleAirportChange = () => {
  // TODO: Apply airport fee if applicable
  console.log('Airport changed:', charterForm.value.airport_location)
}

const handleVehicleSelected = (vehicle) => {
  console.log('Vehicle selected:', vehicle)
  // Additional logic if needed
}

const handleChauffeurSelected = (chauffeur) => {
  console.log('Chauffeur selected:', chauffeur)
  // Additional logic if needed
}

// Routing Methods
const addRoute = () => {
  charterForm.value.routes.push({
    type: 'Stop',
    location: '',
    time: '',
    notes: ''
  })
}

const deleteRoute = (index) => {
  charterForm.value.routes.splice(index, 1)
}

const moveRouteUp = (index) => {
  if (index > 0) {
    const temp = charterForm.value.routes[index]
    charterForm.value.routes[index] = charterForm.value.routes[index - 1]
    charterForm.value.routes[index - 1] = temp
  }
}

const moveRouteDown = (index) => {
  if (index < charterForm.value.routes.length - 1) {
    const temp = charterForm.value.routes[index]
    charterForm.value.routes[index] = charterForm.value.routes[index + 1]
    charterForm.value.routes[index + 1] = temp
  }
}

const updateRouteBilledTime = (index, billedTime) => {
  if (charterForm.value.routes[index]) {
    charterForm.value.routes[index].billedTime = billedTime
  }
}

// Billing Methods
const calculateGratuity = () => {
  const percent = charterForm.value.gratuity_percent || 0
  charterForm.value.gratuity_amount = charterSubtotal.value * (percent / 100)
}

const addCustomCharge = (charge) => {
  charterForm.value.custom_charges.push({
    description: charge.description || '',
    amount: charge.amount || 0
  })
}

const removeCustomCharge = (index) => {
  charterForm.value.custom_charges.splice(index, 1)
}

const updateCustomCharge = (index, charge) => {
  if (charterForm.value.custom_charges[index]) {
    charterForm.value.custom_charges[index] = { ...charge }
  }
}

// Search and Charter Management Methods
async function searchCharters(retryCount = 0) {
  if (!searchQuery.value.trim()) return
  
  try {
    // TODO: Replace with actual API call
    const response = await fetch(`/api/charters/search?q=${encodeURIComponent(searchQuery.value)}`)
    if (response.ok) {
      searchResults.value = await response.json()
    } else if (response.status === 500 && retryCount < 2) {
      // Auto-retry on server error (likely connection issue)
      console.log(`Server error, retrying... (${retryCount + 1}/2)`)
      await new Promise(resolve => setTimeout(resolve, 1000))
      return searchCharters(retryCount + 1)
    } else {
      throw new Error(`Search failed with status ${response.status}`)
    }
  } catch (error) {
    console.error('Search failed:', error)
    
    // Show user-friendly error
    if (retryCount < 2 && (error.message.includes('connection') || error.message.includes('Failed to fetch'))) {
      // Auto-retry on connection errors
      console.log(`Connection error, retrying... (${retryCount + 1}/2)`)
      await new Promise(resolve => setTimeout(resolve, 1000))
      return searchCharters(retryCount + 1)
    }
    
    alert('Search failed: ' + (error.message || 'Connection error. Please try again.'))
    
    // Mock data for development
    searchResults.value = [
      {
        id: 1,
        reserve_number: '019650',
        client_name: 'Balanski, Kevin',
        charter_date: '2026-02-06',
        pickup_time: '08:00',
        vehicle_type: 'Luxury Sedan'
      }
    ]
  }
}

async function loadCharter(charter) {
  try {
    // Fetch full charter details if we only have summary
    let fullCharter = charter
    if (!charter.routes) {
      const response = await fetch(`/api/charters/${charter.id}`)
      if (response.ok) {
        fullCharter = await response.json()
      }
    }
    
    currentCharter.value = fullCharter
    searchResults.value = []
    
    // Populate charter form with loaded data
    charterForm.value = {
      client_name: fullCharter.client_name || '',
      charter_date: fullCharter.charter_date || '',
      pickup_time: fullCharter.pickup_time || '',
      dropoff_time: fullCharter.dropoff_time || '',
      dispatcher_notes: fullCharter.dispatcher_notes || '',
      passenger_count: fullCharter.passenger_count || 1,
      vehicle_type: fullCharter.vehicle_type || '',
      run_type: fullCharter.run_type || '',
      airport_location: fullCharter.airport_location || '',
      out_of_town: fullCharter.out_of_town || false,
      client_notes: fullCharter.client_notes || '',
      vehicle_id: fullCharter.vehicle_id || null,
      chauffeur_id: fullCharter.chauffeur_id || null,
      routes: fullCharter.routes || [{ type: 'Pickup', location: '', time: '', notes: '' }],
      charter_fee_type: fullCharter.charter_fee_type || 'hourly',
      charter_fee_amount: fullCharter.charter_fee_amount || 0,
      hourly_rate: fullCharter.hourly_rate || 0,
      gratuity_percent: fullCharter.gratuity_percent || 15,
      gratuity_amount: fullCharter.gratuity_amount || 0,
      extra_gratuity: fullCharter.extra_gratuity || 0,
      beverage_cart_ids: fullCharter.beverage_cart_ids || [],
      beverage_total: fullCharter.beverage_total || 0,
      fuel_litres: fullCharter.fuel_litres || 0,
      fuel_price: fullCharter.fuel_price || 0,
      custom_charges: fullCharter.custom_charges || [],
      gst_exempt: fullCharter.gst_exempt || false,
      gst_permit_number: fullCharter.gst_permit_number || '',
      split_run_enabled: fullCharter.split_run_enabled || false,
      routing_type: fullCharter.routing_type || 'normal',
      split_time_before: fullCharter.split_time_before || 0,
      split_time_after: fullCharter.split_time_after || 0,
      do_time: fullCharter.do_time || '',
      split_run_pickup_time: fullCharter.split_run_pickup_time || '',
      wait_time_rate: fullCharter.wait_time_rate || 0
    }
    
    // Populate run form with loaded data
    form.value = {
      hos_start_time: fullCharter.hos_start_time || '',
      hos_end_time: fullCharter.hos_end_time || '',
      meal_break_1_start: fullCharter.meal_break_1_start || '',
      meal_break_1_end: fullCharter.meal_break_1_end || '',
      meal_break_2_start: fullCharter.meal_break_2_start || '',
      meal_break_2_end: fullCharter.meal_break_2_end || '',
      driver_hourly_rate: fullCharter.driver_hourly_rate || 0,
      driver_total_pay: fullCharter.driver_total_pay || 0,
      driver_notes: fullCharter.driver_notes || '',
      pre_inspection_complete: fullCharter.pre_inspection_complete || false,
      post_inspection_complete: fullCharter.post_inspection_complete || false,
      logbook_submitted: fullCharter.logbook_submitted || false,
      odometer_start: fullCharter.odometer_start || 0,
      odometer_end: fullCharter.odometer_end || 0,
      fuel_added: fullCharter.fuel_added || 0,
      fuel_cost: fullCharter.fuel_cost || 0,
      exterior_condition: fullCharter.exterior_condition || '',
      interior_condition: fullCharter.interior_condition || '',
      cleanliness: fullCharter.cleanliness || '',
      damage_notes: fullCharter.damage_notes || '',
      needs_wash: fullCharter.needs_wash || false,
      needs_detail: fullCharter.needs_detail || false,
      needs_service: fullCharter.needs_service || false,
      payment_status: fullCharter.payment_status || 'pending',
      invoice_number: fullCharter.invoice_number || '',
      invoice_date: fullCharter.invoice_date || '',
      amount_paid: fullCharter.amount_paid || 0,
      payment_method: fullCharter.payment_method || '',
      cheque_number: fullCharter.cheque_number || '',
      card_last_4: fullCharter.card_last_4 || '',
      etransfer_ref: fullCharter.etransfer_ref || '',
      deposit_amount: fullCharter.deposit_amount || 0,
      deposit_date: fullCharter.deposit_date || '',
      deposit_method: fullCharter.deposit_method || '',
      gratuity_cash_amount: fullCharter.gratuity_cash_amount || 0,
      gratuity_on_card: fullCharter.gratuity_on_card || false,
      revenue_account: fullCharter.revenue_account || '4000',
      expense_account: fullCharter.expense_account || '5100',
      tax_code: fullCharter.tax_code || 'GST',
      accounting_notes: fullCharter.accounting_notes || ''
    }
    
    console.log('Charter loaded successfully:', fullCharter)
  } catch (error) {
    console.error('Failed to load charter:', error)
    alert('Failed to load charter details: ' + error.message)
  }
}

async function cloneCharter(charter) {
  try {
    // Load charter data first
    await loadCharter(charter)
    
    // Clear ID and update date to today
    currentCharter.value = null
    const today = new Date().toISOString().split('T')[0]
    charterForm.value.charter_date = today
    
    console.log('Charter cloned successfully')
  } catch (error) {
    console.error('Failed to clone charter:', error)
    alert('Failed to clone charter: ' + error.message)
  }
}

function linkCharter(charter) {
  // TODO: Create relationship link between charters
  console.log('Linking charter:', charter)
}

function clearForm() {
  currentCharter.value = null
  searchResults.value = []
  
  // Reset charter form
  charterForm.value = {
    client_name: '',
    charter_date: '',
    pickup_time: '',
    dropoff_time: '',
    dispatcher_notes: '',
    passenger_count: 1,
    vehicle_type: '',
    run_type: '',
    airport_location: '',
    out_of_town: false,
    client_notes: '',
    vehicle_id: null,
    chauffeur_id: null,
    routes: [{ type: 'Pickup', location: '', time: '', notes: '' }],
    charter_fee_type: 'hourly',
    charter_fee_amount: 0,
    hourly_rate: 0,
    gratuity_percent: 15,
    gratuity_amount: 0,
    extra_gratuity: 0,
    beverage_cart_ids: [],
    beverage_total: 0,
    fuel_litres: 0,
    fuel_price: 0,
    custom_charges: [],
    gst_exempt: false,
    gst_permit_number: '',
    split_run_enabled: false,
    routing_type: 'normal',
    split_time_before: 0,
    split_time_after: 0,
    do_time: '',
    split_run_pickup_time: '',
    wait_time_rate: 0
  }
  
  // Reset run form
  form.value = {
    hos_start_time: '',
    hos_end_time: '',
    meal_break_1_start: '',
    meal_break_1_end: '',
    meal_break_2_start: '',
    meal_break_2_end: '',
    driver_hourly_rate: 0,
    driver_total_pay: 0,
    driver_notes: '',
    pre_inspection_complete: false,
    post_inspection_complete: false,
    logbook_submitted: false,
    odometer_start: 0,
    odometer_end: 0,
    fuel_added: 0,
    fuel_cost: 0,
    exterior_condition: '',
    interior_condition: '',
    cleanliness: '',
    damage_notes: '',
    needs_wash: false,
    needs_detail: false,
    needs_service: false,
    payment_status: 'pending',
    invoice_number: '',
    invoice_date: '',
    amount_paid: 0,
    payment_method: '',
    cheque_number: '',
    card_last_4: '',
    etransfer_ref: '',
    deposit_amount: 0,
    deposit_date: '',
    deposit_method: '',
    gratuity_cash_amount: 0,
    gratuity_on_card: false,
    revenue_account: '4000',
    expense_account: '5100',
    tax_code: 'GST',
    accounting_notes: ''
  }
}

async function saveCharter() {
  try {
    // Combine charter form and run form data
    const completeCharterData = {
      ...charterForm.value,
      ...form.value,
      subtotal: charterSubtotal.value,
      gst_amount: charterGstAmount.value,
      grand_total: charterGrandTotal.value
    }
    
    // Add ID if updating existing charter
    if (currentCharter.value?.id) {
      completeCharterData.id = currentCharter.value.id
    }
    
    console.log('Saving complete charter data:', completeCharterData)
    
    // Build API URL
    const isUpdate = currentCharter.value?.id
    const apiUrl = isUpdate 
      ? `/api/charters/${currentCharter.value.id}` 
      : '/api/charters'
    
    // TODO: Replace with actual API call
    const response = await fetch(apiUrl, {
      method: isUpdate ? 'PUT' : 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(completeCharterData)
    })
    
    if (response.ok) {
      const result = await response.json()
      console.log('Charter saved successfully:', result)
      alert('Charter saved successfully!')
      currentCharter.value = result
      
      // Reload the charter to ensure form shows updated data
      await loadCharter(result)
    } else {
      throw new Error(`Save failed with status ${response.status}`)
    }
  } catch (error) {
    console.error('Save failed:', error)
    alert('Failed to save charter: ' + error.message)
  }
}

async function saveAndInvoice() {
  await saveCharter()
  // TODO: Generate and download invoice
  console.log('Generating invoice...')
}

async function saveAndPrint() {
  await saveCharter()
  window.print()
}

async function deleteCharter() {
  if (!confirm('Are you sure you want to delete this charter? This action cannot be undone.')) {
    return
  }
  
  try {
    // TODO: API call to delete charter
    console.log('Deleting charter:', currentCharter.value)
    clearForm()
  } catch (error) {
    console.error('Delete failed:', error)
  }
}

// Watchers for auto-calculations
watch(() => charterForm.value.gratuity_percent, () => {
  calculateGratuity()
})

watch(() => charterSubtotal.value, () => {
  calculateGratuity()
})

watch(() => charterForm.value.out_of_town, (isOutOfTown) => {
  if (isOutOfTown && charterForm.value.routes.length === 1) {
    // Add out of town routes
    addRoute()
    charterForm.value.routes[charterForm.value.routes.length - 1].type = 'Return'
  }
})
</script>

<style scoped>
.run-charter-tab {
  background: #f7fafc;
  min-height: 100vh;
}

.charter-search-header {
  background: white;
  padding: 1rem;
  border-bottom: 2px solid #e2e8f0;
  position: sticky;
  top: 0;
  z-index: 100;
}

.search-bar {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.search-input {
  flex: 1;
  padding: 0.75rem 1rem;
  border: 2px solid #cbd5e0;
  border-radius: 8px;
  font-size: 1rem;
  transition: all 0.3s;
}

.search-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.btn-search,
.btn-new {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-search {
  background: #667eea;
  color: white;
}

.btn-search:hover {
  background: #5568d3;
}

.btn-new {
  background: #48bb78;
  color: white;
}

.btn-new:hover {
  background: #38a169;
}

.search-results {
  margin-top: 1rem;
  background: #f7fafc;
  border: 2px solid #cbd5e0;
  border-radius: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.results-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 2px solid #cbd5e0;
  background: white;
}

.results-header h4 {
  margin: 0;
  color: #2d3748;
}

.close-results {
  background: #e2e8f0;
  border: none;
  border-radius: 4px;
  padding: 0.25rem 0.75rem;
  cursor: pointer;
  font-size: 1rem;
}

.results-list {
  padding: 0.5rem;
}

.result-item {
  background: white;
  padding: 0.75rem 1rem;
  margin-bottom: 0.5rem;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  cursor: pointer;
  transition: all 0.2s;
}

.result-item:hover {
  border-color: #667eea;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.15);
}

.result-main {
  color: #2d3748;
  font-size: 1.05rem;
  margin-bottom: 0.25rem;
}

.result-details {
  color: #718096;
  font-size: 0.9rem;
  margin-bottom: 0.5rem;
}

.result-actions {
  display: flex;
  gap: 0.5rem;
}

.btn-clone,
.btn-link {
  padding: 0.4rem 0.75rem;
  border: none;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-clone {
  background: #f6ad55;
  color: white;
}

.btn-clone:hover {
  background: #ed8936;
}

.btn-link {
  background: #4299e1;
  color: white;
}

.btn-link:hover {
  background: #3182ce;
}

.charter-form-sections {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.form-section {
  background: white;
  border-radius: 8px;
  border: 2px solid #e2e8f0;
  padding: 1.5rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.section-header {
  margin: 0 0 1rem 0;
  padding-bottom: 0.75rem;
  border-bottom: 2px solid #667eea;
  color: #2d3748;
  font-size: 1.25rem;
  font-weight: 700;
}

.routing-billing-section {
  padding: 1.5rem 1rem;
}

.routing-billing-layout {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1rem;
  margin-top: 1rem;
}

.routing-column {
  background: #f7fafc;
  padding: 1rem;
  border-radius: 6px;
  max-height: 600px;
  overflow-y: auto;
  overflow-x: auto;
}

.billing-column {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-height: 600px;
  overflow-y: auto;
}

.additional-sections {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.left-column,
.right-column {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.save-actions {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  border: 2px solid #667eea;
  display: flex;
  gap: 1rem;
  justify-content: center;
  position: sticky;
  bottom: 0;
  z-index: 50;
}

.btn-save,
.btn-invoice,
.btn-print,
.btn-delete {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 1rem;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-save {
  background: #667eea;
  color: white;
}

.btn-save:hover {
  background: #5568d3;
}

.btn-invoice {
  background: #48bb78;
  color: white;
}

.btn-invoice:hover {
  background: #38a169;
}

.btn-print {
  background: #4299e1;
  color: white;
}

.btn-print:hover {
  background: #3182ce;
}

.btn-delete {
  background: #fc8181;
  color: white;
}

.btn-delete:hover {
  background: #f56565;
}

@media (max-width: 1200px) {
  .additional-sections {
    grid-template-columns: 1fr;
  }
  
  .routing-billing-layout {
    grid-template-columns: 1fr;
  }
  
  .routing-column,
  .billing-column {
    max-height: none;
  }
}
</style>
