import { watch } from 'vue'

export function useTimeCalculations(form) {
  // Extend pickup time by hours (handles midnight crossing)
  const extendTime = (hours) => {
    if (!form.value.pickupTime) return
    
    const pickup = new Date(`2000-01-01T${form.value.pickupTime}`)
    pickup.setHours(pickup.getHours() + Math.floor(hours))
    pickup.setMinutes(pickup.getMinutes() + Math.round((hours % 1) * 60))
    
    const crossedMidnight = pickup.getDate() > 1
    const timeString = pickup.toTimeString().substring(0, 5)
    
    form.value.dropoffTime = timeString
    
    // If crossed midnight, increment charter date
    if (crossedMidnight && form.value.charterDate) {
      const charterDate = new Date(form.value.charterDate)
      charterDate.setDate(charterDate.getDate() + 1)
      form.value.charterDate = charterDate.toISOString().split('T')[0]
    }
  }

  // Set split time and calculate pickup time
  const setSplitTime = (hours) => {
    form.value.splitTimeBefore = hours / 2
    form.value.splitTimeAfter = hours / 2
    form.value.splitRunTime = hours
  }

  // Calculate split run pickup time from do_time + split duration
  const calculateSplitRunPickupTime = () => {
    if (!form.value.doTime || !form.value.splitRunEnabled) return
    
    const splitDuration = (form.value.splitTimeBefore || 0) + (form.value.splitTimeAfter || 0)
    const dropoff = new Date(`2000-01-01T${form.value.doTime}`)
    dropoff.setHours(dropoff.getHours() + Math.floor(splitDuration))
    dropoff.setMinutes(dropoff.getMinutes() + Math.round((splitDuration % 1) * 60))
    
    form.value.splitRunPickupTime = dropoff.toTimeString().substring(0, 5)
    form.value.splitRunTime = splitDuration
  }

  // Calculate billed time between two times
  const calculateBilledTime = (timeStart, timeFinish) => {
    if (!timeStart || !timeFinish) return 0
    
    const start = new Date(`2000-01-01T${timeStart}`)
    let finish = new Date(`2000-01-01T${timeFinish}`)
    
    if (finish < start) {
      finish.setDate(finish.getDate() + 1) // Crossed midnight
    }
    
    const diffMs = finish - start
    const diffHours = diffMs / (1000 * 60 * 60)
    
    return diffHours
  }

  // Format hours as "X.XX hrs" or "Non-billable"
  const formatBilledTime = (hours, billable = true) => {
    if (!billable) return 'Non-billable'
    if (hours === 0) return '0.00 hrs'
    return `${hours.toFixed(2)} hrs`
  }

  // Watch for split run time changes
  watch([() => form.value.doTime, () => form.value.splitTimeBefore, () => form.value.splitTimeAfter], () => {
    calculateSplitRunPickupTime()
  })

  return {
    extendTime,
    setSplitTime,
    calculateSplitRunPickupTime,
    calculateBilledTime,
    formatBilledTime
  }
}
