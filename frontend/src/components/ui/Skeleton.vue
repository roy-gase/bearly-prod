<script setup>
defineProps({ class: { type: String, default: "h-4 w-full" } });
</script>

<template>
  <div class="animate-pulse rounded-md bg-raised" :class="$props.class" aria-hidden="true" />
</template>
