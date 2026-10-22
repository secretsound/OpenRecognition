/**
 * Phonetically rich enrollment sentences for speaker ID.
 * Core set is first; later sessions pull unused lines so extra training
 * actually covers new sounds instead of repeating the same six clips.
 *
 * Each prompt also has a delivery so the profile hears more than one
 * “reading” voice — the small pitch and pace shifts people use with a
 * voice assistant day to day.
 */
export const VOICE_PHRASE_BANK = [
  "The quick brown fox jumps over the lazy dog near the wide riverbank.",
  "She sells seashells where the soft waves wash against the shore.",
  "Three hundred forty-seven callers registered before noon on Tuesday.",
  "Please say my name clearly so this server can learn how I sound.",
  "Those thick books thought through the path beneath the wooden booth.",
  "I usually drink coffee in the morning and tea later in the day.",
  "Open the front door, walk down the hallway, and turn on the lights.",
  "My voice should sound the same whether I am close or across the room.",
  "Every extra sample helps the model tell me apart from people nearby.",
  "Count with me: one, two, three, four, five, six, seven, eight, nine, ten.",
  "The weather today is bright, a little windy, and not too cold outside.",
  "Can you hear the difference between this sentence and the last one?",
  "I left the keys on the kitchen table next to the yellow envelope.",
  "We measured fifty-six minutes and twelve seconds on the old clock.",
  "Bring a larger bag if you are carrying jackets, shoes, and umbrellas.",
  "That garage door rattles whenever a truck drives past the house.",
  "Remember to speak at a normal pace, not whispered and not shouted.",
  "The library is quiet except for pages turning and chairs sliding back.",
  "Please repeat this after me: north, south, east, west, home again.",
  "A good recording is four to six seconds of clear, natural speech.",
  "Yesterday I walked to the store, bought bread, and came straight back.",
  "This phrase uses v, th, sh, and z so the model hears more of my voice.",
  "If someone else is talking nearby, wait a moment and then try again.",
  "Thank you for taking the time to teach this server who I am.",
  "My phone number is not important, but please listen to how I say numbers.",
  "Red trucks, blue bikes, and gray vans lined up along the busy street.",
  "Would you rather sit by the window or closer to the kitchen door?",
  "The engineer measured voltage, current, and resistance before switching on.",
  "I enjoy jazz, classical piano, and the occasional folk song on Friday.",
  "Put the groceries away: milk, oranges, cereal, and a loaf of rye bread.",
  "Sorry, I missed that. Could you say it one more time, a little slower?",
  "There are thirty-two rooms on the fifth floor of the west building.",
  "A sudden gust of wind knocked the papers off the porch this afternoon.",
  "Please leave a message after the tone and I will call you back tonight.",
  "We should meet at half past seven near the fountain in the town square.",
  "This is my ordinary speaking voice, the one I use on a normal day.",
  "Turn on the kitchen lights and tell me the weather for this afternoon.",
  "Set a timer for ten minutes and play something quiet in the living room.",
  "What's on my calendar today, and remind me to take the trash out later.",
  "Lock the front door, then dim the hallway lights to thirty percent.",
] as const;

export const VOICE_CORE_COUNT = 8;
export const VOICE_IMPROVE_COUNT = 6;

/** First training session — kept as a named alias for older imports. */
export const VOICE_ENROLLMENT_PHRASES = VOICE_PHRASE_BANK.slice(0, VOICE_CORE_COUNT);

export const SOUND_ENROLLMENT_PHRASES = [
  "Record this sound clearly, about five seconds.",
  "Capture the same sound again from a similar distance.",
  "One more sample with a little variation in timing.",
  "Hold for a few extra seconds so the clip is not too short.",
  "Record once more with a small change in position.",
] as const;

export type VoiceSessionMode = "core" | "improve" | "encore";

export type VoiceDelivery = "natural" | "assistant" | "soft" | "low" | "bright" | "across_room";

export interface VoicePrompt {
  text: string;
  delivery: VoiceDelivery;
}

export const VOICE_DELIVERY_COACH: Record<VoiceDelivery, { title: string; hint: string }> = {
  natural: {
    title: "Normal speaking voice",
    hint: "Read it the way you talk to a person in the same room.",
  },
  assistant: {
    title: "Speaker on the table",
    hint: "Talk to it the way you would a Google Home or phone next to you — close, casual, not projected.",
  },
  soft: {
    title: "A bit quieter",
    hint: "Same words, slightly softer — like the mic is already right beside you.",
  },
  low: {
    title: "A little lower",
    hint: "Drop your pitch slightly. Stay natural — no whisper and no cartoon voice.",
  },
  bright: {
    title: "A little more awake",
    hint: "Raise your pitch a little, as if you just walked in the room. Keep it your voice.",
  },
  across_room: {
    title: "Calling across the room",
    hint: "Project like you are talking to an Alexa in the kitchen — farther away, a bit louder. Do not scream into the mic.",
  },
};

const CORE_DELIVERIES: VoiceDelivery[] = [
  "natural",
  "natural",
  "natural",
  "assistant",
  "soft",
  "low",
  "bright",
  "across_room",
];

const IMPROVE_DELIVERIES: VoiceDelivery[] = [
  "assistant",
  "across_room",
  "low",
  "bright",
  "soft",
  "assistant",
];

function normalizePhrase(text: string): string {
  return text.trim().replace(/\s+/g, " ").toLowerCase();
}

function withDeliveries(texts: readonly string[], mode: VoiceSessionMode): VoicePrompt[] {
  const table = mode === "core" ? CORE_DELIVERIES : IMPROVE_DELIVERIES;
  return texts.map((text, i) => ({
    text,
    delivery: table[i % table.length] ?? "natural",
  }));
}

export function pickVoicePhrases(usedTexts: string[]): {
  phrases: VoicePrompt[];
  mode: VoiceSessionMode;
} {
  const used = new Set(usedTexts.map(normalizePhrase).filter(Boolean));
  const unused = VOICE_PHRASE_BANK.filter((p) => !used.has(normalizePhrase(p)));
  if (used.size < VOICE_CORE_COUNT) {
    return { phrases: withDeliveries(unused.slice(0, VOICE_CORE_COUNT), "core"), mode: "core" };
  }
  if (unused.length > 0) {
    return {
      phrases: withDeliveries(unused.slice(0, VOICE_IMPROVE_COUNT), "improve"),
      mode: "improve",
    };
  }
  return {
    phrases: withDeliveries(VOICE_PHRASE_BANK.slice(0, VOICE_IMPROVE_COUNT), "encore"),
    mode: "encore",
  };
}

export function soundPrompts(): VoicePrompt[] {
  return SOUND_ENROLLMENT_PHRASES.map((text) => ({ text, delivery: "natural" as const }));
}
