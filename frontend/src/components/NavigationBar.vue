<template>
  <header class="navbar">
    <div class="logo">Arrow Limousine</div>
    <nav>
      <router-link v-if="!isSupportAccount" to="/" class="nav-link">My Driver Portal</router-link>
      <router-link v-if="!isSupportAccount" to="/driver-hos">My HOS Log</router-link>
      <router-link v-if="isSupportAccount" to="/support" class="nav-link">Admin Driver Access</router-link>

      <div class="user-section">
        <label for="theme-selector" class="theme-label">Theme</label>
        <select id="theme-selector" v-model="selectedTheme" @change="changeTheme" class="theme-selector">
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
        <span v-if="isImpersonating" class="support-view">Admin support view</span>
        <span class="username">{{ currentUser }}</span>
        <button v-if="isImpersonating" class="switch-btn" @click="switchDriver">
          Switch Driver Account
        </button>
        <button @click="handleLogout" class="logout-btn">Logout</button>
      </div>
    </nav>
  </header>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const router = useRouter()
const route = useRoute()
const selectedTheme = ref(localStorage.getItem('theme') || 'light')
const userRecord = computed(() => {
  const storedUser = route.fullPath ? localStorage.getItem('user') : null
  try {
    return JSON.parse(storedUser || '{}')
  } catch {
    return {}
  }
})
const isSupportAccount = computed(() => userRecord.value.role === 'driver_support')
const isImpersonating = computed(() => Boolean(userRecord.value.impersonated_by))

const currentUser = computed(() => {
  const user = route.fullPath ? localStorage.getItem('user') : null
  if (user) {
    try {
      return JSON.parse(user).username || 'User'
    } catch {
      return 'User'
    }
  }
  return 'User'
})

async function switchDriver() {
  await handleLogout()
}

function changeTheme() {
  localStorage.setItem('theme', selectedTheme.value)
  document.documentElement.setAttribute('data-theme', selectedTheme.value)
}

onMounted(() => {
  document.documentElement.setAttribute('data-theme', selectedTheme.value)
})

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
.support-view {
  background: #fef3c7;
  color: #78350f;
  padding: .35rem .55rem;
  border-radius: 4px;
  font-weight: 700;
  font-size: .85rem;
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
.switch-btn {
  background: #fbbf24;
  border: 1px solid #f59e0b;
  color: #422006;
  padding: .5rem 1rem;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 700;
}

.logout-btn:hover {
  background: var(--navbar-btn-hover-bg, rgba(255, 255, 255, 0.3));
  border-color: var(--navbar-btn-hover-border, rgba(255, 255, 255, 0.6));
}

.logout-btn:active {
  background: var(--navbar-btn-active-bg, rgba(255, 255, 255, 0.25));
}
</style>
