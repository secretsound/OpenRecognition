import { createApp } from "vue";
import "@fontsource-variable/inter";
import "./styles/global.css";
import App from "./App.vue";
import router from "./router";

createApp(App).use(router).mount("#app");
