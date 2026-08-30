import type { Bilingual } from '../tree/types';

/**
 * The eight red-flag observation codes, taken VERBATIM from
 * backend/config/red_flags.yaml. These are
 * clinical config, not code — do not rename or add to this list without
 * updating that file too, or `redFlagsFired[]` sent on submit stops
 * meaning anything to the band engine (world.py sets
 * human_assigned_band = RED off exactly these strings).
 */
export interface RedFlagDef {
  id: string; // RF-01 .. RF-08, matches the YAML
  observation: string; // the code sent on submit — matches the YAML `observation` field
  description: Bilingual;
}

export const RED_FLAGS: RedFlagDef[] = [
  {
    id: 'RF-01',
    observation: 'altered_consciousness',
    description: { en: 'Altered consciousness / not responding', hi: 'चेतना में बदलाव / प्रतिक्रिया न देना' },
  },
  {
    id: 'RF-02',
    observation: 'active_labour_or_bleeding_pregnancy',
    description: { en: 'Active labour, or bleeding in pregnancy', hi: 'सक्रिय प्रसव, या गर्भावस्था में रक्तस्राव' },
  },
  {
    id: 'RF-03',
    observation: 'chest_pain_with_sweating_radiation_breathlessness',
    description: { en: 'Chest pain with sweating, radiation, or breathlessness', hi: 'सीने में दर्द के साथ पसीना, फैलाव, या सांस फूलना' },
  },
  {
    id: 'RF-04',
    observation: 'difficulty_speaking_full_sentences',
    description: { en: 'Difficulty speaking in full sentences', hi: 'पूरे वाक्य में बोलने में कठिनाई' },
  },
  {
    id: 'RF-05',
    observation: 'sudden_onesided_weakness_facial_droop_speech_change',
    description: { en: 'Sudden one-sided weakness, facial droop, or speech change', hi: 'अचानक एक तरफ कमजोरी, चेहरे का लटकना, या बोली में बदलाव' },
  },
  {
    id: 'RF-06',
    observation: 'uncontrolled_bleeding_or_penetrating_injury',
    description: { en: 'Uncontrolled bleeding, or penetrating injury', hi: 'अनियंत्रित रक्तस्राव, या गहरी चोट' },
  },
  {
    id: 'RF-07',
    observation: 'poisoning_overdose_or_snakebite',
    description: { en: 'Poisoning, overdose, or snakebite', hi: 'जहर, ओवरडोज, या सांप का काटना' },
  },
  {
    id: 'RF-08',
    observation: 'infant_not_feeding_floppy_inconsolable',
    description: { en: 'Infant not feeding, floppy, or inconsolable', hi: 'शिशु दूध नहीं ले रहा, ढीला, या लगातार रो रहा' },
  },
];

export function redFlagByObservation(code: string): RedFlagDef | undefined {
  return RED_FLAGS.find((f) => f.observation === code);
}
