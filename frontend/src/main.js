import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "@/App.vue";
import { router } from "@/router";
import { setUnauthorizedHandler } from "@/lib/api";
import { useAuthStore } from "@/stores/auth";
import "@/style.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);

// A refresh failure anywhere in the app drops the session and returns to login.
setUnauthorizedHandler(() => {
  useAuthStore().clear();
  router.push({ name: "login" });
});

app.mount("#app");
