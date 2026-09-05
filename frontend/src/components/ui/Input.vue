<script setup>
import { computed, useId } from "vue";

const props = defineProps({
  modelValue: [String, Number],
  label: String,
  hint: String,
  error: String,
  type: { type: String, default: "text" },
  placeholder: String,
  required: Boolean,
  disabled: Boolean,
  autocomplete: String,
  step: [String, Number],
  min: [String, Number],
  max: [String, Number],
  /** Renders a currency affix and right-aligns the figure. */
  money: Boolean,
  suffix: String,
});
const emit = defineEmits(["update:modelValue"]);

const id = useId();
const describedBy = computed(() => {
  const ids = [];
  if (props.hint) ids.push(`${id}-hint`);
  if (props.error) ids.push(`${id}-error`);
  return ids.join(" ") || undefined;
});
</script>

<template>
  <div class="w-full">
    <label v-if="label" :for="id" class="mb-1.5 block text-[13px] font-medium text-ink">
      {{ label }}
      <span v-if="required" class="text-ink-subtle" aria-hidden="true">*</span>
    </label>

    <div class="relative">
      <span
        v-if="money"
        class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-ink-subtle"
        aria-hidden="true"
        >$</span
      >
      <input
        :id="id"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :required="required"
        :disabled="disabled"
        :autocomplete="autocomplete"
        :step="step ?? (money ? '0.01' : undefined)"
        :min="min"
        :max="max"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="describedBy"
        :class="[
          'h-10 w-full rounded-lg border bg-card px-3 text-sm text-ink transition',
          'placeholder:text-ink-subtle disabled:opacity-60',
          money ? 'pl-7 text-right tabular' : '',
          suffix ? 'pr-10' : '',
          error ? 'border-[color:var(--critical)]' : 'border-line hover:border-line-strong',
        ]"
        @input="emit('update:modelValue', $event.target.value)"
      />
      <span
        v-if="suffix"
        class="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm text-ink-subtle"
        aria-hidden="true"
        >{{ suffix }}</span
      >
    </div>

    <p v-if="hint && !error" :id="`${id}-hint`" class="mt-1.5 text-[12px] leading-snug text-ink-muted">
      {{ hint }}
    </p>
    <p v-if="error" :id="`${id}-error`" class="mt-1.5 text-[12px] text-[color:var(--critical-ink)]">
      {{ error }}
    </p>
  </div>
</template>
