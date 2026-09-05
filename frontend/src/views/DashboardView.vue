<script setup>
/**
 * The dashboard answers three questions in order: where am I, what should I do
 * next, and am I improving. Everything on this page comes from one backend read
 * so no two figures can disagree.
 */
import { computed, onMounted, ref } from "vue";
import { api } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import { money0, moneySigned, percent, monthsToHuman, titleCase } from "@/lib/format";
import { FLOW, foldToSeries } from "@/lib/colors";

import StatTile from "@/components/app/StatTile.vue";
import PriorityList from "@/components/app/PriorityList.vue";
import PageState from "@/components/app/PageState.vue";
import Card from "@/components/ui/Card.vue";
import Button from "@/components/ui/Button.vue";
import Alert from "@/components/ui/Alert.vue";
import Badge from "@/components/ui/Badge.vue";
import Progress from "@/components/ui/Progress.vue";
import ScoreDial from "@/components/charts/ScoreDial.vue";
import GroupedBarChart from "@/components/charts/GroupedBarChart.vue";
import LineChart from "@/components/charts/LineChart.vue";
import AllocationBar from "@/components/charts/AllocationBar.vue";
import BudgetBars from "@/components/charts/BudgetBars.vue";

const auth = useAuthStore();
const loading = ref(true);
const error = ref("");
const data = ref(null);
const cashFlow = ref([]);
const snapshots = ref([]);
const savingSnapshot = ref(false);

const BASIS_LABEL = {
  transactions: "from your logged transactions",
  profile: "from your profile figures",
  records: "from your accounts",
  none: "no data yet",
};

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [dashboard, flow, history] = await Promise.all([
      api.get("/dashboard"),
      api.get("/dashboard/cash-flow-history", { months: 12 }),
      api.get("/dashboard/snapshots", { days: 365 }),
    ]);
    data.value = dashboard;
    cashFlow.value = flow;
    snapshots.value = history;
  } catch (err) {
    error.value = err.message || "Could not load your dashboard.";
  } finally {
    loading.value = false;
  }
}

async function captureSnapshot() {
  savingSnapshot.value = true;
  try {
    await api.post("/dashboard/snapshot");
    snapshots.value = await api.get("/dashboard/snapshots", { days: 365 });
  } finally {
    savingSnapshot.value = false;
  }
}

onMounted(load);

const cashFlowGroups = computed(() =>
  cashFlow.value.map((m) => ({ label: m.label, values: [m.income, m.expenses] })),
);
const hasCashFlowHistory = computed(() => cashFlow.value.some((m) => m.income > 0 || m.expenses > 0));

const cashFlowLabels = computed(() => cashFlow.value.map((m) => m.label));
const netCashFlowSeries = computed(() => [
  {
    label: "Net cash flow",
    color: FLOW.net,
    points: cashFlow.value.map((m) => ({ x: m.period, y: m.net })),
  },
]);

const snapshotLabels = computed(() =>
  snapshots.value.map((s) => new Date(s.date).toLocaleDateString(undefined, { month: "short", day: "numeric" })),
);

const netWorthSeries = computed(() => [
  {
    label: "Net worth",
    color: "var(--series-1)",
    points: snapshots.value.map((s) => ({ x: s.date, y: s.net_worth })),
  },
]);

const positionSeries = computed(() => [
  {
    label: "Assets",
    color: "var(--series-3)",
    points: snapshots.value.map((s) => ({ x: s.date, y: s.total_assets })),
  },
  {
    label: "Owed",
    color: "var(--series-2)",
    points: snapshots.value.map((s) => ({ x: s.date, y: s.total_liabilities })),
  },
]);

const savingsRateSeries = computed(() => [
  {
    label: "Savings rate",
    color: "var(--series-1)",
    points: snapshots.value.map((s) => ({ x: s.date, y: s.savings_rate })),
  },
]);

const healthScoreSeries = computed(() => [
  {
    label: "Health score",
    color: "var(--series-1)",
    points: snapshots.value.map((s) => ({ x: s.date, y: s.health_score })),
  },
]);

