<script setup lang="ts">
import { computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import AppPageHeader from "@/components/AppPageHeader.vue";
import WebhooksPanel from "@/components/integrations/WebhooksPanel.vue";
import MqttPanel from "@/components/integrations/MqttPanel.vue";
import WyomingPanel from "@/components/integrations/WyomingPanel.vue";
import McpPanel from "@/components/integrations/McpPanel.vue";

const route = useRoute();
const router = useRouter();

const cards = [
  {
    id: "webhooks",
    title: "Webhooks",
    sentence: "Send a message to Home Assistant, Node-RED, or any web address when something is recognized.",
  },
  {
    id: "mqtt",
    title: "MQTT",
    sentence: "Publish matches to a message broker so other devices can react.",
  },
  {
    id: "wyoming",
    title: "Wyoming",
    sentence: "Home Assistant Assist uses this to hear who is speaking.",
  },
  {
    id: "mcp",
    title: "MCP",
    sentence: "Let an AI assistant call OpenRecognition with an API key. MCP is a tool protocol for those assistants.",
  },
] as const;

type Tab = (typeof cards)[number]["id"];
const validTabs: Tab[] = cards.map((card) => card.id);

const activeTab = computed<Tab>({
  get() {
    const t = route.params.tab as string | undefined;
    return validTabs.includes(t as Tab) ? (t as Tab) : "webhooks";
  },
  set(tab: Tab) {
    router.replace({ name: "integrations", params: { tab } });
  },
});

watch(
  () => route.params.tab,
  (tab) => {
    if (tab && !validTabs.includes(tab as Tab)) {
      router.replace({ name: "integrations", params: { tab: "webhooks" } });
    }
  },
  { immediate: true },
);
</script>

<template>
  <div class="integrations-page">
    <AppPageHeader
      title="Connections"
      description="Tell other apps when someone or something is recognized."
    />

    <div class="or-card-grid">
      <button
        v-for="card in cards"
        :key="card.id"
        type="button"
        class="or-choice-card"
        :class="{ 'is-selected': activeTab === card.id }"
        @click="activeTab = card.id"
      >
        <span class="or-choice-card__title">{{ card.title }}</span>
        <span class="or-choice-card__desc">{{ card.sentence }}</span>
      </button>
    </div>

    <section class="connection-panel">
      <WebhooksPanel v-if="activeTab === 'webhooks'" />
      <MqttPanel v-else-if="activeTab === 'mqtt'" />
      <WyomingPanel v-else-if="activeTab === 'wyoming'" />
      <McpPanel v-else />
    </section>
  </div>
</template>

<style scoped>
.integrations-page {
  display: flex;
  flex-direction: column;
  gap: var(--or-section-gap);
}

.integrations-page :deep(.app-page-header) {
  margin-bottom: 0;
}

.connection-panel {
  display: flex;
  flex-direction: column;
}
</style>
