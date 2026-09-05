<script setup>
/**
 * Horizontal mark + wordmark lockup.
 * "Bear" is 500, "ly" is 700, letter-spacing −0.03em.
 */
import BearMark from "./BearMark.vue";

defineProps({
  markSize: { type: Number, default: 28 },
  variant: { type: String, default: "full" }, // full | mono | icon
  wordSize: { type: String, default: "17px" },
  to: { type: [String, Object], default: null },
});
</script>

<template>
  <component
    :is="to ? 'RouterLink' : 'span'"
    :to="to || undefined"
    class="inline-flex items-center gap-[7px] text-ink no-underline"
  >
    <BearMark :size="markSize" :variant="variant" />
    <span
      class="font-medium tracking-[-0.03em]"
      :style="{ fontSize: wordSize }"
    >Bear<span class="font-bold">ly</span></span>
  </component>
</template>
