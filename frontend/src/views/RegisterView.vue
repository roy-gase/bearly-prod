<script setup>
import { ref } from "vue";
import { useRouter } from "vue-router";
import { useAuthStore } from "@/stores/auth";
import AuthLayout from "@/components/app/AuthLayout.vue";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Alert from "@/components/ui/Alert.vue";

const auth = useAuthStore();
const router = useRouter();

const fullName = ref("");
const email = ref("");
const password = ref("");
const error = ref("");
const fieldErrors = ref({});

async function submit() {
  error.value = "";
  fieldErrors.value = {};
  try {
    await auth.register({
      email: email.value,
      password: password.value,
      full_name: fullName.value || null,
    });
    router.push({ name: "onboarding" });
  } catch (err) {
    error.value = err.message || "Could not create your account.";
    for (const fe of err.fieldErrors ?? []) fieldErrors.value[fe.field] = fe.message;
  }
}
</script>

<template>
  <AuthLayout
    title="Create your account"
    subtitle="A few numbers is all it takes to see your full picture."
  >
    <form class="space-y-4" @submit.prevent="submit">
      <Alert v-if="error && !Object.keys(fieldErrors).length" variant="critical">{{ error }}</Alert>

      <Input v-model="fullName" label="Name" autocomplete="name" placeholder="Optional" />
      <Input
        v-model="email" label="Email" type="email" autocomplete="email" required
        placeholder="you@example.com" :error="fieldErrors.email"
      />
      <Input
        v-model="password" label="Password" type="password" autocomplete="new-password" required
        hint="At least 10 characters, mixing letters with numbers or symbols."
        :error="fieldErrors.password"
      />

      <Button type="submit" class="w-full" size="lg" :loading="auth.loading">Create account</Button>

      <p class="text-center text-[12px] leading-relaxed text-ink-subtle">
        Bearly gives you educational guidance, not licensed financial advice.
      </p>
    </form>

    <template #footer>
      Already have an account?
      <RouterLink :to="{ name: 'login' }" class="font-medium text-primary underline-offset-4 hover:underline">
        Sign in
      </RouterLink>
    </template>
  </AuthLayout>
</template>
