<template>
  <div class="hos-driver-section">
    <h2>🚗 HOS & Driver Details</h2>
    
    <div class="hos-grid">
      <!-- Driver Hours of Service -->
      <div class="form-field">
        <label>HOS Start Time</label>
        <input 
          type="time"
          :value="hosStartTime"
          @input="$emit('update:hosStartTime', $event.target.value)"
        />
      </div>

      <div class="form-field">
        <label>HOS End Time</label>
        <input 
          type="time"
          :value="hosEndTime"
          @input="$emit('update:hosEndTime', $event.target.value)"
        />
      </div>

      <div class="form-field">
        <label>Total HOS Hours</label>
        <input 
          type="text"
          :value="totalHOSHours"
          readonly
          class="readonly-field"
        />
      </div>

      <!-- Driver Meal Breaks -->
      <div class="form-field">
        <label>Meal Break 1 (Start)</label>
        <input 
          type="time"
          :value="mealBreak1Start"
          @input="$emit('update:mealBreak1Start', $event.target.value)"
        />
      </div>

      <div class="form-field">
        <label>Meal Break 1 (End)</label>
        <input 
          type="time"
          :value="mealBreak1End"
          @input="$emit('update:mealBreak1End', $event.target.value)"
        />
      </div>

      <div class="form-field">
        <label>Meal Break 2 (Start)</label>
        <input 
          type="time"
          :value="mealBreak2Start"
          @input="$emit('update:mealBreak2Start', $event.target.value)"
        />
      </div>

      <div class="form-field">
        <label>Meal Break 2 (End)</label>
        <input 
          type="time"
          :value="mealBreak2End"
          @input="$emit('update:mealBreak2End', $event.target.value)"
        />
      </div>

      <!-- Driver Pay -->
      <div class="form-field">
        <label>Driver Hourly Rate</label>
        <input 
          type="number"
          step="0.01"
          :value="driverHourlyRate"
          @input="$emit('update:driverHourlyRate', parseFloat($event.target.value) || 0)"
          placeholder="0.00"
        />
      </div>

      <div class="form-field">
        <label>Driver Total Pay</label>
        <input 
          type="number"
          step="0.01"
          :value="driverTotalPay"
          readonly
          class="readonly-field"
        />
      </div>

      <!-- Driver Notes -->
      <div class="form-field full-width">
        <label>Driver Instructions / Notes</label>
        <textarea
          :value="driverNotes"
          @input="$emit('update:driverNotes', $event.target.value)"
          rows="3"
          placeholder="Special instructions for driver, parking details, customer contact info..."
        ></textarea>
      </div>

      <!-- Compliance Checkboxes -->
      <div class="form-field">
        <label class="checkbox-label">
          <input 
            type="checkbox"
            :checked="preInspectionComplete"
            @change="$emit('update:preInspectionComplete', $event.target.checked)"
          />
          Pre-Trip Inspection Complete
        </label>
      </div>

      <div class="form-field">
        <label class="checkbox-label">
          <input 
            type="checkbox"
            :checked="postInspectionComplete"
            @change="$emit('update:postInspectionComplete', $event.target.checked)"
          />
          Post-Trip Inspection Complete
        </label>
      </div>

      <div class="form-field">
        <label class="checkbox-label">
          <input 
            type="checkbox"
            :checked="logbookSubmitted"
            @change="$emit('update:logbookSubmitted', $event.target.checked)"
          />
          Driver Logbook Submitted
        </label>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  hosStartTime: String,
  hosEndTime: String,
  mealBreak1Start: String,
  mealBreak1End: String,
  mealBreak2Start: String,
  mealBreak2End: String,
  driverHourlyRate: Number,
  driverTotalPay: Number,
  driverNotes: String,
  preInspectionComplete: Boolean,
  postInspectionComplete: Boolean,
  logbookSubmitted: Boolean
})

defineEmits([
  'update:hosStartTime',
  'update:hosEndTime',
  'update:mealBreak1Start',
  'update:mealBreak1End',
  'update:mealBreak2Start',
  'update:mealBreak2End',
  'update:driverHourlyRate',
  'update:driverTotalPay',
  'update:driverNotes',
  'update:preInspectionComplete',
  'update:postInspectionComplete',
  'update:logbookSubmitted'
])

const totalHOSHours = computed(() => {
  if (!props.hosStartTime || !props.hosEndTime) return '--'
  
  const start = new Date(`2000-01-01T${props.hosStartTime}`)
  const end = new Date(`2000-01-01T${props.hosEndTime}`)
  
  let diff = (end - start) / (1000 * 60 * 60)
  if (diff < 0) diff += 24 // Handle midnight crossing
  
  return diff.toFixed(2) + ' hrs'
})
</script>

<style scoped>
.hos-driver-section {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  border: 2px solid #ed8936;
}

.hos-driver-section h2 {
  margin: 0 0 0.75rem 0;
  color: #2d3748;
  font-size: 1.3rem;
}

.hos-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
}

.form-field {
  display: flex;
  flex-direction: column;
}

.form-field.full-width {
  grid-column: 1 / -1;
}

.form-field label {
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: #2d3748;
  font-size: 0.85rem;
}

.form-field input,
.form-field textarea {
  width: 100%;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.9rem;
}

.form-field input:focus,
.form-field textarea:focus {
  outline: none;
  border-color: #ed8936;
  box-shadow: 0 0 0 3px rgba(237, 137, 54, 0.1);
}

.readonly-field {
  background: #f7fafc;
  cursor: not-allowed;
  font-weight: 600;
  color: #2d3748;
}

textarea {
  resize: vertical;
  font-family: inherit;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  cursor: pointer;
  font-weight: 600;
}

.checkbox-label input[type="checkbox"] {
  width: 18px;
  height: 18px;
  cursor: pointer;
}
</style>
