import type { AnswerKind, Lang, Question } from '../tree/types';
import { t } from '../strings';

/**
 * What SHAPE of answer a question is asking for.
 *
 * The five `AnswerKind`s are a rendering distinction — slider vs buttons
 * vs textarea. This is the voice distinction, and the two do not line up:
 * `number` and `scale_0_10` render completely differently but are the
 * same problem to listen for, while `yes_no` and `choice` both render as
 * buttons but need different things said aloud.
 *
 * Before this existed the voice layer only special-cased `choice` (read
 * the options) and `yes_no` (say "yes, or no?"). Numeric questions fell
 * through to the generic path, so the kiosk read the pain question aloud
 * and then simply waited — never telling the patient that a number was
 * what it wanted, and never showing the number it thought it heard.
 */
export type AnswerMode = 'numeric' | 'binary' | 'choice' | 'open';

export function answerModeFor(kind: AnswerKind): AnswerMode {
  switch (kind) {
    case 'number':
    case 'scale_0_10':
      return 'numeric';
    case 'yes_no':
      return 'binary';
    case 'choice':
      return 'choice';
    case 'free_text':
    default:
      return 'open';
  }
}

export function isNumeric(question: Question | null | undefined): boolean {
  return !!question && answerModeFor(question.kind) === 'numeric';
}

/**
 * The inclusive bounds a numeric answer must fall inside. A scale is
 * always 0–10 by definition; an open number uses its declared range and
 * falls back to a human lifespan.
 */
export function numericRange(question: Question): [number, number] {
  if (question.kind === 'scale_0_10') return [0, 10];
  return question.numberRange ?? [0, 120];
}

/**
 * The prompt plus whatever the patient needs to hear to answer it — the
 * options for a choice, "yes or no" for a binary, and for a numeric the
 * fact that a number is wanted and which numbers are allowed.
 *
 * Shared by Conversation and useVoiceAnswer so the two cannot drift; they
 * previously each built this string inline and only Conversation was ever
 * updated.
 */
export function buildSpokenPrompt(question: Question, lang: Lang): string {
  const base = t(lang, question.prompt);
  const mode = answerModeFor(question.kind);

  if (mode === 'choice' && question.options?.length) {
    const joiner = lang === 'hi' ? ', या ' : ', or ';
    const list = question.options.map((o) => t(lang, o.label)).join(joiner);
    return `${base} ${list}${lang === 'hi' ? '. कौन सा?' : '. Which one?'}`;
  }

  if (mode === 'binary') {
    return base + (lang === 'hi' ? ' हां, या नहीं?' : ' Yes, or no?');
  }

  if (mode === 'numeric') {
    const [min, max] = numericRange(question);
    return base + (lang === 'hi'
      ? ` ${min} से ${max} के बीच कोई संख्या बोलें।`
      : ` Say a number between ${min} and ${max}.`);
  }

  return base;
}
