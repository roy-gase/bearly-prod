<script setup>
defineProps({
  title: String,
  subtitle: String,
  /** Removes inner padding so charts and tables can reach the edges. */
  flush: Boolean,
});
</script>

<template>
  <section class="rounded-[20px] border border-line bg-card">
    <header
      v-if="title || $slots.header || $slots.action"
      class="flex items-start justify-between gap-4 px-5 pt-5"
      :class="{ 'pb-4': flush }"
    >
      <div class="min-w-0">
        <slot name="header">
          <h2 class="text-[15px] font-semibold leading-tight text-ink">{{ title }}</h2>
          <p v-if="subtitle" class="mt-1 text-[13px] leading-snug text-ink-muted">{{ subtitle }}</p>
        </slot>
      </div>
      <div v-if="$slots.action" class="shrink-0"><slot name="action" /></div>
    </header>
    <div :class="flush ? '' : 'p-5'" :style="(title || $slots.header) && !flush ? 'padding-top:1rem' : ''">
      <slot />
    </div>
    <footer v-if="$slots.footer" class="border-t border-line px-5 py-3 text-[13px] text-ink-muted">
      <slot name="footer" />
    </footer>
  </section>
</template>
