import { getRoleHome, hasRequiredModuleAccess } from './moduleAccess'

let lastTokenValidationTs = 0
const TOKEN_VALIDATE_CACHE_MS = 60 * 1000

const clearAuthState = () => {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('user')
  localStorage.removeItem('user_role')
  localStorage.removeItem('user_permissions')
}

const validateToken = async (token) => {
  if (!token) return false
  const now = Date.now()
  if (now - lastTokenValidationTs < TOKEN_VALIDATE_CACHE_MS) {
    return true
  }

  try {
    const response = await fetch('/auth/validate', {
      headers: {
        Authorization: `Bearer ${token}`
      }
    })
    if (!response.ok) {
      return false
    }
    const payload = await response.json()
    const user = payload.user || {}
    localStorage.setItem('user', JSON.stringify(user))
    localStorage.setItem('user_role', user.role || 'user')
    localStorage.setItem('user_permissions', JSON.stringify(user.permissions || {}))
    lastTokenValidationTs = now
    return true
  } catch (err) {
    console.warn('Token validation failed:', err)
    return false
  }
}

const checkAutoLogin = async () => {
  try {
    const response = await fetch('/auth/auto-login-check')
    if (response.ok) {
      const data = await response.json()
      if (data.auto_login && data.token) {
        localStorage.setItem('auth_token', data.token)
        localStorage.setItem('user', JSON.stringify(data.user || {}))
        localStorage.setItem('user_role', data.user?.role || 'admin')
        localStorage.setItem('user_permissions', JSON.stringify(data.user?.permissions || {}))
        console.log('Auto-login enabled for local development')
        return true
      }
    }
  } catch (err) {
    console.warn('Auto-login check unavailable:', err)
  }
  return false
}

export const registerAuthGuard = (router) => {
  router.beforeEach(async (to, from, next) => {
    const token = localStorage.getItem('auth_token')
    const requiresAuth = to.matched.some(record => record.meta.requiresAuth)

    if (requiresAuth && !token) {
      const autoLoggedIn = await checkAutoLogin()
      if (autoLoggedIn) {
        next()
      } else {
        next('/login')
      }
    }
    else if (requiresAuth && token) {
      const valid = await validateToken(token)
      if (valid) {
        const role = localStorage.getItem('user_role') || 'user'
        const permissions = JSON.parse(localStorage.getItem('user_permissions') || '{}')
        const requiredModules = to.meta?.modules || []
        if (!hasRequiredModuleAccess(requiredModules, role, permissions)) {
          next(getRoleHome(role))
        } else {
          next()
        }
      } else {
        clearAuthState()
        next('/login')
      }
    }
    else if (to.path === '/login' && token) {
      next('/')
    }
    else {
      next()
    }
  })
}
