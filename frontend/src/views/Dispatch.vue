<template>
  <div>
    <div class="dispatch-header">
      <h1>Dispatch Management</h1>
      
      <div class="view-toggle">
        <button 
          @click="viewMode = 'table'" 
          :class="['view-btn', { active: viewMode === 'table' }]"
        >
          📋 Table
        </button>
        <button 
          @click="viewMode = 'calendar'" 
          :class="['view-btn', { active: viewMode === 'calendar' }]"
        >
          📅 Calendar
        </button>
      </div>
    </div>
    
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
      
      <!-- Calendar-specific filters -->
      <template v-if="viewMode === 'calendar'">
        <select v-model="driverFilter" class="driver-filter">
          <option value="">All Drivers</option>
          <option v-for="driver in drivers" :key="driver.employee_id" :value="driver.employee_id">
            {{ driver.first_name }} {{ driver.last_name }}
          </option>
        </select>
        
        <select v-model="vehicleFilter" class="vehicle-filter">
          <option value="">All Vehicles</option>
          <option v-for="vehicle in vehicles" :key="vehicle.vehicle_id" :value="vehicle.vehicle_id">
            {{ vehicle.vehicle_number }} - {{ vehicle.make }} {{ vehicle.model }}
          </option>
        </select>
      </template>
    </div>

    <!-- Calendar View -->
    <div v-if="viewMode === 'calendar'" class="calendar-view">
      <FullCalendar
        ref="calendar"
        :options="calendarOptions"
      />
    </div>

    <!-- Main Booking Management Table -->
    <div v-if="viewMode === 'table'" class="dispatch-section">
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
    
    <!-- Day Detail Modal -->
    <div v-if="showDayDetail" class="modal-overlay" @click="showDayDetail = false">
      <div class="day-detail-modal" @click.stop>
        <div class="modal-header">
          <h3>📅 {{ formatDayDetailDate(selectedDayDate) }}</h3>
          <button @click="showDayDetail = false" class="close-btn">✕</button>
        </div>
        
        <div class="modal-body">
          <div class="day-timeline">
            <div v-for="charter in selectedDayCharters" :key="charter.charter_id" class="timeline-event">
              <div class="event-time">{{ charter.pickup_time ? charter.pickup_time.substring(0, 5) : 'TBD' }}</div>
              <div class="event-details" @click="goToCharter(charter.charter_id)">
                <div class="event-title">
                  <strong>#{{ charter.reserve_number }}</strong> - {{ charter.client_name }}
                </div>
                <div class="event-meta">
                  <span class="meta-item">🚗 {{ charter.vehicle_type_requested }}</span>
                  <span class="meta-item">👤 {{ charter.driver_name || 'Unassigned' }}</span>
                  <span class="meta-item">👥 {{ charter.passenger_count }} pax</span>
                </div>
                <div class="event-route">
                  📍 {{ charter.pickup_address }} → {{ charter.dropoff_address }}
                </div>
              </div>
              <div :class="['event-status', `status-${charter.status}`]">
                {{ charter.status }}
              </div>
            </div>
            
            <p v-if="!selectedDayCharters.length" class="no-events">
              No charters scheduled for this day
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'
import BookingForm from '../components/BookingForm.vue'
import { formatDate, dateOnly } from '@/utils/dateFormatter'

