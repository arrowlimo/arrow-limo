<template>
  <div class="vehicle-odometer-section">
    <h2>🚙 Vehicle & Odometer</h2>
    
    <div class="odometer-grid">
      <!-- Odometer Readings -->
      <div class="form-field">
        <label>Odometer Start (km)</label>
        <input 
          type="number"
          step="0.1"
          :value="odometerStart"
          @input="$emit('update:odometerStart', parseFloat($event.target.value) || 0)"
          placeholder="0.0"
        />
      </div>

      <div class="form-field">
        <label>Odometer End (km)</label>
        <input 
          type="number"
          step="0.1"
          :value="odometerEnd"
          @input="$emit('update:odometerEnd', parseFloat($event.target.value) || 0)"
          placeholder="0.0"
        />
      </div>

      <div class="form-field">
        <label>Total Distance</label>
        <input 
          type="text"
          :value="totalDistance"
          readonly
          class="readonly-field"
        />
      </div>

      <!-- Fuel Information -->
      <div class="form-field">
        <label>Fuel Added (L)</label>
        <input 
          type="number"
          step="0.01"
          :value="fuelAdded"
          @input="$emit('update:fuelAdded', parseFloat($event.target.value) || 0)"
          placeholder="0.00"
        />
      </div>

      <div class="form-field">
        <label>Fuel Cost ($)</label>
        <input 
          type="number"
          step="0.01"
          :value="fuelCost"
          @input="$emit('update:fuelCost', parseFloat($event.target.value) || 0)"
          placeholder="0.00"
        />
      </div>

      <div class="form-field">
        <label>Fuel Economy (L/100km)</label>
        <input 
          type="text"
          :value="fuelEconomy"
          readonly
          class="readonly-field"
        />
      </div>

      <!-- Vehicle Condition -->
      <div class="form-field full-width">
        <h3>Vehicle Condition</h3>
      </div>

      <div class="form-field">
        <label>Exterior Condition</label>
        <select 
          :value="exteriorCondition"
          @change="$emit('update:exteriorCondition', $event.target.value)"
        >
          <option value="">-- Select --</option>
          <option value="excellent">Excellent</option>
          <option value="good">Good</option>
          <option value="fair">Fair</option>
          <option value="poor">Poor</option>
          <option value="damaged">Damaged</option>
        </select>
      </div>

      <div class="form-field">
        <label>Interior Condition</label>
        <select 
          :value="interiorCondition"
          @change="$emit('update:interiorCondition', $event.target.value)"
        >
          <option value="">-- Select --</option>
          <option value="excellent">Excellent</option>
          <option value="good">Good</option>
          <option value="fair">Fair</option>
          <option value="poor">Poor</option>
          <option value="damaged">Damaged</option>
        </select>
      </div>

      <div class="form-field">
        <label>Cleanliness</label>
        <select 
          :value="cleanliness"
          @change="$emit('update:cleanliness', $event.target.value)"
        >
          <option value="">-- Select --</option>
          <option value="clean">Clean</option>
          <option value="dirty">Needs Cleaning</option>
          <option value="detailed">Detailed</option>
        </select>
      </div>

      <!-- Damage/Issues -->
      <div class="form-field full-width">
        <label>Damage/Issues Reported</label>
        <textarea
          :value="damageNotes"
          @input="$emit('update:damageNotes', $event.target.value)"
          rows="3"
          placeholder="Describe any damage, issues, or maintenance needed..."
        ></textarea>
      </div>

      <!-- Service Checkboxes -->
      <div class="form-field">
        <label class="checkbox-label">
          <input 
            type="checkbox"
            :checked="needsWash"
            @change="$emit('update:needsWash', $event.target.checked)"
          />
          Vehicle Needs Wash
        </label>
      </div>

      <div class="form-field">
        <label class="checkbox-label">
          <input 
            type="checkbox"
            :checked="needsDetail"
            @change="$emit('update:needsDetail', $event.target.checked)"
          />
          Vehicle Needs Detail
        </label>
      </div>

      <div class="form-field">
        <label class="checkbox-label">
          <input 
            type="checkbox"
            :checked="needsService"
            @change="$emit('update:needsService', $event.target.checked)"
          />
          Vehicle Needs Service
        </label>
      </div>

      <!-- Photo Upload -->
      <div class="form-field full-width">
        <label>Vehicle Photos (Damage Documentation)</label>
        <input 
          type="file"
          multiple
          accept="image/*"
          @change="handlePhotoUpload"
        />
        <div v-if="uploadedPhotos.length" class="photo-preview">
          <div v-for="(photo, idx) in uploadedPhotos" :key="idx" class="photo-item">
            <img :src="photo.url" :alt="`Photo ${idx + 1}`" />
            <button @click="removePhoto(idx)" class="remove-photo">✕</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  odometerStart: Number,
  odometerEnd: Number,
  fuelAdded: Number,
  fuelCost: Number,
  exteriorCondition: String,
  interiorCondition: String,
  cleanliness: String,
  damageNotes: String,
  needsWash: Boolean,
  needsDetail: Boolean,
  needsService: Boolean
})

