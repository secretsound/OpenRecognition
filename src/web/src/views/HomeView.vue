<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { NButton, NIcon } from "naive-ui";
import { AddOutline, CheckmarkCircleOutline } from "@vicons/ionicons5";
import { api, loadFailureMessage } from "@/api/client";
import type { ConsoleOverviewOut, EnrollmentOut, PresenceEntry, RecognitionLogOut } from "@/types/api";
import PageHeader from "@/components/kit/PageHeader.vue";
import ProfileMark from "@/components/kit/ProfileMark.vue";
import TimeAgo from "@/components/kit/TimeAgo.vue";
import ContentSkeleton from "@/components/kit/ContentSkeleton.vue";
import Chip from "@/components/kit/Chip.vue";
import EmptyState from "@/components/EmptyState.vue";
import StatusPill from "@/components/StatusPill.vue";
import TypeTag from "@/components/TypeTag.vue";
import { verdictFromLog } from "@/utils/verdict";
import { canWrite } from "@/utils/roles";
import { useAuth } from "@/composables/useAuth";
import { useEventStream } from "@/composables/useEventStream";

const router = useRouter();
const { role } = useAuth();
const loading = ref(true);
const loadError = ref<string | null>(null);
const enrollments = ref<EnrollmentOut[]>([]);
const activity = ref<RecognitionLogOut[]>([]);
const attention = ref<EnrollmentOut[]>([]);
const readyCount = ref(0);
const modelsReady = ref(false);
const models = ref<Record<string, string>>({});
const wyomingOn = ref(false);
const webhookCount = ref(0);
const hasRecognition = ref(false);
const lastSeen = ref<PresenceEntry | null>(null);

const setup = computed(() => {
  const hasModels = modelsReady.value || Object.keys(models.value).length > 0;
  const hasProfile = enrollments.value.length > 0;
  const hasTest = hasRecognition.value;
  const hasConnection = wyomingOn.value || webhookCount.value > 0;
  return [
    {
      id: "models",
      title: "Download models for this machine",
      done: hasModels,
      to: "/models",
    },
    {
      id: "profile",
      title: "Add your first profile",
      done: hasProfile,
      to: "/enrollments/new",
    },
    {
      id: "recognize",
      title: "Recognize something",
      done: hasTest,
      to: "/test",
    },
    {
      id: "connect",
      title: "Connect Home Assistant or a webhook",
      done: hasConnection,
      to: "/integrations/wyoming",
    },
  ];
});

const setupOpen = computed(() => setup.value.some((s) => !s.done));

function applyOverview(data: ConsoleOverviewOut) {
  enrollments.value = data.enrollments;
  attention.value = data.attention;
  readyCount.value = data.ready_count;
  activity.value = data.recent_activity;
  lastSeen.value = data.last_seen;
  modelsReady.value = data.models_ready;
  models.value = data.models;
  wyomingOn.value = data.wyoming_enabled;
  webhookCount.value = data.webhook_count;
  hasRecognition.value = data.has_recognition;
}

async function load() {
  loading.value = true;
  loadError.value = null;
  try {
    applyOverview(await api<ConsoleOverviewOut>("/v1/console/overview"));
  } catch (e) {
    loadError.value = loadFailureMessage(e, "Couldn't load the home page");
  } finally {
    loading.value = false;
  }
}

useEventStream((event) => {
  const log = event.log;
  if (!log || event.type !== "recognition.log") return;
  activity.value = [log, ...activity.value.filter((row) => row.id !== log.id)].slice(0, 8);
  if (log.event.startsWith("recognition.") || log.dry_run) {
    hasRecognition.value = true;
  }
  if (log.event === "recognition.match" && !log.dry_run && log.entity_id && log.label) {
    lastSeen.value = {
      enrollment_id: log.entity_id,
      label: log.label,
      type: lastSeen.value?.enrollment_id === log.entity_id ? lastSeen.value.type : "person",
      last_seen_at: log.created_at,
      last_modality: log.modality ?? lastSeen.value?.last_modality ?? "audio",
      last_camera_id: log.camera_id,
      confidence: log.confidence,
    };
    const idx = enrollments.value.findIndex((row) => row.id === log.entity_id);
    if (idx >= 0) {
      const next = { ...enrollments.value[idx], last_seen_at: log.created_at };
      enrollments.value.splice(idx, 1, next);
    }
  }
});

onMounted(load);
</script>

