import { ref } from 'vue'
import { useTimeCalculations } from './useTimeCalculations'

export function useRouting(form) {
  const routingLocked = ref(false)
  const { calculateBilledTime, formatBilledTime } = useTimeCalculations(form)

  // Add new route
  const addRoute = () => {
    form.value.routes.push({
      id: Date.now(),
      type: 'pickup_at',
      address: '',
      notes: '',
      timeStart: '',
      timeFinish: '',
      billedTime: '',
      billable: true
    })
  }

  // Delete route
  const deleteRoute = (index) => {
    if (confirm('Delete this route?')) {
      form.value.routes.splice(index, 1)
    }
  }

  // Move route up
  const moveRouteUp = (index) => {
    if (index > 0) {
      const temp = form.value.routes[index]
      form.value.routes[index] = form.value.routes[index - 1]
      form.value.routes[index - 1] = temp
    }
  }

  // Move route down
  const moveRouteDown = (index) => {
    if (index < form.value.routes.length - 1) {
      const temp = form.value.routes[index]
      form.value.routes[index] = form.value.routes[index + 1]
      form.value.routes[index + 1] = temp
    }
  }

  // Update route billed time
  const updateRouteBilledTime = (route) => {
    if (!route.timeStart || !route.timeFinish) {
      route.billedTime = ''
      return
    }

    const hours = calculateBilledTime(route.timeStart, route.timeFinish)
    route.billedTime = formatBilledTime(hours, route.billable)
  }

  // Initialize default routes (pickup + dropoff)
  const initializeRoutes = () => {
    if (form.value.routes.length === 0) {
      form.value.routes = [
        {
          id: Date.now(),
          type: 'pickup_at',
          address: '',
          notes: '',
          timeStart: form.value.pickupTime || '',
          timeFinish: '',
          billedTime: '',
          billable: true
        },
        {
          id: Date.now() + 1,
          type: 'dropoff_at',
          address: '',
          notes: '',
          timeStart: '',
          timeFinish: form.value.dropoffTime || '',
          billedTime: '',
          billable: true
        }
      ]
    }
  }

  // Insert out of town routes (Primary A/B, Secondary B/A)
  const insertOutOfTownRoutes = () => {
    if (!form.value.isOutOfTown) return

    // Insert Primary A (Leave Red Deer For) at beginning
    const primaryA = {
      id: Date.now(),
      type: 'leave_red_deer',
      address: '',
      notes: 'Primary A',
      timeStart: form.value.pickupTime || '',
      timeFinish: '',
      billedTime: '',
      billable: true
    }

    // Insert Primary B (Pickup In)
    const primaryB = {
      id: Date.now() + 1,
      type: 'pickup_in',
      address: '',
      notes: 'Primary B',
      timeStart: '',
      timeFinish: '',
      billedTime: '',
      billable: true
    }

    // Insert at beginning
    form.value.routes.unshift(primaryA, primaryB)

    // Insert Secondary B/A at end (before regular dropoff)
    const secondaryB = {
      id: Date.now() + 2,
      type: 'drop_off_at',
      address: '',
      notes: 'Secondary B',
      timeStart: '',
      timeFinish: '',
      billedTime: '',
      billable: true
    }

    const secondaryA = {
      id: Date.now() + 3,
      type: 'return_to_red_deer',
      address: '',
      notes: 'Secondary A',
      timeStart: '',
      timeFinish: '',
      billedTime: '',
      billable: true
    }

    // Insert before last route (dropoff)
    const lastIndex = form.value.routes.length - 1
    form.value.routes.splice(lastIndex, 0, secondaryB, secondaryA)
  }

  // Insert split run/standby routes
  const insertSplitRunRoutes = () => {
    if (!form.value.splitRunEnabled || !form.value.doTime) return

    const splitStopType = form.value.routingType === 'standby' ? 'standby_stop' : 'dropoff_at'
    const splitStopNotes = form.value.routingType === 'standby' 
      ? 'Driver standby - wait time charged' 
      : 'Split run - non-billable period'

    const splitStop = {
      id: Date.now(),
      type: splitStopType,
      address: '',
      notes: splitStopNotes,
      timeStart: form.value.doTime,
      timeFinish: form.value.splitRunPickupTime,
      billedTime: formatBilledTime(form.value.splitRunTime, form.value.routingType === 'standby'),
      billable: form.value.routingType === 'standby'
    }

    const resumePickup = {
      id: Date.now() + 1,
      type: 'pickup_at',
      address: '',
      notes: 'Billing resumes',
      timeStart: form.value.splitRunPickupTime,
      timeFinish: '',
      billedTime: '',
      billable: true
    }

    // Insert before final dropoff
    const dropoffIndex = form.value.routes.findIndex(r => r.type === 'dropoff_at' && !r.notes.includes('split'))
    if (dropoffIndex > 0) {
      form.value.routes.splice(dropoffIndex, 0, splitStop, resumePickup)
    }
  }

  return {
    routingLocked,
    addRoute,
    deleteRoute,
    moveRouteUp,
    moveRouteDown,
    updateRouteBilledTime,
    initializeRoutes,
    insertOutOfTownRoutes,
    insertSplitRunRoutes
  }
}
