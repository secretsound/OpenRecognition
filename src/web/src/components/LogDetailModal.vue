<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { NButton, NIcon, NModal, NTag, NTimeline, NTimelineItem } from "naive-ui";
import { ChevronBackOutline, ChevronForwardOutline } from "@vicons/ionicons5";
import type { RecognitionLogOut } from "@/types/api";
import SegmentedControl from "@/components/kit/SegmentedControl.vue";
import {
  activityBlurb,
  enrollmentTarget,
  eventHeading,
  processEvents,
  storyMeta,
  storySteps,
  storyTitle,
  technicalRows,
} from "@/utils/activityStory";

const show = defineModel<boolean>("show", { required: true });

const props = defineProps<{
  logs: RecognitionLogOut[] | null;
}>();

const router = useRouter();

const entries = computed(() => props.logs ?? []);
const title = computed(() => storyTitle(entries.value));
const meta = computed(() => storyMeta(entries.value));
const steps = computed(() => storySteps(entries.value));
const practice = computed(() => entries.value.some((log) => log.dry_run));
const targetId = computed(() => enrollmentTarget(entries.value));
const tab = ref<"story" | "technical">("story");
const techIndex = ref(0);
const tabOptions = [
  { value: "story" as const, label: "What happened" },
  { value: "technical" as const, label: "Technical details" },
];
const techLog = computed(() => entries.value[techIndex.value] ?? entries.value[0] ?? null);
const techQuote = computed(() => (techLog.value ? activityBlurb(techLog.value) : ""));

watch(
  () => entries.value.map((log) => log.id).join("|"),
  () => {
    tab.value = "story";
    techIndex.value = 0;
  },
);

function stepTech(delta: number) {
  const next = techIndex.value + delta;
  if (next < 0 || next >= entries.value.length) return;
  techIndex.value = next;
}

function openEnrollment() {
  if (!targetId.value) return;
  show.value = false;
  void router.push(`/enrollments/${targetId.value}`);
}
</script>

<template>
  <NModal
    v-model:show="show"
    preset="card"
    :title="title"
    class="log-detail-modal or-modal"
    :mask-closable="true"
  >
    <template v-if="entries.length">
      <div class="log-meta">
        <span>{{ meta }}</span>
        <NTag v-if="practice" size="small" :bordered="false" round class="log-meta__tag">Practice</NTag>
      </div>

      <SegmentedControl v-model="tab" class="log-tabs" aria-label="Event details" :options="tabOptions" />

      <NTimeline v-if="tab === 'story'" class="log-timeline" size="medium">
        <NTimelineItem
          v-for="step in steps"
          :key="step.key"
          :type="step.type"
          :title="step.title"
          :time="step.time"
        >
          <ul v-if="step.people?.length" class="log-people">
            <li
              v-for="person in step.people"
              :key="person.label"
              :class="person.passed ? 'is-pass' : 'is-fail'"
            >
              <span class="log-people__name">{{ person.label }}</span>
              <span class="log-people__score">
                {{ person.score }}
                <template v-if="person.bar"> · bar {{ person.bar }}</template>
              </span>
              <span class="log-people__status">{{ person.passed ? "Passed" : "Below" }}</span>
            </li>
          </ul>
          <p
            v-for="(line, index) in step.lines"
            :key="`${step.key}-${index}`"
            :class="step.quote ? 'log-quote' : 'log-line'"
          >
            {{ line }}
          </p>
        </NTimelineItem>
      </NTimeline>

      <div v-else-if="techLog" class="log-tech">
        <div v-if="entries.length > 1" class="log-pager">
          <NButton
            quaternary
            circle
            aria-label="Previous command"
            :disabled="techIndex === 0"
            @click="stepTech(-1)"
          >
            <template #icon>
              <NIcon><ChevronBackOutline /></NIcon>
            </template>
          </NButton>
          <div class="log-pager__copy">
            <span class="log-pager__count">{{ techIndex + 1 }} of {{ entries.length }}</span>
            <span v-if="techQuote && techQuote !== '—'" class="log-pager__quote">{{ techQuote }}</span>
          </div>
          <NButton
            quaternary
            circle
            aria-label="Next command"
            :disabled="techIndex >= entries.length - 1"
            @click="stepTech(1)"
          >
            <template #icon>
              <NIcon><ChevronForwardOutline /></NIcon>
            </template>
          </NButton>
        </div>

        <section>
          <h4 class="log-tech-heading">{{ eventHeading(techLog) }}</h4>
          <div v-for="event in processEvents(techLog)" :key="event.key" class="log-block">
            <h5>{{ event.title }}</h5>
            <p v-for="(line, index) in event.lines" :key="`${event.key}-${index}`">{{ line }}</p>
          </div>
          <div class="log-block log-block--quiet">
            <h5>Record</h5>
            <dl class="log-tech-list">
              <div v-for="row in technicalRows(techLog)" :key="`${techLog.id}-${row.label}`">
                <dt>{{ row.label }}</dt>
                <dd>{{ row.value }}</dd>
              </div>
            </dl>
          </div>
        </section>
      </div>

      <div v-if="targetId" class="log-actions">
        <NButton type="primary" secondary @click="openEnrollment">Open enrollment</NButton>
      </div>
    </template>
  </NModal>
