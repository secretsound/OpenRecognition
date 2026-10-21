import type { SelectOption } from "naive-ui";

/** Stored value sent as `species_hint` on the API. */
export const PET_SPECIES_OTHER = "other";

export const petSpeciesOptions: SelectOption[] = [
  { label: "Dog", value: "dog" },
  { label: "Cat", value: "cat" },
  { label: "Bird", value: "bird" },
  { label: "Rabbit", value: "rabbit" },
  { label: "Hamster / rodent", value: "hamster" },
  { label: "Fish", value: "fish" },
  { label: "Reptile", value: "reptile" },
  { label: "Horse", value: "horse" },
  { label: "Other", value: PET_SPECIES_OTHER },
];

export function formatSpeciesHint(value: string): string {
  const opt = petSpeciesOptions.find((o) => o.value === value);
  if (opt && value !== PET_SPECIES_OTHER) return String(opt.label);
  return value;
}
