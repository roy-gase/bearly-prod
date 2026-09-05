<script setup>
import ThemeToggle from "./ThemeToggle.vue";
import BearLockup from "@/components/brand/BearLockup.vue";

defineProps({ title: String, subtitle: String });
</script>

<template>
  <div class="flex min-h-dvh flex-col bg-page">
    <header class="flex items-center justify-between px-5 py-4">
      <BearLockup :mark-size="28" word-size="17px" />
      <ThemeToggle />
    </header>

    <main class="flex flex-1 items-center justify-center px-4 pb-16">
      <div class="w-full max-w-[26rem]">
        <div class="mb-6 text-center">
          <h1 class="text-[24px] font-semibold tracking-tight text-ink">{{ title }}</h1>
          <p v-if="subtitle" class="mx-auto mt-2 max-w-sm text-[14px] leading-relaxed text-ink-muted">
            {{ subtitle }}
          </p>
        </div>

        <div class="rounded-[20px] border border-line bg-card p-6">
          <slot />
        </div>

        <p v-if="$slots.footer" class="mt-5 text-center text-[13px] text-ink-muted">
          <slot name="footer" />
        </p>
      </div>
    </main>
  </div>
</template>
