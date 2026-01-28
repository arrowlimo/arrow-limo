<!--
  Non-Charter Employee Management Component
  Purpose: Extends dispatch dashboard to manage monthly employees, part-time workers, 
           volunteers, accountants, bookkeepers with scheduling and time tracking
  Created: October 21, 2025
-->
<template>
  <div class="non-charter-employee-management">
    <!-- Header with Navigation Tabs -->
    <div class="employee-management-header">
      <h2>Employee Management</h2>
      <div class="tab-navigation">
        <button 
          v-for="tab in tabs" 
          :key="tab.id"
          @click="activeTab = tab.id"
          :class="['tab-button', { 'active': activeTab === tab.id }]"
        >
          <i :class="tab.icon"></i>
          {{ tab.label }}
          <span v-if="tab.count" class="badge">{{ tab.count }}</span>
        </button>
      </div>
    </div>

    <!-- Employee Scheduling Tab -->
    <div v-if="activeTab === 'scheduling'" class="tab-content">
      <EmployeeScheduling
        :employees="nonCharterEmployees"
        @schedule-updated="handleScheduleUpdate"
        @time-submitted="handleTimeSubmission"
      />
    </div>

    <!-- Time Off Management Tab -->
    <div v-if="activeTab === 'timeoff'" class="tab-content">
      <TimeOffManagement
        :employees="nonCharterEmployees"
        :pending-requests="pendingTimeOffRequests"
        @request-approved="handleTimeOffApproval"
        @request-denied="handleTimeOffDenial"
      />
    </div>

    <!-- Work Assignments Tab -->
    <div v-if="activeTab === 'assignments'" class="tab-content">
      <WorkAssignments
        :employees="nonCharterEmployees"
        :assignments="monthlyAssignments"
        @assignment-created="handleAssignmentCreation"
        @assignment-completed="handleAssignmentCompletion"
      />
    </div>

    <!-- Payroll Approval Tab -->
    <div v-if="activeTab === 'payroll'" class="tab-content">
      <PayrollApproval
        :payroll-entries="pendingPayrollEntries"
        :approval-workflow="payrollWorkflow"
        @payroll-approved="handlePayrollApproval"
        @payroll-rejected="handlePayrollRejection"
      />
    </div>

    <!-- Expense Management Tab -->
    <div v-if="activeTab === 'expenses'" class="tab-content">
      <ExpenseManagement
        :employees="nonCharterEmployees"
        :pending-expenses="pendingExpenses"
        @expense-approved="handleExpenseApproval"
        @receipt-uploaded="handleReceiptUpload"
      />
    </div>

    <!-- Employee Classifications Tab -->
    <div v-if="activeTab === 'classifications'" class="tab-content">
      <EmployeeClassifications
        :employees="nonCharterEmployees"
        :classifications="workClassifications"
        @classification-updated="handleClassificationUpdate"
      />
    </div>
  </div>
</template>

<script>
import EmployeeScheduling from './components/EmployeeScheduling.vue'
import TimeOffManagement from './components/TimeOffManagement.vue'
import WorkAssignments from './components/WorkAssignments.vue'
import PayrollApproval from './components/PayrollApproval.vue'
import ExpenseManagement from './components/ExpenseManagement.vue'
import EmployeeClassifications from './components/EmployeeClassifications.vue'

