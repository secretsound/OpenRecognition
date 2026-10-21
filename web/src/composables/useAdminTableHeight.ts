import { onBeforeUnmount, onMounted, ref } from "vue";

/** Viewport-based height for admin list tables. Updates when the window resizes. */
export function useAdminTableHeight(offset = 280) {
  const height = ref(480);

  function measure() {
    height.value = Math.max(320, window.innerHeight - offset);
  }

  onMounted(() => {
    measure();
    window.addEventListener("resize", measure);
  });

  onBeforeUnmount(() => {
    window.removeEventListener("resize", measure);
  });

  return height;
}
