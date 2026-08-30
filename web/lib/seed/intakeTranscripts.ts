import type { IntakeAnswer } from '../api/types';

/**
 * Backfilled kiosk conversations for the P-01�P-20 corpus.
 *
 * The seeded patients pre-date the intake module, so they arrived on the
 * board with a chief complaint and nothing behind it � a nurse opening any
 * corpus card saw a one-line summary and no record of what was asked. These
 * transcripts fill that in.
 *
 * THREE RULES THEY FOLLOW, because a transcript that does not hold together
 * is worse than none at all:
 *
 *  1. **The questions are real.** Every id and prompt here is copied from
 *     the actual branch files in `intake/tree/branches/`. Nothing is
 *     invented, so a judge can walk from a card back to the tree and find
 *     the same question.
 *
 *  2. **The branch matches the complaint.** Chest pain runs the chestPain
 *     block, fever runs the fever block, and so on. A patient is never shown
 *     answering questions their presentation would not have reached.
 *
 *  3. **The answers agree with the band.** The safety questions in each
 *     branch are the ones that fire red flags. Where a corpus patient is
 *     YELLOW with no red-flag codes, their answers to those questions are
 *     the non-firing ones � otherwise the card would show a patient
 *     reporting a red-flag symptom next to an empty red-flag list.
 *
 * On (3) there are two judgement calls worth naming, because both are
 * clinical distinctions rather than fudges:
 *
 *  - **P-03** ("poor feeding since morning") answers *no* to "Has the child
 *    stopped feeding, or become unusually floppy or hard to wake?" � RF-08's
 *    threshold is *stopped* feeding plus floppy or inconsolable, which is a
 *    materially worse state than reduced feeding. That gap is exactly what
 *    the question is drawing.
 *  - **P-04** ("mildly confused", GCS 13) answers *yes* to "Are you fully
 *    awake and thinking clearly?" � RF-01 is altered consciousness, not mild
 *    disorientation, and she is oriented enough to complete the intake.
 *
 * If either patient is ever meant to arrive RED, change the answer here and
 * the red-flag codes together � not one without the other.
 */
