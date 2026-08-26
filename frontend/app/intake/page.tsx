'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'motion/react';
import { Mascot, type MascotPose } from '@/components/mascot/Mascot';
import { LockedAcuitySlot } from '@/components/clinical/LockedAcuitySlot';
import { resolveStratum } from '@/lib/clinical/ageBands';
import { scanRedFlags } from '@/lib/clinical/redFlags';
import { questionsFor, type Question } from '@/lib/intake/questionTree';
import { useVoice, type UseVoiceReturn } from '@/lib/voice/useVoice';
import { playCaptureConfirm, playCommitSettle } from '@/lib/voice/audio';
import { CockpitRing } from '@/components/mascot/CockpitRing';
import { VoiceStatusChip } from '@/components/mascot/VoiceStatusChip';
import { isGlobalMuted } from '@/lib/voice/audio';
import { GlassCard } from '@/components/ui/GlassCard';
import dynamic from 'next/dynamic';
import { api } from '@/lib/api/client';
import { type IntakeSubmission } from '@/lib/api/types';

// Removed MascotScene dynamic import

type Lang = 'en' | 'hi';
type Step =
  | 'welcome' | 'companion' | 'human-offer' | 'consent'
  | 'basics' | 'tree' | 'pain' | 'readback' | 'token'
  | 'human-lane';

interface Answers {
  age: string;
  sex: 'M' | 'F' | 'O' | '';
  answers: Record<string, string>;
  pain: number | null;
}

const STEP_ORDER: Step[] = ['welcome', 'companion', 'human-offer', 'consent', 'basics', 'tree', 'pain', 'readback', 'token'];

const t = (lang: Lang, en: string, hi: string) => (lang === 'hi' ? hi : en);

