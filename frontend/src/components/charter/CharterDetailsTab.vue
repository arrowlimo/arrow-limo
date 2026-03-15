<template>
  <div class="charter-details-tab">
    <div class="charter-layout">
      <!-- Client Details Section -->
      <div class="client-section">
        <ClientDetailsSection
          v-model:customerSearch="form.client_name"
          v-model:charterDate="form.charter_date"
          v-model:pickupTime="form.pickup_time"
          v-model:dropoffTime="form.dropoff_time"
          v-model:dispatchNotes="form.dispatcher_notes"
          v-model:passengerCount="form.passenger_count"
          v-model:vehicleType="form.vehicle_type"
          v-model:runType="form.run_type"
          v-model:airportLocation="form.airport_location"
          v-model:outOfTown="form.out_of_town"
          v-model:clientNotes="form.client_notes"
          @extend-time="handleExtendTime"
          @vehicle-type-changed="handleVehicleTypeChange"
          @run-type-changed="handleRunTypeChange"
          @airport-changed="handleAirportChange"
        />
      </div>

      <!-- Dispatch Section -->
      <div class="dispatch-section">
        <DispatchSection
          v-model:vehicleId="form.vehicle_id"
          v-model:chauffeurId="form.chauffeur_id"
          @vehicle-selected="handleVehicleSelected"
          @chauffeur-selected="handleChauffeurSelected"
        />
      </div>

      <!-- Middle Row: Routing Table + Billing Panel + Split Run -->
      <div class="middle-row">
        <div class="routing-column">
          <RoutingTable
            v-model:routes="form.routes"
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
            v-model:charterFeeType="form.charter_fee_type"
            v-model:charterFeeAmount="form.charter_fee_amount"
            :hourlyRate="form.hourly_rate"
            v-model:gratuityPercent="form.gratuity_percent"
            :gratuityAmount="form.gratuity_amount"
            v-model:extraGratuity="form.extra_gratuity"
            v-model:beverageCartIds="form.beverage_cart_ids"
            v-model:beverageTotal="form.beverage_total"
            v-model:fuelLitres="form.fuel_litres"
            v-model:fuelPrice="form.fuel_price"
            :customCharges="form.custom_charges"
            v-model:gstExempt="form.gst_exempt"
            v-model:gstPermitNumber="form.gst_permit_number"
            :subtotal="subtotal"
            :gstAmount="gstAmount"
            :grandTotal="grandTotal"
            @add-custom-charge="addCustomCharge"
            @remove-custom-charge="removeCustomCharge"
            @update-custom-charge="updateCustomCharge"
            @calculate-gratuity="calculateGratuity"
          />

          <SplitRunControls
            v-model:enabled="form.split_run_enabled"
            v-model:routingType="form.routing_type"
            v-model:timeBefore="form.split_time_before"
            v-model:timeAfter="form.split_time_after"
            v-model:doTime="form.do_time"
            v-model:pickupTime="form.split_run_pickup_time"
            v-model:waitTimeRate="form.wait_time_rate"
            @quick-split="handleQuickSplit"
          />
        </div>
      </div>

      <!-- Actions -->
      <CharterActions
        :saving="isSaving"
        @save="handleSaveCharter"
        @quote="handleGenerateQuote"
        @reset="handleResetForm"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import ClientDetailsSection from './ClientDetailsSection.vue'
import DispatchSection from './DispatchSection.vue'
import SplitRunControls from './SplitRunControls.vue'
import RoutingTable from './RoutingTable.vue'
import BillingPanel from './BillingPanel.vue'
import CharterActions from './CharterActions.vue'

// Composables
import { useCharterForm } from '@/composables/useCharterForm'
import { useTimeCalculations } from '@/composables/useTimeCalculations'
import { useBilling } from '@/composables/useBilling'
import { useRouting } from '@/composables/useRouting'
import { useVehiclePricing } from '@/composables/useVehiclePricing'