<template>
  <div class="or-page">
    <PageHeader
      title="Overview"
      description="How this server is doing, and what needs a look."
    >
      <template v-if="canWrite(role)" #action>
        <NButton type="primary" @click="router.push('/enrollments/new')">
          <template #icon>
            <NIcon><AddOutline /></NIcon>
          </template>
          Add
        </NButton>
      </template>
    </PageHeader>

    <ContentSkeleton v-if="loading" variant="detail" />
    <EmptyState
      v-else-if="loadError"
      title="Couldn't load overview"
      :description="loadError"
      action-label="Retry"
      @action="load"
    />
    <template v-else>
      <section v-if="setupOpen" class="or-surface or-surface--md">
        <h2 class="or-heading">Get started</h2>
        <p class="or-muted or-small" style="margin-top: 6px">
          Four steps. Each one unlocks the next thing this server is good at.
        </p>
        <ol class="setup-list">
          <li v-for="step in setup" :key="step.id">
            <button type="button" class="setup-row" @click="router.push(step.to)">
              <NIcon
                :size="20"
                :class="step.done ? 'is-done' : 'is-todo'"
                :component="CheckmarkCircleOutline"
              />
              <span :class="{ 'is-done-label': step.done }">{{ step.title }}</span>
            </button>
          </li>
        </ol>
      </section>

      <div class="status-strip">
        <button type="button" class="status-tile" @click="router.push('/models')">
          <span class="or-caps">Models</span>
          <strong>{{ modelsReady || Object.keys(models).length ? "Ready" : "Not downloaded" }}</strong>
        </button>
        <button type="button" class="status-tile" @click="router.push('/integrations/wyoming')">
          <span class="or-caps">Home Assistant</span>
          <strong>{{ wyomingOn ? "Connected" : "Off" }}</strong>
        </button>
        <button type="button" class="status-tile" @click="router.push('/enrollments')">
          <span class="or-caps">Library</span>
          <strong>{{ readyCount }} ready</strong>
          <span v-if="attention.length" class="or-muted or-small">{{ attention.length }} need a look</span>
        </button>
        <button
          type="button"
          class="status-tile"
          @click="router.push(lastSeen ? `/enrollments/${lastSeen.enrollment_id}` : '/logs')"
        >
          <span class="or-caps">Last seen</span>
          <strong v-if="lastSeen">{{ lastSeen.label }}</strong>
          <strong v-else>Nobody yet</strong>
          <TimeAgo v-if="lastSeen" :value="lastSeen.last_seen_at" />
        </button>
      </div>

      <section v-if="enrollments.length === 0">
        <EmptyState
          title="Nothing enrolled yet"
          description="Add a person, pet, object, or sound. You can recognize them after the first samples are in."
          action-label="Add"
          @action="router.push('/enrollments/new')"
        />
      </section>

      <section v-else-if="attention.length" class="or-stack">
        <h2 class="or-heading">Needs attention</h2>
        <button
          v-for="row in attention"
          :key="row.id"
          type="button"
          class="or-list-card person-row"
          @click="router.push(`/enrollments/${row.id}`)"
        >
          <span class="person-row__who">
            <ProfileMark :label="row.label" :type="row.type" />
            <span class="or-list-card__title">{{ row.label }}</span>
          </span>
          <span class="or-list-card__meta">
            <TypeTag :type="row.type" />
            <StatusPill :enrollment="row" />
            <span>{{ row.sample_count }} samples</span>
          </span>
        </button>
      </section>

      <section v-if="activity.length" class="or-stack">
        <div class="section-head">
          <h2 class="or-heading">Recent activity</h2>
          <NButton text type="primary" @click="router.push('/logs')">View all</NButton>
        </div>
        <ul class="activity">
          <li v-for="row in activity" :key="row.id">
            <button type="button" class="activity__row" @click="router.push('/logs')">
              <ProfileMark :label="row.label || 'Event'" size="sm" />
              <span class="activity__copy">
                <span>{{ verdictFromLog(row).sentence }}</span>
                <span class="activity__meta">
                  <Chip v-if="row.dry_run">Practice</Chip>
                  <TimeAgo :value="row.created_at" />
                </span>
              </span>
            </button>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<style scoped>
.setup-list {
  list-style: none;
  margin: 16px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.setup-row {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 8px 0;
  border: 0;
  background: none;
  color: inherit;
  font: inherit;
  cursor: pointer;
  text-align: left;
}

.is-done {
  color: var(--or-success);
}

.is-todo {
  color: var(--or-text-3);
}

.is-done-label {
  color: var(--or-text-3);
  text-decoration: line-through;
}

.status-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--or-space-3);
}

.status-tile {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
  padding: 16px 18px;
  border-radius: var(--or-radius-md);
  border: 1px solid var(--or-line);
  background: var(--or-surface);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.status-tile:hover {
  border-color: var(--or-accent);
}

.status-tile strong {
  font-size: var(--or-text-body);
  font-weight: 600;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.person-row__who {
  display: flex;
  align-items: center;
  gap: 10px;
}

.activity {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--or-line);
  border-radius: var(--or-radius-md);
  background: var(--or-surface);
}

.activity__row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  width: 100%;
  padding: 12px 14px;
  border: 0;
  border-top: 1px solid var(--or-line);
  background: none;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.activity li:first-child .activity__row {
  border-top: 0;
}

.activity__copy {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.activity__meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

@media (max-width: 899px) {
  .status-strip {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