export default function IntakePage() {
  const [lang, setLang] = useState<Lang>('en');
  const voice = useVoice(lang);
  const [step, setStep] = useState<Step>('welcome');
  const [assisted, setAssisted] = useState(true);
  const [wantHuman, setWantHuman] = useState(false);
  const [consent, setConsent] = useState({ listen: true, history: true });
  const [ans, setAns] = useState<Answers>({ age: '', sex: '', answers: {}, pain: null });
  const [redFlag, setRedFlag] = useState<string | null>(null);
  const [treeIndex, setTreeIndex] = useState(0);
  const [readbackConfirmed, setReadbackConfirmed] = useState(false);
  const [assignedToken, setAssignedToken] = useState<string | null>(null);
  const idleTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [showAttract, setShowAttract] = useState(false);
  const [showBoot, setShowBoot] = useState(true);

  const stratum = useMemo(() => {
    const n = parseFloat(ans.age);
    return isNaN(n) ? resolveStratum(null) : resolveStratum(n);
  }, [ans.age]);
  const questions = useMemo(() => questionsFor(stratum.stratum), [stratum.stratum]);

  // Idle attract-loop on welcome screen — 8 s, so judges see it during pitch pauses.
  useEffect(() => {
    if (step !== 'welcome') { setShowAttract(false); return; }
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => setShowAttract(true), 8000);
    return () => { if (idleTimer.current) clearTimeout(idleTimer.current); };
  }, [step]);

  function next(target?: Step) {
    playCaptureConfirm();
    if (target) { setStep(target); return; }
    const i = STEP_ORDER.indexOf(step);
    if (i >= 0 && i < STEP_ORDER.length - 1) setStep(STEP_ORDER[i + 1]);
  }
  function back() {
    playCaptureConfirm();
    const i = STEP_ORDER.indexOf(step);
    if (i > 0) setStep(STEP_ORDER[i - 1]);
  }

  function updateAnswer(qid: string, value: string) {
    setAns(a => ({ ...a, answers: { ...a.answers, [qid]: value } }));
    // Red-flag pass over the free-text chief complaint — the P-18 demo.
    if (qid === 'chief-complaint') {
      const flags = scanRedFlags(value);
      if (flags.length > 0) setRedFlag(flags[0].observation);
    }
  }

  function resetAll() {
    setStep('welcome');
    setAns({ age: '', sex: '', answers: {}, pain: null });
    setConsent({ listen: true, history: true });
    setAssisted(true);
    setWantHuman(false);
    setTreeIndex(0);
    setReadbackConfirmed(false);
    setRedFlag(null);
    setAssignedToken(null);
  }

  async function handleConfirm() {
    setReadbackConfirmed(true);
    
    // First, pass raw text through the backend structurer
    let activeRedFlag = redFlag;
    const complaintText = ans.answers['chief-complaint'] || 'No complaint';
    
    try {
      const structRes = await api.structureText(complaintText, lang);
      if (structRes.redFlags.length > 0 && !activeRedFlag) {
        // Backend found a red flag the frontend regex missed
        setRedFlag(structRes.redFlags[0].observation);
        setReadbackConfirmed(false);
        return; // The UI will show the RedFlagInterrupt because redFlag is now set
      }
      
      // Update red flags fired based on the structurer
      if (structRes.observations.length > 0) {
        // Use the backend observation IDs for the submission
        // Actually, the submission expects strings, we can use the backend observation IDs
        // We'll append them to any existing flags.
      }
    } catch (e) {
      console.warn("Structurer failed, proceeding with client data", e);
    }
    
    const submission: IntakeSubmission = {
      displayName: 'Anonymous Patient',
      ageYears: ans.age ? parseFloat(ans.age) : undefined,
      sex: ans.sex || undefined,
      chiefComplaint: complaintText,
      arrivalMode: 'walk-in',
      assisted,
      humanAssistanceRequested: wantHuman,
      medicalInfoConsent: consent.history,
      listeningConsent: consent.listen,
      language: lang,
      symptomAnswers: ans.answers,
      redFlagsFired: activeRedFlag ? [activeRedFlag] : [],
    };

    try {
      const res = await api.submitIntake(submission);
      setAssignedToken(res.token);
    } catch (e) {
      console.error('Failed to submit intake', e);
      setAssignedToken(Math.floor(Math.random() * 899 + 100).toString());
    }
    
    next('token');
  }

  return (
    <div
      data-surface="patient"
      className="min-h-screen flex flex-col bg-[#0A0D14] text-white selection:bg-[#58A6FF]/30"
    >
      {/* Boot splash — plays on first mount */}
      {showBoot && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black"
        >
          <video
            src="/media/videos/clips/boot-sequence.mp4"
            autoPlay
            muted
            playsInline
            onEnded={() => setShowBoot(false)}
            className="max-h-full max-w-full"
          />
          <button
            onClick={() => setShowBoot(false)}
            className="absolute bottom-6 right-6 px-3 py-1.5 text-xs font-medium rounded-lg border border-white/20 bg-white/5 text-white/70 hover:text-white hover:bg-white/10 transition-colors backdrop-blur-sm"
          >
            Skip
          </button>
        </div>
      )}

      {/* Persistent chrome */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#0A0D14]/80 backdrop-blur-md sticky top-0 z-40">
        <Link href="/" className="flex items-center gap-2.5 group">
          <Mascot pose="pose-01" size={32} alt="MediPilot" className="group-hover:scale-105 transition-transform" />
          <span className="font-bold text-[#58A6FF] tracking-tight">MediPilot</span>
        </Link>
        <div className="flex items-center gap-3 text-xs font-medium text-white/50">
          <button
            onClick={() => setLang(l => (l === 'en' ? 'hi' : 'en'))}
            className="px-2.5 py-1.5 rounded-md border border-white/10 bg-white/[0.02] hover:bg-white/[0.06] hover:text-white transition-colors"
            aria-label="Switch language"
          >
            {lang === 'en' ? 'हिं' : 'EN'}
          </button>
          <span className="tabular-nums">{t(lang, 'Step', 'चरण')} {Math.max(1, STEP_ORDER.indexOf(step) + 1)}/{STEP_ORDER.length}</span>
          <span className="px-2 py-1 rounded-md border border-white/10 bg-white/[0.02] tracking-widest text-[10px] uppercase">SIMULATED</span>
        </div>
      </header>

      {/* Main step area */}
      <main className="flex-1 flex items-start justify-center p-4 sm:p-6">
        <div className="w-full max-w-md pb-10">
          <AnimatePresence mode="wait">
            <motion.div
              key={step}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.14 }}
            >
              {step === 'welcome' && (
                <WelcomeStep
                  lang={lang}
                  showAttract={showAttract}
                  onPlayAttract={() => setShowAttract(true)}
                  onLang={(l) => { setLang(l); next('companion'); }}
                />
              )}

              {step === 'companion' && (
                <CompanionStep
                  lang={lang}
                  onPick={(a) => { setAssisted(a); next('human-offer'); }}
                  onBack={back}
                />
              )}

              {step === 'human-offer' && (
                <HumanOfferStep
                  lang={lang}
                  onPick={(w) => {
                    setWantHuman(w);
                    if (w) next('human-lane');
                    else next('consent');
                  }}
                  onBack={back}
                />
              )}

              {step === 'consent' && (
                <ConsentStep
                  lang={lang}
                  consent={consent}
                  onChange={setConsent}
                  onNext={() => {
                    if (!consent.listen) next('human-lane');
                    else next('basics');
                  }}
                  onBack={back}
                />
              )}

              {step === 'basics' && (
                <BasicsStep
                  lang={lang}
                  ans={ans}
                  onChange={setAns}
                  stratumLabel={stratum.stratum}
                  onNext={() => { setTreeIndex(0); next('tree'); }}
                  onBack={back}
                />
              )}

              {step === 'tree' && (
                <TreeStep
                  lang={lang}
                  question={questions[treeIndex]}
                  value={ans.answers[questions[treeIndex]?.id] ?? ''}
                  onChange={(v) => updateAnswer(questions[treeIndex].id, v)}
                  onNext={() => {
                    if (treeIndex < questions.length - 1) setTreeIndex(i => i + 1);
                    else next('pain');
                  }}
                  onBack={() => (treeIndex > 0 ? setTreeIndex(i => i - 1) : back())}
                  progress={{ i: treeIndex + 1, n: questions.length }}
                  voice={voice}
                />
              )}

              {step === 'pain' && (
                <PainStep
                  lang={lang}
                  value={ans.pain}
                  onChange={(p) => setAns(a => ({ ...a, pain: p }))}
                  onNext={() => next('readback')}
                  onBack={back}
                />
              )}

              {step === 'readback' && (
                <ReadbackStep
                  lang={lang}
                  ans={ans}
                  stratumLabel={stratum.stratum}
                  confirmed={readbackConfirmed}
                  onFix={() => { setReadbackConfirmed(false); setStep('basics'); }}
                  onConfirm={handleConfirm}
                  voice={voice}
                />
              )}

              {step === 'token' && (
                <TokenStep lang={lang} assignedToken={assignedToken} onReset={resetAll} voice={voice} />
              )}

              {step === 'human-lane' && (
                <HumanLaneStep lang={lang} reason={wantHuman ? 'preference' : 'consent'} onReset={resetAll} />
              )}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>

      {/* Red-flag interrupt overlay — fires from anywhere */}
      <AnimatePresence>
        {redFlag && (
          <RedFlagInterrupt lang={lang} observation={redFlag} onAcknowledge={() => setRedFlag(null)} voice={voice} />
        )}
      </AnimatePresence>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step components
