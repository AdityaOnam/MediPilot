import type { AgeStratum } from '../api/types';

export interface Question {
  id: string;
  label: { en: string; hi: string };
  kind: 'text' | 'yesno' | 'number' | 'options';
  options?: { value: string; label: { en: string; hi: string } }[];
  required?: boolean;
  /** Only ask this question for these strata. Omitted = ask for all. */
  strata?: AgeStratum[];
  unit?: string;
}

/**
 * Age-aware typed question tree. Order matters — each question is one
 * decision on one screen. Questions with a `strata` filter are only asked
 * for the resolved stratum.
 *
 * The `chief-complaint` text is what the red-flag pass sweeps over — that
 * is P-18's demonstration: unremarkable vitals plus a labour-related phrase
 * in the free text is enough to fire the interrupt.
 */
export const QUESTION_TREE: Question[] = [
  {
    id: 'chief-complaint',
    label: { en: "What brought you here today?", hi: 'आज आप यहाँ किस वजह से आए हैं?' },
    kind: 'text',
    required: true,
  },
  {
    id: 'onset',
    label: { en: 'When did it start?', hi: 'यह कब शुरू हुआ?' },
    kind: 'options',
    options: [
      { value: 'now',         label: { en: 'Just now',        hi: 'अभी अभी' } },
      { value: 'hours',       label: { en: 'A few hours ago', hi: 'कुछ घंटे पहले' } },
      { value: 'today',       label: { en: 'Earlier today',   hi: 'आज ही' } },
      { value: 'days',        label: { en: 'Days ago',        hi: 'कुछ दिन पहले' } },
      { value: 'weeks',       label: { en: 'A week or more',  hi: 'एक सप्ताह या अधिक' } },
    ],
  },
  {
    id: 'severity',
    label: { en: 'How severe does it feel?', hi: 'यह कितना गंभीर लगता है?' },
    kind: 'options',
    options: [
      { value: 'mild',    label: { en: 'Mild',        hi: 'हल्का' } },
      { value: 'medium',  label: { en: 'Moderate',    hi: 'मध्यम' } },
      { value: 'severe',  label: { en: 'Severe',      hi: 'गंभीर' } },
      { value: 'worst',   label: { en: 'Worst ever',  hi: 'अब तक का सबसे बुरा' } },
    ],
  },
  {
    id: 'peds-feeding',
    label: { en: 'Is the child feeding normally?', hi: 'क्या बच्चा सामान्य रूप से खा-पी रहा है?' },
    kind: 'yesno',
    strata: ['neonate', 'infant', 'child'],
  },
  {
    id: 'peds-alert',
    label: { en: 'Is the child alert and responsive?', hi: 'क्या बच्चा सजग और प्रतिक्रिया दे रहा है?' },
    kind: 'yesno',
    strata: ['neonate', 'infant', 'child'],
  },
  {
    id: 'geri-baseline',
    label: { en: 'Any change from usual baseline function?', hi: 'सामान्य स्थिति से कोई बदलाव?' },
    kind: 'yesno',
    strata: ['geriatric'],
  },
  {
    id: 'geri-falls',
    label: { en: 'Any recent falls?', hi: 'क्या हाल ही में गिरे हैं?' },
    kind: 'yesno',
    strata: ['geriatric'],
  },
  {
    id: 'meds',
    label: { en: 'On any medications right now?', hi: 'क्या आप अभी कोई दवा ले रहे हैं?' },
    kind: 'text',
  },
];

export function questionsFor(stratum: AgeStratum): Question[] {
  return QUESTION_TREE.filter(q => !q.strata || q.strata.includes(stratum));
}
