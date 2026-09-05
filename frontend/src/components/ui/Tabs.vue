<script setup>
defineProps({
  modelValue: String,
  /** [{ value, label, badge? }] */
  tabs: { type: Array, default: () => [] },
});
const emit = defineEmits(["update:modelValue"]);
</script>

<template>
  <div class="inline-flex gap-1 rounded-lg border border-line bg-raised p-1" role="tablist">
    <button
      v-for="tab in tabs"
      :key="tab.value"
      type="button"
      role="tab"
      :aria-selected="modelValue === tab.value"
      :class="[
        'rounded-md px-3 py-1.5 text-[13px] font-medium transition',
        modelValue === tab.value
          ? 'bg-card text-ink shadow-card'
          : 'text-ink-muted hover:text-ink',
      ]"
      @click="emit('update:modelValue', tab.value)"
    >
      {{ tab.label }}
      <span v-if="tab.badge != null" class="ml-1 text-ink-subtle tabular">{{ tab.badge }}</span>
    </button>
  </div>
</template>
