<template>
  <div class="dispatch-section">
    <h2>🚗 Dispatch</h2>
    
    <div class="dispatch-row">
      <div class="dispatch-field">
        <label>Vehicle</label>
        <select 
          :value="vehicleId"
          @change="$emit('update:vehicleId', parseInt($event.target.value))"
          @input="onVehicleChange"
        >
          <option value="">-- Select Vehicle --</option>
          <option v-for="v in vehicles" :key="v.vehicle_id" :value="v.vehicle_id">
            {{ v.vehicle_number }} - {{ v.make }} {{ v.model }}
          </option>
        </select>
        <div v-if="vehicleId && selectedVehicle" class="info-display vehicle-display">
          {{ selectedVehicle.vehicle_number }} - {{ selectedVehicle.vehicle_type || selectedVehicle.make + ' ' + selectedVehicle.model }}
          <small v-if="selectedVehicle.license_plate">({{ selectedVehicle.license_plate }})</small>
        </div>
      </div>

      <div class="dispatch-field">
        <label>Chauffeur</label>
        <select 
          :value="chauffeurId"
          @change="$emit('update:chauffeurId', parseInt($event.target.value))"
          @input="onChauffeurChange"
        >
          <option value="">-- Select Chauffeur --</option>
          <option v-for="c in chauffeurs" :key="c.employee_id" :value="c.employee_id">
            {{ c.first_name }} {{ c.last_name }}
          </option>
        </select>
        <div v-if="chauffeurId && selectedChauffeur" class="info-display chauffeur-display">
          {{ selectedChauffeur.first_name }} {{ selectedChauffeur.last_name }}
          <small v-if="selectedChauffeur.employee_category"> - {{ selectedChauffeur.employee_category }}</small>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'

const props = defineProps({
  vehicleId: Number,
  chauffeurId: Number
})

const emit = defineEmits(['update:vehicleId', 'update:chauffeurId'])

const vehicles = ref([])
const chauffeurs = ref([])

const selectedVehicle = computed(() => {
  return vehicles.value.find(v => v.vehicle_id === props.vehicleId)
})

const selectedChauffeur = computed(() => {
  return chauffeurs.value.find(c => c.employee_id === props.chauffeurId)
})

const loadVehicles = async () => {
  try {
    // TODO: Replace with actual API call
    const response = await fetch('/api/vehicles')
    vehicles.value = await response.json()
  } catch (error) {
    console.error('Failed to load vehicles:', error)
    // Mock data for development
    vehicles.value = [
      { vehicle_id: 1, vehicle_number: 'L-10', make: 'Lincoln', model: 'MKT', vehicle_type: 'Luxury Sedan (4 pax)', license_plate: 'ABC 123' },
      { vehicle_id: 2, vehicle_number: 'L-14', make: 'Cadillac', model: 'XTS', vehicle_type: 'Luxury Sedan (4 pax)', license_plate: 'DEF 456' },
      { vehicle_id: 3, vehicle_number: 'L-18', make: 'Ford', model: 'Transit', vehicle_type: 'Shuttle Bus (18 pax)', license_plate: 'GHI 789' }
    ]
  }
}

const loadChauffeurs = async () => {
  try {
    // TODO: Replace with actual API call
    const response = await fetch('/api/employees?category=chauffeur')
    chauffeurs.value = await response.json()
  } catch (error) {
    console.error('Failed to load chauffeurs:', error)
    // Mock data for development
    chauffeurs.value = [
      { employee_id: 1, first_name: 'John', last_name: 'Smith', employee_category: 'Lead Chauffeur' },
      { employee_id: 2, first_name: 'Jane', last_name: 'Doe', employee_category: 'Chauffeur' },
      { employee_id: 3, first_name: 'Mike', last_name: 'Johnson', employee_category: 'Senior Chauffeur' }
    ]
  }
}

const onVehicleChange = () => {
  // Emit vehicle selection for pricing updates
  emit('vehicle-selected', selectedVehicle.value)
}

const onChauffeurChange = () => {
  // Emit chauffeur selection
  emit('chauffeur-selected', selectedChauffeur.value)
}

onMounted(() => {
  loadVehicles()
  loadChauffeurs()
})
</script>

<style scoped>
.dispatch-section {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  border: 2px solid #48bb78;
}

.dispatch-section h2 {
  margin: 0 0 0.5rem 0;
  color: #2d3748;
  font-size: 1.3rem;
}

.dispatch-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.dispatch-field label {
  display: block;
  font-weight: 600;
  margin-bottom: 0.25rem;
  color: #2d3748;
  font-size: 0.85rem;
}

.dispatch-field select {
  width: 100%;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
}

.dispatch-field select:focus {
  outline: none;
  border-color: #48bb78;
  box-shadow: 0 0 0 3px rgba(72, 187, 120, 0.1);
}

.info-display {
  background: #f7fafc;
  padding: 0.75rem;
  border-radius: 4px;
  font-weight: 600;
  color: #2d3748;
  font-size: 0.9rem;
}

.vehicle-display {
  border-left: 4px solid #48bb78;
}

.chauffeur-display {
  border-left: 4px solid #667eea;
}

.info-display small {
  display: block;
  font-weight: normal;
  color: #718096;
  margin-top: 0.25rem;
  font-size: 0.85rem;
}
</style>
