<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { api } from "@/lib/api";
import { money0, longDate, titleCase } from "@/lib/format";

import PageState from "@/components/app/PageState.vue";
import Card from "@/components/ui/Card.vue";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Select from "@/components/ui/Select.vue";
import Badge from "@/components/ui/Badge.vue";
import Dialog from "@/components/ui/Dialog.vue";
import EmptyState from "@/components/ui/EmptyState.vue";

const loading = ref(true);
const error = ref("");
const page = ref({ items: [], total: 0, sum_income: 0, sum_expense: 0 });
const categories = ref([]);
const accounts = ref([]);

const filters = ref({ q: "", category_id: "", account_id: "", txn_type: "", date_from: "", date_to: "" });
const offset = ref(0);
const LIMIT = 25;

const blank = () => ({
  id: null,
  occurred_on: new Date().toISOString().slice(0, 10),
  amount: "",
  merchant: "",
  description: "",
  notes: "",
  txn_type: "expense",
  category_id: "",
  account_id: "",
  transfer_account_id: "",
});
const form = ref(blank());
const dialogOpen = ref(false);
const saving = ref(false);
const formError = ref("");

async function loadReference() {
  const [c, a] = await Promise.all([api.get("/budgets/categories"), api.get("/accounts")]);
  categories.value = c;
  accounts.value = a;
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    page.value = await api.get("/transactions", {
      ...filters.value,
      limit: LIMIT,
      offset: offset.value,
    });
  } catch (err) {
    error.value = err.message || "Could not load transactions.";
  } finally {
    loading.value = false;
  }
}

let debounce;
watch(
  filters,
  () => {
    clearTimeout(debounce);
    debounce = setTimeout(() => {
      offset.value = 0;
      load();
    }, 250);
  },
  { deep: true },
);
watch(offset, load);

onMounted(async () => {
  await loadReference();
  await load();
});

function openNew() {
  form.value = blank();
  formError.value = "";
  dialogOpen.value = true;
}

function openEdit(txn) {
  form.value = {
    ...txn,
    category_id: txn.category_id ?? "",
    account_id: txn.account_id ?? "",
    transfer_account_id: txn.transfer_account_id ?? "",
    description: txn.description ?? "",
    notes: txn.notes ?? "",
  };
  formError.value = "";
  dialogOpen.value = true;
}

function payload() {
  const body = {
    occurred_on: form.value.occurred_on,
    amount: Number(form.value.amount),
    merchant: form.value.merchant,
    description: form.value.description || null,
    notes: form.value.notes || null,
    txn_type: form.value.txn_type,
    category_id: form.value.category_id ? Number(form.value.category_id) : null,
    account_id: form.value.account_id ? Number(form.value.account_id) : null,
    transfer_account_id: form.value.transfer_account_id ? Number(form.value.transfer_account_id) : null,
  };
  return body;
}

async function save() {
  saving.value = true;
  formError.value = "";
  try {
    if (form.value.id) await api.patch(`/transactions/${form.value.id}`, payload());
    else await api.post("/transactions", payload());
    dialogOpen.value = false;
    await load();
  } catch (err) {
    formError.value = err.fieldErrors?.[0]?.message || err.message || "Could not save.";
  } finally {
    saving.value = false;
  }
}

async function remove(id) {
  await api.delete(`/transactions/${id}`);
  await load();
}

const categoryOptions = computed(() => categories.value.map((c) => ({ value: String(c.id), label: c.name })));
const accountOptions = computed(() => accounts.value.map((a) => ({ value: String(a.id), label: a.name })));
const hasFilters = computed(() => Object.values(filters.value).some((v) => v !== ""));

const TYPE_STYLE = { income: "good", expense: "neutral", transfer: "primary" };
</script>