const allocation = computed(() => {
  const byType = data.value?.investments?.by_asset_type ?? {};
  const rows = Object.entries(byType)
    .map(([key, v]) => ({ label: titleCase(key), value: v.value }))
    .sort((a, b) => b.value - a.value);
  return foldToSeries(rows);
});

const riskAllocation = computed(() => {
  const byRisk = data.value?.investments?.by_risk ?? {};
  const rows = Object.entries(byRisk)
    .map(([key, v]) => ({ label: titleCase(key), value: v.value }))
    .sort((a, b) => b.value - a.value);
  return foldToSeries(rows);
});

const balanceSlices = computed(() => {
  if (!data.value) return [];
  const cash = data.value.net_worth.cash;
  const investments = data.value.net_worth.investments;
  const other = Math.max(0, data.value.net_worth.assets - cash - investments);
  return foldToSeries(
    [
      { label: "Cash", value: cash },
      { label: "Investments", value: investments },
      { label: "Other assets", value: other },
    ]
      .filter((row) => row.value > 0)
      .sort((a, b) => b.value - a.value),
  );
});

const spendMix = computed(() => {
  if (!data.value) return [];
  return foldToSeries(
    [
      { label: "Essential", value: data.value.cash_flow.essential },
      { label: "Discretionary", value: data.value.cash_flow.discretionary },
    ]
      .filter((row) => row.value > 0)
      .sort((a, b) => b.value - a.value),
  );
});

const ownVsOwe = computed(() => {
  if (!data.value) return [];
  return foldToSeries(
    [
      { label: "What you own", value: data.value.net_worth.assets },
      { label: "What you owe", value: data.value.net_worth.liabilities },
    ].filter((row) => row.value > 0),
  );
});

const debtMix = computed(() => {
  if (!data.value || data.value.debt.total <= 0) return [];
  const high = data.value.debt.high_interest;
  const rest = Math.max(0, data.value.debt.total - high);
  return foldToSeries(
    [
      { label: "Above 8% APR", value: high },
      { label: "Other debt", value: rest },
    ].filter((row) => row.value > 0),
  );
});

const investmentGain = computed(() => {
  if (!data.value) return null;
  const value = data.value.investments.value;
  const cost = data.value.investments.cost_basis;
  if (!cost) return null;
  return value - cost;
});

const emergencyTone = computed(() => {
  const months = data.value?.emergency_fund?.months_covered ?? 0;
  if (months >= 3) return "good";
  if (months >= 1) return "warning";
  return "critical";
});

const netWorthTrend = computed(() => snapshots.value.map((s) => s.net_worth));
const savingsTrend = computed(() => snapshots.value.map((s) => s.savings_rate));
</script>

