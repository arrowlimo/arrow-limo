<template>
  <div>
    <h1>Vehicle Management</h1>
    <div class="vehicle-section">
      <VehicleForm />
    </div>
  </div>
</template>

<script setup>
import VehicleForm from '../components/VehicleForm.vue'
</script>

<style scoped>
.vehicle-section {
  background: #fff;
  border-radius: 8px;
  padding: 2rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  margin-top: 2rem;
}
</style>