export default {
  name: 'Dispatch',
  components: {
    BookingForm,
    FullCalendar
  },
  data() {
    return {
      viewMode: 'table',
      searchText: '',
      statusFilter: '',
      searchDate: '',
      driverFilter: '',
      vehicleFilter: '',
      showBookingForm: false,
      showDayDetail: false,
      selectedDayDate: null,
      selectedDayCharters: [],
      bookings: [],
      drivers: [],
      vehicles: [],
      stats: {
        activeBookings: 0,
        availableVehicles: 0,
        pendingAssignments: 0,
        activeRoutes: 0
      },
      calendarOptions: {
        plugins: [dayGridPlugin, timeGridPlugin, interactionPlugin],
        initialView: 'dayGridMonth',
        headerToolbar: {
          left: 'prev,next today',
          center: 'title',
          right: 'dayGridMonth,timeGridWeek,timeGridDay'
        },
        events: [],
        editable: false,
        selectable: true,
        selectMirror: true,
        dayMaxEvents: 3,
        weekends: true,
        eventClick: this.handleEventClick,
        dateClick: this.handleDateClick,
        eventContent: this.renderEventContent
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
      
      if (this.driverFilter) {
        filtered = filtered.filter(b => b.assigned_driver_id == this.driverFilter);
      }
      
      if (this.vehicleFilter) {
        filtered = filtered.filter(b => b.vehicle_booked_id == this.vehicleFilter);
      }
      
      return filtered;
    }
  },
  
  watch: {
    filteredBookings: {
      handler() {
        if (this.viewMode === 'calendar') {
          this.updateCalendarEvents();
        }
      },
      deep: true
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
      this.showDayDetail = false;
      this.$router.push(`/charter/${charterId}`);
    },
    
    async loadDrivers() {
      try {
        const response = await fetch('/api/employees?role=driver');
        const data = await response.json();
        this.drivers = data;
      } catch (error) {
        console.error('Error loading drivers:', error);
      }
    },
    
    async loadVehicles() {
      try {
        const response = await fetch('/api/vehicles');
        const data = await response.json();
        this.vehicles = data;
      } catch (error) {
        console.error('Error loading vehicles:', error);
      }
    },
    
    updateCalendarEvents() {
      const events = this.filteredBookings.map(charter => {
        const duration = this.estimateCharterDuration(charter);
        const startTime = charter.pickup_time || '08:00:00';
        
        return {
          id: charter.charter_id,
          title: `#${charter.reserve_number} - ${charter.client_name}`,
          start: `${charter.charter_date}T${startTime}`,
          end: this.calculateEndTime(charter.charter_date, startTime, duration),
          backgroundColor: this.getStatusColor(charter.status),
          borderColor: this.getStatusColor(charter.status),
          extendedProps: {
            charter: charter
          }
        };
      });
      
      this.calendarOptions.events = events;
    },
    
    estimateCharterDuration(charter) {
      const type = charter.charter_type?.toLowerCase() || '';
      const quoted = charter.quoted_hours || 0;
      
      const durations = {
        'wedding': 6,
        'airport': 2,
        'funeral': 4,
        'concert': 5,
        'corporate': 3,
        'hourly': quoted || 3,
        'default': 2
      };
      
      for (const [key, hours] of Object.entries(durations)) {
        if (type.includes(key)) {
          return hours;
        }
      }
      
      return durations.default;
    },
    
    calculateEndTime(date, startTime, durationHours) {
      const start = new Date(`${date}T${startTime}`);
      start.setHours(start.getHours() + durationHours);
      return start.toISOString();
    },
    
    getStatusColor(status) {
      const colors = {
        'quote': '#9E9E9E',
        'confirmed': '#2196F3',
        'assigned': '#4CAF50',
        'in progress': '#FF9800',
        'completed': '#607D8B',
        'cancelled': '#F44336',
        'pending': '#FFC107'
      };
      return colors[status?.toLowerCase()] || '#9E9E9E';
    },
    
    handleEventClick(info) {
      const charterId = info.event.id;
      this.goToCharter(charterId);
    },
    
    handleDateClick(info) {
      this.selectedDayDate = info.dateStr;
      this.loadDayCharters(info.dateStr);
      this.showDayDetail = true;
    },
    
    loadDayCharters(date) {
      this.selectedDayCharters = this.filteredBookings.filter(c => c.charter_date === date);
    },
    
    formatDayDetailDate(dateStr) {
      if (!dateStr) return '';
      const date = new Date(dateStr + 'T00:00:00');
      return date.toLocaleDateString('en-US', { 
        weekday: 'long', 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
      });
    },
    
    renderEventContent(eventInfo) {
      const charter = eventInfo.event.extendedProps.charter;
      const time = charter.pickup_time?.substring(0, 5) || '';
      
      return {
        html: `
          <div class="custom-event">
            <div class="event-time-badge">${time}</div>
            <div class="event-title-text">#${charter.reserve_number}</div>
            <div class="event-client">${charter.client_name}</div>
          </div>
        `
      };
    },

    formatDate,
    dateOnly,
  },
  
  async mounted() {
    await Promise.all([
      this.loadBookings(),
      this.loadDrivers(),
      this.loadVehicles()
    ]);
  }
}
</script>

<style scoped>
.dispatch-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.dispatch-header h1 {
  margin: 0;
  color: #2d3748;
}

.view-toggle {
  display: flex;
  gap: 0.5rem;
  background: #f7fafc;
  padding: 4px;
  border-radius: 8px;
}

.view-btn {
  padding: 0.5rem 1.5rem;
  border: none;
  background: transparent;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.3s;
  color: #4a5568;
}

.view-btn:hover {
  background: #edf2f7;
}

.view-btn.active {
  background: #667eea;
  color: white;
  box-shadow: 0 2px 4px rgba(102, 126, 234, 0.3);
}

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

/* Calendar View */
.calendar-view {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

:deep(.custom-event) {
  padding: 2px 4px;
  font-size: 0.85rem;
}

:deep(.event-time-badge) {
  font-weight: 700;
  color: inherit;
}

:deep(.event-title-text) {
  font-weight: 600;
}

:deep(.event-client) {
  font-size: 0.75rem;
  opacity: 0.9;
}

/* Day Detail Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
}

.day-detail-modal {
  background: white;
  border-radius: 12px;
  max-width: 800px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.day-detail-modal .modal-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 12px 12px 0 0;
  padding: 1.5rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.day-detail-modal .modal-header h3 {
  margin: 0;
  color: white;
}

.day-detail-modal .close-btn {
  background: rgba(255, 255, 255, 0.2);
  color: white;
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 1.2rem;
}

.day-detail-modal .close-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}

.modal-body {
  padding: 2rem;
}

.day-timeline {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.timeline-event {
  display: grid;
  grid-template-columns: 80px 1fr 120px;
  gap: 1rem;
  padding: 1rem;
  background: #f7fafc;
  border-radius: 8px;
  border-left: 4px solid #667eea;
  cursor: pointer;
  transition: all 0.3s;
}

.timeline-event:hover {
  background: #edf2f7;
  transform: translateX(4px);
}

.event-time {
  font-weight: 700;
  color: #667eea;
  font-size: 1.1rem;
}

.event-details {
  flex: 1;
}

.event-title {
  margin-bottom: 0.5rem;
}

.event-meta {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.5rem;
  font-size: 0.9rem;
  color: #718096;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.event-route {
  font-size: 0.85rem;
  color: #a0aec0;
}

.event-status {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.75rem;
}

.event-status.status-quote { background: #e2e8f0; color: #2d3748; }
.event-status.status-confirmed { background: #bee3f8; color: #2c5282; }
.event-status.status-assigned { background: #c6f6d5; color: #22543d; }
.event-status.status-in-progress { background: #fed7d7; color: #742a2a; }
.event-status.status-completed { background: #e2e8f0; color: #2d3748; }
.event-status.status-cancelled { background: #fed7d7; color: #742a2a; }
.event-status.status-pending { background: #fefcbf; color: #744210; }

.no-events {
  text-align: center;
  color: #a0aec0;
  padding: 3rem;
  font-style: italic;
}
</style>