</template>

<style scoped>
.log-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin: 0 0 18px;
  color: var(--n-text-color-3);
  font-size: 0.8125rem;
  line-height: 1.4;
}

.log-meta__tag {
  margin-left: 2px;
}

.log-tabs {
  margin-bottom: 16px;
}

.log-timeline {
  margin-top: 2px;
}

.log-line,
.log-quote {
  margin: 0;
  line-height: 1.45;
}

.log-line {
  color: var(--n-text-color-2);
  font-size: 0.875rem;
}

.log-line + .log-line,
.log-quote + .log-quote {
  margin-top: 4px;
}

.log-quote {
  font-size: 0.975rem;
}

.log-people {
  list-style: none;
  margin: 2px 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: max-content max-content max-content;
  column-gap: 12px;
  row-gap: 8px;
  justify-content: start;
  width: max-content;
  max-width: 100%;
}

.log-people li {
  display: contents;
}

.log-people__name {
  font-weight: 600;
}

.log-people__score {
  color: var(--n-text-color-2);
  font-size: 0.8125rem;
  font-variant-numeric: tabular-nums;
}

.log-people__status {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.log-people .is-pass .log-people__status {
  color: var(--n-success-color, #63e2b7);
}

.log-people .is-fail .log-people__status {
  color: var(--n-text-color-3);
}

.log-tech {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.log-pager {
  display: grid;
  grid-template-columns: auto 1fr auto;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}

.log-pager__copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  text-align: center;
}

.log-pager__count {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--n-text-color-3);
}

.log-pager__quote {
  max-width: 100%;
  font-size: 0.9375rem;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.log-tech-heading {
  margin: 0 0 4px;
  font-size: 0.9375rem;
  font-weight: 600;
}

.log-block {
  padding: 12px 0;
  border-top: 1px solid var(--n-border-color);
}

.log-block h5 {
  margin: 0 0 6px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--n-text-color-3);
}

.log-block p {
  margin: 0;
  font-size: 0.9375rem;
  line-height: 1.5;
}

.log-block p + p {
  margin-top: 2px;
}

.log-block--quiet {
  padding-bottom: 0;
}

.log-tech-list {
  display: grid;
  gap: 8px;
  margin: 0;
}

.log-tech-list div {
  display: grid;
  grid-template-columns: 6.5rem 1fr;
  gap: 12px;
  align-items: baseline;
}

.log-tech-list dt,
.log-tech-list dd {
  margin: 0;
  font-size: 0.8125rem;
  line-height: 1.45;
}

.log-tech-list dt {
  color: var(--n-text-color-3);
}

.log-tech-list dd {
  word-break: break-word;
}

.log-actions {
  margin-top: 16px;
}
</style>
