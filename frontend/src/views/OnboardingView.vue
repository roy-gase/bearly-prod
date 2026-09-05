<script setup>
/**
 * Onboarding collects the figures every metric depends on.
 *
 * Split into four short steps rather than one long form: a wall of financial
 * questions is where people give up. Every field is optional except income —
 * an incomplete picture still produces a useful one.
 */
import { computed, ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import { money0 } from "@/lib/format";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Select from "@/components/ui/Select.vue";
import Alert from "@/components/ui/Alert.vue";
import ThemeToggle from "@/components/app/ThemeToggle.vue";
import BearLockup from "@/components/brand/BearLockup.vue";

const router = useRouter();
const auth = useAuthStore();

const step = ref(0);
const saving = ref(false);
const error = ref("");

const form = ref({
  monthly_net_income: "",
  other_monthly_income: "",
  checking_balance: "",
  savings_balance: "",
  emergency_savings: "",
  investment_balance: "",
  monthly_housing_cost: "",
  monthly_essential_expenses: "",
  monthly_discretionary_expenses: "",
  stated_total_debt: "",
  stated_debt_interest_rate: "",
  stated_minimum_payments: "",
  financial_goals: [],
  investment_horizon_years: 10,
  risk_tolerance: "moderate",
});

const GOALS = [
  "Build an emergency fund",
  "Pay off debt",
  "Buy a home",
  "Save for retirement",
  "Save for a big purchase",
  "Grow long-term investments",
  "Just spend less than I earn",
];

const STEPS = [
  { title: "What comes in", blurb: "Start with the money you actually take home each month." },
  { title: "What goes out", blurb: "Rough monthly figures are fine — you can refine them later." },
  { title: "What you have and owe", blurb: "Balances as they stand today." },
  { title: "What you're aiming for", blurb: "This shapes the guidance you get." },
];

function num(value) {
  const n = Number(String(value).replace(/[^0-9.-]/g, ""));
  return Number.isFinite(n) ? n : 0;
}

const income = computed(() => num(form.value.monthly_net_income) + num(form.value.other_monthly_income));
const expenses = computed(
  () =>
    num(form.value.monthly_housing_cost) +
    num(form.value.monthly_essential_expenses) +
    num(form.value.monthly_discretionary_expenses),
);
const surplus = computed(() => income.value - expenses.value);

function toggleGoal(goal) {
  const list = form.value.financial_goals;
  const index = list.indexOf(goal);
  if (index === -1) list.push(goal);
  else list.splice(index, 1);
}

async function finish() {
  saving.value = true;
  error.value = "";
  try {
    const payload = { ...form.value };
    for (const key of Object.keys(payload)) {
      if (key === "financial_goals" || key === "risk_tolerance") continue;
      payload[key] = num(payload[key]);
    }
    payload.investment_horizon_years = Math.round(num(form.value.investment_horizon_years)) || 10;
    await api.put("/profile", payload);
    await auth.markOnboarded();
    router.push({ name: "dashboard" });
  } catch (err) {
    error.value = err.message || "Could not save your profile.";
  } finally {
    saving.value = false;
  }
}

onMounted(async () => {
  // Returning to onboarding should not wipe what was already entered.
  try {
    const existing = await api.get("/profile");
    for (const key of Object.keys(form.value)) {
      if (existing[key] !== undefined && existing[key] !== null) form.value[key] = existing[key];
    }
  } catch {
    /* first run — nothing saved yet */
  }
});
</script>

<template>
  <div class="min-h-dvh bg-page">
    <header class="flex items-center justify-between px-5 py-4">
      <BearLockup :mark-size="28" word-size="17px" />
      <ThemeToggle />
    </header>

    <main class="mx-auto w-full max-w-xl px-4 pb-16">
      <!-- Progress: four short steps, always visible -->
      <div class="mb-7 flex gap-1.5" role="progressbar" :aria-valuenow="step + 1" aria-valuemin="1" aria-valuemax="4">
        <div
          v-for="(_, i) in STEPS" :key="i"
          class="h-1 flex-1 rounded-full transition-colors"
          :style="{ backgroundColor: i <= step ? 'var(--primary)' : 'var(--line)' }"
        />
      </div>

      <p class="text-[12px] font-medium uppercase tracking-wide text-ink-subtle">
        Step {{ step + 1 }} of {{ STEPS.length }}
      </p>
      <h1 class="mt-1.5 text-[24px] font-semibold tracking-tight text-ink">{{ STEPS[step].title }}</h1>
      <p class="mt-1.5 text-[14px] leading-relaxed text-ink-muted">{{ STEPS[step].blurb }}</p>

      <div class="mt-6 rounded-xl border border-line bg-card p-5 shadow-card sm:p-6">
        <Alert v-if="error" variant="critical" class="mb-4">{{ error }}</Alert>

        <div v-show="step === 0" class="space-y-4">
          <Input v-model="form.monthly_net_income" label="Monthly take-home pay" money
            hint="After tax and deductions — what actually lands in your account." />
          <Input v-model="form.other_monthly_income" label="Other monthly income" money
            hint="Side work, rental income, benefits. Leave blank if none." />
        </div>

        <div v-show="step === 1" class="space-y-4">
          <Input v-model="form.monthly_housing_cost" label="Housing" money hint="Rent or mortgage, plus property costs." />
          <Input v-model="form.monthly_essential_expenses" label="Other essentials" money
            hint="Groceries, utilities, transport, insurance, childcare." />
          <Input v-model="form.monthly_discretionary_expenses" label="Everything else" money
            hint="Eating out, subscriptions, shopping, entertainment." />

          <div v-if="income > 0" class="rounded-lg border border-line bg-page p-3.5">
            <div class="flex items-center justify-between text-[13px]">
              <span class="text-ink-muted">Left over each month</span>
              <span
                class="text-[15px] font-semibold tabular"
                :style="{ color: surplus >= 0 ? 'var(--good-ink)' : 'var(--critical-ink)' }"
              >{{ money0(surplus) }}</span>
            </div>
            <p v-if="surplus < 0" class="mt-1.5 text-[12px] leading-relaxed text-ink-muted">
              That is more going out than coming in. Bearly will make closing this gap your first priority.
            </p>
          </div>
        </div>

        <div v-show="step === 2" class="space-y-4">
          <div class="grid gap-4 sm:grid-cols-2">
            <Input v-model="form.checking_balance" label="Checking" money />
            <Input v-model="form.savings_balance" label="Savings" money />
            <Input v-model="form.emergency_savings" label="Emergency fund" money
              hint="The part you would only touch in a crisis." />
            <Input v-model="form.investment_balance" label="Investments" money
              hint="Brokerage and retirement accounts." />
          </div>

          <div class="border-t border-line pt-4">
            <p class="mb-3 text-[13px] font-medium text-ink">Debt</p>
            <p class="mb-3 text-[12px] leading-relaxed text-ink-muted">
              A rough total is enough for now. You can add each debt separately later to compare payoff strategies.
            </p>
            <div class="grid gap-4 sm:grid-cols-3">
              <Input v-model="form.stated_total_debt" label="Total owed" money />
              <Input v-model="form.stated_debt_interest_rate" label="Average rate" suffix="%" />
              <Input v-model="form.stated_minimum_payments" label="Min. payments" money />
            </div>
          </div>
        </div>

        <div v-show="step === 3" class="space-y-5">
          <div>
            <p class="mb-2.5 text-[13px] font-medium text-ink">What matters most right now?</p>
            <div class="flex flex-wrap gap-2">
              <button
                v-for="goal in GOALS" :key="goal" type="button"
                :aria-pressed="form.financial_goals.includes(goal)"
                :class="[
                  'rounded-full border px-3 py-1.5 text-[13px] transition',
                  form.financial_goals.includes(goal)
                    ? 'border-transparent bg-[color:var(--primary-soft)] font-medium text-primary'
                    : 'border-line text-ink-muted hover:border-line-strong hover:text-ink',
                ]"
                @click="toggleGoal(goal)"
              >{{ goal }}</button>
            </div>
          </div>

          <Select
            v-model="form.risk_tolerance" label="How do you feel about investment risk?"
            :options="[
              { value: 'conservative', label: 'Conservative — I would rather not see big swings' },
              { value: 'moderate', label: 'Moderate — some ups and downs are fine' },
              { value: 'aggressive', label: 'Aggressive — I can ride out a bad year' },
            ]"
          />
          <Input
            v-model="form.investment_horizon_years" label="Years until you need this money" type="number"
            min="0" max="60" hint="Retirement is often 20+ years; a house deposit might be 3."
          />
        </div>

        <div class="mt-6 flex items-center justify-between gap-3 border-t border-line pt-5">
          <Button v-if="step > 0" variant="ghost" @click="step--">Back</Button>
          <span v-else />
          <Button v-if="step < STEPS.length - 1" @click="step++">Continue</Button>
          <Button v-else :loading="saving" @click="finish">Finish setup</Button>
        </div>
      </div>

      <p class="mt-4 text-center text-[12px] text-ink-subtle">
        You can change any of this later in Settings.
      </p>
    </main>
  </div>
</template>
