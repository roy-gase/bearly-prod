<script setup>
defineProps({
  modelValue: Boolean,
  label: String,
  description: String,
});
const emit = defineEmits(["update:modelValue"]);
</script>

<template>
  <label class="flex cursor-pointer items-start justify-between gap-4">
    <span class="min-w-0">
      <span class="block text-[13px] font-medium text-ink">{{ label }}</span>
      <span v-if="description" class="mt-0.5 block text-[12px] leading-snug text-ink-muted">{{ description }}</span>
    </span>
    <button
      type="button"
      role="switch"
      :aria-checked="modelValue"
      :aria-label="label"
      class="relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition"
      :style="{ backgroundColor: modelValue ? 'var(--primary)' : 'var(--line-strong)' }"
      @click="emit('update:modelValue', !modelValue)"
    >
      <span
        class="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all"
        :style="{ left: modelValue ? '1.125rem' : '0.125rem' }"
      />
    </button>
  </label>
</template>
