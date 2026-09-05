<script setup>
import Button from "@/components/ui/Button.vue";
import BearAvatar from "@/components/brand/BearAvatar.vue";
</script>

<template>
  <div class="flex min-h-[60vh] flex-col items-center justify-center text-center">
    <BearAvatar :size="80" detail="full" />
    <h1 class="mt-4 text-[20px] font-semibold text-ink">That page does not exist</h1>
    <p class="mt-1 text-[14px] text-ink-muted">The link may be out of date.</p>
    <Button :as="'a'" class="mt-5" @click="$router.push({ name: 'dashboard' })">Back to dashboard</Button>
  </div>
</template>