export const INTAKE_TRANSCRIPTS: Record<string, { branch: string; answers: IntakeAnswer[] }> = {
  // -- P-01 � chest_pain � RED at the door, red-flag before the model ------
  'P-01': {
    branch: 'chest_pain',
    answers: [
      { id: 'chief_complaint', question: 'Tell me what�s wrong. Take your time.', answer: 'Very bad pain in my chest, it started while I was walking and I am sweating a lot' },
      { id: 'cp_onset',        question: 'When did the chest pain start?',        answer: 'within_hour' },
      { id: 'cp_quality',      question: 'What does the pain feel like?',          answer: 'pressure' },
      { id: 'cp_radiation',    question: 'Does the pain spread anywhere?',         answer: 'left_arm' },
      { id: 'cp_sweating',     question: 'Are you sweating, or were you sweating when it started?', answer: 'yes' },
      { id: 'cp_breathless',   question: 'Are you finding it hard to breathe?',    answer: 'yes' },
    ],
  },

  // -- P-02 � trauma � the negative control, Green that stays Green --------
  'P-02': {
    branch: 'trauma',
    answers: [
      { id: 'chief_complaint',          question: 'Tell me what�s wrong. Take your time.', answer: 'I cut my forearm on a metal sheet at work' },
      { id: 'tr_mechanism',             question: 'What happened?',                        answer: 'Caught my arm on the edge of a metal sheet' },
      { id: 'tr_when',                  question: 'When did it happen?',                   answer: 'just_now' },
      { id: 'tr_bleeding_uncontrolled', question: 'Is there bleeding that will not stop?', answer: 'no' },
      { id: 'tr_lost_consciousness',    question: 'Did you black out, even for a moment?', answer: 'no' },
      { id: 'tr_head_neck_back',        question: 'Was your head, neck or back hurt?',     answer: 'no' },
      { id: 'tr_can_move',              question: 'Can you move the injured part normally?', answer: 'yes' },
      { id: 'meds_taken',               question: 'Have you taken any medicine for this? Which one?', answer: 'none' },
      { id: 'allergies',                question: 'Are you allergic to any medicine?',     answer: 'none' },
      { id: 'can_walk',                 question: 'Are you able to walk right now?',       answer: 'yes' },
      { id: 'pain_score',               question: 'On a scale of 0 to 10, how bad is the pain?', answer: '3' },
    ],
  },

  // -- P-03 � fever � paediatric half of the age pair (see note above) -----
  'P-03': {
    branch: 'fever',
    answers: [
      { id: 'chief_complaint',   question: 'Tell me what�s wrong. Take your time.', answer: 'My son has had a fever since last night and he is breathing fast and not eating properly' },
      { id: 'fv_duration',       question: 'How long have you had the fever?',       answer: 'today' },
      { id: 'fv_highest',        question: 'How high has it been, if you checked?',  answer: '38.5 at home this morning' },
      { id: 'fv_rigors',         question: 'Have you had shivering or chills with it?', answer: 'yes' },
      { id: 'fv_rash',           question: 'Any rash on the skin?',                  answer: 'no' },
      { id: 'fv_alert',          question: 'Are you fully awake and thinking clearly?', answer: 'yes' },
      { id: 'fv_poor_feeding',   question: 'Has the child stopped feeding, or become unusually floppy or hard to wake?', answer: 'no' },
      { id: 'meds_taken',        question: 'Have you taken any medicine for this? Which one?', answer: 'paracetamol syrup at 6am' },
      { id: 'allergies',         question: 'Are you allergic to any medicine?',      answer: 'none that we know of' },
      { id: 'prior_episode',     question: 'Has this happened to you before?',       answer: 'no' },
    ],
  },

  // -- P-04 � fever � geriatric half. Same 38.5, different reasoning -------
  'P-04': {
    branch: 'fever',
    answers: [
      { id: 'chief_complaint', question: 'Tell me what�s wrong. Take your time.', answer: 'I have had a fever for two days and I feel muddled, not myself' },
      { id: 'fv_duration',     question: 'How long have you had the fever?',       answer: 'few_days' },
      { id: 'fv_highest',      question: 'How high has it been, if you checked?',  answer: '38.5 last night' },
      { id: 'fv_rigors',       question: 'Have you had shivering or chills with it?', answer: 'no' },
      { id: 'fv_rash',         question: 'Any rash on the skin?',                  answer: 'no' },
      { id: 'fv_alert',        question: 'Are you fully awake and thinking clearly?', answer: 'yes' },
      { id: 'meds_taken',      question: 'Have you taken any medicine for this? Which one?', answer: 'paracetamol, and my usual blood pressure tablet' },
      { id: 'allergies',       question: 'Are you allergic to any medicine?',      answer: 'none' },
      { id: 'prior_episode',   question: 'Has this happened to you before?',       answer: 'no' },
      { id: 'can_walk',        question: 'Are you able to walk right now?',        answer: 'yes' },
    ],
  },

  // -- P-05 � chest_pain � THE HERO. Deliberately unremarkable at intake ---
  'P-05': {
    branch: 'chest_pain',
    answers: [
      { id: 'chief_complaint', question: 'Tell me what�s wrong. Take your time.', answer: 'Some discomfort in my chest since this morning, probably just acidity' },
      { id: 'cp_onset',        question: 'When did the chest pain start?',        answer: 'today' },
      { id: 'cp_quality',      question: 'What does the pain feel like?',          answer: 'burning' },
      { id: 'cp_radiation',    question: 'Does the pain spread anywhere?',         answer: 'stays_chest' },
      { id: 'cp_sweating',     question: 'Are you sweating, or were you sweating when it started?', answer: 'no' },
      { id: 'cp_breathless',   question: 'Are you finding it hard to breathe?',    answer: 'no' },
      { id: 'cp_exertion',     question: 'Did it start while you were doing something physical?', answer: 'no' },
      { id: 'meds_taken',      question: 'Have you taken any medicine for this? Which one?', answer: 'an antacid at home, it did not help much' },
      { id: 'allergies',       question: 'Are you allergic to any medicine?',      answer: 'none' },
      { id: 'prior_episode',   question: 'Has this happened to you before?',       answer: 'yes' },
      { id: 'can_walk',        question: 'Are you able to walk right now?',        answer: 'yes' },
      { id: 'pain_score',      question: 'On a scale of 0 to 10, how bad is the pain?', answer: '3' },
    ],
  },

  // -- P-06 � other � atypical sepsis, no localising signs -----------------
  'P-06': {
    branch: 'other',
    answers: [
      { id: 'chief_complaint',     question: 'Tell me what�s wrong. Take your time.', answer: 'My father has been confused since yesterday and very sleepy, he has no fever' },
      { id: 'other_location',      question: 'Where exactly do you feel it?',         answer: 'Nowhere in particular � he is just not himself' },
      { id: 'other_severity',      question: 'How would you describe it?',            answer: 'moderate' },
      { id: 'other_getting_worse', question: 'Is it getting worse?',                  answer: 'yes' },
      { id: 'other_alert',         question: 'Are you fully awake and thinking clearly?', answer: 'yes' },
      { id: 'other_breathing',     question: 'Can you speak a full sentence without stopping for breath?', answer: 'yes' },
      { id: 'meds_taken',          question: 'Have you taken any medicine for this? Which one?', answer: 'nothing new' },
      { id: 'prior_episode',       question: 'Has this happened to you before?',      answer: 'no' },
      { id: 'can_walk',            question: 'Are you able to walk right now?',       answer: 'no' },
    ],
  },

  // -- P-07 � abdominal � THE AMBIGUOUS ONE. Gastritis or inferior MI ------
  'P-07': {
    branch: 'abdominal_pain',
    answers: [
      { id: 'chief_complaint',   question: 'Tell me what�s wrong. Take your time.', answer: 'Burning pain at the top of my stomach and I feel sick' },
      { id: 'ab_location',       question: 'Where in the belly does it hurt most?',  answer: 'upper' },
      { id: 'ab_onset',          question: 'Did it come on suddenly, or build up slowly?', answer: 'gradual' },
      { id: 'ab_vomiting',       question: 'Have you been vomiting?',                answer: 'no' },
      { id: 'ab_chest_related',  question: 'Does it feel connected to your chest at all, or does it come with sweating or breathlessness?', answer: 'no' },
      { id: 'ab_rigid',          question: 'Is your belly hard or rigid when you press it?', answer: 'no' },
      { id: 'ab_blood',          question: 'Any blood in vomit or stool, or black stool?', answer: 'no' },
      { id: 'meds_taken',        question: 'Have you taken any medicine for this? Which one?', answer: 'antacid syrup last night' },
      { id: 'allergies',         question: 'Are you allergic to any medicine?',      answer: 'none' },
      { id: 'prior_episode',     question: 'Has this happened to you before?',       answer: 'yes' },
      { id: 'pain_score',        question: 'On a scale of 0 to 10, how bad is the pain?', answer: '6' },
    ],
  },

  // -- P-08 � breathing � pulse-oximeter bias case -------------------------
  'P-08': {
    branch: 'breathing',
    answers: [
      { id: 'chief_complaint', question: 'Tell me what�s wrong. Take your time.', answer: 'I cannot catch my breath properly, it has been getting worse today' },
      { id: 'br_onset',        question: 'When did the breathlessness start?',     answer: 'today' },
      { id: 'br_at_rest',      question: 'Is it hard to breathe even when you are sitting still?', answer: 'yes' },
      { id: 'br_chest_pain',   question: 'Do you have chest pain along with it?',  answer: 'no' },
      { id: 'br_wheeze',       question: 'Is your breathing noisy or wheezy?',     answer: 'yes' },
      { id: 'br_known_lung',   question: 'Do you have asthma or a known lung condition?', answer: 'no' },
      { id: 'meds_taken',      question: 'Have you taken any medicine for this? Which one?', answer: 'none' },
      { id: 'allergies',       question: 'Are you allergic to any medicine?',      answer: 'none' },
      { id: 'can_walk',        question: 'Are you able to walk right now?',        answer: 'yes' },
    ],
  },

  // -- P-09 � abdominal � freshness contract, vitals 3h old ----------------
  'P-09': {
    branch: 'abdominal_pain',
    answers: [
      { id: 'chief_complaint', question: 'Tell me what�s wrong. Take your time.', answer: 'Pain low down in my stomach since this morning' },
      { id: 'ab_location',     question: 'Where in the belly does it hurt most?',  answer: 'lower_right' },
      { id: 'ab_onset',        question: 'Did it come on suddenly, or build up slowly?', answer: 'gradual' },
      { id: 'ab_vomiting',     question: 'Have you been vomiting?',                answer: 'yes' },
      { id: 'ab_chest_related', question: 'Does it feel connected to your chest at all, or does it come with sweating or breathlessness?', answer: 'no' },
      { id: 'ab_rigid',        question: 'Is your belly hard or rigid when you press it?', answer: 'no' },
      { id: 'ab_blood',        question: 'Any blood in vomit or stool, or black stool?', answer: 'no' },
      { id: 'prior_episode',   question: 'Has this happened to you before?',       answer: 'no' },
      { id: 'pain_score',      question: 'On a scale of 0 to 10, how bad is the pain?', answer: '5' },
    ],
  },

  // -- P-10 � chest_pain � sensor-loss rule fires independently ------------
  'P-10': {
    branch: 'chest_pain',
    answers: [
      { id: 'chief_complaint', question: 'Tell me what�s wrong. Take your time.', answer: 'Tightness across my chest, comes and goes' },
      { id: 'cp_onset',        question: 'When did the chest pain start?',        answer: 'today' },
      { id: 'cp_quality',      question: 'What does the pain feel like?',          answer: 'tight_band' },
      { id: 'cp_radiation',    question: 'Does the pain spread anywhere?',         answer: 'stays_chest' },
      { id: 'cp_sweating',     question: 'Are you sweating, or were you sweating when it started?', answer: 'no' },
      { id: 'cp_breathless',   question: 'Are you finding it hard to breathe?',    answer: 'no' },
      { id: 'cp_exertion',     question: 'Did it start while you were doing something physical?', answer: 'yes' },
      { id: 'prior_episode',   question: 'Has this happened to you before?',       answer: 'yes' },
      { id: 'pain_score',      question: 'On a scale of 0 to 10, how bad is the pain?', answer: '4' },
    ],
  },

  // -- P-11 � neuro � ZERO HISTORY. No prior record, no ABHA link ----------
  'P-11': {
    branch: 'neuro',
    answers: [
      { id: 'chief_complaint',  question: 'Tell me what�s wrong. Take your time.', answer: 'Very bad headache, the light hurts my eyes and my neck feels stiff' },
      { id: 'nr_weakness_side', question: 'Is one side of your body weak, or does your face feel different on one side?', answer: 'no' },
      { id: 'nr_speech_change', question: 'Has your speech become slurred or hard to get out?', answer: 'no' },
      { id: 'nr_alert',         question: 'Are you fully awake and aware of where you are?', answer: 'yes' },
      { id: 'nr_seizure',       question: 'Did you have a fit or seizure?',        answer: 'no' },
      { id: 'meds_taken',       question: 'Have you taken any medicine for this? Which one?', answer: 'two paracetamol, no help' },
      { id: 'allergies',        question: 'Are you allergic to any medicine?',     answer: 'I do not know' },
      { id: 'prior_episode',    question: 'Has this happened to you before?',      answer: 'no' },
      { id: 'can_walk',         question: 'Are you able to walk right now?',       answer: 'yes' },
      { id: 'pain_score',       question: 'On a scale of 0 to 10, how bad is the pain?', answer: '8' },
    ],
  },

  // -- P-12 � chest_pain � the other half of the 50/50 history split -------
  'P-12': {
    branch: 'chest_pain',
    answers: [
      { id: 'chief_complaint', question: 'Tell me what�s wrong. Take your time.', answer: 'My chest pain is back again, I have heart disease and I take blood thinners' },
      { id: 'cp_onset',        question: 'When did the chest pain start?',        answer: 'today' },
      { id: 'cp_quality',      question: 'What does the pain feel like?',          answer: 'pressure' },
      { id: 'cp_radiation',    question: 'Does the pain spread anywhere?',         answer: 'stays_chest' },
      { id: 'cp_sweating',     question: 'Are you sweating, or were you sweating when it started?', answer: 'no' },
      { id: 'cp_breathless',   question: 'Are you finding it hard to breathe?',    answer: 'no' },
      { id: 'cp_exertion',     question: 'Did it start while you were doing something physical?', answer: 'no' },
      { id: 'meds_taken',      question: 'Have you taken any medicine for this? Which one?', answer: 'ecosprin and my heart tablets, and a sorbitrate under the tongue' },
      { id: 'allergies',       question: 'Are you allergic to any medicine?',      answer: 'none' },
      { id: 'prior_episode',   question: 'Has this happened to you before?',       answer: 'yes' },
      { id: 'pain_score',      question: 'On a scale of 0 to 10, how bad is the pain?', answer: '5' },
    ],
  },

  // -- P-13 � abdominal � communication barrier, answers are short ---------
  'P-13': {
    branch: 'abdominal_pain',
    answers: [
      { id: 'chief_complaint', question: 'Tell me what�s wrong. Take your time.', answer: '[through an attendant] Stomach swollen, pain' },
      { id: 'ab_location',     question: 'Where in the belly does it hurt most?',  answer: 'all_over' },
      { id: 'ab_onset',        question: 'Did it come on suddenly, or build up slowly?', answer: 'gradual' },
      { id: 'ab_vomiting',     question: 'Have you been vomiting?',                answer: 'no' },
      { id: 'ab_chest_related', question: 'Does it feel connected to your chest at all, or does it come with sweating or breathlessness?', answer: 'no' },
      { id: 'ab_rigid',        question: 'Is your belly hard or rigid when you press it?', answer: 'no' },
      { id: 'ab_blood',        question: 'Any blood in vomit or stool, or black stool?', answer: 'no' },
      { id: 'pain_score',      question: 'On a scale of 0 to 10, how bad is the pain?', answer: '5' },
    ],
  },

  // -- P-14 � abdominal � the override case. Kiosk missed the rigid abdomen
  'P-14': {
    branch: 'abdominal_pain',
    answers: [
      { id: 'chief_complaint', question: 'Tell me what�s wrong. Take your time.', answer: 'Stomach pain, it has been worse since this morning' },
      { id: 'ab_location',     question: 'Where in the belly does it hurt most?',  answer: 'all_over' },
      { id: 'ab_onset',        question: 'Did it come on suddenly, or build up slowly?', answer: 'gradual' },
      { id: 'ab_vomiting',     question: 'Have you been vomiting?',                answer: 'yes' },
      { id: 'ab_chest_related', question: 'Does it feel connected to your chest at all, or does it come with sweating or breathlessness?', answer: 'no' },
      // The kiosk asked. The patient said no. The nurse then palpated the
      // abdomen and found otherwise -- which is the entire point of P-14 and
      // the reason the override exists.
      { id: 'ab_rigid',        question: 'Is your belly hard or rigid when you press it?', answer: 'no' },
      { id: 'ab_blood',        question: 'Any blood in vomit or stool, or black stool?', answer: 'no' },
      { id: 'meds_taken',      question: 'Have you taken any medicine for this? Which one?', answer: 'none' },
      { id: 'prior_episode',   question: 'Has this happened to you before?',       answer: 'no' },
      { id: 'pain_score',      question: 'On a scale of 0 to 10, how bad is the pain?', answer: '7' },
    ],
  },

  // -- P-15 � other � the OOD case. Nothing here maps cleanly --------------
  'P-15': {
    branch: 'other',
    answers: [
      { id: 'chief_complaint',     question: 'Tell me what�s wrong. Take your time.', answer: 'I feel strange all over, my skin is crawling and my vision keeps shimmering' },
      { id: 'other_location',      question: 'Where exactly do you feel it?',         answer: 'Everywhere, it moves around' },
      { id: 'other_severity',      question: 'How would you describe it?',            answer: 'severe' },
      { id: 'other_getting_worse', question: 'Is it getting worse?',                  answer: 'yes' },
      { id: 'other_alert',         question: 'Are you fully awake and thinking clearly?', answer: 'yes' },
      { id: 'other_breathing',     question: 'Can you speak a full sentence without stopping for breath?', answer: 'yes' },
      { id: 'meds_taken',          question: 'Have you taken any medicine for this? Which one?', answer: 'none' },
      { id: 'allergies',           question: 'Are you allergic to any medicine?',     answer: 'none' },
      { id: 'prior_episode',       question: 'Has this happened to you before?',      answer: 'no' },
      { id: 'pain_score',          question: 'On a scale of 0 to 10, how bad is the pain?', answer: '4' },
    ],
  },

  // -- P-16 � unaccompanied and unresponsive. There is no conversation. ----
  // Deliberately absent from this map: nobody answered anything. The card
  // shows the empty state, which is the honest record for a patient found
  // unresponsive with no ID. Inventing answers here would be the one place
  // a fabricated transcript actually misleads.

  // -- P-17 � other � declines to share history. Consent gate. -------------
  'P-17': {
    branch: 'other',
    answers: [
      { id: 'chief_complaint',     question: 'Tell me what�s wrong. Take your time.', answer: 'My heart is racing and I feel very anxious' },
      { id: 'other_location',      question: 'Where exactly do you feel it?',         answer: 'In my chest, like fluttering' },
      { id: 'other_severity',      question: 'How would you describe it?',            answer: 'moderate' },
      { id: 'other_getting_worse', question: 'Is it getting worse?',                  answer: 'no' },
      { id: 'other_alert',         question: 'Are you fully awake and thinking clearly?', answer: 'yes' },
      { id: 'other_breathing',     question: 'Can you speak a full sentence without stopping for breath?', answer: 'yes' },
      // Consent to use the medical record was declined, so the history
      // questions were still ASKED and simply not answered. Recording the
      // refusal is not the same as recording a risk factor -- see
      // DESIGN_SYSTEM.md section 8, "consent must never be rendered as risk".
      { id: 'meds_taken',          question: 'Have you taken any medicine for this? Which one?', answer: 'declined to say' },
      { id: 'prior_episode',       question: 'Has this happened to you before?',      answer: 'declined to say' },
    ],
  },

  // -- P-18 � obstetric � RED on narrative alone, vitals unremarkable ------
  'P-18': {
    branch: 'obstetric',
    answers: [
      { id: 'chief_complaint',  question: 'Tell me what�s wrong. Take your time.', answer: 'The baby is coming, the pains are close together now' },
      { id: 'ob_weeks',         question: 'How many weeks or months pregnant are you?', answer: '39 weeks' },
      { id: 'ob_contractions',  question: 'Are you having regular tightening or contractions?', answer: 'yes' },
      { id: 'ob_bleeding',      question: 'Is there any bleeding?',                answer: 'no' },
      { id: 'ob_waters',        question: 'Have your waters broken?',              answer: 'yes' },
    ],
  },

  // -- P-19 � other � the stoic. Self-report and physiology disagree -------
  'P-19': {
    branch: 'other',
    answers: [
      { id: 'chief_complaint',     question: 'Tell me what�s wrong. Take your time.', answer: 'My family made me come. I am fine, it is nothing' },
      { id: 'other_location',      question: 'Where exactly do you feel it',          answer: 'Nowhere really' },
      { id: 'other_severity',      question: 'How would you describe it?',            answer: 'mild' },
      { id: 'other_getting_worse', question: 'Is it getting worse?',                  answer: 'no' },
      { id: 'other_alert',         question: 'Are you fully awake and thinking clearly?', answer: 'yes' },
      { id: 'other_breathing',     question: 'Can you speak a full sentence without stopping for breath?', answer: 'yes' },
      { id: 'meds_taken',          question: 'Have you taken any medicine for this? Which one?', answer: 'nothing' },
      { id: 'prior_episode',       question: 'Has this happened to you before?',      answer: 'no' },
      { id: 'can_walk',            question: 'Are you able to walk right now?',       answer: 'yes' },
      // The reassuring answer that the reliability weighting exists to
      // discount. It never lowers the alarming physiology beside it.
      { id: 'pain_score',          question: 'On a scale of 0 to 10, how bad is the pain?', answer: '1' },
    ],
  },

  // -- P-20 � trauma � Green, then two missed rechecks under load ----------
  'P-20': {
    branch: 'trauma',
    answers: [
      { id: 'chief_complaint',          question: 'Tell me what�s wrong. Take your time.', answer: 'I twisted my ankle coming down the stairs' },
      { id: 'tr_mechanism',             question: 'What happened?',                        answer: 'Missed the last step and went over on my ankle' },
      { id: 'tr_when',                  question: 'When did it happen?',                   answer: 'today' },
      { id: 'tr_bleeding_uncontrolled', question: 'Is there bleeding that will not stop?', answer: 'no' },
      { id: 'tr_lost_consciousness',    question: 'Did you black out, even for a moment?', answer: 'no' },
      { id: 'tr_head_neck_back',        question: 'Was your head, neck or back hurt?',     answer: 'no' },
      { id: 'tr_can_move',              question: 'Can you move the injured part normally?', answer: 'no' },
      { id: 'meds_taken',               question: 'Have you taken any medicine for this? Which one?', answer: 'an ibuprofen at home' },
      { id: 'allergies',                question: 'Are you allergic to any medicine?',     answer: 'none' },
      { id: 'can_walk',                 question: 'Are you able to walk right now?',       answer: 'no' },
      { id: 'pain_score',               question: 'On a scale of 0 to 10, how bad is the pain?', answer: '4' },
    ],
  },
};
