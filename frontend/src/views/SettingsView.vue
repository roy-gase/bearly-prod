<script setup>
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import { money0 } from "@/lib/format";

import Card from "@/components/ui/Card.vue";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Select from "@/components/ui/Select.vue";
import Alert from "@/components/ui/Alert.vue";
import Tabs from "@/components/ui/Tabs.vue";

const auth = useAuthStore();
const router = useRouter();

const tab = ref("profile");
const notice = ref("");
const error = ref("");

const account = ref({ full_name: "", currency: "USD" });
const passwords = ref({ current_password: "", new_password: "", confirm: "" });
const profile = ref(null);
const savingProfile = ref(false);

async function load() {
  account.value = {
    full_name: auth.user?.full_name ?? "",
    currency: auth.user?.currency ?? "USD",
  };
  profile.value = await api.get("/profile");
}

onMounted(load);

async function saveAccount() {
  notice.value = "";
  error.value = "";
  try {
    await auth.updateProfile(account.value);
    notice.value = "Account updated.";
  } catch (err) {
    error.value = err.message;
  }
}

async function saveProfile() {
  savingProfile.value = true;
  notice.value = "";
  error.value = "";
  try {
    const payload = { ...profile.value };
    delete payload.id;
    delete payload.onboarding_completed_at;
    delete payload.updated_at;
    for (const key of Object.keys(payload)) {
      if (key === "financial_goals" || key === "risk_tolerance" || key === "notes") continue;
      payload[key] = Number(payload[key]) || 0;
    }
    profile.value = await api.put("/profile", payload);
    notice.value = "Financial profile updated. Your metrics and AI advice have been refreshed.";
  } catch (err) {
    error.value = err.fieldErrors?.[0]?.message || err.message;
  } finally {
    savingProfile.value = false;
  }
}

async function changePassword() {
  notice.value = "";
  error.value = "";
  if (passwords.value.new_password !== passwords.value.confirm) {
    error.value = "Those passwords do not match.";
    return;
  }
  try {
    await auth.changePassword(passwords.value.current_password, passwords.value.new_password);
    passwords.value = { current_password: "", new_password: "", confirm: "" };
    notice.value = "Password changed.";
  } catch (err) {
    error.value = err.fieldErrors?.[0]?.message || err.message;
  }
}

async function signOutEverywhere() {
  await api.post("/auth/logout-all");
  auth.clear();
  router.push({ name: "login" });
}

async function signOut() {
  await auth.logout();
  router.push({ name: "login" });
}
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-[22px] font-semibold tracking-tight text-ink">Settings</h1>
      <p class="mt-1 text-[14px] text-ink-muted">Your account and the figures Bearly reasons from.</p>
    </div>

    <div class="mb-5">
      <Tabs
        v-model="tab"
        :tabs="[
          { value: 'profile', label: 'Financial profile' },
          { value: 'account', label: 'Account' },
          { value: 'security', label: 'Security' },
        ]"
      />
    </div>

    <Alert v-if="notice" variant="good" class="mb-4">{{ notice }}</Alert>
    <Alert v-if="error" variant="critical" class="mb-4">{{ error }}</Alert>

    <Card v-if="tab === 'profile' && profile" title="Financial profile"
      subtitle="These figures feed every metric. Where you have logged real transactions, debts or holdings, those take precedence.">
      <div class="space-y-6">
        <div>
          <h3 class="mb-3 text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">Income</h3>
          <div class="grid gap-4 sm:grid-cols-2">
            <Input v-model="profile.monthly_net_income" label="Monthly take-home pay" money />
            <Input v-model="profile.other_monthly_income" label="Other monthly income" money />
          </div>
        </div>

        <div>
          <h3 class="mb-3 text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">Monthly expenses</h3>
          <div class="grid gap-4 sm:grid-cols-3">
            <Input v-model="profile.monthly_housing_cost" label="Housing" money />
            <Input v-model="profile.monthly_essential_expenses" label="Other essentials" money />
            <Input v-model="profile.monthly_discretionary_expenses" label="Discretionary" money />
          </div>
        </div>

        <div>
          <h3 class="mb-3 text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">Balances</h3>
          <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Input v-model="profile.checking_balance" label="Checking" money />
            <Input v-model="profile.savings_balance" label="Savings" money />
            <Input v-model="profile.emergency_savings" label="Emergency fund" money />
            <Input v-model="profile.investment_balance" label="Investments" money />
          </div>
        </div>

        <div>
          <h3 class="mb-3 text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">Debt summary</h3>
          <p class="mb-3 text-[12px] text-ink-muted">
            Used only when you have not added individual debts on the Debt page.
          </p>
          <div class="grid gap-4 sm:grid-cols-3">
            <Input v-model="profile.stated_total_debt" label="Total owed" money />
            <Input v-model="profile.stated_debt_interest_rate" label="Average rate" suffix="%" />
            <Input v-model="profile.stated_minimum_payments" label="Minimum payments" money />
          </div>
        </div>

        <div>
          <h3 class="mb-3 text-[12px] font-semibold uppercase tracking-wide text-ink-subtle">Investing</h3>
          <div class="grid gap-4 sm:grid-cols-2">
            <Select
              v-model="profile.risk_tolerance" label="Risk tolerance"
              :options="[
                { value: 'conservative', label: 'Conservative' },
                { value: 'moderate', label: 'Moderate' },
                { value: 'aggressive', label: 'Aggressive' },
              ]"
            />
            <Input v-model="profile.investment_horizon_years" label="Investment horizon (years)" type="number" min="0" max="60" />
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end">
          <Button :loading="savingProfile" @click="saveProfile">Save profile</Button>
        </div>
      </template>
    </Card>

    <Card v-if="tab === 'account'" title="Account">
      <div class="max-w-md space-y-4">
        <Input v-model="account.full_name" label="Name" />
        <Select
          v-model="account.currency" label="Currency"
          :options="[
            { value: 'USD', label: 'US Dollar (USD)' },
            { value: 'EUR', label: 'Euro (EUR)' },
            { value: 'GBP', label: 'British Pound (GBP)' },
            { value: 'CAD', label: 'Canadian Dollar (CAD)' },
            { value: 'AUD', label: 'Australian Dollar (AUD)' },
          ]"
        />
        <p class="text-[12px] text-ink-muted">Signed in as {{ auth.user?.email }}</p>
        <Button @click="saveAccount">Save changes</Button>
      </div>
    </Card>

    <div v-if="tab === 'security'" class="space-y-6">
      <Card title="Change password">
        <form class="max-w-md space-y-4" @submit.prevent="changePassword">
          <Input v-model="passwords.current_password" label="Current password" type="password" autocomplete="current-password" required />
          <Input
            v-model="passwords.new_password" label="New password" type="password" autocomplete="new-password" required
            hint="At least 10 characters, mixing letters with numbers or symbols."
          />
          <Input v-model="passwords.confirm" label="Confirm new password" type="password" autocomplete="new-password" required />
          <Button type="submit">Change password</Button>
        </form>
      </Card>

      <Card title="Sessions" subtitle="Signing out everywhere ends every session on every device.">
        <div class="flex flex-wrap gap-2">
          <Button variant="secondary" @click="signOut">Sign out</Button>
          <Button variant="danger" @click="signOutEverywhere">Sign out everywhere</Button>
        </div>
      </Card>
    </div>
  </div>
</template>
