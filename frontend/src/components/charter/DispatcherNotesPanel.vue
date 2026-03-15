<template>
  <div class="dispatcher-notes-panel">
    <h2>📝 Dispatcher Notes</h2>
    <textarea 
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
      rows="20"
      placeholder="Internal dispatcher notes, special instructions, customer requests, flight delays, special accommodations..."
    ></textarea>
  </div>
</template>

<script setup>
defineProps({
  modelValue: {
    type: String,
    default: ''
  }
})

defineEmits(['update:modelValue'])
</script>

<style scoped>
.dispatcher-notes-panel {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  border: 2px solid #e2e8f0;
  height: 100%;
}

.dispatcher-notes-panel h2 {
  margin: 0 0 1rem 0;
  color: #2d3748;
  font-size: 1.3rem;
}

textarea {
  width: 100%;
  padding: 0.75rem;
  border: 1px solid #cbd5e0;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: 0.9rem;
  resize: vertical;
  line-height: 1.5;
}

textarea:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}
</style>
