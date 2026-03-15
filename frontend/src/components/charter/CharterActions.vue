<template>
  <div class="charter-actions">
    <button @click="$emit('reset')" class="btn-reset" :disabled="saving">
      🔄 Reset Form
    </button>
    <button @click="$emit('quote')" class="btn-quote" :disabled="saving">
      📄 Generate Quote
    </button>
    <button @click="$emit('save')" class="btn-save" :disabled="saving">
      {{ saving ? '⏳ Saving...' : '💾 Save Charter' }}
    </button>
  </div>
</template>

<script setup>
defineProps({
  saving: {
    type: Boolean,
    default: false
  }
})

defineEmits(['save', 'quote', 'reset'])
</script>

<style scoped>
.charter-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  padding: 1.5rem;
  background: white;
  border-radius: 8px;
  border: 2px solid #e2e8f0;
  margin-top: 1.5rem;
}

.charter-actions button {
  padding: 0.75rem 2rem;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.charter-actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-reset {
  background: #cbd5e0;
  color: #2d3748;
}

.btn-reset:hover:not(:disabled) {
  background: #a0aec0;
}

.btn-quote {
  background: #667eea;
  color: white;
}

.btn-quote:hover:not(:disabled) {
  background: #5a67d8;
}

.btn-save {
  background: #48bb78;
  color: white;
}

.btn-save:hover:not(:disabled) {
  background: #38a169;
}
</style>
