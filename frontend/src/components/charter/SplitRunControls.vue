<template>
  <div class="split-run-controls">
    <h2>⏱️ Split Run / Standby</h2>
    
    <div class="split-run-header">
      <label class="checkbox-label">
        <input 
          type="checkbox"
          :checked="enabled"
          @change="$emit('update:enabled', $event.target.checked)"
        />
        <strong>Enable Split Run / Standby Routing</strong>
      </label>
    </div>

    <div v-if="enabled" class="split-run-content">
      <!-- Routing Type -->
      <div class="form-field">
        <label>Routing Type</label>
        <select 
          :value="routingType"
          @change="$emit('update:routingType', $event.target.value)"
        >
          <option value="split_run">Split Run (Chauffeur leaves, returns later)</option>
          <option value="standby">Standby (Chauffeur waits on-site)</option>
        </select>
        <small v-if="routingType === 'split_run'" class="hint">
          ✦ Chauffeur drops off, leaves, returns for pickup. Billed time before + after dropoff.
        </small>
        <small v-if="routingType === 'standby'" class="hint">
          ✦ Chauffeur remains on-site during wait time. Continuous billing with wait time rate.
        </small>
      </div>

      <!-- Time Split -->
      <div class="time-split-section">
        <h3>Package Time Split</h3>
        <div class="time-split-grid">
          <div class="form-field">
            <label>Time Before Dropoff</label>
            <input 
              type="number"
              step="0.25"
              :value="timeBefore"
              @input="$emit('update:timeBefore', parseFloat($event.target.value) || 0)"
            />
            <small>hours</small>
          </div>

          <div class="form-field">
            <label>Time After Pickup</label>
            <input 
              type="number"
              step="0.25"
              :value="timeAfter"
              @input="$emit('update:timeAfter', parseFloat($event.target.value) || 0)"
            />
            <small>hours</small>
          </div>
        </div>

        <!-- Quick Split Buttons -->
        <div class="quick-split">
          <label>Quick Even Split:</label>
          <div class="quick-split-buttons">
            <button @click="$emit('quick-split', 1)" type="button">1h (0.5 / 0.5)</button>
            <button @click="$emit('quick-split', 1.5)" type="button">1.5h (0.75 / 0.75)</button>
            <button @click="$emit('quick-split', 2)" type="button">2h (1 / 1)</button>
            <button @click="$emit('quick-split', 2.25)" type="button">2h 15m (1.125 / 1.125)</button>
            <button @click="$emit('quick-split', 3)" type="button">3h (1.5 / 1.5)</button>
          </div>
        </div>

        <div class="time-totals">
          <strong>Total Split Time: {{ (timeBefore + timeAfter).toFixed(2) }} hours</strong>
        </div>
      </div>

      <!-- Dropoff & Pickup Times (Split Run Only) -->
      <div v-if="routingType === 'split_run'" class="split-times-section">
        <h3>Split Run Times</h3>
        <div class="split-times-grid">
          <div class="form-field">
            <label>Dropoff Time (Billing Stops)</label>
            <input 
              type="time"
              :value="doTime"
              @input="$emit('update:doTime', $event.target.value)"
            />
          </div>

          <div class="form-field">
            <label>Pickup Time (Billing Resumes) - Auto-calculated</label>
            <input 
              type="time"
              :value="pickupTime"
              readonly
              class="readonly-field"
              title="Auto-calculated from dropoff time + time before + time after"
            />
            <small class="hint">Calculated: Dropoff + {{ timeBefore.toFixed(2) }}h + {{ timeAfter.toFixed(2) }}h</small>
          </div>
        </div>
      </div>

      <!-- Standby Wait Time Rate -->
      <div v-if="routingType === 'standby'" class="standby-rate-section">
        <h3>Standby Wait Time</h3>
        <div class="form-field">
          <label>Wait Time Hourly Rate</label>
          <input 
            type="number"
            step="0.01"
            :value="waitTimeRate"
            @input="$emit('update:waitTimeRate', parseFloat($event.target.value) || 0)"
            placeholder="e.g., 45.00"
          />
          <small class="hint">Reduced hourly rate while chauffeur waits on-site (typically 50-60% of regular rate)</small>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  enabled: Boolean,
  routingType: {
    type: String,
    default: 'split_run'
  },
  timeBefore: {
    type: Number,
    default: 0
  },
  timeAfter: {
    type: Number,
    default: 0
  },
  doTime: String,
  pickupTime: String,
  waitTimeRate: Number
})

defineEmits([
  'update:enabled',
  'update:routingType',
  'update:timeBefore',
  'update:timeAfter',
  'update:doTime',
  'update:pickupTime',
  'update:waitTimeRate',
  'quick-split'
])
</script>

<style scoped>
.split-run-controls {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  border: 2px solid #f6ad55;
}

.split-run-controls h2 {
  margin: 0 0 0.75rem 0;
  color: #2d3748;
  font-size: 1.3rem;
}

.split-run-controls h3 {
  margin: 0 0 0.5rem 0;
  color: #2d3748;
  font-size: 1.1rem;
  border-bottom: 2px solid #f6ad55;
  padding-bottom: 0.25rem;
}

.split-run-header {
  margin-bottom: 0.75rem;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-size: 1.05rem;
}

.checkbox-label input[type="checkbox"] {
  width: 20px;
  height: 20px;
  cursor: pointer;
}

.split-run-content {
  border-top: 2px solid #e2e8f0;
  padding-top: 0.75rem;
}

.form-field {
  margin-bottom: 0.75rem;
}

.form-field label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: #2d3748;
  font-size: 0.85rem;
}

.form-field input,
.form-field select {
  width: 100%;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.9rem;
}

.form-field input:focus,
.form-field select:focus {
  outline: none;
  border-color: #f6ad55;
  box-shadow: 0 0 0 3px rgba(246, 173, 85, 0.1);
}

.form-field small {
  display: block;
  margin-top: 0.25rem;
  color: #718096;
  font-size: 0.85rem;
}

.hint {
  color: #f6ad55;
  font-style: italic;
}

.time-split-section,
.split-times-section,
.standby-rate-section {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: #fffaf0;
  border-radius: 6px;
}

.time-split-grid,
.split-times-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 0.5rem;
}

.quick-split {
  margin: 0.5rem 0;
}

.quick-split label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: #2d3748;
  font-size: 0.85rem;
}

.quick-split-buttons {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.quick-split-buttons button {
  padding: 0.4rem 0.75rem;
  background: #f6ad55;
  color: #2d3748;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
  transition: background 0.2s;
}

.quick-split-buttons button:hover {
  background: #ed8936;
  color: white;
}

.time-totals {
  text-align: right;
  color: #2d3748;
  font-size: 1.05rem;
  padding: 0.5rem;
  background: white;
  border-radius: 4px;
}

.readonly-field {
  background: #f7fafc;
  cursor: not-allowed;
}
</style>