<template>
  <div>
    <template v-if="!loading && !error && data">
      <div class="mb-6">
        <h1 class="text-[22px] font-semibold tracking-tight text-ink">
          Hello, {{ auth.displayName }}
        </h1>
        <p class="mt-1 text-[14px] text-ink-muted">{{ data.health.summary }}</p>
      </div>
    </template>

    <PageState :loading="loading" :error="error" :rows="4">
      <template v-if="data">
        <!-- The single most important thing, before any numbers -->
        <Alert
          v-if="data.priorities.blocking_issue === 'negative_cash_flow'"
          variant="critical"
          title="You are spending more than you earn"
          class="mb-6"
        >
          Every month this continues, the gap is funded by savings or borrowing. Closing it comes
          before saving, investing, or extra debt payments.
        </Alert>

        <!-- Headline widgets -->
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatTile
            label="Net worth"
            :value="money0(data.net_worth.value)"
            :detail="`${money0(data.net_worth.assets)} assets − ${money0(data.net_worth.liabilities)} owed`"
            :trend="netWorthTrend"
            :footnote="`Calculated ${BASIS_LABEL[data.net_worth.basis]}`"
          />
          <StatTile
            label="Monthly cash flow"
            :value="moneySigned(data.cash_flow.net)"
            :detail="`${money0(data.cash_flow.income)} in, ${money0(data.cash_flow.expenses)} out`"
            :delta="{
              text: data.cash_flow.net >= 0 ? 'surplus' : 'shortfall',
              direction: data.cash_flow.net >= 0 ? 'up' : 'down',
              good: data.cash_flow.net >= 0,
            }"
            :footnote="`Income ${BASIS_LABEL[data.cash_flow.income_basis]}`"
          />
          <StatTile
            label="Savings rate"
            :value="percent(data.savings_rate.value)"
            :detail="`Target ${percent(data.savings_rate.target)}`"
            :trend="savingsTrend"
            :delta="{
              text: data.savings_rate.value >= data.savings_rate.target ? 'on target' : `${percent(Math.max(0, data.savings_rate.target - data.savings_rate.value))} to go`,
              direction: data.savings_rate.value >= data.savings_rate.target ? 'up' : 'flat',
              good: data.savings_rate.value >= 10,
            }"
          />
          <StatTile
            label="Total debt"
            :value="money0(data.debt.total)"
            :detail="data.debt.count ? `${data.debt.count} debts at ${percent(data.debt.weighted_apr, 1)} avg` : 'No debt recorded'"
            :footnote="data.debt.high_interest > 0 ? `${money0(data.debt.high_interest)} is above 8% APR` : undefined"
          />
        </div>

        <!-- Focus + score -->
        <div class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card class="lg:col-span-2" title="What to focus on next"
            subtitle="Worked out from your own numbers, in the order that helps you most.">
            <template #action>
              <Button variant="ghost" size="sm" @click="$router.push({ name: 'coach' })">Ask the coach</Button>
            </template>
            <PriorityList :steps="data.priorities.steps" :limit="4" />
          </Card>

          <Card title="Financial health" subtitle="Six weighted measures, no AI input.">
            <div class="flex flex-col items-center">
              <ScoreDial :score="data.health.score" :grade="data.health.grade" />
            </div>
            <ul class="mt-5 space-y-2.5">
              <li v-for="c in data.health.components" :key="c.key">
                <div class="mb-1 flex items-baseline justify-between gap-2">
                  <span class="text-[12.5px] text-ink">{{ c.label }}</span>
                  <span class="text-[11px] text-ink-subtle tabular">
                    {{ Math.round(c.points_earned) }}/{{ c.points_possible }}
                  </span>
                </div>
                <Progress
                  :value="c.score" size="sm"
                  :tone="c.score >= 80 ? 'good' : c.score >= 50 ? 'warning' : 'critical'"
                  :label="c.label"
                />
              </li>
            </ul>
            <p class="mt-4 border-t border-line pt-3 text-[11px] leading-relaxed text-ink-subtle">
              {{ data.health.methodology }}
            </p>
          </Card>
        </div>

        <!-- Charts -->
        <div class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card title="Income vs spending" subtitle="Last six months of recorded transactions.">
            <GroupedBarChart
              v-if="hasCashFlowHistory"
              :series="[
                { label: 'Income', color: FLOW.income },
                { label: 'Spending', color: FLOW.expense },
              ]"
              :groups="cashFlowGroups"
            />
            <div v-else class="py-8 text-center">
              <p class="text-[13px] text-ink-muted">No transactions logged yet.</p>
              <Button variant="secondary" size="sm" class="mt-3" @click="$router.push({ name: 'expenses' })">
                Add your first transaction
              </Button>
            </div>
          </Card>

          <Card title="Net worth over time" subtitle="Saved snapshots of your position.">
            <template #action>
              <Button variant="secondary" size="sm" :loading="savingSnapshot" @click="captureSnapshot">
                Save today
              </Button>
            </template>
            <LineChart
              v-if="snapshots.length > 1"
              :series="netWorthSeries" :labels="snapshotLabels" area
            />
            <div v-else class="py-8 text-center">
              <p class="text-[13px] text-ink-muted">
                {{ snapshots.length === 1 ? "One snapshot saved. Save another to see a trend." : "No snapshots yet." }}
              </p>
              <Button variant="secondary" size="sm" class="mt-3" :loading="savingSnapshot" @click="captureSnapshot">
                Save today's snapshot
              </Button>
            </div>
          </Card>
        </div>

        <div class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card title="Net cash flow" subtitle="Income minus spending, month by month.">
            <LineChart
              v-if="hasCashFlowHistory"
              :series="netCashFlowSeries"
              :labels="cashFlowLabels"
              area
            />
            <p v-else class="py-8 text-center text-[13px] text-ink-muted">
              Log a few months of transactions to see the surplus or shortfall over time.
            </p>
          </Card>

          <Card title="What you own vs owe" subtitle="How your balance sheet is split today.">
            <AllocationBar v-if="ownVsOwe.length" :slices="ownVsOwe" />
            <p v-else class="py-8 text-center text-[13px] text-ink-muted">
              Add balances and debts to see the split.
            </p>
          </Card>
        </div>

        <div class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card
            v-if="snapshots.length > 1"
            title="Assets and debt over time"
            subtitle="Saved snapshots of what you own and what you owe."
          >
            <LineChart :series="positionSeries" :labels="snapshotLabels" area />
          </Card>

          <Card
            v-if="snapshots.length > 1"
            title="Savings rate over time"
            subtitle="Share of income left after spending, from each snapshot."
          >
            <LineChart
              :series="savingsRateSeries"
              :labels="snapshotLabels"
              :format-y="(v) => percent(v)"
              :format-tooltip="(v) => percent(v, 1)"
              area
            />
          </Card>
        </div>

        <div v-if="snapshots.length > 1" class="mt-6">
          <Card title="Health score over time" subtitle="The same six-measure score, saved with each snapshot.">
            <LineChart
              :series="healthScoreSeries"
              :labels="snapshotLabels"
              :format-y="(v) => String(Math.round(v))"
              :format-tooltip="(v) => String(Math.round(v))"
              :show-zero="false"
              area
            />
          </Card>
        </div>

        <div class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card title="Where your money sits" subtitle="Cash, investments, and everything else you own.">
            <AllocationBar v-if="balanceSlices.length" :slices="balanceSlices" />
            <p v-else class="py-6 text-center text-[13px] text-ink-muted">No asset balances recorded.</p>
          </Card>

          <Card title="Spending mix" subtitle="This month’s outgoings, essential versus discretionary.">
            <AllocationBar v-if="spendMix.length" :slices="spendMix" />
            <p v-else class="py-6 text-center text-[13px] text-ink-muted">No spending recorded this month.</p>
          </Card>

          <Card title="Debt mix" subtitle="High-interest balances versus the rest.">
            <template v-if="debtMix.length">
              <p class="mb-3 text-[13px] text-ink-muted">
                {{ percent(data.debt.debt_to_income_pct, 1) }} of monthly income goes to minimum payments
                of {{ money0(data.debt.minimum_payments) }}.
              </p>
              <AllocationBar :slices="debtMix" />
            </template>
            <p v-else class="py-6 text-center text-[13px] text-ink-muted">No debt recorded.</p>
          </Card>
        </div>

        <div class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
          <Card title="Emergency fund">
            <p class="text-[26px] font-semibold leading-none text-ink">
              {{ monthsToHuman(Math.round(data.emergency_fund.months_covered)) }}
            </p>
            <p class="mt-1.5 text-[13px] text-ink-muted">of essential expenses covered</p>

            <Progress
              class="mt-4"
              :value="data.emergency_fund.current" :max="data.emergency_fund.target || 1"
              :tone="emergencyTone" label="Emergency fund progress"
            />
            <div class="mt-2 flex items-baseline justify-between text-[12px]">
              <span class="font-medium text-ink tabular">{{ money0(data.emergency_fund.current) }}</span>
              <span class="text-ink-subtle tabular">
                target {{ money0(data.emergency_fund.target) }}
              </span>
            </div>
            <p class="mt-3 text-[12px] leading-relaxed text-ink-muted">
              Three months of essentials is the usual first milestone; six if your income varies.
            </p>
          </Card>

          <Card title="Budget this month">
            <template v-if="data.budget.budgeted > 0">
              <div class="flex items-baseline justify-between">
                <p class="text-[26px] font-semibold leading-none text-ink">
                  {{ percent(data.budget.utilization_pct) }}
                </p>
                <Badge :variant="data.budget.over_budget_count ? 'critical' : 'good'">
                  {{ data.budget.over_budget_count ? `${data.budget.over_budget_count} over` : "On plan" }}
                </Badge>
              </div>
              <p class="mt-1.5 text-[13px] text-ink-muted">
                {{ money0(data.budget.spent) }} of {{ money0(data.budget.budgeted) }} used
              </p>
              <div class="mt-4">
                <BudgetBars :rows="data.budget.top_categories" :limit="4" />
              </div>
            </template>
            <div v-else class="py-6 text-center">
              <p class="text-[13px] text-ink-muted">No budget set for this month.</p>
              <Button variant="secondary" size="sm" class="mt-3" @click="$router.push({ name: 'budget' })">
                Set a budget
              </Button>
            </div>
          </Card>

          <Card title="Investment allocation">
            <template v-if="allocation.length">
              <p class="text-[26px] font-semibold leading-none text-ink">
                {{ money0(data.investments.value) }}
              </p>
              <p class="mt-1.5 text-[13px] text-ink-muted">
                across {{ data.investments.holding_count }} holdings
                <template v-if="investmentGain !== null">
                  ·
                  <span :style="{ color: investmentGain >= 0 ? 'var(--good-ink)' : 'var(--critical-ink)' }">
                    {{ moneySigned(investmentGain) }} vs cost
                  </span>
                </template>
              </p>
              <div class="mt-4">
                <AllocationBar :slices="allocation" />
              </div>
            </template>
            <div v-else class="py-6 text-center">
              <p class="text-[13px] text-ink-muted">
                {{ data.investments.value > 0 ? "Recorded as a single balance." : "No holdings recorded." }}
              </p>
              <Button variant="secondary" size="sm" class="mt-3" @click="$router.push({ name: 'investments' })">
                Add holdings
              </Button>
            </div>
          </Card>
        </div>

        <div class="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card title="Savings goals" subtitle="How far you are toward the totals you set.">
            <template v-if="data.goals.count">
              <p class="text-[26px] font-semibold leading-none text-ink">
                {{ percent(data.goals.target > 0 ? (data.goals.saved / data.goals.target) * 100 : 0) }}
              </p>
              <p class="mt-1.5 text-[13px] text-ink-muted">
                {{ money0(data.goals.saved) }} of {{ money0(data.goals.target) }}
                across {{ data.goals.count }} {{ data.goals.count === 1 ? "goal" : "goals" }}
              </p>
              <Progress
                class="mt-4"
                :value="data.goals.saved" :max="data.goals.target || 1"
                :tone="data.goals.saved >= data.goals.target ? 'good' : 'primary'"
                label="Goals progress"
              />
              <p class="mt-3 text-[12px] text-ink-muted">
                {{ money0(data.goals.monthly) }} planned each month.
              </p>
            </template>
            <div v-else class="py-6 text-center">
              <p class="text-[13px] text-ink-muted">No savings goals yet.</p>
              <Button variant="secondary" size="sm" class="mt-3" @click="$router.push({ name: 'savings' })">
                Add a goal
              </Button>
            </div>
          </Card>

          <Card title="Investment risk" subtitle="Holdings grouped by the risk you assigned.">
            <AllocationBar v-if="riskAllocation.length" :slices="riskAllocation" />
            <p v-else class="py-6 text-center text-[13px] text-ink-muted">
              Break holdings into types to see risk mix.
            </p>
          </Card>
        </div>
      </template>
    </PageState>
  </div>
</template>
