import { ref } from 'vue'

export function useCharterForm() {
  const form = ref({
    // Client
    clientId: null,
    clientName: '',
    phone: '',
    email: '',
    
    // Charter basics
    charterDate: '',
    pickupTime: '',
    dropoffTime: '',
    passengerCount: 1,
    vehicleType: '',
    runType: 'hourly',
    airportLocation: '',
    isOutOfTown: false,
    
    // Split run / Standby
    splitRunEnabled: false,
    routingType: 'regular', // 'regular', 'split_run', 'standby'
    splitTimeBefore: 0,
    splitTimeAfter: 0,
    doTime: '', // Dropoff time (billing stops)
    splitRunPickupTime: '', // Calculated pickup time (billing resumes)
    splitRunTime: 0, // Duration of non-billable gap
    waitTimeRate: 0,
    
    // Dispatch
    dispatcherNotes: '',
    assignedVehicleId: null,
    assignedChauffeurId: null,
    
    // Routing
    routes: [],
    
    // Billing
    charterFeeType: 'hourly',
    charterFeeAmount: 0,
    hourlyRate: 0, // Display only - from vehicle type
    gratuityPercent: 18,
    gratuityAmount: 0,
    extraGratuityAmount: 0,
    beverageCartTotal: 0,
    cartOrderList: '',
    fuelLitres: 0,
    fuelPrice: 0,
    fuelGst: 0,
    customCharges: [],
    gstExempt: false,
    gstExemptPermitNumber: '',
    
    // Extra time
    extraTimeFeeEnabled: false,
    extraTimeRate: 0
  })

  const resetForm = () => {
    form.value = {
      clientId: null,
      clientName: '',
      phone: '',
      email: '',
      charterDate: '',
      pickupTime: '',
      dropoffTime: '',
      passengerCount: 1,
      vehicleType: '',
      runType: 'hourly',
      airportLocation: '',
      isOutOfTown: false,
      splitRunEnabled: false,
      routingType: 'regular',
      splitTimeBefore: 0,
      splitTimeAfter: 0,
      doTime: '',
      splitRunPickupTime: '',
      splitRunTime: 0,
      waitTimeRate: 0,
      dispatcherNotes: '',
      assignedVehicleId: null,
      assignedChauffeurId: null,
      routes: [],
      charterFeeType: 'hourly',
      charterFeeAmount: 0,
      hourlyRate: 0,
      gratuityPercent: 18,
      gratuityAmount: 0,
      extraGratuityAmount: 0,
      beverageCartTotal: 0,
      cartOrderList: '',
      fuelLitres: 0,
      fuelPrice: 0,
      fuelGst: 0,
      customCharges: [],
      gstExempt: false,
      gstExemptPermitNumber: '',
      extraTimeFeeEnabled: false,
      extraTimeRate: 0
    }
  }

  return {
    form,
    resetForm
  }
}
