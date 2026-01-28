<template>
  <div class="form-field" :class="{ 'has-error': error, 'is-required': required, 'is-disabled': disabled }">
    <label v-if="label" :for="inputId" class="field-label">
      {{ label }}
      <span v-if="required" class="required-mark">*</span>
      <span v-if="helpText" class="help-icon" :title="helpText">?</span>
    </label>

    <!-- Text Input -->
    <input
      v-if="type === 'text' || type === 'email' || type === 'tel' || type === 'number' || type === 'password'"
      :id="inputId"
      :type="type"
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
      @blur="$emit('blur')"
      @focus="$emit('focus')"
      :placeholder="placeholder"
      :disabled="disabled"
      :readonly="readonly"
      :required="required"
      :tabindex="tabindex"
      :autocomplete="autocomplete"
      :maxlength="maxlength"
      :min="min"
      :max="max"
      :step="step"
      class="field-input"
    />

    <!-- Textarea -->
    <textarea
      v-else-if="type === 'textarea'"
      :id="inputId"
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
      @blur="$emit('blur')"
      @focus="$emit('focus')"
      :placeholder="placeholder"
      :disabled="disabled"
      :readonly="readonly"
      :required="required"
      :tabindex="tabindex"
      :rows="rows"
      :maxlength="maxlength"
      class="field-input field-textarea"
    ></textarea>

    <!-- Select Dropdown -->
    <select
      v-else-if="type === 'select'"
      :id="inputId"
      :value="modelValue"
      @change="$emit('update:modelValue', $event.target.value)"
      @blur="$emit('blur')"
      @focus="$emit('focus')"
      :disabled="disabled"
      :required="required"
      :tabindex="tabindex"
      class="field-input field-select"
    >
      <option value="" disabled>{{ placeholder || 'Select...' }}</option>
      <option
        v-for="option in options"
        :key="option.value"
        :value="option.value"
      >
        {{ option.label }}
      </option>
    </select>

    <!-- Checkbox -->
    <div v-else-if="type === 'checkbox'" class="field-checkbox-wrapper">
      <input
        :id="inputId"
        type="checkbox"
        :checked="modelValue"
        @change="$emit('update:modelValue', $event.target.checked)"
        @blur="$emit('blur')"
        @focus="$emit('focus')"
        :disabled="disabled"
        :required="required"
        :tabindex="tabindex"
        class="field-checkbox"
      />
      <label :for="inputId" class="checkbox-label">{{ checkboxLabel }}</label>
    </div>

    <!-- Radio Group -->
    <div v-else-if="type === 'radio'" class="field-radio-group">
      <div
        v-for="(option, index) in options"
        :key="option.value"
        class="field-radio-wrapper"
      >
        <input
          :id="`${inputId}-${index}`"
          type="radio"
          :name="inputId"
          :value="option.value"
          :checked="modelValue === option.value"
          @change="$emit('update:modelValue', option.value)"
          @blur="$emit('blur')"
          @focus="$emit('focus')"
          :disabled="disabled"
          :required="required && index === 0"
          :tabindex="tabindex"
          class="field-radio"
        />
        <label :for="`${inputId}-${index}`" class="radio-label">
          {{ option.label }}
        </label>
      </div>
    </div>

    <!-- Date Picker -->
    <input
      v-else-if="type === 'date' || type === 'datetime-local' || type === 'time'"
      :id="inputId"
      :type="type"
      :value="modelValue"
      @input="$emit('update:modelValue', $event.target.value)"
      @blur="$emit('blur')"
      @focus="$emit('focus')"
      :disabled="disabled"
      :readonly="readonly"
      :required="required"
      :tabindex="tabindex"
      :min="min"
      :max="max"
      class="field-input"
    />

    <!-- Currency Input -->
    <div v-else-if="type === 'currency'" class="field-currency-wrapper">
      <span class="currency-symbol">$</span>
      <input
        :id="inputId"
        type="number"
        :value="modelValue"
        @input="$emit('update:modelValue', $event.target.value)"
        @blur="$emit('blur')"
        @focus="$emit('focus')"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :required="required"
        :tabindex="tabindex"
        :min="0"
        :step="0.01"
        class="field-input currency-input"
      />
    </div>

    <!-- Error Message -->
    <div v-if="error" class="field-error">
      <span class="error-icon">⚠</span>
      {{ error }}
    </div>

    <!-- Help Text -->
    <div v-if="helpText && !error" class="field-help">
      {{ helpText }}
    </div>

    <!-- Character Counter -->
    <div v-if="maxlength && (type === 'text' || type === 'textarea')" class="field-counter">
      {{ (modelValue || '').length }} / {{ maxlength }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  modelValue: { type: [String, Number, Boolean], default: '' },
  type: { type: String, default: 'text' },
  label: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  helpText: { type: String, default: '' },
  error: { type: String, default: '' },
  required: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  readonly: { type: Boolean, default: false },
  tabindex: { type: Number, default: 0 },
  autocomplete: { type: String, default: 'off' },
  maxlength: { type: Number, default: null },
  rows: { type: Number, default: 4 },
  options: { type: Array, default: () => [] },
  checkboxLabel: { type: String, default: '' },
  min: { type: [String, Number], default: null },
  max: { type: [String, Number], default: null },
  step: { type: [String, Number], default: null }
})

