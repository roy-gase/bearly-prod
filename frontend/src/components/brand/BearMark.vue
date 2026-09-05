<script setup>
/**
 * Approved "Stash" mark — option 2a.
 * Variants: full (color), mono (currentColor silhouette), icon (app tile).
 */
import { computed } from "vue";

const props = defineProps({
  size: { type: [Number, String], default: 28 },
  variant: { type: String, default: "full" }, // full | mono | icon
  label: { type: String, default: "Bearly" },
});

const px = computed(() => Number(props.size));
</script>

<template>
  <svg
    v-if="variant === 'mono'"
    :width="px"
    :height="px"
    viewBox="0 0 100 100"
    fill="currentColor"
    :aria-label="label"
    role="img"
  >
    <circle cx="26" cy="26" r="12" />
    <circle cx="74" cy="26" r="12" />
    <circle cx="50" cy="55" r="30" />
  </svg>

  <span
    v-else-if="variant === 'icon'"
    class="inline-flex shrink-0 items-center justify-center overflow-hidden"
    :style="{ width: `${px}px`, height: `${px}px`, borderRadius: `${px * 0.26}px`, background: '#F6E7CE' }"
    :aria-label="label"
    role="img"
  >
    <svg :width="px * 0.74" :height="px * 0.74" viewBox="0 0 100 100" aria-hidden="true">
      <circle cx="26" cy="26" r="12" fill="#8B5E34" />
      <circle cx="74" cy="26" r="12" fill="#8B5E34" />
      <circle cx="50" cy="55" r="30" fill="#8B5E34" />
      <ellipse cx="50" cy="66" rx="15" ry="11.5" fill="#F6E7CE" />
      <circle cx="38" cy="50" r="3.4" fill="#241A12" />
      <circle cx="62" cy="50" r="3.4" fill="#241A12" />
    </svg>
  </span>

  <svg
    v-else
    :width="px"
    :height="px"
    viewBox="0 0 100 100"
    :aria-label="label"
    role="img"
  >
    <circle cx="26" cy="26" r="12" fill="#8B5E34" />
    <circle cx="74" cy="26" r="12" fill="#8B5E34" />
    <circle cx="50" cy="55" r="30" fill="#8B5E34" />
    <ellipse cx="50" cy="66" rx="15" ry="11.5" fill="#F6E7CE" />
    <circle cx="38" cy="50" r="3.4" fill="#241A12" />
    <circle cx="62" cy="50" r="3.4" fill="#241A12" />
    <circle cx="50" cy="61" r="4.2" fill="#241A12" />
  </svg>
</template>
