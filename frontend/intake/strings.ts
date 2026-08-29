/**
 * Every user-facing string in the kiosk, in one place. Each entry is the
 * exact text both shown on screen AND spoken by TTS (Part 5 of the plan) —
 * a sighted and a non-sighted patient get the same information. Where the
 * spoken version must be shorter (consent legalese), a `*_spoken` sibling
 * key carries the plain-language reading; the screen still shows the full
 * text under `*`.
 */
import type { Bilingual } from './tree/types';

export const STR = {
  appName: { en: 'MediPilot', hi: 'मेडीपायलट' } as Bilingual,

  // ---- welcome --------------------------------------------------------
  welcomeGreeting: { en: 'Hello. I’m MediPilot.', hi: 'नमस्ते। मैं मेडीपायलट हूं।' } as Bilingual,
  welcomeSub: { en: 'I’ll ask a few questions and get you seen.', hi: 'मैं कुछ सवाल पूछूंगा और आपको जल्द देखे जाने की व्यवस्था करूंगा।' } as Bilingual,
  chooseLanguage: { en: 'Choose your language', hi: 'अपनी भाषा चुनें' } as Bilingual,
  langEnglish: { en: 'English', hi: 'English' } as Bilingual,
  langHindi: { en: 'हिंदी', hi: 'हिंदी' } as Bilingual,
  needHelp: { en: 'I need help using this', hi: 'मुझे इसे इस्तेमाल करने में मदद चाहिए' } as Bilingual,

  // ---- companion -------------------------------------------------------
  companionQ: { en: 'Is someone here with you?', hi: 'क्या कोई आपके साथ यहां है?' } as Bilingual,
  companionWith: { en: 'Yes, someone is with me', hi: 'हां, कोई मेरे साथ है' } as Bilingual,
  companionAlone: { en: 'I’m here alone', hi: 'मैं अकेला हूं' } as Bilingual,

  // ---- human offer -------------------------------------------------------
  humanOfferQ: { en: 'Would you rather talk to a person instead of me?', hi: 'क्या आप मेरे बजाय किसी इंसान से बात करना चाहेंगे?' } as Bilingual,
  humanOfferYes: { en: 'Yes, I’d like a person', hi: 'हां, मुझे किसी इंसान से बात करनी है' } as Bilingual,
  humanOfferNo: { en: 'No, let’s continue', hi: 'नहीं, चलते हैं' } as Bilingual,

  // ---- consent -------------------------------------------------------
  consentTitle: { en: 'Before we start', hi: 'शुरू करने से पहले' } as Bilingual,
  consentListenLabel: { en: 'Let MediPilot listen and fill in the form for you', hi: 'मेडीपायलट को सुनने और आपके लिए फॉर्म भरने दें' } as Bilingual,
  consentListenSpoken: { en: 'Can I listen to you and fill in your form?', hi: 'क्या मैं आपको सुन कर आपका फॉर्म भर सकता हूं?' } as Bilingual,
  consentRecordsLabel: { en: 'Let MediPilot use your health record to help the nurse', hi: 'नर्स की मदद के लिए मेडीपायलट को आपका स्वास्थ्य रिकॉर्ड देखने दें' } as Bilingual,
  consentRecordsSpoken: { en: 'Can I look at your past health records to help the nurse?', hi: 'क्या मैं नर्स की मदद के लिए आपके पुराने स्वास्थ्य रिकॉर्ड देख सकता हूं?' } as Bilingual,
  consentContinue: { en: 'Continue', hi: 'जारी रखें' } as Bilingual,

  // ---- basics -------------------------------------------------------
  basicsAgeQ: { en: 'How old are you?', hi: 'आपकी उम्र क्या है?' } as Bilingual,
  // Asked as gender, not sex. The wire field stays `sex` because that is
  // the shared backend contract, but nothing the patient reads says it.
  basicsSexQ: { en: 'What is your gender?', hi: 'आपका जेंडर क्या है?' } as Bilingual,
  sexMale: { en: 'Male', hi: 'पुरुष' } as Bilingual,
  sexFemale: { en: 'Female', hi: 'महिला' } as Bilingual,
  sexOther: { en: 'Other', hi: 'अन्य' } as Bilingual,

  // ---- conversation / opening question -------------------------------------------------------
  openingQ: { en: 'Tell me what’s wrong. Take your time.', hi: 'मुझे बताइए क्या तकलीफ है। आराम से बताइए।' } as Bilingual,

  // ---- pain -------------------------------------------------------
  painQ: { en: 'On a scale of 0 to 10, how bad is the pain?', hi: '0 से 10 के बीच, दर्द कितना है?' } as Bilingual,

  // ---- readback -------------------------------------------------------
  readbackTitle: { en: 'Here’s what I heard', hi: 'मैंने यह सुना' } as Bilingual,
  readbackConfirm: { en: 'That’s right', hi: 'यह सही है' } as Bilingual,
  readbackFix: { en: 'Fix something', hi: 'कुछ ठीक करें' } as Bilingual,

  // ---- token -------------------------------------------------------
  tokenIssued: { en: 'Token', hi: 'टोकन' } as Bilingual,
  tokenWatch: { en: 'Watch the board. If anything feels worse, press this.', hi: 'बोर्ड देखते रहें। अगर कुछ भी बदतर लगे, तो यह दबाएं।' } as Bilingual,
  feelWorse: { en: 'I feel worse', hi: 'मुझे ज्यादा खराब लग रहा है' } as Bilingual,

  // Counter step — shown between the token and the wait, when the
  // complaint owes measurements before it can be scored on more than words.
  counterGoTo: { en: 'Please go to', hi: 'कृपया यहां जाएं' } as Bilingual,
  counterWhy: {
    en: 'A staff member there will take these measurements:',
    hi: 'वहां एक स्टाफ सदस्य ये माप लेगा:',
  } as Bilingual,
  counterThen: {
    en: 'You are already in the queue. Taking these only makes your place more accurate.',
    hi: 'आप पहले से ही कतार में हैं। ये माप लेने से आपका स्थान और सटीक हो जाएगा।',
  } as Bilingual,

  // ---- human lane -------------------------------------------------------
  humanLaneTitle: { en: 'No problem. A person will take your details.', hi: 'कोई बात नहीं। कोई आपकी जानकारी लेगा।' } as Bilingual,
  humanLaneNote: { en: 'Your place in the queue is not affected.', hi: 'आपका क्रम प्रभावित नहीं होगा।' } as Bilingual,

  // ---- nurse call (red-flag interrupt) -------------------------------------------------------
  nurseCallTitle: { en: 'Let’s get someone to you right now.', hi: 'अभी किसी को आपके पास भेजते हैं।' } as Bilingual,
  nurseCalledAt: { en: 'A nurse was called at', hi: 'नर्स को बुलाया गया' } as Bilingual,

  // ---- common controls -------------------------------------------------------
  back: { en: 'Back', hi: 'वापस' } as Bilingual,
  continue: { en: 'Continue', hi: 'जारी रखें' } as Bilingual,
  typeInstead: { en: 'Type instead', hi: 'टाइप करें' } as Bilingual,
  tapToAnswer: { en: 'Tap to answer', hi: 'उत्तर देने के लिए टैप करें' } as Bilingual,
  listening: { en: 'Listening…', hi: 'सुन रहा हूं…' } as Bilingual,
  didntCatch: { en: 'I didn’t catch that. Could you say it again?', hi: 'मैं समझ नहीं पाया। क्या आप फिर से बोल सकते हैं?' } as Bilingual,
  pleasePickBelow: { en: 'Please pick one of the choices below.', hi: 'कृपया नीचे दिए गए विकल्पों में से एक चुनें।' } as Bilingual,
};

export function t(lang: 'en' | 'hi', s: Bilingual): string {
  return lang === 'hi' ? s.hi : s.en;
}
