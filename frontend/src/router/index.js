import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const routes = [
  { path: "/login", name: "login", component: () => import("@/views/LoginView.vue"), meta: { public: true, layout: "auth" } },
  { path: "/register", name: "register", component: () => import("@/views/RegisterView.vue"), meta: { public: true, layout: "auth" } },
  { path: "/forgot-password", name: "forgot-password", component: () => import("@/views/ForgotPasswordView.vue"), meta: { public: true, layout: "auth" } },
  { path: "/reset-password", name: "reset-password", component: () => import("@/views/ResetPasswordView.vue"), meta: { public: true, layout: "auth" } },

  { path: "/welcome", name: "onboarding", component: () => import("@/views/OnboardingView.vue"), meta: { layout: "bare" } },

  { path: "/", name: "dashboard", component: () => import("@/views/DashboardView.vue"), meta: { title: "Dashboard" } },
  { path: "/budget", name: "budget", component: () => import("@/views/BudgetView.vue"), meta: { title: "Budget" } },
  { path: "/expenses", name: "expenses", component: () => import("@/views/ExpensesView.vue"), meta: { title: "Expenses" } },
  { path: "/debt", name: "debt", component: () => import("@/views/DebtView.vue"), meta: { title: "Debt" } },
  { path: "/savings", name: "savings", component: () => import("@/views/SavingsView.vue"), meta: { title: "Savings" } },
  { path: "/investments", name: "investments", component: () => import("@/views/InvestmentsView.vue"), meta: { title: "Investments" } },
  { path: "/coach", name: "coach", component: () => import("@/views/CoachView.vue"), meta: { title: "Bearly AI" } },
  { path: "/settings", name: "settings", component: () => import("@/views/SettingsView.vue"), meta: { title: "Settings" } },

  { path: "/:pathMatch(.*)*", name: "not-found", component: () => import("@/views/NotFoundView.vue") },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!auth.ready) await auth.restore();

  if (!to.meta.public && !auth.isAuthenticated) {
    return { name: "login", query: to.fullPath !== "/" ? { next: to.fullPath } : undefined };
  }
  if (to.meta.public && auth.isAuthenticated) {
    return { name: "dashboard" };
  }
  // Onboarding collects the figures every metric depends on, so it comes first.
  if (auth.isAuthenticated && auth.needsOnboarding && to.name !== "onboarding" && to.name !== "settings") {
    return { name: "onboarding" };
  }
  return true;
});

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · Bearly` : "Bearly";
});