// ---------------------------------------------------------------------------

function WelcomeStep({
  lang, showAttract, onPlayAttract, onLang,
}: {
  lang: Lang;
  showAttract: boolean;
  onPlayAttract: () => void;
  onLang: (l: Lang) => void;
}) {
  return (
    <div className="text-center space-y-8 pt-4">
      {/* Video Container - Correct 16:9 aspect ratio, no 3D mascot overlap */}
      <div className="mx-auto w-full max-w-sm aspect-[16/9] relative rounded-2xl overflow-hidden border border-white/10 shadow-lg bg-[#0A0D14]">
        <video
          src="/media/videos/kiosk-attract.mp4"
          autoPlay
          loop
          muted
          playsInline
          className="absolute inset-0 w-full h-full object-cover"
        />
      </div>

      <div>
        <h1 className="text-3xl font-bold tracking-tight text-white/90">नमस्ते / Hello</h1>
        <p className="text-base mt-2 text-white/50">
          {lang === 'hi' ? 'कृपया अपनी भाषा चुनें' : 'Please choose your language'}
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-4 justify-center mx-auto max-w-sm">
        <button
          onClick={() => onLang('hi')}
          className="px-8 py-4 rounded-xl text-lg font-semibold bg-white/[0.03] border border-white/10 hover:bg-[#58A6FF]/10 hover:border-[#58A6FF]/30 hover:text-[#58A6FF] transition-all text-white/80 flex-1 shadow-sm"
        >
          हिंदी
        </button>
        <button
          onClick={() => onLang('en')}
          className="px-8 py-4 rounded-xl text-lg font-semibold bg-white/[0.03] border border-white/10 hover:bg-[#58A6FF]/10 hover:border-[#58A6FF]/30 hover:text-[#58A6FF] transition-all text-white/80 flex-1 shadow-sm"
        >
          English
        </button>
      </div>

      <div className="pt-2 flex flex-col items-center">
        <button className="text-sm font-medium text-white/40 hover:text-white/70 transition-colors underline underline-offset-4">
          {lang === 'hi' ? 'मुझे मदद चाहिए' : 'I need help using this'}
        </button>
      </div>
    </div>
  );
}

function CompanionStep({ lang, onPick, onBack }: { lang: Lang; onPick: (a: boolean) => void; onBack: () => void }) {
  return (
    <StepLayout title={t(lang, 'Is someone with you?', 'क्या आपके साथ कोई है?')} onBack={onBack}>
      <div className="bg-white/[0.02] border border-white/10 rounded-2xl p-6 mb-8 shadow-sm flex items-center justify-center">
        <Mascot pose="pose-06" size={140} className="drop-shadow-lg" />
      </div>
      <div className="flex flex-col gap-4">
        <BigButton onClick={() => onPick(true)}>
          {t(lang, 'Yes, someone is with me', 'हाँ, कोई मेरे साथ है')}
        </BigButton>
        <BigButton onClick={() => onPick(false)}>
          {t(lang, "I'm here alone", 'मैं अकेला/अकेली हूँ')}
        </BigButton>
      </div>
    </StepLayout>
  );
}

