import type { Branch } from '../types';

/**
 * Deliberately includes the epigastric-pain ambiguity (gastritis vs.
 * inferior MI) that the demo corpus's P-07/case_id `ambiguous_epigastric_pain`
 * is built around — the deciding evidence is genuinely absent at this
 * stage, and this branch does not try to manufacture it.
 */
export const ABDOMINAL_BRANCH: Branch = {
  id: 'abdominal_pain',
  label: { en: 'Abdominal pain', hi: 'पेट में दर्द' },
  questions: [
    {
      id: 'ab_location',
      kind: 'choice',
      prompt: { en: 'Where in the belly does it hurt most?', hi: 'पेट में सबसे ज्यादा दर्द कहां है?' },
      options: [
        { value: 'upper', label: { en: 'Upper abdomen', hi: 'पेट के ऊपरी हिस्से में' } },
        { value: 'lower_right', label: { en: 'Lower right', hi: 'नीचे दाईं ओर' } },
        { value: 'lower_left', label: { en: 'Lower left', hi: 'नीचे बाईं ओर' } },
        { value: 'all_over', label: { en: 'All over', hi: 'पूरे पेट में' } },
      ],
    },
    {
      id: 'ab_onset',
      kind: 'choice',
      prompt: { en: 'Did it come on suddenly, or build up slowly?', hi: 'क्या यह अचानक शुरू हुआ, या धीरे धीरे बढ़ा?' },
      options: [
        { value: 'sudden', label: { en: 'Suddenly', hi: 'अचानक' } },
        { value: 'gradual', label: { en: 'Slowly', hi: 'धीरे धीरे' } },
      ],
    },
    {
      id: 'ab_vomiting',
      kind: 'yes_no',
      prompt: { en: 'Have you been vomiting?', hi: 'क्या आपको उल्टी हो रही है?' },
    },
    {
      id: 'ab_chest_related',
      kind: 'yes_no',
      prompt: { en: 'Does it feel connected to your chest at all, or does it come with sweating or breathlessness?', hi: 'क्या यह किसी तरह सीने से जुड़ा लगता है, या इसके साथ पसीना या सांस फूलना है?' },
      observes: ['chest_pain_with_sweating_radiation_breathlessness'],
    },
    {
      id: 'ab_rigid',
      kind: 'yes_no',
      prompt: { en: 'Is your belly hard or rigid when you press it?', hi: 'दबाने पर क्या पेट सख्त या कड़ा लगता है?' },
    },
    {
      id: 'ab_blood',
      kind: 'yes_no',
      prompt: { en: 'Any blood in vomit or stool, or black stool?', hi: 'क्या उल्टी या मल में खून है, या मल काला है?' },
      observes: ['uncontrolled_bleeding_or_penetrating_injury'],
    },
  ],
};
