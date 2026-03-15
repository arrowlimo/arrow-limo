import { ref } from 'vue'

export function useVehiclePricing(form) {
  const vehicleTypes = ref([
    { value: 'Luxury Sedan (4 pax)', label: 'Luxury Sedan (4 pax)', hourlyRate: 85, packageRate3: 225, packageRate4: 285, packageRate8: 535, airportFlat: 150 },
    { value: 'SUV (6 pax)', label: 'SUV (6 pax)', hourlyRate: 95, packageRate3: 255, packageRate4: 315, packageRate8: 595, airportFlat: 175 },
    { value: 'Sedan Stretch (6 Pax)', label: 'Sedan Stretch (6 Pax)', hourlyRate: 125, packageRate3: 345, packageRate4: 435, packageRate8: 835, airportFlat: 225 },
    { value: 'SUV Stretch (10 pax)', label: 'SUV Stretch (10 pax)', hourlyRate: 145, packageRate3: 405, packageRate4: 515, packageRate8: 995, airportFlat: 275 },
    { value: 'Shuttle Bus (18 pax)', label: 'Shuttle Bus (18 pax)', hourlyRate: 115, packageRate3: 315, packageRate4: 405, packageRate8: 775, airportFlat: 200 },
    { value: 'Shuttle Bus (27 pax)', label: 'Shuttle Bus (27 pax)', hourlyRate: 135, packageRate3: 375, packageRate4: 475, packageRate8: 915, airportFlat: 250 },
    { value: 'Bus (72 pax)', label: 'Bus (72 pax)', hourlyRate: 185, packageRate3: 525, packageRate4: 675, packageRate8: 1315, airportFlat: 400 }
  ])

  const airportFees = ref({
    edmonton: 45,
    calgary: 65,
    red_deer: 0
  })

  // Load pricing when vehicle type changes
  const loadVehiclePricing = () => {
    const vehicleType = vehicleTypes.value.find(v => v.value === form.value.vehicleType)
    if (!vehicleType) return

    form.value.hourlyRate = vehicleType.hourlyRate

    // Apply run type defaults
    switch (form.value.runType) {
      case 'hourly':
        form.value.charterFeeAmount = 0 // Calculate based on time
        form.value.charterFeeType = 'hourly'
        break
      case 'package_3hr':
        form.value.charterFeeAmount = vehicleType.packageRate3
        form.value.charterFeeType = 'flat'
        break
      case 'package_4hr':
        form.value.charterFeeAmount = vehicleType.packageRate4
        form.value.charterFeeType = 'flat'
        break
      case 'package_8hr':
        form.value.charterFeeAmount = vehicleType.packageRate8
        form.value.charterFeeType = 'flat'
        break
      case 'airport':
        form.value.charterFeeAmount = vehicleType.airportFlat
        form.value.charterFeeType = 'flat'
        break
      case 'flat':
      case 'custom':
        form.value.charterFeeType = 'flat'
        break
    }
  }

  // Apply airport pickup fee
  const applyAirportFee = () => {
    if (!form.value.airportLocation) return

    const fee = airportFees.value[form.value.airportLocation] || 0
    
    // Only add charge if there's actually a fee (Edmonton/Calgary)
    if (fee > 0) {
      // Add as custom charge
      const existingAirportCharge = form.value.customCharges.findIndex(c => c.description.includes('Airport Pickup'))
      
      if (existingAirportCharge >= 0) {
        form.value.customCharges[existingAirportCharge].amount = fee
      } else {
        form.value.customCharges.push({
          id: Date.now(),
          description: `Airport Pickup Fee (${form.value.airportLocation})`,
          amount: fee,
          gstExempt: false
        })
      }
    } else {
      // Remove airport charge if switching to Red Deer (no fee)
      const existingAirportCharge = form.value.customCharges.findIndex(c => c.description.includes('Airport Pickup'))
      if (existingAirportCharge >= 0) {
        form.value.customCharges.splice(existingAirportCharge, 1)
      }
    }
  }

  return {
    vehicleTypes,
    airportFees,
    loadVehiclePricing,
    applyAirportFee
  }
}
