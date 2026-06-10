<template>
  <header class="navbar">
    <div class="logo">Arrow Limousine</div>
    <nav>
      <router-link to="/" class="nav-link">Main</router-link>

      <router-link v-if="canAccess('drivers')" to="/drivers">My Schedule</router-link>
      <router-link v-if="canAccess('driver-hos')" to="/driver-hos">HOS Log</router-link>

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
        <label for="theme-selector" class="theme-label">Theme</label>
        <select id="theme-selector" v-model="selectedTheme" @change="changeTheme" class="theme-selector">
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
        <span class="username">{{ currentUser }}</span>
        <button @click="handleLogout" class="logout-btn">Logout</button>
      </div>
    </nav>
  </header>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const normalizeRole = (role) => {
  const aliases = {
    superuser: 'super_user'
  }
  const lowered = (role || 'user').toLowerCase()
  return aliases[lowered] || lowered
}

const userRole = ref(normalizeRole(localStorage.getItem('user_role') || 'user'))
const permissions = ref(JSON.parse(localStorage.getItem('user_permissions') || '{}'))
const selectedTheme = ref(localStorage.getItem('theme') || 'light')

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

function changeTheme() {
  localStorage.setItem('theme', selectedTheme.value)
  document.documentElement.setAttribute('data-theme', selectedTheme.value)
}

onMounted(() => {
  document.documentElement.setAttribute('data-theme', selectedTheme.value)
})

function canAccess(section) {
  if (userRole.value === 'driver' || userRole.value === 'operator') {
    return ['drivers', 'driver-hos'].includes(section)
  }

  if (userRole.value === 'dispatch' || userRole.value === 'dispatcher') {
    return ['dispatch', 'charter', 'vehicles', 'customers'].includes(section)
  }

  if (userRole.value === 'admin' || userRole.value === 'super_user') {
    return true
  }

  if (userRole.value === 'accountant') {
    return ['charter', 'accounting', 'payroll', 'tax-management', 'payroll-compliance', 'audit-center', 'cash-box', 'year-end-close', 'beverage-reconciliation', 'reports', 'customers', 'documents'].includes(section)
  }

  if (permissions.value[section]) {
    return true
  }

  return false
}

async function handleLogout() {
  try {
    const token = localStorage.getItem('auth_token')
    if (token) {
      await fetch('/auth/logout', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }).catch(() => {})
    }
  } catch (err) {
    console.error('Logout error:', err)
  } finally {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user')
    localStorage.removeItem('user_role')
    localStorage.removeItem('user_permissions')
    router.push('/login')
  }
}
</script>

<style scoped>
.navbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--navbar-bg, #667eea);
  color: var(--navbar-text, white);
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
  color: var(--navbar-link, white);
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
  gap: 0.75rem;
  margin-left: 1rem;
  padding-left: 1rem;
  border-left: 1px solid var(--navbar-border, rgba(255, 255, 255, 0.3));
}

.theme-label {
  font-size: 0.85rem;
}

.theme-selector {
  padding: 0.3rem 0.6rem;
  border-radius: 4px;
  border: 1px solid #ccc;
  font-size: 0.9rem;
}

.username {
  font-weight: 500;
  font-size: 0.9rem;
}

.logout-btn {
  background: var(--navbar-btn-bg, rgba(255, 255, 255, 0.2));
  border: 1px solid var(--navbar-btn-border, rgba(255, 255, 255, 0.4));
  color: var(--navbar-btn-text, white);
  padding: 0.5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s;
}

.logout-btn:hover {
  background: var(--navbar-btn-hover-bg, rgba(255, 255, 255, 0.3));
  border-color: var(--navbar-btn-hover-border, rgba(255, 255, 255, 0.6));
}

.logout-btn:active {
  background: var(--navbar-btn-active-bg, rgba(255, 255, 255, 0.25));
}
</style>
