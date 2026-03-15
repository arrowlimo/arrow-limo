import { computed, watch } from 'vue'

export function useBilling(form) {
  // Calculate gratuity from charter fee
  const calculateGratuity = () => {
    const base = form.value.charterFeeAmount || 0
    form.value.gratuityAmount = base * (form.value.gratuityPercent / 100)
  }

  // Watch for gratuity percent changes
  watch(() => form.value.gratuityPercent, () => {
    calculateGratuity()
  })

  watch(() => form.value.charterFeeAmount, () => {
    calculateGratuity()
  })

  // Calculate subtotal (before GST)
  const subtotal = computed(() => {
    let total = form.value.charterFeeAmount || 0
    total += form.value.gratuityAmount || 0
    // Note: extra gratuity is GST exempt, not included in subtotal
    total += form.value.beverageCartTotal || 0
    total += form.value.fuelPrice || 0
    
    // Add custom charges
    form.value.customCharges.forEach(charge => {
      total += charge.amount || 0
    })
    
    return total
  })

  // Calculate GST amount
  const gstAmount = computed(() => {
    if (form.value.gstExempt) return 0
    return subtotal.value * 0.05
  })

  // Calculate grand total
  const grandTotal = computed(() => {
    return subtotal.value + gstAmount.value + (form.value.extraGratuityAmount || 0)
  })

  // Add custom charge
  const addCustomCharge = () => {
    form.value.customCharges.push({
      id: Date.now(),
      description: '',
      amount: 0,
      gstExempt: false
    })
  }

  // Remove custom charge
  const removeCustomCharge = (index) => {
    form.value.customCharges.splice(index, 1)
  }

  return {
    calculateGratuity,
    subtotal,
    gstAmount,
    grandTotal,
    addCustomCharge,
    removeCustomCharge
  }
}