// Form State
const { form, resetForm } = useCharterForm()

// Time Calculations
const { extendTime, setSplitTime, calculateSplitRunPickupTime, calculateBilledTime, formatBilledTime } = useTimeCalculations(form)

// Billing
const { calculateGratuity, subtotal, gstAmount, grandTotal, addCustomCharge, removeCustomCharge, updateCustomCharge } = useBilling(form)

// Routing
const { 
  routingLocked, 
  addRoute, 
  deleteRoute, 
  moveRouteUp, 
  moveRouteDown, 
  updateRouteBilledTime,
  initializeRoutes,
  insertOutOfTownRoutes,
  insertSplitRunRoutes
} = useRouting(form, calculateBilledTime, formatBilledTime)

// Vehicle Pricing
const { loadVehiclePricing, applyAirportFee } = useVehiclePricing(form)

// Component State
const isSaving = ref(false)

// Initialize routing table
if (form.routes.length === 0) {
  initializeRoutes()
}

// Event Handlers
const handleExtendTime = (hours) => {
  extendTime(hours)
}

const handleQuickSplit = (hours) => {
  setSplitTime(hours)
}

const handleVehicleTypeChange = () => {
  loadVehiclePricing()
}

const handleRunTypeChange = () => {
  loadVehiclePricing()
}

const handleAirportChange = () => {
  applyAirportFee()
}

const handleVehicleSelected = (vehicle) => {
  // Update form with vehicle details if needed
  console.log('Vehicle selected:', vehicle)
}

const handleChauffeurSelected = (chauffeur) => {
  // Update form with chauffeur details if needed
  console.log('Chauffeur selected:', chauffeur)
}

const handleSaveCharter = async () => {
  isSaving.value = true
  try {
    // TODO: Replace with actual API call
    const response = await fetch('/api/charters', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(form)
    })
    
    if (response.ok) {
      const result = await response.json()
      console.log('Charter saved:', result)
      // TODO: Show success message, navigate to charter detail page
    } else {
      throw new Error('Failed to save charter')
    }
  } catch (error) {
    console.error('Error saving charter:', error)
    // TODO: Show error message
  } finally {
    isSaving.value = false
  }
}

const handleGenerateQuote = async () => {
  try {
    // TODO: Replace with actual API call
    const response = await fetch('/api/charters/quote', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(form)
    })
    
    if (response.ok) {
      const quote = await response.json()
      console.log('Quote generated:', quote)
      // TODO: Show quote modal or download PDF
    } else {
      throw new Error('Failed to generate quote')
    }
  } catch (error) {
    console.error('Error generating quote:', error)
    // TODO: Show error message
  }
}

const handleResetForm = () => {
  if (confirm('Are you sure you want to reset the form? All unsaved changes will be lost.')) {
    resetForm()
    initializeRoutes()
  }
}

// Watchers for auto-calculations and auto-insertions
watch(() => form.out_of_town, (isOutOfTown) => {
  if (isOutOfTown) {
    insertOutOfTownRoutes()
  }
})

watch(() => form.split_run_enabled, (isEnabled) => {
  if (isEnabled) {
    insertSplitRunRoutes()
  }
})

// Auto-calculate split run pickup time
watch([() => form.do_time, () => form.split_time_before, () => form.split_time_after], () => {
  if (form.split_run_enabled && form.routing_type === 'split_run') {
    calculateSplitRunPickupTime()
  }
})
</script>

<style scoped>
.charter-details-tab {
  padding: 1rem;
  background: #f7fafc;
  min-height: 100vh;
}

.charter-layout {
  max-width: 1800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.client-section {
  width: 100%;
}

.dispatch-section {
  width: 100%;
}

.middle-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 1rem;
}

.routing-column {
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

@media (max-width: 1200px) {
  .middle-row {
    grid-template-columns: 1fr;
  }
  
  .routing-column,
  .billing-column {
    max-height: none;
  }
}
</style>
