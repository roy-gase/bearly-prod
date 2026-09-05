<script setup>
import { computed } from "vue";

const props = defineProps({
  variant: { type: String, default: "primary" }, // primary | secondary | ghost | danger | link
  size: { type: String, default: "md" }, // sm | md | lg | icon
  type: { type: String, default: "button" },
  disabled: Boolean,
  loading: Boolean,
  as: { type: String, default: "button" },
});

const VARIANTS = {
  primary: "bg-primary text-[color:var(--primary-ink)] hover:opacity-90 shadow-card",
  secondary: "bg-card text-ink border border-line hover:bg-raised",
  ghost: "text-ink-muted hover:bg-raised hover:text-ink",
  danger: "bg-[color:var(--critical)] text-white hover:opacity-90",
  link: "text-primary underline-offset-4 hover:underline p-0 h-auto",
};

const SIZES = {
  sm: "h-8 px-3 text-[13px] gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
  lg: "h-11 px-5 text-[15px] gap-2",
  icon: "h-9 w-9 p-0",
};

const classes = computed(() => [
  "inline-flex items-center justify-center rounded-lg font-medium transition",
  "disabled:pointer-events-none disabled:opacity-50 select-none whitespace-nowrap",
  VARIANTS[props.variant] ?? VARIANTS.primary,
  props.variant === "link" ? "" : (SIZES[props.size] ?? SIZES.md),
]);
</script>

<template>
  <component
    :is="as"
    :type="as === 'button' ? type : undefined"
    :class="classes"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
  >
    <svg v-if="loading" class="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="2.5" class="opacity-25" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" />
    </svg>
    <slot />
  </component>
</template>
