<template>
  <div class="booking-page">
    <div class="page-header">
      <h1>🆕 Create New Booking</h1>
      <p>Fill out the form below to create a new charter booking or quote.</p>
    </div>
    <div class="page-content">
      <BookingFormLMS />
    </div>
  </div>
 </template>

<script setup>
import BookingFormLMS from '@/components/BookingFormLMS.vue'
</script>

<style scoped>
.booking-page {
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 2rem;
  border-bottom: 2px solid #1976d2;
  padding-bottom: 1rem;
}

.page-header h1 {
  margin: 0;
  color: #1976d2;
}

.page-header p {
  margin: 0.5rem 0 0 0;
  color: #666;
  font-size: 1.1rem;
}

.page-content {
  background: #f9f9f9;
  padding: 2rem;
  border-radius: 8px;
}
</style>