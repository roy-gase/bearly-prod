<script setup>
import { ref } from "vue";
import { api } from "@/lib/api";
import AuthLayout from "@/components/app/AuthLayout.vue";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Alert from "@/components/ui/Alert.vue";

const email = ref("");
const sent = ref(false);
const loading = ref(false);
const devToken = ref("");

async function submit() {
  loading.value = true;
  try {
    const body = await api.post("/auth/forgot-password", { email: email.value });
    // Development convenience only: the backend withholds this in production,
    // where the token is delivered by email instead.
    devToken.value = body.dev_reset_token ?? "";
    sent.value = true;
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <AuthLayout
    title="Reset your password"
    subtitle="Enter your email and we'll send you a link to set a new password."
  >
    <div v-if="sent" class="space-y-4">
      <Alert variant="good" title="Check your email">
        If an account exists for that address, a reset link is on its way.
      </Alert>

      <div v-if="devToken" class="rounded-lg border border-dashed border-line bg-page p-3">
        <p class="text-[12px] font-medium text-ink">Development mode</p>
        <p class="mt-1 text-[12px] text-ink-muted">No mail is sent locally. Use this token:</p>
        <code class="mt-2 block break-all rounded bg-raised p-2 text-[11px] text-ink">{{ devToken }}</code>
        <RouterLink
          :to="{ name: 'reset-password', query: { token: devToken } }"
          class="mt-2 inline-block text-[12px] font-medium text-primary underline-offset-4 hover:underline"
        >Continue to reset →</RouterLink>
      </div>
    </div>

    <form v-else class="space-y-4" @submit.prevent="submit">
      <Input v-model="email" label="Email" type="email" autocomplete="email" required placeholder="you@example.com" />
      <Button type="submit" class="w-full" size="lg" :loading="loading">Send reset link</Button>
    </form>

    <template #footer>
      <RouterLink :to="{ name: 'login' }" class="font-medium text-primary underline-offset-4 hover:underline">
        Back to sign in
      </RouterLink>
    </template>
  </AuthLayout>
</template>