const emit = defineEmits(['update:modelValue', 'blur', 'focus'])

const inputId = computed(() => {
  return `field-${Math.random().toString(36).substr(2, 9)}`
})
</script>

<style scoped>
.form-field {
  margin-bottom: 20px;
}

.field-label {
  display: block;
  margin-bottom: 8px;
  font-size: 0.95rem;
  font-weight: 500;
  color: #374151;
}

.required-mark {
  color: #ef4444;
  margin-left: 4px;
}

.help-icon {
  display: inline-block;
  width: 16px;
  height: 16px;
  line-height: 16px;
  text-align: center;
  background: #6b7280;
  color: white;
  border-radius: 50%;
  font-size: 0.75rem;
  margin-left: 6px;
  cursor: help;
}

.field-input {
  width: 100%;
  padding: 10px 14px;
  border: 2px solid #d1d5db;
  border-radius: 6px;
  font-size: 1rem;
  transition: all 0.2s;
  background: white;
}

.field-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.field-input:disabled {
  background: #f3f4f6;
  cursor: not-allowed;
}

.field-input::placeholder {
  color: #9ca3af;
}

.field-textarea {
  resize: vertical;
  min-height: 100px;
  font-family: inherit;
}

.field-select {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml;charset=UTF-8,%3csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3e%3cpolyline points='6 9 12 15 18 9'%3e%3c/polyline%3e%3c/svg%3e");
  background-repeat: no-repeat;
  background-position: right 10px center;
  background-size: 20px;
  padding-right: 40px;
}

.field-checkbox-wrapper, .field-radio-wrapper {
  display: flex;
  align-items: center;
  gap: 10px;
}

.field-checkbox, .field-radio {
  width: 20px;
  height: 20px;
  cursor: pointer;
  accent-color: #667eea;
}

.checkbox-label, .radio-label {
  margin: 0;
  cursor: pointer;
  user-select: none;
}

.field-radio-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-currency-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.currency-symbol {
  position: absolute;
  left: 14px;
  font-size: 1rem;
  font-weight: 500;
  color: #6b7280;
  pointer-events: none;
}

.currency-input {
  padding-left: 32px;
}

.field-error {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  color: #ef4444;
  font-size: 0.875rem;
}

.error-icon {
  font-size: 1rem;
}

.has-error .field-input {
  border-color: #ef4444;
}

.has-error .field-input:focus {
  box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.1);
}

.field-help {
  margin-top: 6px;
  font-size: 0.875rem;
  color: #6b7280;
}

.field-counter {
  margin-top: 6px;
  text-align: right;
  font-size: 0.875rem;
  color: #6b7280;
}

.is-required .field-label {
  font-weight: 600;
}

.is-disabled {
  opacity: 0.6;
}

/* Focus visible for accessibility */
.field-input:focus-visible,
.field-checkbox:focus-visible,
.field-radio:focus-visible {
  outline: 2px solid #667eea;
  outline-offset: 2px;
}
</style>