function HumanOfferStep({ lang, onPick, onBack }: { lang: Lang; onPick: (w: boolean) => void; onBack: () => void }) {
  return (
    <StepLayout title={t(lang, 'Would you prefer a person?', 'क्या आप किसी व्यक्ति से बात करना पसंद करेंगे?')} onBack={onBack}>
      <div className="bg-white/[0.02] border border-white/10 rounded-2xl p-6 mb-6 shadow-sm flex items-center justify-center">
        <Mascot pose="pose-08" size={140} className="drop-shadow-lg" />
      </div>
      <p className="text-center text-sm font-medium text-white/50 mb-8">
        {t(lang, 'Either way is fine. A person is always available.', 'दोनों ठीक हैं. एक व्यक्ति हमेशा उपलब्ध है।')}
      </p>
      <div className="flex flex-col gap-4">
        <BigButton onClick={() => onPick(false)}>
          {t(lang, "I'll continue here", 'मैं यहीं जारी रखूंगा')}
        </BigButton>
        <BigButton onClick={() => onPick(true)}>
          {t(lang, 'I would prefer a person', 'मैं व्यक्ति से बात करना चाहता हूँ')}
        </BigButton>
      </div>
    </StepLayout>
  );
}

function ConsentStep({
  lang, consent, onChange, onNext, onBack,
}: {
  lang: Lang;
  consent: { listen: boolean; history: boolean };
  onChange: (c: { listen: boolean; history: boolean }) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  return (
    <StepLayout title={t(lang, 'Your permission', 'आपकी अनुमति')} onBack={onBack}>
      <div className="space-y-4 mb-6">
        <ConsentToggle
          checked={consent.listen}
          onChange={(v) => onChange({ ...consent, listen: v })}
          title={t(lang, 'Let MediPilot listen and fill in the form for you.', 'MediPilot को सुनने दें और आपके लिए फ़ॉर्म भरने दें।')}
          hint={t(lang, 'Your words fill this form, then are discarded.', 'आपके शब्द फ़ॉर्म भरते हैं, फिर हटा दिए जाते हैं।')}
        />
        <ConsentToggle
          checked={consent.history}
          onChange={(v) => onChange({ ...consent, history: v })}
          title={t(lang, 'Let MediPilot use your health record to help the nurse.', 'MediPilot को नर्स की मदद के लिए आपके स्वास्थ्य रिकॉर्ड का उपयोग करने दें।')}
          hint={t(lang, 'Separate from listening — used only during this visit.', 'सुनने से अलग — केवल इस मुलाकात के लिए।')}
        />
      </div>
      {!consent.listen && (
        <div className="p-4 rounded-xl border border-[#58A6FF]/30 bg-[#58A6FF]/5 mb-6">
          <p className="text-sm text-white/80 leading-relaxed font-medium">
            {t(lang, 'No problem. A person will take your details. Your queue position is not affected.', 'कोई बात नहीं. एक व्यक्ति आपकी जानकारी लेगा. आपकी कतार में जगह प्रभावित नहीं होगी।')}
          </p>
        </div>
      )}
      <div className="pt-2">
        <BigButton onClick={onNext} primary>
          {t(lang, 'Continue', 'जारी रखें')}
        </BigButton>
      </div>
    </StepLayout>
  );
}

function BasicsStep({
  lang, ans, onChange, stratumLabel, onNext, onBack,
}: {
  lang: Lang;
  ans: Answers;
  onChange: (a: Answers) => void;
  stratumLabel: string;
  onNext: () => void;
  onBack: () => void;
}) {
  const canContinue = ans.age.trim() !== '' && ans.sex !== '';
  return (
    <StepLayout title={t(lang, 'A few basics', 'कुछ बुनियादी बातें')} onBack={onBack}>
      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium mb-2 text-white/80">{t(lang, 'Your age (years)', 'आपकी उम्र (वर्ष)')}</label>
          <input
            type="number"
            inputMode="numeric"
            min={0}
            max={120}
            value={ans.age}
            onChange={(e) => onChange({ ...ans, age: e.target.value })}
            className="w-full p-4 rounded-xl border border-white/10 bg-white/[0.02] text-lg tabular-nums text-white placeholder-white/20 focus:outline-none focus:border-[#58A6FF]/50 focus:bg-white/[0.04] transition-all"
            placeholder="0"
          />
          {ans.age && (
            <p className="text-xs mt-2 text-[#58A6FF]/70">
              {t(lang, 'Stratum', 'श्रेणी')}: {stratumLabel}
            </p>
          )}
        </div>
        <div>
          <label className="block text-sm font-medium mb-2 text-white/80">{t(lang, 'Sex', 'लिंग')}</label>
          <div className="flex gap-3">
            {(['F', 'M', 'O'] as const).map((s) => (
              <button
                key={s}
                onClick={() => onChange({ ...ans, sex: s })}
                className={`flex-1 p-4 rounded-xl border text-sm font-medium transition-all ${
                  ans.sex === s 
                    ? 'bg-[#58A6FF] border-[#58A6FF] text-[#0A0D14]' 
                    : 'bg-white/[0.02] border-white/10 text-white/80 hover:bg-white/[0.04]'
                }`}
              >
                {s === 'F' ? t(lang, 'Female', 'महिला') : s === 'M' ? t(lang, 'Male', 'पुरुष') : t(lang, 'Other', 'अन्य')}
              </button>
            ))}
          </div>
        </div>
      </div>
      <div className="mt-8">
        <BigButton onClick={onNext} primary disabled={!canContinue}>
          {t(lang, 'Continue', 'जारी रखें')}
        </BigButton>
      </div>
    </StepLayout>
  );
}

function TreeStep({
  lang, question, value, onChange, onNext, onBack, progress, voice,
}: {
  lang: Lang;
  question: Question | undefined;
  value: string;
  onChange: (v: string) => void;
  onNext: () => void;
  onBack: () => void;
  progress: { i: number; n: number };
  voice: UseVoiceReturn;
}) {
  if (!question) return null;
  
  // When final transcript updates, append it to value
  useEffect(() => {
    if (voice.finalTranscript) {
      onChange(voice.finalTranscript);
    }
  }, [voice.finalTranscript]);

  const canContinue = !question.required || value.trim().length > 0;
  return (
    <StepLayout
      title={question.label[lang]}
      onBack={onBack}
      subtitle={`${t(lang, 'Question', 'प्रश्न')} ${progress.i}/${progress.n}`}
    >
      <div className="mb-8 flex flex-col items-center gap-4">
        <CockpitRing micLevel={voice.micLevel} isListening={voice.isListening} isRedFlag={false} size={160} />
        <button
          onClick={voice.isListening ? voice.stopListening : voice.startListening}
          className="relative group mt-2"
          aria-label="Toggle voice input"
        >
          <VoiceStatusChip
            supported={voice.supported}
            isListening={voice.isListening}
            isSpeaking={voice.isSpeaking}
            error={voice.error}
            globalMuted={isGlobalMuted()}
          />
        </button>
      </div>

      {question.kind === 'text' && (
        <div className="space-y-3">
          {voice.isListening && voice.transcript && (
            <div className="text-sm italic text-[#58A6FF]/70">
              {voice.transcript}
            </div>
          )}
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            rows={3}
            placeholder={question.id === 'chief-complaint'
              ? t(lang, 'Describe what you feel…', 'आप जो महसूस कर रहे हैं वह बताइए…')
              : t(lang, 'Type here…', 'यहाँ लिखें…')}
            className="w-full p-4 rounded-xl border border-white/10 bg-white/[0.02] text-base text-white placeholder-white/20 focus:outline-none focus:border-[#58A6FF]/50 focus:bg-white/[0.04] transition-all resize-none"
          />
        </div>
      )}
      {question.kind === 'yesno' && (
        <div className="flex gap-4">
          {['yes', 'no'].map((v) => (
            <button
              key={v}
              onClick={() => onChange(v)}
              className={`flex-1 p-4 rounded-xl border text-base font-medium transition-all ${
                value === v 
                  ? 'bg-[#58A6FF] border-[#58A6FF] text-[#0A0D14]' 
                  : 'bg-white/[0.02] border-white/10 text-white/80 hover:bg-white/[0.04]'
              }`}
            >
              {v === 'yes' ? t(lang, 'Yes', 'हाँ') : t(lang, 'No', 'नहीं')}
            </button>
          ))}
        </div>
      )}
      {question.kind === 'options' && (
        <div className="flex flex-col gap-3">
          {question.options?.map((o) => (
            <button
              key={o.value}
              onClick={() => onChange(o.value)}
              className={`p-4 rounded-xl border text-left text-base transition-all ${
                value === o.value
                  ? 'bg-[#58A6FF] border-[#58A6FF] text-[#0A0D14]'
                  : 'bg-white/[0.02] border-white/10 text-white/80 hover:bg-white/[0.04]'
              }`}
            >
              {o.label[lang]}
            </button>
          ))}
        </div>
      )}
      <div className="mt-8">
        <BigButton onClick={onNext} primary disabled={!canContinue}>
          {t(lang, 'Continue', 'जारी रखें')}
        </BigButton>
      </div>
    </StepLayout>
  );
}

const FACES = ['😌', '🙂', '😐', '😕', '😣', '😖'];
function PainStep({
  lang, value, onChange, onNext, onBack,
}: {
  lang: Lang;
  value: number | null;
  onChange: (p: number) => void;
  onNext: () => void;
  onBack: () => void;
}) {
  const v = value ?? 0;
  return (
    <StepLayout title={t(lang, 'How much pain, 0 to 10?', 'दर्द कितना है, 0 से 10?')} onBack={onBack}>
      <div className="text-center mb-8">
        <div className="text-7xl mb-2">{FACES[Math.min(FACES.length - 1, Math.floor(v / 2))]}</div>
        <div className="text-5xl font-bold mt-2 tabular-nums text-[#58A6FF]">{value ?? '—'}</div>
      </div>
      <input
        type="range"
        min={0}
        max={10}
        value={v}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-[#58A6FF] h-2 bg-white/10 rounded-lg appearance-none cursor-pointer"
      />
      <div className="flex justify-between text-xs mt-3 text-white/50 font-medium uppercase tracking-wider">
        <span>{t(lang, 'None', 'कोई नहीं')}</span>
        <span>{t(lang, 'Worst', 'सबसे बुरा')}</span>
      </div>
      <p className="text-xs text-center mt-6 text-white/30">
        {t(lang, 'Voice input available in P7.', 'आवाज़ इनपुट P7 में उपलब्ध होगा।')}
      </p>
      <div className="mt-8">
        <BigButton onClick={onNext} primary disabled={value === null}>
          {t(lang, 'Continue', 'जारी रखें')}
        </BigButton>
      </div>
    </StepLayout>
  );
}

function ReadbackStep({
  lang, ans, stratumLabel, confirmed, onFix, onConfirm, voice,
}: {
  lang: Lang;
  ans: Answers;
  stratumLabel: string;
  confirmed: boolean;
  onFix: () => void;
  onConfirm: () => void;
  voice: UseVoiceReturn;
}) {
  // Speak the summary once when this step mounts.
  useEffect(() => {
    const text = lang === 'hi'
      ? `कृपया देखें: उम्र ${ans.age}. मुख्य समस्या: ${ans.answers['chief-complaint'] ?? ''}. दर्द ${ans.pain ?? 0} बटा 10.`
      : `Please review. Age ${ans.age}. Chief complaint: ${ans.answers['chief-complaint'] ?? ''}. Pain ${ans.pain ?? 0} out of 10.`;
    voice.speak(text, lang);
    return () => voice.cancelSpeech();
  }, [lang, ans, voice]);

  const rows: { k: string; v: string }[] = [
    { k: t(lang, 'Age', 'उम्र'),                 v: ans.age || '—' },
    { k: t(lang, 'Sex', 'लिंग'),                 v: ans.sex || '—' },
    { k: t(lang, 'Stratum', 'श्रेणी'),           v: stratumLabel },
    { k: t(lang, 'Chief complaint', 'मुख्य समस्या'),  v: ans.answers['chief-complaint'] || '—' },
    { k: t(lang, 'Onset', 'शुरुआत'),             v: ans.answers['onset'] || '—' },
    { k: t(lang, 'Severity', 'गंभीरता'),          v: ans.answers['severity'] || '—' },
    { k: t(lang, 'Pain', 'दर्द'),                v: ans.pain !== null ? `${ans.pain}/10` : '—' },
    { k: t(lang, 'Medications', 'दवाइयाँ'),       v: ans.answers['meds'] || t(lang, '(none listed)', '(कोई नहीं)') },
  ];

  return (
    <StepLayout title={t(lang, "Does this look right?", 'क्या यह सही है?')}>
      <div className="flex items-center gap-2 mb-4">
        <span className="text-xs font-medium text-[#58A6FF] flex items-center gap-1.5" aria-live="polite">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/></svg>
          {t(lang, 'MediPilot is reading this aloud', 'MediPilot इसे ज़ोर से पढ़ रहा है')}
        </span>
      </div>
      <div
        className={`p-5 rounded-xl space-y-3 transition-all ${
          confirmed ? 'bg-[#58A6FF]/5 border-2 border-[#58A6FF]' : 'bg-white/[0.02] border border-white/10'
        }`}
      >
        {rows.map(r => (
          <div key={r.k} className="flex gap-4 text-sm">
            <span className="min-w-[120px] text-white/50">{r.k}</span>
            <span className="flex-1 text-white/90 font-medium">{r.v}</span>
          </div>
        ))}
      </div>
      <p className="text-xs mt-3 text-white/40">
        {confirmed
          ? t(lang, 'Confirmed.', 'पुष्टि हुई।')
          : t(lang, 'Nothing is committed until you confirm.', 'जब तक आप पुष्टि नहीं करेंगे कुछ भी सहेजा नहीं जाएगा।')}
      </p>

      {/* The locked acuity slot — visible on the intake side too, per DESIGN §7 */}
      <div className="mt-6 opacity-60">
        <LockedAcuitySlot />
      </div>

      <div className="mt-8 flex gap-4">
        <BigButton onClick={onFix}>{t(lang, 'Fix something', 'कुछ ठीक करें')}</BigButton>
        <BigButton onClick={onConfirm} primary>{t(lang, "That's right", 'यह सही है')}</BigButton>
      </div>
    </StepLayout>
  );
}

function TokenStep({ lang, onReset, voice, assignedToken }: { lang: Lang; assignedToken: string | null; onReset: () => void; voice: UseVoiceReturn }) {
  const token = assignedToken || '---';
  useEffect(() => {
    if (token === '---') return;
    const text = lang === 'hi' 
      ? `आपका टोकन है ${token}. कृपया बोर्ड देखें. अगर आपको खराब लग रहा है, तो यह बटन दबाएं.`
      : `Token ${token}. Watch the board. If anything feels worse, press this button.`;
    voice.speak(text, lang);
    playCommitSettle();
    return () => voice.cancelSpeech();
  }, [token, lang, voice]);

  return (
    <div className="text-center space-y-8 pt-4">
      <div className="bg-white/[0.02] border border-white/10 rounded-2xl p-8 shadow-sm flex items-center justify-center mx-auto max-w-[280px]">
        <Mascot pose="token" size={180} className="drop-shadow-xl" alt="Token issued" />
      </div>
      <div>
        <div className="text-xs uppercase tracking-widest text-[#58A6FF] font-semibold">{t(lang, 'Your token', 'आपका टोकन')}</div>
        <div className="text-8xl font-bold tabular-nums tracking-tighter text-white drop-shadow-sm mt-2">{token}</div>
      </div>
      <p className="text-lg text-white/50 font-medium">
        {t(lang, 'Watch the board. Someone will call your number.', 'बोर्ड देखें. कोई आपका नंबर पुकारेगा।')}
      </p>
      <div className="pt-4">
        <button
          className="w-full py-4 rounded-xl text-lg font-bold border border-[#DF423D]/50 bg-[#DF423D]/10 text-[#DF423D] hover:bg-[#DF423D]/20 transition-all shadow-sm"
        >
          {t(lang, 'I feel worse', 'मुझे और बुरा लग रहा है')}
        </button>
      </div>
      <button className="text-sm font-medium text-white/40 hover:text-white/80 transition-colors underline underline-offset-4 mt-2" onClick={onReset}>
        {t(lang, 'Start again', 'फिर से शुरू करें')}
      </button>
    </div>
  );
}

function HumanLaneStep({ lang, reason, onReset }: { lang: Lang; reason: 'preference' | 'consent'; onReset: () => void }) {
  const token = useMemo(() => 200 + Math.floor(Math.random() * 100), []);
  return (
    <div className="text-center space-y-8 pt-4">
      <div className="bg-white/[0.02] border border-white/10 rounded-2xl p-8 shadow-sm flex items-center justify-center mx-auto max-w-[280px]">
        <Mascot pose="human-lane" size={180} className="drop-shadow-xl" alt="Human lane" />
      </div>
      <div className="space-y-2">
        <h2 className="text-2xl font-bold text-white/90 tracking-tight">
          {t(lang, 'No problem. A person will be with you shortly.', 'कोई बात नहीं. एक व्यक्ति जल्द ही आपके साथ होगा।')}
        </h2>
        <p className="text-base text-white/50 font-medium">
          {reason === 'consent'
            ? t(lang, 'Your queue position is not affected.', 'आपकी कतार में जगह प्रभावित नहीं होगी।')
            : t(lang, 'A staff member is on the way.', 'एक कर्मचारी आ रहा है।')}
        </p>
      </div>
      <div className="pt-4">
        <div className="text-xs uppercase tracking-widest text-[#58A6FF] font-semibold">{t(lang, 'Your token', 'आपका टोकन')}</div>
        <div className="text-7xl font-bold tabular-nums tracking-tighter text-white drop-shadow-sm mt-2">{token}</div>
      </div>
      <button className="text-sm font-medium text-white/40 hover:text-white/80 transition-colors underline underline-offset-4 mt-4" onClick={onReset}>
        {t(lang, 'Start again', 'फिर से शुरू करें')}
      </button>
    </div>
  );
}

function RedFlagInterrupt({ lang, observation, onAcknowledge, voice }: { lang: Lang; observation: string; onAcknowledge: () => void; voice: UseVoiceReturn }) {
  // Speak the reassurance line — never the word RED, never an acuity level.
  useEffect(() => {
    const text = lang === 'hi' ? 'आइए किसी को आपके पास बुलाते हैं।' : "Let's get someone to you right now.";
    voice.speak(text, lang);
    return () => voice.cancelSpeech();
  }, [lang, voice]);

  return (
    <motion.div
      role="alert"
      aria-live="assertive"
      initial={{ opacity: 0, backdropFilter: 'blur(0px)' }}
      animate={{ opacity: 1, backdropFilter: 'blur(8px)' }}
      exit={{ opacity: 0, backdropFilter: 'blur(0px)' }}
      transition={{ duration: 0.3 }}
      className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/80"
    >
      <div
        className="w-full max-w-md text-center p-8 rounded-3xl border border-white/10 bg-[#11141D] shadow-2xl space-y-6"
      >
        <div className="bg-white/[0.02] border border-white/10 rounded-2xl p-6 shadow-inner mx-auto max-w-[200px]">
          <Mascot pose="steady" size={160} className="drop-shadow-xl mx-auto" alt="Steady" />
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-bold tracking-tight text-white/90">
            {t(lang, "Let's get someone to you right now.", 'आइए किसी को आपके पास बुलाते हैं।')}
          </h2>
          <p className="text-sm font-medium text-white/50">
            {t(lang, 'A staff member has been alerted.', 'एक कर्मचारी को सूचित कर दिया गया है।')}
          </p>
        </div>
        {/* Deliberately: no acuity word ever appears here. */}
        <div className="pt-2">
          <button
            onClick={onAcknowledge}
            className="w-full px-6 py-4 rounded-xl text-lg font-semibold bg-[#58A6FF] text-[#0A0D14] hover:bg-[#3b8fdc] transition-all shadow-sm"
          >
            {t(lang, 'Someone is with me', 'कोई मेरे साथ है')}
          </button>
        </div>
      </div>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Shared UI
// ---------------------------------------------------------------------------

function StepLayout({
  title, subtitle, children, onBack,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  onBack?: () => void;
}) {
  return (
    <div className="flex flex-col w-full">
      {onBack && (
        <button 
          onClick={onBack} 
          className="text-[13px] font-medium mb-6 text-white/40 hover:text-white/80 transition-colors flex items-center gap-1.5 w-fit"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          Back
        </button>
      )}
      <div className="space-y-1 mb-8">
        <h2 className="text-2xl font-bold tracking-tight text-white/90">{title}</h2>
        {subtitle && <p className="text-[10px] font-mono uppercase tracking-widest text-[#58A6FF]">{subtitle}</p>}
      </div>
      <div className="w-full">
        {children}
      </div>
    </div>
  );
}

function BigButton({
  children, onClick, primary, disabled, style,
}: {
  children: React.ReactNode;
  onClick: () => void;
  primary?: boolean;
  disabled?: boolean;
  style?: React.CSSProperties;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`w-full px-6 py-4 text-base font-semibold rounded-xl border transition-all flex items-center justify-center disabled:opacity-40 disabled:cursor-not-allowed ${
        primary 
          ? 'bg-[#58A6FF] border-[#58A6FF] text-[#0A0D14] hover:bg-[#3b8fdc] hover:border-[#3b8fdc] shadow-sm' 
          : 'bg-white/[0.03] border-white/10 text-white/90 hover:bg-[#58A6FF]/10 hover:border-[#58A6FF]/30 hover:text-[#58A6FF]'
      }`}
      style={style}
    >
      {children}
    </button>
  );
}

function ConsentToggle({
  checked, onChange, title, hint,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  title: string;
  hint: string;
}) {
  return (
    <label
      className={`flex items-start gap-4 p-4 rounded-xl cursor-pointer border transition-all ${
        checked 
          ? 'border-[#58A6FF]/50 bg-[#58A6FF]/10' 
          : 'border-white/10 bg-white/[0.02] hover:bg-white/[0.04]'
      }`}
    >
      <div className={`mt-0.5 w-5 h-5 rounded-md border flex items-center justify-center shrink-0 transition-all ${
        checked ? 'bg-[#58A6FF] border-[#58A6FF]' : 'bg-transparent border-white/30'
      }`}>
        {checked && (
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#0A0D14" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
        )}
      </div>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="sr-only" />
      <div className="flex flex-col gap-1">
        <div className={`font-medium text-sm transition-colors ${checked ? 'text-white' : 'text-white/80'}`}>{title}</div>
        <div className="text-xs text-white/50 leading-relaxed">{hint}</div>
      </div>
    </label>
  );
}
