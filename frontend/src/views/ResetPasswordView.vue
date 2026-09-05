<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "@/lib/api";
import AuthLayout from "@/components/app/AuthLayout.vue";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Alert from "@/components/ui/Alert.vue";

const route = useRoute();
const router = useRouter();

const token = ref(route.query.token ?? "");
const password = ref("");
const confirm = ref("");
const error = ref("");
const loading = ref(false);

async function submit() {
  error.value = "";
  if (password.value !== confirm.value) {
    error.value = "Those passwords do not match.";
    return;
  }
  loading.value = true;
  try {
    await api.post("/auth/reset-password", { token: token.value, new_password: password.value });
    router.push({ name: "login", query: { reset: "1" } });
  } catch (err) {
    error.value = err.fieldErrors?.[0]?.message || err.message || "Could not reset your password.";
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <AuthLayout title="Set a new password" subtitle="Choose something you have not used elsewhere.">
    <form class="space-y-4" @submit.prevent="submit">
      <Alert v-if="error" variant="critical">{{ error }}</Alert>

      <Input v-if="!route.query.token" v-model="token" label="Reset token" required />
      <Input
        v-model="password" label="New password" type="password" autocomplete="new-password" required
        hint="At least 10 characters, mixing letters with numbers or symbols."
      />
      <Input v-model="confirm" label="Confirm new password" type="password" autocomplete="new-password" required />

      <Button type="submit" class="w-full" size="lg" :loading="loading">Update password</Button>
      <p class="text-center text-[12px] text-ink-subtle">
        Resetting your password signs you out everywhere else.
      </p>
    </form>
  </AuthLayout>
</template>
