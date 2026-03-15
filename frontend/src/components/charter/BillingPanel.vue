<template>
  <div class="billing-panel">
    <h2>💰 Billing</h2>

    <div class="billing-section">
      <!-- Charter Fee -->
      <div class="billing-row">
        <label>Charter Fee</label>
        <div class="charter-fee-inputs">
          <select 
            :value="charterFeeType"
            @change="$emit('update:charterFeeType', $event.target.value)"
            class="fee-type-select"
          >
            <option value="hourly">Hourly</option>
            <option value="flat">Flat Rate</option>
            <option value="custom">Custom</option>
          </select>
          <input 
            type="number"
            step="0.01"
            :value="charterFeeAmount"
            @input="$emit('update:charterFeeAmount', parseFloat($event.target.value) || 0)"
            placeholder="0.00"
            class="amount-input"
          />
          <span v-if="charterFeeType === 'hourly'" class="rate-display">
            @ ${{ hourlyRate.toFixed(2) }}/hr
          </span>
        </div>
      </div>

      <!-- Gratuity -->
      <div class="billing-row">
        <label>Gratuity ({{ gratuityPercent }}%)</label>
        <div class="gratuity-inputs">
          <input 
            type="number"
            step="1"
            min="0"
            max="100"
            :value="gratuityPercent"
            @input="$emit('update:gratuityPercent', parseFloat($event.target.value) || 0); $emit('calculate-gratuity')"
            class="percent-input"
          />
          <span class="percent-symbol">%</span>
          <input 
            type="number"
            step="0.01"
            :value="gratuityAmount"
            readonly
            class="amount-input readonly"
          />
        </div>
      </div>

      <!-- Extra Gratuity (GST Exempt, T4 Field) -->
      <div class="billing-row highlight-row">
        <label>Extra Gratuity (Cash - GST Exempt, T4)</label>
        <input 
          type="number"
          step="0.01"
          :value="extraGratuity"
          @input="$emit('update:extraGratuity', parseFloat($event.target.value) || 0)"
          placeholder="0.00"
          class="amount-input"
        />
      </div>

      <!-- Beverage Cart -->
      <div class="billing-row">
        <label>Beverage Cart (GST included)</label>
        <div class="beverage-inputs">
          <input 
            type="text"
            :value="beverageCartIds"
            @input="$emit('update:beverageCartIds', $event.target.value)"
            placeholder="Cart order IDs (comma-separated)"
            class="cart-ids-input"
          />
          <input 
            type="number"
            step="0.01"
            :value="beverageTotal"
            @input="$emit('update:beverageTotal', parseFloat($event.target.value) || 0)"
            placeholder="0.00"
            class="amount-input"
          />
        </div>
      </div>

      <!-- Fuel Receipt Split -->
      <div class="billing-row">
        <label>Fuel Receipt Split</label>
        <div class="fuel-inputs">
          <input 
            type="number"
            step="0.01"
            :value="fuelLitres"
            @input="$emit('update:fuelLitres', parseFloat($event.target.value) || 0)"
            placeholder="Litres"
            class="fuel-litres-input"
          />
          <span class="separator">L @</span>
          <input 
            type="number"
            step="0.001"
            :value="fuelPrice"
            @input="$emit('update:fuelPrice', parseFloat($event.target.value) || 0)"
            placeholder="$/L"
            class="fuel-price-input"
          />
          <span class="separator">=</span>
          <input 
            type="number"
            step="0.01"
            :value="fuelTotal"
            readonly
            class="amount-input readonly"
          />
          <small class="fuel-gst">(GST: ${{ fuelGst.toFixed(2) }})</small>
        </div>
      </div>

      <!-- Custom Charges -->
      <div class="custom-charges-section">
        <div class="custom-charges-header">
          <label>Custom Charges</label>
          <button @click="$emit('add-custom-charge')" class="btn-add-charge">
            ➕ Add Charge
          </button>
        </div>
        
        <div v-for="(charge, index) in customCharges" :key="index" class="custom-charge-row">
          <input 
            type="text"
            :value="charge.description"
            @input="updateCustomCharge(index, 'description', $event.target.value)"
            placeholder="Description"
            class="charge-description-input"
          />
          <input 
            type="number"
            step="0.01"
            :value="charge.amount"
            @input="updateCustomCharge(index, 'amount', parseFloat($event.target.value) || 0)"
            placeholder="0.00"
            class="amount-input"
          />
          <button @click="$emit('remove-custom-charge', index)" class="btn-remove-charge">
            🗑️
          </button>
        </div>

        <div v-if="customCharges.length === 0" class="no-charges">
          No custom charges
        </div>
      </div>

      <!-- Totals -->
      <div class="totals-section">
        <div class="total-row subtotal-row">
          <label>Subtotal</label>
          <span class="total-amount">${{ subtotal.toFixed(2) }}</span>
        </div>
        
        <div class="total-row gst-row">
          <label>GST (5%)</label>
          <span class="total-amount">${{ gstAmount.toFixed(2) }}</span>
        </div>
        
        <div class="total-row grand-total-row">
          <label>Grand Total</label>
          <span class="total-amount grand-total">${{ grandTotal.toFixed(2) }}</span>
        </div>
      </div>

      <!-- GST Exempt -->
      <div class="gst-exempt-section">
        <label class="checkbox-label">
          <input 
            type="checkbox"
            :checked="gstExempt"
            @change="$emit('update:gstExempt', $event.target.checked)"
          />
          <strong>GST Exempt Charter</strong>
        </label>
        <div v-if="gstExempt" class="gst-permit-field">
          <label>GST Permit Number</label>
          <input 
            type="text"
            :value="gstPermitNumber"
            @input="$emit('update:gstPermitNumber', $event.target.value)"
            placeholder="Enter GST permit number"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  charterFeeType: String,
  charterFeeAmount: Number,
  hourlyRate: Number,
  gratuityPercent: {
    type: Number,
    default: 18
  },
  gratuityAmount: Number,
  extraGratuity: Number,
  beverageCartIds: String,
  beverageTotal: Number,
  fuelLitres: Number,
  fuelPrice: Number,
  customCharges: {
    type: Array,
    default: () => []
  },
  gstExempt: Boolean,
  gstPermitNumber: String,
  subtotal: Number,
  gstAmount: Number,
  grandTotal: Number
})

