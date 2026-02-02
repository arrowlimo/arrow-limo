/**
 * Fetch wrapper that automatically includes authentication token
 * Usage: use authFetch() instead of fetch() for API calls
 */

export async function authFetch(url, options = {}) {
  const token = localStorage.getItem('auth_token')
  
  // Default headers
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers
  }
  
  // Add auth token if available
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  
  // Merge with provided options
  const config = {
    ...options,
    headers
  }
  
  try {
    const response = await fetch(url, config)
    
    // If 401 Unauthorized, clear token and redirect to login
    if (response.status === 401) {
      localStorage.removeItem('auth_token')
      localStorage.removeItem('user')
      localStorage.removeItem('user_role')
      localStorage.removeItem('user_permissions')
      window.location.href = '/login'
      return null
    }
    
    return response
  } catch (error) {
    console.error('Fetch error:', error)
    throw error
  }
}
