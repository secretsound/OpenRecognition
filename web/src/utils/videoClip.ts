export type VideoModalityChoice = "both" | "face" | "audio";

export interface VideoLimits {
  recommended_sec: [number, number];
  enrollment_max_sec: number;
  recognize_sync_max_sec: number;
  recognize_async_max_sec: number;
  max_upload_bytes: number;
}

export const DEFAULT_VIDEO_LIMITS: VideoLimits = {
  recommended_sec: [10, 30],
  enrollment_max_sec: 60,
  recognize_sync_max_sec: 120,
  recognize_async_max_sec: 300,
  max_upload_bytes: 100 * 1024 * 1024,
};

export const VIDEO_CODEC_UNSUPPORTED =
  "Your browser cannot decode the video track in this file (audio may still work). " +
  "For face/visual recognition, convert to H.264 MP4 or VP8/WebM — e.g. with ffmpeg: " +
  "ffmpeg -i input.mov -c:v libx264 -c:a aac output.mp4";

export function videoModalitiesParam(choice: VideoModalityChoice): string {
  if (choice === "both") return JSON.stringify(["face", "audio"]);
  if (choice === "face") return JSON.stringify(["face"]);
  return JSON.stringify(["audio"]);
}

export function formatDuration(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m > 0 ? `${m}:${s.toString().padStart(2, "0")}` : `${s}s`;
}

function waitForEvent(target: EventTarget, event: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const onOk = () => {
      cleanup();
      resolve();
    };
    const onErr = () => {
      cleanup();
      reject(new Error(`Video ${event} failed.`));
    };
    const cleanup = () => {
      target.removeEventListener(event, onOk);
      target.removeEventListener("error", onErr);
    };
    target.addEventListener(event, onOk, { once: true });
    target.addEventListener("error", onErr, { once: true });
  });
}

async function loadVideoElement(file: File): Promise<HTMLVideoElement> {
  const url = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.preload = "auto";
  video.playsInline = true;
  video.muted = true;
  video.src = url;
  try {
    await waitForEvent(video, "loadedmetadata");
    await waitForEvent(video, "loadeddata");
    return video;
  } catch (e) {
    URL.revokeObjectURL(url);
    video.removeAttribute("src");
    video.load();
    throw e;
  }
}

export async function loadVideoMetadata(file: File): Promise<{
  durationSec: number;
  width: number;
  height: number;
  hasVideoTrack: boolean;
}> {
  const video = await loadVideoElement(file);
  const url = video.src;
  try {
    if (video.videoWidth > 0) {
      video.currentTime = Math.min(0.05, Math.max(0, video.duration - 0.01));
      try {
        await waitForEvent(video, "seeked");
      } catch {
        /* first frame optional */
      }
    }
    return {
      durationSec: Number.isFinite(video.duration) ? video.duration : 0,
      width: video.videoWidth,
      height: video.videoHeight,
      hasVideoTrack: video.videoWidth > 0 && video.videoHeight > 0,
    };
  } finally {
    URL.revokeObjectURL(url);
    video.removeAttribute("src");
    video.load();
  }
}

function pickRecorderMimeType(): string {
  const candidates = [
    "video/webm;codecs=vp9,opus",
    "video/webm;codecs=vp8,opus",
    "video/webm",
    "video/mp4",
  ];
  for (const type of candidates) {
    if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }
  return "video/webm";
}

function assertVideoTrack(video: HTMLVideoElement) {
  if (video.videoWidth <= 0 || video.videoHeight <= 0) {
    throw new Error(VIDEO_CODEC_UNSUPPORTED);
  }
}

/** Draw the current video frame to a canvas (returns false if no decodable video). */
export function drawVideoFrame(
  video: HTMLVideoElement,
  canvas: HTMLCanvasElement,
): boolean {
  if (video.videoWidth <= 0 || video.videoHeight <= 0) return false;
  const w = video.videoWidth;
  const h = video.videoHeight;
  if (canvas.width !== w) canvas.width = w;
  if (canvas.height !== h) canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return false;
  ctx.drawImage(video, 0, 0, w, h);
  return true;
}

/** Extract [startSec, endSec) by playing through a canvas recorder (keeps video frames). */
export async function extractVideoClip(
  file: File,
  startSec: number,
  endSec: number,
): Promise<Blob> {
  if (endSec <= startSec) {
    throw new Error("End time must be after start time.");
  }
  if (typeof MediaRecorder === "undefined") {
    throw new Error("Video trimming is not supported in this browser.");
  }

  const video = await loadVideoElement(file);
  const url = video.src;

  try {
    assertVideoTrack(video);

    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) throw new Error("Could not initialize video canvas.");

    const mimeType = pickRecorderMimeType();
    const outStream = canvas.captureStream(30);
    const srcStream = (
      video as HTMLVideoElement & { captureStream?: () => MediaStream }
    ).captureStream?.();
    if (srcStream) {
      for (const track of srcStream.getAudioTracks()) {
        outStream.addTrack(track);
      }
    }

    const chunks: BlobPart[] = [];
    const recorder = new MediaRecorder(outStream, { mimeType });
    const blobReady = new Promise<Blob>((resolve, reject) => {
      recorder.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunks.push(ev.data);
      };
      recorder.onstop = () => {
        outStream.getTracks().forEach((t) => t.stop());
        if (chunks.length === 0) {
          reject(new Error("Failed to extract video clip — no video frames captured."));
          return;
        }
        resolve(new Blob(chunks, { type: mimeType.split(";")[0] }));
      };
      recorder.onerror = () => reject(new Error("Recording failed while trimming video."));
    });

    video.currentTime = Math.max(0, startSec);
    await waitForEvent(video, "seeked");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    recorder.start(100);
    await video.play();

    await new Promise<void>((resolve) => {
      const deadline = performance.now() + (endSec - startSec) * 1000 + 800;

      const tick = () => {
        if (video.currentTime >= endSec - 0.05 || video.ended) {
          video.pause();
          if (recorder.state !== "inactive") recorder.stop();
          resolve();
          return;
        }
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        if (performance.now() >= deadline) {
          video.pause();
          if (recorder.state !== "inactive") recorder.stop();
          resolve();
          return;
        }
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });

    return await blobReady;
  } finally {
    video.pause();
    video.removeAttribute("src");
    video.load();
    URL.revokeObjectURL(url);
  }
}

export function clipFileFromBlob(blob: Blob, baseName: string): File {
  const ext = blob.type.includes("mp4") ? "mp4" : "webm";
  const safe = baseName.replace(/\.[^.]+$/, "");
  return new File([blob], `${safe}-clip.${ext}`, { type: blob.type || `video/${ext}` });
}

export function validateClipDuration(
  durationSec: number,
  maxSec: number,
  label = "Clip",
): string | null {
  if (durationSec <= 0) return `${label} must have a positive duration.`;
  if (durationSec > maxSec) {
    return `${label} is ${formatDuration(durationSec)} — maximum is ${formatDuration(maxSec)}.`;
  }
  return null;
}

export function validateClipSize(bytes: number, maxBytes: number): string | null {
  if (bytes > maxBytes) {
    const mb = (bytes / (1024 * 1024)).toFixed(1);
    const maxMb = (maxBytes / (1024 * 1024)).toFixed(0);
    return `Clip is ${mb} MB — maximum upload is ${maxMb} MB.`;
  }
  return null;
}