<template>
  <div>
    <div class="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-[22px] font-semibold tracking-tight text-ink">Expenses</h1>
        <p class="mt-1 text-[14px] text-ink-muted">Every transaction you have logged.</p>
      </div>
      <Button @click="openNew">Add transaction</Button>
    </div>

    <!-- Filters sit in one row above the table -->
    <Card flush class="mb-6">
      <div class="grid grid-cols-1 gap-3 p-4 sm:grid-cols-2 lg:grid-cols-6">
        <div class="lg:col-span-2">
          <Input v-model="filters.q" placeholder="Search merchant or notes…" />
        </div>
        <Select v-model="filters.txn_type" placeholder="All types"
          :options="[{ value: 'expense', label: 'Expense' }, { value: 'income', label: 'Income' }, { value: 'transfer', label: 'Transfer' }]" />
        <Select v-model="filters.category_id" placeholder="All categories" :options="categoryOptions" />
        <Input v-model="filters.date_from" type="date" />
        <Input v-model="filters.date_to" type="date" />
      </div>
      <div v-if="hasFilters" class="flex items-center justify-between border-t border-line px-4 py-2.5">
        <p class="text-[12px] text-ink-muted">
          {{ page.total }} matching · {{ money0(page.sum_expense) }} spent · {{ money0(page.sum_income) }} received
        </p>
        <Button variant="ghost" size="sm" @click="filters = { q: '', category_id: '', account_id: '', txn_type: '', date_from: '', date_to: '' }">
          Clear filters
        </Button>
      </div>
    </Card>

    <PageState :loading="loading" :error="error">
      <Card v-if="page.items.length" flush>
        <div class="overflow-x-auto">
          <table class="w-full text-left text-[13px]">
            <thead class="border-b border-line text-[12px] text-ink-muted">
              <tr>
                <th scope="col" class="px-4 py-2.5 font-medium">Date</th>
                <th scope="col" class="px-4 py-2.5 font-medium">Merchant</th>
                <th scope="col" class="hidden px-4 py-2.5 font-medium sm:table-cell">Category</th>
                <th scope="col" class="hidden px-4 py-2.5 font-medium md:table-cell">Account</th>
                <th scope="col" class="px-4 py-2.5 text-right font-medium">Amount</th>
                <th scope="col" class="px-4 py-2.5"><span class="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="txn in page.items" :key="txn.id" class="border-b border-line last:border-0 hover:bg-raised">
                <td class="whitespace-nowrap px-4 py-3 text-ink-muted tabular">{{ longDate(txn.occurred_on) }}</td>
                <td class="px-4 py-3">
                  <p class="font-medium text-ink">{{ txn.merchant }}</p>
                  <p v-if="txn.description" class="text-[12px] text-ink-muted">{{ txn.description }}</p>
                </td>
                <td class="hidden px-4 py-3 sm:table-cell">
                  <Badge v-if="txn.category_name" size="sm">{{ txn.category_name }}</Badge>
                  <span v-else class="text-[12px] text-ink-subtle">Uncategorised</span>
                </td>
                <td class="hidden px-4 py-3 text-ink-muted md:table-cell">{{ txn.account_name || "—" }}</td>
                <td class="whitespace-nowrap px-4 py-3 text-right font-medium tabular"
                  :style="{ color: txn.txn_type === 'income' ? 'var(--good-ink)' : 'var(--ink)' }">
                  {{ txn.txn_type === "income" ? "+" : txn.txn_type === "expense" ? "−" : "" }}{{ money0(txn.amount) }}
                </td>
                <td class="whitespace-nowrap px-4 py-3 text-right">
                  <button type="button" class="rounded p-1 text-ink-subtle hover:text-ink" aria-label="Edit" @click="openEdit(txn)">
                    <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none"><path d="M4 20h4L19 9l-4-4L4 16v4Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" /></svg>
                  </button>
                  <button type="button" class="rounded p-1 text-ink-subtle hover:text-[color:var(--critical-ink)]" aria-label="Delete" @click="remove(txn.id)">
                    <svg class="h-4 w-4" viewBox="0 0 24 24" fill="none"><path d="M5 7h14M9 7V5h6v2m-8 0 1 13h8l1-13" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" /></svg>
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="page.total > LIMIT" class="flex items-center justify-between border-t border-line px-4 py-3">
          <p class="text-[12px] text-ink-muted">
            {{ offset + 1 }}–{{ Math.min(offset + LIMIT, page.total) }} of {{ page.total }}
          </p>
          <div class="flex gap-2">
            <Button variant="secondary" size="sm" :disabled="offset === 0" @click="offset = Math.max(0, offset - LIMIT)">
              Previous
            </Button>
            <Button variant="secondary" size="sm" :disabled="offset + LIMIT >= page.total" @click="offset += LIMIT">
              Next
            </Button>
          </div>
        </div>
      </Card>

      <EmptyState
        v-else
        :title="hasFilters ? 'No transactions match those filters' : 'No transactions yet'"
        :description="hasFilters
          ? 'Try widening the date range or clearing the search.'
          : 'Log what you spend and earn, and Bearly will use real figures instead of your profile estimates.'"
      >
        <Button v-if="!hasFilters" @click="openNew">Add your first transaction</Button>
      </EmptyState>
    </PageState>

    <Dialog v-model:open="dialogOpen" :title="form.id ? 'Edit transaction' : 'Add transaction'">
      <form class="space-y-4" @submit.prevent="save">
        <p v-if="formError" class="text-[13px] text-[color:var(--critical-ink)]">{{ formError }}</p>

        <div class="grid gap-4 sm:grid-cols-2">
          <Select
            v-model="form.txn_type" label="Type"
            :options="[{ value: 'expense', label: 'Expense' }, { value: 'income', label: 'Income' }, { value: 'transfer', label: 'Transfer' }]"
          />
          <Input v-model="form.occurred_on" label="Date" type="date" required />
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
          <Input v-model="form.amount" label="Amount" money required placeholder="0.00" />
          <Input v-model="form.merchant" label="Merchant or description" required placeholder="e.g. Whole Foods" />
        </div>

        <div class="grid gap-4 sm:grid-cols-2">
          <Select v-model="form.category_id" label="Category" placeholder="Uncategorised" :options="categoryOptions" />
          <Select v-model="form.account_id" label="Account" placeholder="None" :options="accountOptions" />
        </div>

        <Select
          v-if="form.txn_type === 'transfer'" v-model="form.transfer_account_id"
          label="Transfer to" placeholder="Choose an account" :options="accountOptions"
        />

        <Input v-model="form.notes" label="Notes" placeholder="Optional" />
      </form>

      <template #footer>
        <Button variant="ghost" @click="dialogOpen = false">Cancel</Button>
        <Button :loading="saving" @click="save">{{ form.id ? "Save changes" : "Add transaction" }}</Button>
      </template>
    </Dialog>
  </div>
</template>