const emit = defineEmits([
  'update:odometerStart',
  'update:odometerEnd',
  'update:fuelAdded',
  'update:fuelCost',
  'update:exteriorCondition',
  'update:interiorCondition',
  'update:cleanliness',
  'update:damageNotes',
  'update:needsWash',
  'update:needsDetail',
  'update:needsService'
])

const uploadedPhotos = ref([])

const totalDistance = computed(() => {
  if (!props.odometerStart || !props.odometerEnd) return '--'
  const distance = props.odometerEnd - props.odometerStart
  if (distance < 0) return 'Invalid'
  return distance.toFixed(1) + ' km'
})

const fuelEconomy = computed(() => {
  if (!props.fuelAdded || !props.odometerStart || !props.odometerEnd) return '--'
  const distance = props.odometerEnd - props.odometerStart
  if (distance <= 0) return '--'
  const economy = (props.fuelAdded / distance) * 100
  return economy.toFixed(2) + ' L/100km'
})

const handlePhotoUpload = (event) => {
  const files = Array.from(event.target.files)
  files.forEach(file => {
    const reader = new FileReader()
    reader.onload = (e) => {
      uploadedPhotos.value.push({
        url: e.target.result,
        file: file,
        name: file.name
      })
    }
    reader.readAsDataURL(file)
  })
}

const removePhoto = (index) => {
  uploadedPhotos.value.splice(index, 1)
}
</script>

<style scoped>
.vehicle-odometer-section {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  border: 2px solid #4299e1;
}

.vehicle-odometer-section h2 {
  margin: 0 0 0.75rem 0;
  color: #2d3748;
  font-size: 1.3rem;
}

.vehicle-odometer-section h3 {
  margin: 0;
  color: #2d3748;
  font-size: 1.1rem;
  font-weight: 600;
}

.odometer-grid {
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
.form-field select,
.form-field textarea {
  width: 100%;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.9rem;
}

.form-field input:focus,
.form-field select:focus,
.form-field textarea:focus {
  outline: none;
  border-color: #4299e1;
  box-shadow: 0 0 0 3px rgba(66, 153, 225, 0.1);
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

.photo-preview {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 0.5rem;
  margin-top: 0.5rem;
}

.photo-item {
  position: relative;
  border: 2px solid #cbd5e0;
  border-radius: 4px;
  overflow: hidden;
}

.photo-item img {
  width: 100%;
  height: 120px;
  object-fit: cover;
}

.remove-photo {
  position: absolute;
  top: 0.25rem;
  right: 0.25rem;
  background: #fc8181;
  color: white;
  border: none;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  cursor: pointer;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.remove-photo:hover {
  background: #f56565;
}
</style>
