<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import AuthLayout from "@/components/app/AuthLayout.vue";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Alert from "@/components/ui/Alert.vue";

const auth = useAuthStore();
const route = useRoute();
const router = useRouter();

const email = ref("");
const password = ref("");
const error = ref("");

async function submit() {
  error.value = "";
  try {
    await auth.login(email.value, password.value);
    router.push(route.query.next || { name: "dashboard" });
  } catch (err) {
    error.value = err.message || "Could not sign you in.";
  }
}
</script>

<template>
  <AuthLayout
    title="Welcome back"
    subtitle="Sign in to see where you stand and what to focus on next."
  >
    <form class="space-y-4" @submit.prevent="submit">
      <Alert v-if="error" variant="critical">{{ error }}</Alert>

      <Input v-model="email" label="Email" type="email" autocomplete="email" required placeholder="you@example.com" />
      <Input v-model="password" label="Password" type="password" autocomplete="current-password" required />

      <div class="flex justify-end">
        <RouterLink :to="{ name: 'forgot-password' }" class="text-[13px] text-primary underline-offset-4 hover:underline">
          Forgot your password?
        </RouterLink>
      </div>

      <Button type="submit" class="w-full" size="lg" :loading="auth.loading">Sign in</Button>
    </form>

    <template #footer>
      New to Bearly?
      <RouterLink :to="{ name: 'register' }" class="font-medium text-primary underline-offset-4 hover:underline">
        Create an account
      </RouterLink>
    </template>
  </AuthLayout>
</template>
