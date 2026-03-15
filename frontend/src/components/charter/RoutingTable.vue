<template>
  <div class="routing-table-wrapper">
    <div class="routing-header">
      <h2>🗺️ Routing & Charges</h2>
      <div class="routing-controls">
        <button @click="$emit('toggle-lock')" :class="['btn-lock', { locked: isLocked }]">
          {{ isLocked ? '🔒 Locked' : '🔓 Allow Edits' }}
        </button>
        <button @click="$emit('add-route')" :disabled="isLocked" class="btn-add">
          ➕ Add Split Run Stops
        </button>
      </div>
    </div>

    <div class="routing-table">
      <draggable 
        v-model="localRoutes" 
        @end="onDragEnd"
        item-key="id"
        :disabled="isLocked"
        handle=".drag-handle"
      >
        <template #item="{ element: route, index }">
          <div class="route-row" :class="{ 'non-billable': !route.is_billable }">
            <!-- Route Type -->
            <div class="route-cell type-cell">
              <select 
                :value="route.route_type"
                @change="updateRoute(index, 'route_type', $event.target.value)"
                :disabled="isLocked"
              >
                <option value="pickup_at">Pickup At</option>
                <option value="dropoff_at">Drop-off At</option>
                <option value="leave_red_deer">Leave Red Deer</option>
                <option value="pickup_in">Pickup In</option>
                <option value="drop_off_at">Drop Off At</option>
                <option value="return_to_red_deer">Return to Red Deer</option>
                <option value="standby_stop">Standby Stop</option>
                <option value="breakdown_at">Breakdown At</option>
                <option value="new_vehicle_arrived">New Vehicle Arrived</option>
                <option value="extra_time_starts">Extra Time Starts</option>
                <option value="travel_arrangement">Travel Arrangement</option>
              </select>
            </div>

            <!-- Description/Address -->
            <div class="route-cell description-cell">
              <input 
                type="text"
                :value="route.description"
                @input="updateRoute(index, 'description', $event.target.value)"
                :disabled="isLocked"
                placeholder="Address or location..."
              />
            </div>

            <!-- Notes -->
            <div class="route-cell notes-cell">
              <input 
                type="text"
                :value="route.notes"
                @input="updateRoute(index, 'notes', $event.target.value)"
                :disabled="isLocked"
                placeholder="Route notes..."
              />
            </div>

            <!-- Time Start -->
            <div class="route-cell time-cell">
              <label>Time:</label>
              <input 
                type="time"
                :value="route.time_start"
                @input="updateRoute(index, 'time_start', $event.target.value); $emit('calculate-billed-time', index)"
                :disabled="isLocked"
              />
            </div>

            <!-- Time Finish -->
            <div class="route-cell time-cell">
              <label>To:</label>
              <input 
                type="time"
                :value="route.time_finish"
                @input="updateRoute(index, 'time_finish', $event.target.value); $emit('calculate-billed-time', index)"
                :disabled="isLocked"
              />
            </div>

            <!-- Billed Time -->
            <div class="route-cell billed-time-cell">
              <span :class="{ 'non-billable-text': !route.is_billable }">
                {{ route.billed_time_display || '--' }}
              </span>
            </div>

            <!-- Actions -->
            <div class="route-cell actions-cell">
              <button 
                @click="$emit('move-up', index)" 
                :disabled="isLocked || index === 0"
                class="btn-action"
                title="Move Up"
              >
                ▲
              </button>
              <button 
                @click="$emit('move-down', index)" 
                :disabled="isLocked || index === routes.length - 1"
                class="btn-action"
                title="Move Down"
              >
                ▼
              </button>
              <button 
                @click="$emit('delete-route', index)" 
                :disabled="isLocked || routes.length <= 2"
                class="btn-delete"
                title="Delete Route"
              >
                🗑️
              </button>
            </div>
          </div>
        </template>
      </draggable>
    </div>

    <!-- Routing Summary -->
    <div class="routing-summary">
      <strong>Total Routes: {{ routes.length }}</strong>
      <span class="separator">|</span>
      <strong>Total Billed Time: {{ totalBilledTime }} hrs</strong>
      <span class="separator">|</span>
      <strong>Non-Billable Routes: {{ nonBillableCount }}</strong>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import draggable from 'vuedraggable'

