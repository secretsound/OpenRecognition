<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { NButton, NIcon, NSkeleton, NTag } from "naive-ui";
import { AddOutline, CameraOutline, LinkOutline } from "@vicons/ionicons5";
import { api, loadFailureMessage } from "@/api/client";
import AppPageHeader from "@/components/AppPageHeader.vue";
import EmptyState from "@/components/EmptyState.vue";
import StatusPill from "@/components/StatusPill.vue";
import TypeTag from "@/components/TypeTag.vue";
import type { EnrollmentOut, RecognitionLogListOut, RecognitionLogOut } from "@/types/api";
import { needsAttention } from "@/utils/enrollmentStatus";
import { formatLogEvent } from "@/utils/logEvent";

const router = useRouter();
const loading = ref(true);
const loadError = ref<string | null>(null);
const enrollments = ref<EnrollmentOut[]>([]);
const activity = ref<RecognitionLogOut[]>([]);

const attention = computed(() => enrollments.value.filter(needsAttention).slice(0, 5));

onMounted(async () => {
  loading.value = true;
  loadError.value = null;
  try {
    const [people, logs] = await Promise.all([
      api<EnrollmentOut[]>("/v1/enrollments"),
      api<RecognitionLogListOut>("/v1/admin/logs?limit=5&offset=0").catch(() => null),
    ]);
    enrollments.value = people;
    activity.value = logs?.items ?? [];
  } catch (e) {
    loadError.value = loadFailureMessage(e, "Couldn't load the home page");
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <div class="home">
    <AppPageHeader
      title="Home"
      description="Enroll people, pets, objects, and sounds, then try a match to see who or what was recognized."
    >
      <template #action>
        <NButton type="primary" @click="router.push('/enrollments/new')">
          <template #icon>
            <NIcon><AddOutline /></NIcon>
          </template>
          Add someone or something
        </NButton>
      </template>
    </AppPageHeader>

    <NSkeleton v-if="loading" text :repeat="6" />
    <EmptyState
      v-else-if="loadError"
      title="Couldn't load home"
      :description="loadError"
      action-label="Retry"
      @action="router.go(0)"
    />
    <template v-else>
      <div class="or-card-grid">
        <button type="button" class="or-choice-card" @click="router.push('/enrollments/new')">
          <span class="or-choice-card__title">Add someone or something</span>
          <span class="or-choice-card__desc">
            Start with a person, pet, object, or sound. Guided capture walks you through samples.
          </span>
        </button>
        <button type="button" class="or-choice-card" @click="router.push('/test')">
          <NIcon :size="18"><CameraOutline /></NIcon>
          <span class="or-choice-card__title">Try a photo or clip</span>
          <span class="or-choice-card__desc">
            Upload or record media and see the closest match. Practice runs do not notify Connections.
          </span>
        </button>
        <button
          type="button"
          class="or-choice-card"
          @click="router.push({ name: 'integrations', params: { tab: 'wyoming' } })"
        >
          <NIcon :size="18"><LinkOutline /></NIcon>
          <span class="or-choice-card__title">Connect Home Assistant</span>
          <span class="or-choice-card__desc">
            Wyoming lets Assist hear who is speaking. Webhooks and MQTT are on the same page.
          </span>
        </button>
      </div>

      <EmptyState
        v-if="enrollments.length === 0"
        title="Nothing enrolled yet"
        description="Add a person, pet, object, or sound. You can try a match after the first samples are in."
        action-label="Add someone or something"
        @action="router.push('/enrollments/new')"
      />

      <section v-else class="home-section">
        <h2 class="home-section__title">Needs attention</h2>
        <p v-if="attention.length === 0" class="home-empty">
          Everything enrolled is ready to match.
        </p>
        <div v-else class="or-list-cards home-list">
          <button
            v-for="row in attention"
            :key="row.id"
            type="button"
            class="or-list-card"
            @click="router.push(`/enrollments/${row.id}`)"
          >
            <span class="or-list-card__title">{{ row.label }}</span>
            <span class="or-list-card__meta">
              <TypeTag :type="row.type" />
              <StatusPill :enrollment="row" />
              <span>{{ row.sample_count }} samples</span>
            </span>
          </button>
        </div>
      </section>

      <section v-if="activity.length" class="home-section">
        <div class="home-section__head">
          <h2 class="home-section__title">Recent activity</h2>
          <NButton text type="primary" @click="router.push('/logs')">View all</NButton>
        </div>
        <ul class="activity">
          <li v-for="row in activity" :key="row.id" class="activity__row">
            <span class="activity__event">{{ formatLogEvent(row.event) }}</span>
            <span class="activity__label">{{ row.label || row.summary || "—" }}</span>
            <NTag v-if="row.dry_run" size="small" round :bordered="false">Practice</NTag>
            <time class="activity__time">{{ new Date(row.created_at).toLocaleString() }}</time>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  gap: var(--or-section-gap);
}

.home :deep(.app-page-header) {
  margin-bottom: 0;
}

.home-section {
  display: flex;
  flex-direction: column;
  gap: var(--or-inline-gap);
}

.home-section__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.home-section__title {
  margin: 0;
  font-size: 1rem;
  font-weight: 600;
}

.home-empty {
  margin: 0;
  color: var(--n-text-color-3);
  font-size: 0.9rem;
}

.home-list {
  display: flex;
}

.activity {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--or-line, var(--n-border-color));
  border-radius: var(--or-radius);
  background: var(--or-surface, var(--n-color));
}

.activity__row {
  display: grid;
  grid-template-columns: minmax(120px, 180px) 1fr auto auto;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border-top: 1px solid var(--or-line, var(--n-border-color));
}

.activity__row:first-child {
  border-top: none;
}

.activity__event {
  font-weight: 600;
}

.activity__label {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--n-text-color-2);
}

.activity__time {
  color: var(--n-text-color-3);
  font-size: 0.8125rem;
}

@media (max-width: 768px) {
  .activity__row {
    grid-template-columns: 1fr auto;
  }

  .activity__time {
    grid-column: 1 / -1;
  }
}
</style>
