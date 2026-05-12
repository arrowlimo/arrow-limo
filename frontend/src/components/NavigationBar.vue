<template>
  <header class="navbar">
    <div class="logo">Arrow Limousine</div>
    <nav>
      <router-link to="/" class="nav-link">Main</router-link>
      
      <!-- Driver-only sections -->
      <router-link v-if="canAccess('drivers')" to="/drivers">My Schedule</router-link>
      <router-link v-if="canAccess('driver-hos')" to="/driver-hos">HOS Log</router-link>
      
      <!-- Admin/Manager sections -->
      <router-link v-if="canAccess('dispatch')" to="/dispatch">Dispatch</router-link>
      <router-link v-if="canAccess('charter')" to="/charter">Charter</router-link>
      <router-link v-if="canAccess('vehicles')" to="/vehicles">Vehicles</router-link>
      <router-link v-if="canAccess('employees')" to="/employees">Employees</router-link>
      <router-link v-if="canAccess('customers')" to="/customers">Customers</router-link>
      <router-link v-if="canAccess('accounting')" to="/accounting">Accounting</router-link>
      <router-link v-if="canAccess('payroll')" to="/payroll">Payroll</router-link>
      <router-link v-if="canAccess('tax-management')" to="/tax-management">Tax</router-link>
      <router-link v-if="canAccess('payroll-compliance')" to="/payroll-compliance">Compliance</router-link>
      <router-link v-if="canAccess('audit-center')" to="/audit-center">Audit Center</router-link>
      <router-link v-if="canAccess('cash-box')" to="/cash-box">Cash Box</router-link>
      <router-link v-if="canAccess('year-end-close')" to="/year-end-close">Year-End</router-link>
      <router-link v-if="canAccess('beverage-reconciliation')" to="/beverage-reconciliation">Beverage</router-link>
      <router-link v-if="canAccess('reports')" to="/reports">Reports</router-link>
      <router-link v-if="canAccess('documents')" to="/documents">Documents</router-link>
      <router-link v-if="canAccess('admin')" to="/admin">Admin</router-link>
      
      <div class="user-section">
        <span class="username">{{ currentUser }}</span>
        <button @click="handleLogout" class="logout-btn">Logout</button>
      </div>
    </nav>
  </header>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const userRole = ref(localStorage.getItem('user_role') || 'user')
const permissions = ref(JSON.parse(localStorage.getItem('user_permissions') || '{}'))

const currentUser = computed(() => {
  const user = localStorage.getItem('user')
  if (user) {
    try {
      return JSON.parse(user).username || 'User'
    } catch {
      return 'User'
    }
  }
  return 'User'
})

function canAccess(section) {
  // Driver role: only access driver sections
  if (userRole.value === 'driver' || userRole.value === 'operator') {
    return ['drivers', 'driver-hos'].includes(section)
  }
  
  // Admin/Superuser: access everything
  if (userRole.value === 'admin' || userRole.value === 'superuser') {
    return true
  }
  
  // Accountant: access accounting and related sections
  if (userRole.value === 'accountant') {
    return ['charter', 'accounting', 'payroll', 'tax-management', 'payroll-compliance', 'audit-center', 'cash-box', 'year-end-close', 'beverage-reconciliation', 'reports', 'customers', 'documents'].includes(section)
  }
  
  // Check permissions object
  if (permissions.value[section]) {
    return true
  }
  
  // Default deny
  return false
}

async function handleLogout() {
  try {
    // Call logout API endpoint
    const token = localStorage.getItem('auth_token')
    if (token) {
      await fetch('/auth/logout', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }).catch(() => {}) // Ignore errors, proceed with logout
    }
  } catch (err) {
    console.error('Logout error:', err)
  } finally {
    // Clear all session data
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user')
    localStorage.removeItem('user_role')
    localStorage.removeItem('user_permissions')
    
    // Redirect to login
    router.push('/login')
  }
}
</script>

<style scoped>
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #667eea;
  color: white;
  padding: 1rem 2rem;
}
.logo {
  font-weight: bold;
  font-size: 1.5rem;
}
nav {
  display: flex;
  gap: 1.5rem;
  align-items: center;
}
nav a {
  color: white;
  text-decoration: none;
  font-weight: 500;
  transition: opacity 0.2s;
}
nav a:hover {
  opacity: 0.8;
}
nav a.router-link-active {
  text-decoration: underline;
}
.user-section {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-left: 1rem;
  padding-left: 1rem;
  border-left: 1px solid rgba(255, 255, 255, 0.3);
}
.username {
  font-weight: 500;
  font-size: 0.9rem;
}
.logout-btn {
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.4);
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}
.logout-btn:hover {
  background: rgba(255, 255, 255, 0.3);
  border-color: rgba(255, 255, 255, 0.6);
}
.logout-btn:active {
  background: rgba(255, 255, 255, 0.25);
}
</style>
