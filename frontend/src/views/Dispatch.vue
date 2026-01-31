<template>
  <div>
    <h1>Dispatch Management</h1>
    
    <!-- Dispatch Stats -->
    <div class="dispatch-stats">
      <div class="stat-card active">
        <div class="stat-value">{{ stats.activeBookings }}</div>
        <div class="stat-label">Active Bookings</div>
      </div>
      <div class="stat-card available">
        <div class="stat-value">{{ stats.availableVehicles }}</div>
        <div class="stat-label">Available Vehicles</div>
      </div>
      <div class="stat-card pending">
        <div class="stat-value">{{ stats.pendingAssignments }}</div>
        <div class="stat-label">Pending Assignments</div>
      </div>
      <div class="stat-card routes">
        <div class="stat-value">{{ stats.activeRoutes }}</div>
        <div class="stat-label">Active Routes</div>
      </div>
    </div>

    <!-- Booking Filters -->
    <div class="booking-filters">
      <input v-model="searchText" placeholder="Search (client, vehicle, notes, etc.)" />
      <select v-model="statusFilter" class="status-filter">
        <option value="">All Status</option>
        <option value="pending">Pending</option>
        <option value="assigned">Assigned</option>
        <option value="active">Active</option>
        <option value="completed">Completed</option>
      </select>
      <input v-model="searchDate" type="date" placeholder="Date" />
    </div>

    <!-- Main Booking Management Table -->
    <div class="dispatch-section">
      <div class="section-header">
        <h2>Booking Management</h2>
        <button @click="showBookingForm = true" class="btn-primary">+ New Booking</button>
      </div>
      
      <!-- Booking Form Modal -->
      <div v-if="showBookingForm" class="booking-form-modal">
        <div class="modal-content">
          <div class="modal-header">
            <h3>Create New Booking</h3>
            <button @click="showBookingForm = false" class="close-btn">×</button>
          </div>
          <BookingForm @booking-saved="onBookingSaved" @cancel="showBookingForm = false" />
        </div>
      </div>
      
      <table class="bookings-table">
        <thead>
          <tr>
            <th>Reserve #</th>
            <th>Date</th>
            <th>Client</th>
            <th>Vehicle</th>
            <th>Driver</th>
            <th>Status</th>
            <th>Passengers</th>
            <th>Vehicle Cap</th>
            <th>Pickup</th>
            <th>Notes</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in filteredBookings" :key="b.charter_id" :class="getRowClass(b)" @click="goToCharter(b.charter_id)" style="cursor: pointer;">
            <td>{{ b.reserve_number || '(unknown)' }}</td>
            <td>{{ formatDate(b.charter_date) || '(unknown)' }}</td>
            <td>{{ b.client_name || '(unknown)' }}</td>
            <td>{{ b.vehicle_type_requested || '(unknown)' }}</td>
            <td>{{ b.driver_name || '(unknown)' }}</td>
            <td :class="'status-' + (b.status || 'pending')">
              {{ b.status || 'pending' }}
            </td>
            <td>{{ b.passenger_load !== undefined && b.passenger_load !== null ? b.passenger_load : '(unknown)' }}</td>
            <td>{{ b.vehicle_capacity !== undefined && b.vehicle_capacity !== null ? b.vehicle_capacity : '(unknown)' }}</td>
            <td>{{ truncateText(b.pickup_address, 30) || '(unknown)' }}</td>
            <td>{{ truncateText(b.vehicle_notes, 20) || '(unknown)' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script>

import BookingForm from '../components/BookingForm.vue'
import { formatDate, dateOnly } from '@/utils/dateFormatter'

export default {
  name: 'Dispatch',
  components: {
    BookingForm
  },
  data() {
    return {
      searchText: '',
      statusFilter: '',
      searchDate: '',
      showBookingForm: false,
      bookings: [],
      stats: {
        activeBookings: 0,
        availableVehicles: 0,
        pendingAssignments: 0,
        activeRoutes: 0
      }
    }
  },
  computed: {
    filteredBookings() {
      let filtered = this.bookings;
      
      if (this.searchText) {
        const search = this.searchText.toLowerCase();
        filtered = filtered.filter(b => 
          (b.client_name && b.client_name.toLowerCase().includes(search)) ||
          (b.vehicle_type_requested && b.vehicle_type_requested.toLowerCase().includes(search)) ||
          (b.driver_name && b.driver_name.toLowerCase().includes(search)) ||
          (b.pickup_address && b.pickup_address.toLowerCase().includes(search)) ||
          (b.vehicle_notes && b.vehicle_notes.toLowerCase().includes(search))
        );
      }
      
      if (this.statusFilter) {
        filtered = filtered.filter(b => (b.status || 'pending') === this.statusFilter);
      }
      
      if (this.searchDate) {
        filtered = filtered.filter(b => this.dateOnly(b.charter_date) === this.searchDate);
      }
      
      return filtered;
    }
  },
  methods: {
    truncateText(text, maxLength) {
      if (!text) return '';
      return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
    },

    getRowClass(booking) {
      const status = booking.status || 'pending';
      return `row-${status}`;
    },

    async loadBookings() {
      try {
        const response = await fetch('/api/bookings');
        const data = await response.json();
        // API returns { bookings: [...] }
        this.bookings = Array.isArray(data) ? data : (data.bookings || []);
        this.calculateStats();
      } catch (error) {
        console.error('Error loading bookings:', error);
      }
    },

    calculateStats() {
      this.stats.activeBookings = this.bookings.filter(b => 
        ['assigned', 'active'].includes(b.status)
      ).length;

      this.stats.pendingAssignments = this.bookings.filter(b => 
        b.status === 'pending'
      ).length;

      // Placeholder values - these would come from actual API calls
      this.stats.availableVehicles = 12;
      this.stats.activeRoutes = 8;
    },

    onBookingSaved() {
      this.showBookingForm = false;
      this.loadBookings(); // Refresh the bookings list
    },

    goToCharter(charterId) {
      this.$router.push(`/charter/${charterId}`);
    },

    formatDate,
    dateOnly,
  },
  
  async mounted() {
    await this.loadBookings();
  }
}
</script>

<style scoped>
.dispatch-stats {
  display: flex;
  gap: 20px;
  margin-bottom: 30px;
}

.stat-card {
  background: white;
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  min-width: 120px;
}

.stat-value {
  font-size: 2rem;
  font-weight: bold;
  margin-bottom: 5px;
}

.stat-card.active .stat-value { color: #28a745; }
.stat-card.available .stat-value { color: #007bff; }
.stat-card.pending .stat-value { color: #ffc107; }
.stat-card.routes .stat-value { color: #6f42c1; }

.stat-label {
  font-size: 0.9rem;
  color: #666;
}

.booking-filters {
  display: flex;
  gap: 15px;
  margin-bottom: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 8px;
}

.booking-filters input, .booking-filters select {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.dispatch-section {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.btn-primary {
  background: #007bff;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 5px;
  cursor: pointer;
  font-weight: 500;
}

.btn-primary:hover {
  background: #0056b3;
}

.booking-form-modal {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  max-width: 90%;
  max-height: 90%;
  overflow: auto;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #eee;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #999;
}

.close-btn:hover {
  color: #333;
}

.bookings-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 15px;
}

.bookings-table th,
.bookings-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.bookings-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #333;
}

.bookings-table tr:hover {
  background-color: #f5f5f5;
}

.status-pending { color: #ffc107; font-weight: bold; }
.status-assigned { color: #007bff; font-weight: bold; }
.status-active { color: #28a745; font-weight: bold; }
.status-completed { color: #6c757d; font-weight: bold; }

.row-active { background-color: #d4edda; }
.row-pending { background-color: #fff3cd; }
.row-completed { background-color: #f8f9fa; }
</style>