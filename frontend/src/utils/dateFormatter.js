/**
 * Shared date formatting utilities for Arrow Limousine Management System
 * Standardizes date display format to DD/MMM/YY (e.g., 23/Sept/25)
 */

/**
 * Format a date input to DD/MMM/YY format
 * @param {string|Date} input - Date string or Date object
 * @returns {string} Formatted date string like "23/Sept/25"
 */
export function formatDate(input) {
  if (!input) return ''
  
  const d = new Date(input)
  if (isNaN(d.getTime())) {
    // Fallback: input may already be a date-only string like "2025-09-23"
    try {
      const [y, m, dd] = String(input).split('T')[0].split('-').map(Number)
      if (!y || !m || !dd) return String(input)
      const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sept','Oct','Nov','Dec']
      const mon = months[m - 1] || ''
      const day = String(dd).padStart(2, '0')
      const yy = String(y % 100).padStart(2, '0')
      return `${day}/${mon}/${yy}`
    } catch (_) {
      return String(input)
    }
  }
  
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sept','Oct','Nov','Dec']
  const day = String(d.getDate()).padStart(2, '0')
  const mon = months[d.getMonth()]
  const yy = String(d.getFullYear() % 100).padStart(2, '0')
  return `${day}/${mon}/${yy}`
}

/**
 * Convert date input to YYYY-MM-DD format for filtering
 * @param {string|Date} input - Date string or Date object
 * @returns {string} Date in YYYY-MM-DD format
 */
export function dateOnly(input) {
  if (!input) return ''
  
  // Return YYYY-MM-DD for filtering against <input type="date">
  const s = String(input)
  if (s.length >= 10 && s[4] === '-' && s[7] === '-') return s.slice(0, 10)
  
  const d = new Date(input)
  if (isNaN(d.getTime())) return ''
  
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${dd}`
}

/**
 * Format date range display for quick filters
 * @param {string} filterType - Quick filter type (today, this_week, etc.)
 * @returns {string} Human-readable date range
 */
export function formatDateRange(filterType) {
  const today = new Date()
  
  switch (filterType) {
    case 'day':
      return formatDate(today)
    case 'today':
      return formatDate(today)
    case 'tomorrow':
      const tomorrow = new Date(today)
      tomorrow.setDate(today.getDate() + 1)
      return formatDate(tomorrow)
    case 'upcoming_week':
      const endOfUpcomingWeek = new Date(today)
      endOfUpcomingWeek.setDate(today.getDate() + 7)
      return `${formatDate(today)} - ${formatDate(endOfUpcomingWeek)}`
    case 'this_month':
      const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1)
      const endOfMonth = new Date(today.getFullYear(), today.getMonth() + 1, 0)
      return `${formatDate(startOfMonth)} - ${formatDate(endOfMonth)}`
    case 'this_year':
      const startOfYear = new Date(today.getFullYear(), 0, 1)
      const endOfYear = new Date(today.getFullYear(), 11, 31)
      return `${formatDate(startOfYear)} - ${formatDate(endOfYear)}`
    case 'future_all':
      return `${formatDate(today)} - Future`
    default:
      return ''
  }
}