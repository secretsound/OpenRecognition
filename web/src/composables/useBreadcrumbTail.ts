import { inject, onUnmounted, provide, ref, watch, type Ref } from "vue";

export interface AppBreadcrumb {
  label: string;
  to?: string;
}

const breadcrumbTailKey = Symbol("breadcrumbTail");
const breadcrumbOverrideKey = Symbol("breadcrumbOverride");

/** Replace header breadcrumbs entirely (e.g. Enrollments / Luke / Training). */
export function useBreadcrumbOverride(items: Ref<AppBreadcrumb[] | null | undefined>) {
  const override = inject<Ref<AppBreadcrumb[] | null> | undefined>(
    breadcrumbOverrideKey,
    undefined,
  );
  if (!override) return;

  const stop = watch(
    items,
    (v) => {
      override.value = v?.length ? v : null;
    },
    { immediate: true, deep: true },
  );

  onUnmounted(() => {
    stop();
    override.value = null;
  });
}

/** Override the last breadcrumb label (e.g. enrollment display name on detail). */
export function useBreadcrumbTail(label: Ref<string | undefined | null>) {
  const tail = inject<Ref<string | null> | undefined>(breadcrumbTailKey, undefined);
  if (!tail) return;

  const stop = watch(
    label,
    (v) => {
      tail.value = v?.trim() || null;
    },
    { immediate: true },
  );

  onUnmounted(() => {
    stop();
    tail.value = null;
  });
}

export function provideBreadcrumbTail() {
  const tail = ref<string | null>(null);
  const override = ref<AppBreadcrumb[] | null>(null);
  provide(breadcrumbTailKey, tail);
  provide(breadcrumbOverrideKey, override);
  return { tail, override };
}
