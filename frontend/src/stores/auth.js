import { defineStore } from "pinia";
import { api, getRefreshToken, setAccessToken, setRefreshToken } from "@/lib/api";

export const useAuthStore = defineStore("auth", {
  state: () => ({
    user: null,
    onboarding: { has_profile: false, completed: false },
    ready: false,
    loading: false,
  }),
  getters: {
    isAuthenticated: (state) => state.user !== null,
    needsOnboarding: (state) => state.user !== null && !state.onboarding.completed,
    displayName: (state) => state.user?.full_name || state.user?.email?.split("@")[0] || "there",
    currency: (state) => state.user?.currency || "USD",
  },
  actions: {
    _storeTokens(tokens) {
      setAccessToken(tokens.access_token);
      setRefreshToken(tokens.refresh_token);
    },

    async register(payload) {
      this.loading = true;
      try {
        this._storeTokens(await api.post("/auth/register", payload));
        await this.loadSession();
      } finally {
        this.loading = false;
      }
    },

    async login(email, password) {
      this.loading = true;
      try {
        this._storeTokens(await api.post("/auth/login", { email, password }));
        await this.loadSession();
      } finally {
        this.loading = false;
      }
    },

    async logout() {
      const refresh = getRefreshToken();
      try {
        if (refresh) await api.post("/auth/logout", { refresh_token: refresh });
      } catch {
        /* logging out locally matters more than the server acknowledging it */
      }
      this.clear();
    },

    clear() {
      this.user = null;
      this.onboarding = { has_profile: false, completed: false };
      setAccessToken(null);
      setRefreshToken(null);
    },

    async loadSession() {
      this.user = await api.get("/auth/me");
      this.onboarding = await api.get("/profile/status");
      return this.user;
    },

    /** Called once at startup: restores a session from the stored refresh token. */
    async restore() {
      if (!getRefreshToken()) {
        this.ready = true;
        return;
      }
      try {
        const tokens = await api.post("/auth/refresh", {
          refresh_token: getRefreshToken(),
        });
        this._storeTokens(tokens);
        await this.loadSession();
      } catch {
        this.clear();
      } finally {
        this.ready = true;
      }
    },

    async updateProfile(payload) {
      this.user = await api.patch("/auth/me", payload);
    },

    async changePassword(current_password, new_password) {
      await api.post("/auth/change-password", { current_password, new_password });
    },

    async markOnboarded() {
      this.onboarding = await api.get("/profile/status");
    },
  },
});
