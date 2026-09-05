<script setup>
import { useId } from "vue";

defineProps({
  modelValue: [String, Number, null],
  label: String,
  hint: String,
  error: String,
  /** [{ value, label }] */
  options: { type: Array, default: () => [] },
  placeholder: String,
  disabled: Boolean,
});
const emit = defineEmits(["update:modelValue"]);
const id = useId();
</script>

<template>
  <div class="w-full">
    <label v-if="label" :for="id" class="mb-1.5 block text-[13px] font-medium text-ink">{{ label }}</label>
    <div class="relative">
      <select
        :id="id"
        :value="modelValue"
        :disabled="disabled"
        :class="[
          'h-10 w-full appearance-none rounded-lg border bg-card pl-3 pr-9 text-sm text-ink transition',
          'disabled:opacity-60',
          error ? 'border-[color:var(--critical)]' : 'border-line hover:border-line-strong',
        ]"
        @change="emit('update:modelValue', $event.target.value)"
      >
        <option v-if="placeholder" value="">{{ placeholder }}</option>
        <option v-for="opt in options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
      </select>
      <svg
        class="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-subtle"
        viewBox="0 0 20 20" fill="none" aria-hidden="true"
      >
        <path d="m6 8 4 4 4-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </div>
    <p v-if="hint && !error" class="mt-1.5 text-[12px] text-ink-muted">{{ hint }}</p>
    <p v-if="error" class="mt-1.5 text-[12px] text-[color:var(--critical-ink)]">{{ error }}</p>
  </div>
</template>