const props = defineProps({
  routes: {
    type: Array,
    required: true
  },
  isLocked: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits([
  'update:routes',
  'toggle-lock',
  'add-route',
  'delete-route',
  'move-up',
  'move-down',
  'calculate-billed-time'
])

const localRoutes = ref([...props.routes])

watch(() => props.routes, (newRoutes) => {
  localRoutes.value = [...newRoutes]
}, { deep: true })

watch(localRoutes, (newRoutes) => {
  emit('update:routes', newRoutes)
}, { deep: true })

const updateRoute = (index, field, value) => {
  localRoutes.value[index][field] = value
}

const onDragEnd = () => {
  emit('update:routes', localRoutes.value)
}

const totalBilledTime = computed(() => {
  return props.routes
    .filter(r => r.is_billable)
    .reduce((sum, r) => sum + (parseFloat(r.billed_hours) || 0), 0)
    .toFixed(2)
})

const nonBillableCount = computed(() => {
  return props.routes.filter(r => !r.is_billable).length
})
</script>

<style scoped>
.routing-table-wrapper {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  border: 2px solid #4299e1;
}

.routing-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
}

.routing-header h2 {
  margin: 0;
  color: #2d3748;
  font-size: 1.3rem;
}

.routing-controls {
  display: flex;
  gap: 0.75rem;
}

.routing-controls button {
  padding: 0.4rem 0.75rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
  transition: all 0.2s;
}

.btn-lock {
  background: #cbd5e0;
  color: #2d3748;
}

.btn-lock.locked {
  background: #fc8181;
  color: white;
}

.btn-add {
  background: #48bb78;
  color: white;
}

.btn-add:hover:not(:disabled) {
  background: #38a169;
}

.btn-add:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.routing-table {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.route-row {
  display: grid;
  grid-template-columns: 180px 1fr 3fr 120px 120px 100px 100px;
  gap: 0.25rem;
  padding: 0.5rem;
  border-bottom: 1px solid #e2e8f0;
  align-items: center;
  background: white;
  transition: background 0.2s;
}

.route-row:hover {
  background: #f7fafc;
}

.route-row.non-billable {
  background: #fffaf0;
}



.route-cell input,
.route-cell select {
  width: 100%;
  padding: 0.4rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-size: 0.9rem;
}

.route-cell label {
  font-size: 0.7rem;
  color: #718096;
  margin-right: 0.25rem;
  white-space: nowrap;
  display: inline-block;
}

.route-cell input:disabled,
.route-cell select:disabled {
  background: #f7fafc;
  cursor: not-allowed;
}

.route-cell input:focus:not(:disabled),
.route-cell select:focus:not(:disabled) {
  outline: none;
  border-color: #4299e1;
  box-shadow: 0 0 0 3px rgba(66, 153, 225, 0.1);
}

.billed-time-cell {
  text-align: center;
  font-weight: 600;
  color: #2d3748;
}

.non-billable-text {
  color: #f6ad55;
  font-style: italic;
}

.actions-cell {
  display: flex;
  gap: 0.25rem;
  justify-content: center;
}

.btn-action,
.btn-delete {
  padding: 0.25rem 0.5rem;
  border: none;
  border-radius: 3px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
}

.btn-action {
  background: #e2e8f0;
  color: #2d3748;
}

.btn-action:hover:not(:disabled) {
  background: #cbd5e0;
}

.btn-action:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.btn-delete {
  background: #fc8181;
  color: white;
}

.btn-delete:hover:not(:disabled) {
  background: #f56565;
}

.btn-delete:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.routing-summary {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  padding: 1rem;
  background: #f7fafc;
  border-radius: 6px;
  color: #2d3748;
  font-size: 0.95rem;
}

.separator {
  color: #cbd5e0;
}
</style>
