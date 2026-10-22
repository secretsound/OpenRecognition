<script setup lang="ts">
import { computed, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import PageHeader from "@/components/kit/PageHeader.vue";
import SegmentedControl from "@/components/kit/SegmentedControl.vue";
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
    sentence: "Connect to a broker — including username and password — and publish each match.",
  },
  {
    id: "wyoming",
    title: "Wyoming",
    sentence: "Home Assistant Assist connects here to hear who is speaking, then sends the audio to speech-to-text.",
  },
  {
    id: "mcp",
    title: "MCP",
    sentence: "Give Cursor, Claude, or another assistant a key so it can look up people and run a match.",
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
  <div class="or-page">
    <PageHeader
      title="Connections"
      description="Tell other apps when someone or something is recognized."
    />

    <p class="or-muted">{{ cards.find((c) => c.id === activeTab)?.sentence }}</p>
    <SegmentedControl
      v-model="activeTab"
      aria-label="Connections"
      :options="cards.map((c) => ({ value: c.id, label: c.title }))"
    />

    <section class="connection-panel">
      <WebhooksPanel v-if="activeTab === 'webhooks'" />
      <MqttPanel v-else-if="activeTab === 'mqtt'" />
      <WyomingPanel v-else-if="activeTab === 'wyoming'" />
      <McpPanel v-else />
    </section>
  </div>
</template>

<style scoped>
.connection-panel {
  display: flex;
  flex-direction: column;
}
</style>