export default {
  name: 'NonCharterEmployeeManagement',
  components: {
    EmployeeScheduling,
    TimeOffManagement,
    WorkAssignments,
    PayrollApproval,
    ExpenseManagement,
    EmployeeClassifications
  },
  data() {
    return {
      activeTab: 'scheduling',
      nonCharterEmployees: [],
      pendingTimeOffRequests: [],
      monthlyAssignments: [],
      pendingPayrollEntries: [],
      payrollWorkflow: [],
      pendingExpenses: [],
      workClassifications: [],
      refreshInterval: null
    }
  },
  computed: {
    tabs() {
      return [
        {
          id: 'scheduling',
          label: 'Scheduling',
          icon: 'fas fa-calendar-alt',
          count: this.pendingSchedules?.length || 0
        },
        {
          id: 'timeoff',
          label: 'Time Off',
          icon: 'fas fa-calendar-times',
          count: this.pendingTimeOffRequests?.length || 0
        },
        {
          id: 'assignments',
          label: 'Work Assignments',
          icon: 'fas fa-tasks',
          count: this.monthlyAssignments?.filter(a => a.status === 'assigned')?.length || 0
        },
        {
          id: 'payroll',
          label: 'Payroll Approval',
          icon: 'fas fa-dollar-sign',
          count: this.pendingPayrollEntries?.length || 0
        },
        {
          id: 'expenses',
          label: 'Expenses',
          icon: 'fas fa-receipt',
          count: this.pendingExpenses?.length || 0
        },
        {
          id: 'classifications',
          label: 'Employee Setup',
          icon: 'fas fa-user-cog',
          count: null
        }
      ]
    }
  },
  async mounted() {
    await this.loadData()
    this.startAutoRefresh()
  },
  beforeUnmount() {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval)
    }
  },
  methods: {
    async loadData() {
      try {
        // Load all non-charter employees
        const employeesResponse = await fetch('/api/employees/non-charter')
        this.nonCharterEmployees = await employeesResponse.json()

        // Load pending time off requests
        const timeOffResponse = await fetch('/api/time-off/pending')
        this.pendingTimeOffRequests = await timeOffResponse.json()

        // Load monthly work assignments
        const assignmentsResponse = await fetch('/api/work-assignments/current-month')
        this.monthlyAssignments = await assignmentsResponse.json()

        // Load pending payroll entries
        const payrollResponse = await fetch('/api/payroll/non-charter/pending')
        this.pendingPayrollEntries = await payrollResponse.json()

        // Load payroll approval workflow
        const workflowResponse = await fetch('/api/payroll/approval-workflow')
        this.payrollWorkflow = await workflowResponse.json()

        // Load pending expenses
        const expensesResponse = await fetch('/api/expenses/pending')
        this.pendingExpenses = await expensesResponse.json()

        // Load work classifications
        const classificationsResponse = await fetch('/api/employee-classifications')
        this.workClassifications = await classificationsResponse.json()

      } catch (error) {
        console.error('Error loading employee management data:', error)
        this.$toast.error('Failed to load employee data')
      }
    },

    startAutoRefresh() {
      // Refresh data every 2 minutes for real-time updates
      this.refreshInterval = setInterval(() => {
        this.loadData()
      }, 120000)
    },

    // Schedule Management
    async handleScheduleUpdate(scheduleData) {
      try {
        const response = await fetch('/api/employee-schedules', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(scheduleData)
        })
        
        if (response.ok) {
          this.$toast.success('Schedule updated successfully')
          await this.loadData()
        } else {
          throw new Error('Failed to update schedule')
        }
      } catch (error) {
        console.error('Error updating schedule:', error)
        this.$toast.error('Failed to update schedule')
      }
    },

    async handleTimeSubmission(timeData) {
      try {
        const response = await fetch('/api/employee-schedules/submit-time', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(timeData)
        })
        
        if (response.ok) {
          this.$toast.success('Time submitted for approval')
          await this.loadData()
        } else {
          throw new Error('Failed to submit time')
        }
      } catch (error) {
        console.error('Error submitting time:', error)
        this.$toast.error('Failed to submit time')
      }
    },

    // Time Off Management
    async handleTimeOffApproval(requestId) {
      try {
        const response = await fetch(`/api/time-off/${requestId}/approve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
        
        if (response.ok) {
          this.$toast.success('Time off request approved')
          await this.loadData()
        } else {
          throw new Error('Failed to approve time off request')
        }
      } catch (error) {
        console.error('Error approving time off:', error)
        this.$toast.error('Failed to approve time off request')
      }
    },

    async handleTimeOffDenial(requestId, reason) {
      try {
        const response = await fetch(`/api/time-off/${requestId}/deny`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason })
        })
        
        if (response.ok) {
          this.$toast.success('Time off request denied')
          await this.loadData()
        } else {
          throw new Error('Failed to deny time off request')
        }
      } catch (error) {
        console.error('Error denying time off:', error)
        this.$toast.error('Failed to deny time off request')
      }
    },

    // Work Assignment Management
    async handleAssignmentCreation(assignmentData) {
      try {
        const response = await fetch('/api/work-assignments', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(assignmentData)
        })
        
        if (response.ok) {
          this.$toast.success('Work assignment created')
          await this.loadData()
        } else {
          throw new Error('Failed to create work assignment')
        }
      } catch (error) {
        console.error('Error creating assignment:', error)
        this.$toast.error('Failed to create work assignment')
      }
    },

    async handleAssignmentCompletion(assignmentId, completionData) {
      try {
        const response = await fetch(`/api/work-assignments/${assignmentId}/complete`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(completionData)
        })
        
        if (response.ok) {
          this.$toast.success('Work assignment completed')
          await this.loadData()
        } else {
          throw new Error('Failed to complete work assignment')
        }
      } catch (error) {
        console.error('Error completing assignment:', error)
        this.$toast.error('Failed to complete work assignment')
      }
    },

    // Payroll Management
    async handlePayrollApproval(payrollId, approvalData) {
      try {
        const response = await fetch(`/api/payroll/non-charter/${payrollId}/approve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(approvalData)
        })
        
        if (response.ok) {
          this.$toast.success('Payroll approved')
          await this.loadData()
        } else {
          throw new Error('Failed to approve payroll')
        }
      } catch (error) {
        console.error('Error approving payroll:', error)
        this.$toast.error('Failed to approve payroll')
      }
    },

    async handlePayrollRejection(payrollId, rejectionReason) {
      try {
        const response = await fetch(`/api/payroll/non-charter/${payrollId}/reject`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: rejectionReason })
        })
        
        if (response.ok) {
          this.$toast.success('Payroll rejected')
          await this.loadData()
        } else {
          throw new Error('Failed to reject payroll')
        }
      } catch (error) {
        console.error('Error rejecting payroll:', error)
        this.$toast.error('Failed to reject payroll')
      }
    },

    // Expense Management
    async handleExpenseApproval(expenseId) {
      try {
        const response = await fetch(`/api/expenses/${expenseId}/approve`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        })
        
        if (response.ok) {
          this.$toast.success('Expense approved')
          await this.loadData()
        } else {
          throw new Error('Failed to approve expense')
        }
      } catch (error) {
        console.error('Error approving expense:', error)
        this.$toast.error('Failed to approve expense')
      }
    },

    async handleReceiptUpload(expenseId, file) {
      try {
        const formData = new FormData()
        formData.append('receipt', file)
        formData.append('expense_id', expenseId)

        const response = await fetch('/api/expenses/upload-receipt', {
          method: 'POST',
          body: formData
        })
        
        if (response.ok) {
          this.$toast.success('Receipt uploaded')
          await this.loadData()
        } else {
          throw new Error('Failed to upload receipt')
        }
      } catch (error) {
        console.error('Error uploading receipt:', error)
        this.$toast.error('Failed to upload receipt')
      }
    },

    // Employee Classification Management
    async handleClassificationUpdate(employeeId, classificationData) {
      try {
        const response = await fetch(`/api/employee-classifications/${employeeId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(classificationData)
        })
        
        if (response.ok) {
          this.$toast.success('Employee classification updated')
          await this.loadData()
        } else {
          throw new Error('Failed to update employee classification')
        }
      } catch (error) {
        console.error('Error updating classification:', error)
        this.$toast.error('Failed to update employee classification')
      }
    }
  }
}
</script>

<style scoped>
.non-charter-employee-management {
  padding: 20px;
  background-color: #f8f9fa;
  min-height: 100vh;
}

.employee-management-header {
  background: white;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.employee-management-header h2 {
  margin: 0 0 20px 0;
  color: #2c3e50;
  font-size: 1.8rem;
}

.tab-navigation {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.tab-button {
  padding: 12px 20px;
  border: 2px solid #e9ecef;
  background: white;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-weight: 500;
  color: #495057;
  display: flex;
  align-items: center;
  gap: 8px;
}

.tab-button:hover {
  border-color: #007bff;
  color: #007bff;
}

.tab-button.active {
  background: #007bff;
  border-color: #007bff;
  color: white;
}

.badge {
  background: #dc3545;
  color: white;
  border-radius: 12px;
  padding: 2px 8px;
  font-size: 0.75rem;
  font-weight: bold;
  min-width: 18px;
  text-align: center;
}

.tab-button.active .badge {
  background: rgba(255,255,255,0.3);
}

.tab-content {
  background: white;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  min-height: 600px;
}

/* Responsive Design */
@media (max-width: 768px) {
  .tab-navigation {
    flex-direction: column;
  }
  
  .tab-button {
    width: 100%;
    justify-content: center;
  }
  
  .non-charter-employee-management {
    padding: 10px;
  }
}
</style>