const emit = defineEmits([
  'update:charterFeeType',
  'update:charterFeeAmount',
  'update:gratuityPercent',
  'update:extraGratuity',
  'update:beverageCartIds',
  'update:beverageTotal',
  'update:fuelLitres',
  'update:fuelPrice',
  'update:gstExempt',
  'update:gstPermitNumber',
  'add-custom-charge',
  'remove-custom-charge',
  'update-custom-charge',
  'calculate-gratuity'
])

const fuelTotal = computed(() => {
  return (props.fuelLitres || 0) * (props.fuelPrice || 0)
})

const fuelGst = computed(() => {
  return fuelTotal.value * 0.05
})

const updateCustomCharge = (index, field, value) => {
  emit('update-custom-charge', { index, field, value })
}
</script>

<style scoped>
.billing-panel {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  border: 2px solid #48bb78;
}

.billing-panel h2 {
  margin: 0 0 0.75rem 0;
  color: #2d3748;
  font-size: 1.3rem;
}

.billing-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.billing-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem;
  border-bottom: 1px solid #e2e8f0;
}

.billing-row label {
  font-weight: 600;
  color: #2d3748;
  font-size: 0.85rem;
}

.highlight-row {
  background: #fffaf0;
  border-left: 4px solid #f6ad55;
}

.charter-fee-inputs,
.gratuity-inputs,
.beverage-inputs,
.fuel-inputs {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.fee-type-select {
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.85rem;
}

.amount-input {
  width: 100px;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  text-align: right;
  font-size: 0.85rem;
}

.amount-input.readonly {
  background: #f7fafc;
  cursor: not-allowed;
  font-weight: 600;
}

.percent-input {
  width: 50px;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  text-align: right;
  font-size: 0.85rem;
}

.percent-symbol {
  font-weight: 600;
  color: #718096;
}

.rate-display {
  font-size: 0.85rem;
  color: #718096;
  font-style: italic;
}

.cart-ids-input {
  flex: 1;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.85rem;
}

.fuel-litres-input,
.fuel-price-input {
  width: 70px;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  text-align: right;
  font-size: 0.85rem;
}

.separator {
  color: #718096;
  font-weight: 600;
  padding: 0 0.25rem;
}

.fuel-gst {
  font-size: 0.85rem;
  color: #718096;
  margin-left: 0.5rem;
}

.custom-charges-section {
  margin-top: 0.5rem;
  padding: 0.75rem;
  background: #f7fafc;
  border-radius: 6px;
}

.custom-charges-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.custom-charges-header label {
  font-weight: 600;
  color: #2d3748;
}

.btn-add-charge {
  padding: 0.4rem 0.75rem;
  background: #48bb78;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
  transition: background 0.2s;
}

.btn-add-charge:hover {
  background: #38a169;
}

.custom-charge-row {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.5rem;
  align-items: center;
}

.charge-description-input {
  flex: 1;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.85rem;
}

.btn-remove-charge {
  padding: 0.4rem;
  background: #fc8181;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: background 0.2s;
}

.btn-remove-charge:hover {
  background: #f56565;
}

.no-charges {
  text-align: center;
  color: #a0aec0;
  padding: 0.5rem;
  font-style: italic;
  font-size: 0.85rem;
}

.totals-section {
  margin-top: 0.75rem;
  padding-top: 0.5rem;
  border-top: 2px solid #e2e8f0;
}

.total-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem;
}

.total-row label {
  font-weight: 600;
  color: #2d3748;
  font-size: 0.9rem;
}

.total-amount {
  font-weight: 600;
  font-size: 1rem;
  color: #2d3748;
}

.subtotal-row {
  background: #f7fafc;
}

.gst-row {
  background: #fffaf0;
}

.grand-total-row {
  background: #c6f6d5;
  border-radius: 6px;
  margin-top: 0.5rem;
}

.grand-total {
  font-size: 1.3rem;
  color: #22543d;
}

.gst-exempt-section {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: #fffaf0;
  border-radius: 6px;
  border: 2px solid #f6ad55;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  margin-bottom: 0.5rem;
}

.checkbox-label input[type="checkbox"] {
  width: 20px;
  height: 20px;
  cursor: pointer;
}

.gst-permit-field label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: #2d3748;
  font-size: 0.85rem;
}

.gst-permit-field input {
  width: 100%;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.9rem;
}
</style>
