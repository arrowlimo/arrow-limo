<!--
  Employee Scheduling Component
  Purpose: Manage schedules for non-charter employees (bookkeepers, cleaners, part-time, etc.)
  Features: Time tracking, schedule approval, overtime calculation
-->
<template>
  <div class="employee-scheduling">
    <!-- Header Controls -->
    <div class="scheduling-header">
      <div class="date-controls">
        <button @click="previousWeek" class="btn btn-outline-secondary">
          <i class="fas fa-chevron-left"></i> Previous Week
        </button>
        <h3>{{ formatWeekRange(currentWeekStart) }}</h3>
        <button @click="nextWeek" class="btn btn-outline-secondary">
          Next Week <i class="fas fa-chevron-right"></i>
        </button>
      </div>
      
      <div class="view-controls">
        <button 
          @click="viewMode = 'week'" 
          :class="['btn', viewMode === 'week' ? 'btn-primary' : 'btn-outline-primary']"
        >
          Week View
        </button>
        <button 
          @click="viewMode = 'month'" 
          :class="['btn', viewMode === 'month' ? 'btn-primary' : 'btn-outline-primary']"
        >
          Month View
        </button>
      </div>

      <button @click="showCreateSchedule = true" class="btn btn-success">
        <i class="fas fa-plus"></i> Schedule Employee
      </button>
    </div>

    <!-- Week View Schedule Grid -->
    <div v-if="viewMode === 'week'" class="week-schedule">
      <div class="schedule-grid">
        <!-- Header Row -->
        <div class="schedule-header">
          <div class="employee-column">Employee</div>
          <div 
            v-for="day in weekDays" 
            :key="day.date"
            class="day-column"
          >
            <div class="day-name">{{ day.name }}</div>
            <div class="day-date">{{ formatDate(day.date) }}</div>
          </div>
        </div>

        <!-- Employee Rows -->
        <div 
          v-for="employee in employees" 
          :key="employee.employee_id"
          class="employee-row"
        >
          <div class="employee-info">
            <div class="employee-name">{{ employee.full_name }}</div>
            <div class="employee-role">{{ getEmployeeClassifications(employee.employee_id) }}</div>
            <div class="week-hours">{{ getWeeklyHours(employee.employee_id) }}h</div>
          </div>
          
          <div 
            v-for="day in weekDays" 
            :key="`${employee.employee_id}-${day.date}`"
            class="day-cell"
            @click="openScheduleModal(employee, day.date)"
          >
            <div 
              v-for="schedule in getSchedulesForDay(employee.employee_id, day.date)"
              :key="schedule.schedule_id"
              :class="['schedule-block', `status-${schedule.status}`]"
            >
              <div class="schedule-time">
                {{ formatTime(schedule.scheduled_start_time) }} - 
                {{ formatTime(schedule.scheduled_end_time) }}
              </div>
              <div class="schedule-type">{{ schedule.work_type }}</div>
              <div v-if="schedule.actual_start_time" class="actual-time">
                Actual: {{ formatTime(schedule.actual_start_time) }} - 
                {{ formatTime(schedule.actual_end_time) }}
              </div>
            </div>
            
            <div v-if="!getSchedulesForDay(employee.employee_id, day.date).length" class="no-schedule">
              <i class="fas fa-plus-circle"></i>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Month View Calendar -->
    <div v-if="viewMode === 'month'" class="month-schedule">
      <FullCalendar
        ref="calendar"
        :options="calendarOptions"
        @event-click="handleEventClick"
        @date-click="handleDateClick"
      />
    </div>

    <!-- Time Submission Panel -->
    <div class="time-submission-panel">
      <h4>Time Submissions Pending Approval</h4>
      <div class="pending-submissions">
        <div 
          v-for="submission in pendingTimeSubmissions" 
          :key="submission.schedule_id"
          class="submission-card"
        >
          <div class="submission-header">
            <span class="employee-name">{{ submission.employee_name }}</span>
            <span class="submission-date">{{ formatDate(submission.work_date) }}</span>
            <span :class="['status-badge', `status-${submission.status}`]">
              {{ submission.status }}
            </span>
          </div>
          
          <div class="submission-details">
            <div class="time-details">
              <strong>Scheduled:</strong> {{ formatTime(submission.scheduled_start_time) }} - {{ formatTime(submission.scheduled_end_time) }}
              <br>
              <strong>Actual:</strong> {{ formatTime(submission.actual_start_time) }} - {{ formatTime(submission.actual_end_time) }}
              <br>
              <strong>Hours:</strong> {{ submission.total_hours_worked }}h ({{ submission.work_type }})
            </div>
            
            <div class="approval-actions">
              <button 
                @click="approveTimeSubmission(submission.schedule_id)"
                class="btn btn-sm btn-success"
              >
                <i class="fas fa-check"></i> Approve
              </button>
              <button 
                @click="rejectTimeSubmission(submission.schedule_id)"
                class="btn btn-sm btn-danger"
              >
                <i class="fas fa-times"></i> Reject
              </button>
              <button 
                @click="editTimeSubmission(submission)"
                class="btn btn-sm btn-warning"
              >
                <i class="fas fa-edit"></i> Edit
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Create/Edit Schedule Modal -->
    <div v-if="showCreateSchedule || editingSchedule" class="modal-overlay" @click="closeModals">
      <div class="modal-content" @click.stop>
        <div class="modal-header">
          <h3>{{ editingSchedule ? 'Edit Schedule' : 'Create Schedule' }}</h3>
          <button @click="closeModals" class="close-btn">
            <i class="fas fa-times"></i>
          </button>
        </div>
        
        <form @submit.prevent="saveSchedule" class="schedule-form">
          <div class="form-row">
            <div class="form-group">
              <label>Employee</label>
              <select v-model="scheduleForm.employee_id" required>
                <option value="">Select Employee</option>
                <option 
                  v-for="employee in employees" 
                  :key="employee.employee_id"
                  :value="employee.employee_id"
                >
                  {{ employee.full_name }} - {{ getEmployeeClassifications(employee.employee_id) }}
                </option>
              </select>
            </div>
            
            <div class="form-group">
              <label>Work Date</label>
              <input type="date" v-model="scheduleForm.work_date" required>
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label>Work Type</label>
              <select v-model="scheduleForm.work_type" required>
                <option value="regular">Regular</option>
                <option value="overtime">Overtime</option>
                <option value="holiday">Holiday</option>
                <option value="training">Training</option>
                <option value="on_call">On Call</option>
              </select>
            </div>
            
            <div class="form-group">
              <label>Classification</label>
              <select v-model="scheduleForm.classification_type" required>
                <option value="bookkeeper">Bookkeeper</option>
                <option value="cleaner">Cleaner</option>
                <option value="accountant">Accountant</option>
                <option value="dispatcher">Dispatcher</option>
                <option value="part_time">Part Time</option>
                <option value="volunteer">Volunteer</option>
              </select>
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label>Start Time</label>
              <input type="time" v-model="scheduleForm.scheduled_start_time" required>
            </div>
            
            <div class="form-group">
              <label>End Time</label>
              <input type="time" v-model="scheduleForm.scheduled_end_time" required>
            </div>
          </div>
          
          <div class="form-row">
            <div class="form-group">
              <label>Hourly Rate</label>
              <input 
                type="number" 
                step="0.01" 
                v-model="scheduleForm.hourly_rate" 
                placeholder="Override default rate"
              >
            </div>
            
            <div class="form-group">
              <label>Location</label>
              <input 
                type="text" 
                v-model="scheduleForm.location" 
                placeholder="Office, Client Site, Remote"
              >
            </div>
          </div>
          
          <div class="form-group">
            <label>Description/Tasks</label>
            <textarea 
              v-model="scheduleForm.description" 
              rows="3"
              placeholder="Describe the work to be done"
            ></textarea>
          </div>
          
          <div class="form-actions">
            <button type="button" @click="closeModals" class="btn btn-secondary">Cancel</button>
            <button type="submit" class="btn btn-primary">
              {{ editingSchedule ? 'Update Schedule' : 'Create Schedule' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script>
import FullCalendar from '@fullcalendar/vue3'
import dayGridPlugin from '@fullcalendar/daygrid'
import timeGridPlugin from '@fullcalendar/timegrid'
import interactionPlugin from '@fullcalendar/interaction'

export default {
  name: 'EmployeeScheduling',
  components: {
    FullCalendar
  },
  props: {
    employees: {
      type: Array,
      default: () => []
    }
  },
  data() {
    return {
      viewMode: 'week',
      currentWeekStart: this.getWeekStart(new Date()),
      schedules: [],
      pendingTimeSubmissions: [],
      showCreateSchedule: false,
      editingSchedule: null,
      scheduleForm: this.getEmptyScheduleForm(),
      calendarOptions: {
        plugins: [dayGridPlugin, timeGridPlugin, interactionPlugin],
        initialView: 'dayGridMonth',
        headerToolbar: {
          left: 'prev,next today',
          center: 'title',
          right: 'dayGridMonth,timeGridWeek,timeGridDay'
        },
        events: [],
        editable: true,
        selectable: true,
        selectMirror: true,
        dayMaxEvents: true,
        weekends: true
      }
    }
  },
  computed: {
    weekDays() {
      const days = []
      const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
      
      for (let i = 0; i < 7; i++) {
        const date = new Date(this.currentWeekStart)
        date.setDate(date.getDate() + i)
        days.push({
          name: dayNames[i],
          date: date.toISOString().split('T')[0]
        })
      }
      
      return days
    }
  },
  async mounted() {
    await this.loadSchedules()
    await this.loadPendingSubmissions()
  },
  methods: {
    // Date Navigation
    getWeekStart(date) {
      const d = new Date(date)
      const day = d.getDay()
      const diff = d.getDate() - day
      return new Date(d.setDate(diff))
    },
    
    previousWeek() {
      this.currentWeekStart.setDate(this.currentWeekStart.getDate() - 7)
      this.loadSchedules()
    },
    
    nextWeek() {
      this.currentWeekStart.setDate(this.currentWeekStart.getDate() + 7)
      this.loadSchedules()
    },
    
    formatWeekRange(startDate) {
      const endDate = new Date(startDate)
      endDate.setDate(endDate.getDate() + 6)
      
      const options = { month: 'short', day: 'numeric' }
      return `${startDate.toLocaleDateString('en-US', options)} - ${endDate.toLocaleDateString('en-US', options)}, ${startDate.getFullYear()}`
    },
    
    formatDate(dateString) {
      return new Date(dateString).toLocaleDateString('en-US', { 
        month: 'short', 
        day: 'numeric' 
      })
    },
    
    formatTime(timeString) {
      if (!timeString) return ''
      return new Date(`2000-01-01T${timeString}`).toLocaleTimeString('en-US', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true
      })
    },
    
    // Data Loading
    async loadSchedules() {
      try {
        const weekEnd = new Date(this.currentWeekStart)
        weekEnd.setDate(weekEnd.getDate() + 6)
        
        const startDate = this.currentWeekStart.toISOString().split('T')[0]
        const endDate = weekEnd.toISOString().split('T')[0]
        
        const response = await fetch(`/api/employee-schedules?start_date=${startDate}&end_date=${endDate}`)
        this.schedules = await response.json()
        
        // Update calendar events for month view
        this.updateCalendarEvents()
        
      } catch (error) {
        console.error('Error loading schedules:', error)
      }
    },
    
    async loadPendingSubmissions() {
      try {
        const response = await fetch('/api/employee-schedules/pending-approval')
        this.pendingTimeSubmissions = await response.json()
      } catch (error) {
        console.error('Error loading pending submissions:', error)
      }
    },
    
    updateCalendarEvents() {
      const events = this.schedules.map(schedule => ({
        id: schedule.schedule_id,
        title: `${schedule.employee_name} - ${schedule.work_type}`,
        start: `${schedule.work_date}T${schedule.scheduled_start_time}`,
        end: `${schedule.work_date}T${schedule.scheduled_end_time}`,
        backgroundColor: this.getStatusColor(schedule.status),
        extendedProps: {
          schedule: schedule
        }
      }))
      
      this.calendarOptions.events = events
    },
    
    getStatusColor(status) {
      const colors = {
        'scheduled': '#007bff',
        'in_progress': '#ffc107',
        'completed': '#28a745',
        'cancelled': '#dc3545',
        'no_show': '#6c757d'
      }
      return colors[status] || '#007bff'
    },
    
    // Schedule Management
    getSchedulesForDay(employeeId, date) {
      return this.schedules.filter(s => 
        s.employee_id === employeeId && s.work_date === date
      )
    },
    
    getWeeklyHours(employeeId) {
      const employeeSchedules = this.schedules.filter(s => s.employee_id === employeeId)
      return employeeSchedules.reduce((total, schedule) => {
        return total + (schedule.total_hours_worked || schedule.total_hours_scheduled || 0)
      }, 0).toFixed(1)
    },
    
    getEmployeeClassifications(employeeId) {
      const employee = this.employees.find(e => e.employee_id === employeeId)
      // This would come from the employee classifications data
      return employee?.classifications?.join(', ') || 'General'
    },
    
    // Modal Management
    openScheduleModal(employee, date) {
      this.scheduleForm = this.getEmptyScheduleForm()
      this.scheduleForm.employee_id = employee.employee_id
      this.scheduleForm.work_date = date
      this.showCreateSchedule = true
    },
    
    editTimeSubmission(submission) {
      this.editingSchedule = submission
      this.scheduleForm = { ...submission }
      this.showCreateSchedule = true
    },
    
    closeModals() {
      this.showCreateSchedule = false
      this.editingSchedule = null
      this.scheduleForm = this.getEmptyScheduleForm()
    },
    
    getEmptyScheduleForm() {
      return {
        employee_id: '',
        work_date: '',
        work_type: 'regular',
        classification_type: '',
        scheduled_start_time: '09:00',
        scheduled_end_time: '17:00',
        hourly_rate: '',
        location: '',
        description: ''
      }
    },
    
    // Schedule Actions
    async saveSchedule() {
      try {
        const url = this.editingSchedule 
          ? `/api/employee-schedules/${this.editingSchedule.schedule_id}`
          : '/api/employee-schedules'
        
        const method = this.editingSchedule ? 'PUT' : 'POST'
        
        const response = await fetch(url, {
          method: method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(this.scheduleForm)
        })
        
        if (response.ok) {
          this.$emit('schedule-updated', this.scheduleForm)
          this.closeModals()
          await this.loadSchedules()
        } else {
          throw new Error('Failed to save schedule')
        }
      } catch (error) {
        console.error('Error saving schedule:', error)
        this.$toast.error('Failed to save schedule')
      }
    },
    
    async approveTimeSubmission(scheduleId) {
      try {
        const response = await fetch(`/api/employee-schedules/${scheduleId}/approve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
        
        if (response.ok) {
          this.$toast.success('Time submission approved')
          await this.loadPendingSubmissions()
          await this.loadSchedules()
          this.$emit('time-submitted', { scheduleId, status: 'approved' })
        } else {
          throw new Error('Failed to approve time submission')
        }
      } catch (error) {
        console.error('Error approving time:', error)
        this.$toast.error('Failed to approve time submission')
      }
    },
    
    async rejectTimeSubmission(scheduleId) {
      try {
        const response = await fetch(`/api/employee-schedules/${scheduleId}/reject`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
        
        if (response.ok) {
          this.$toast.success('Time submission rejected')
          await this.loadPendingSubmissions()
          this.$emit('time-submitted', { scheduleId, status: 'rejected' })
        } else {
          throw new Error('Failed to reject time submission')
        }
      } catch (error) {
        console.error('Error rejecting time:', error)
        this.$toast.error('Failed to reject time submission')
      }
    },
    
    // Calendar Event Handlers
    handleEventClick(info) {
      const schedule = info.event.extendedProps.schedule
      this.editTimeSubmission(schedule)
    },
    
    handleDateClick(info) {
      this.scheduleForm = this.getEmptyScheduleForm()
      this.scheduleForm.work_date = info.dateStr
      this.showCreateSchedule = true
    }
  }
}
</script>

<style scoped>
.employee-scheduling {
  padding: 20px;
}

.scheduling-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 30px;
  flex-wrap: wrap;
  gap: 20px;
}

.date-controls {
  display: flex;
  align-items: center;
  gap: 20px;
}

.date-controls h3 {
  margin: 0;
  font-size: 1.5rem;
  color: #2c3e50;
}

.view-controls {
  display: flex;
  gap: 10px;
}

/* Week Schedule Grid */
.schedule-grid {
  border: 1px solid #dee2e6;
  border-radius: 8px;
  overflow: hidden;
  background: white;
}

.schedule-header {
  display: grid;
  grid-template-columns: 200px repeat(7, 1fr);
  background: #f8f9fa;
  border-bottom: 2px solid #dee2e6;
}

.employee-column, .day-column {
  padding: 15px 10px;
  font-weight: 600;
  text-align: center;
  border-right: 1px solid #dee2e6;
}

.day-column {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.day-name {
  font-size: 0.9rem;
  color: #495057;
}

.day-date {
  font-size: 0.8rem;
  color: #6c757d;
}

.employee-row {
  display: grid;
  grid-template-columns: 200px repeat(7, 1fr);
  border-bottom: 1px solid #dee2e6;
}

.employee-info {
  padding: 15px 10px;
  border-right: 1px solid #dee2e6;
  background: #f8f9fa;
}

.employee-name {
  font-weight: 600;
  color: #2c3e50;
}

.employee-role {
  font-size: 0.8rem;
  color: #6c757d;
  margin-top: 5px;
}

.week-hours {
  font-size: 0.9rem;
  color: #007bff;
  font-weight: 600;
  margin-top: 5px;
}

.day-cell {
  padding: 10px;
  border-right: 1px solid #dee2e6;
  min-height: 80px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.day-cell:hover {
  background-color: #f8f9fa;
}

.schedule-block {
  background: #007bff;
  color: white;
  padding: 5px 8px;
  border-radius: 4px;
  margin-bottom: 5px;
  font-size: 0.8rem;
}

.schedule-block.status-completed {
  background: #28a745;
}

.schedule-block.status-cancelled {
  background: #dc3545;
}

.schedule-block.status-in_progress {
  background: #ffc107;
  color: #212529;
}

.schedule-time {
  font-weight: 600;
}

.schedule-type {
  font-size: 0.7rem;
  opacity: 0.9;
}

.actual-time {
  font-size: 0.7rem;
  margin-top: 3px;
  padding-top: 3px;
  border-top: 1px solid rgba(255,255,255,0.3);
}

.no-schedule {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
  color: #6c757d;
  opacity: 0.5;
}

.no-schedule:hover {
  opacity: 1;
  color: #007bff;
}

/* Time Submission Panel */
.time-submission-panel {
  margin-top: 30px;
  background: white;
  border-radius: 8px;
  padding: 20px;
  border: 1px solid #dee2e6;
}

.time-submission-panel h4 {
  margin-bottom: 20px;
  color: #2c3e50;
}

.pending-submissions {
  display: grid;
  gap: 15px;
}

.submission-card {
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 15px;
  background: #f8f9fa;
}

.submission-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.employee-name {
  font-weight: 600;
  color: #2c3e50;
}

.submission-date {
  color: #6c757d;
}

.status-badge {
  padding: 3px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.status-badge.status-pending {
  background: #ffc107;
  color: #212529;
}

.submission-details {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 20px;
}

.time-details {
  flex: 1;
  font-size: 0.9rem;
}

.approval-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}

/* Modal Styles */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  padding: 0;
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #dee2e6;
}

.modal-header h3 {
  margin: 0;
  color: #2c3e50;
}

.close-btn {
  background: none;
  border: none;
  font-size: 1.5rem;
  color: #6c757d;
  cursor: pointer;
}

.close-btn:hover {
  color: #495057;
}

.schedule-form {
  padding: 20px;
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
  margin-bottom: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
}

.form-group label {
  font-weight: 600;
  margin-bottom: 5px;
  color: #495057;
}

.form-group input,
.form-group select,
.form-group textarea {
  padding: 8px 12px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 0.9rem;
}

.form-group input:focus,
.form-group select:focus,
.form-group textarea:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 2px rgba(0,123,255,0.25);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 30px;
  padding-top: 20px;
  border-top: 1px solid #dee2e6;
}

/* Responsive Design */
@media (max-width: 1200px) {
  .schedule-grid {
    overflow-x: auto;
  }
  
  .schedule-header,
  .employee-row {
    min-width: 1000px;
  }
}

@media (max-width: 768px) {
  .scheduling-header {
    flex-direction: column;
    align-items: stretch;
  }
  
  .date-controls {
    justify-content: center;
  }
  
  .form-row {
    grid-template-columns: 1fr;
  }
  
  .submission-details {
    flex-direction: column;
    gap: 15px;
  }
  
  .approval-actions {
    justify-content: center;
  }
}
</style>