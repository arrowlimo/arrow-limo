<template>
  <header class="navbar">
    <div class="logo">Arrow Limousine</div>
    <nav>
      <router-link to="/" class="nav-link">My Driver Portal</router-link>
      <router-link to="/driver-hos">My HOS Log</router-link>

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
