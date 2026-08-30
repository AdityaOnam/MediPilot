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
import { isGlobalMuted, setGlobalMute } from '@/lib/voice/audio';
import { GlassCard } from '@/components/ui/GlassCard';
import dynamic from 'next/dynamic';
import { api } from '@/lib/api/client';
import { type IntakeSubmission, type TreeState, type TreeStructure } from '@/lib/api/types';
import { matchYesNo, matchOption, MATCH_CONFIDENCE_THRESHOLD } from '@/lib/intake/optionMatcher';
import { translatePrompt } from '@/lib/intake/promptTranslations';

/**
 * The one question shape this screen renders, whichever tree produced it.
 *
 * Two trees can drive intake. The real one is the ~140-node clinical tree
 * in intake/question_tree.py, walked turn-by-turn over /v1/intake/tree/*
 * — it branches on complaint, skips what the patient already volunteered,
 * and truncates itself when the red-flag table fires. The fallback is the
 * short static list in lib/intake/questionTree.ts, used only when the
 * backend is unreachable so a demo never dead-ends on a network error.
 *
 * Rendering keys off `options.length`, not `kind`: the backend expresses a
 * closed answer set as yes_no + options, the static tree as its own
 * 'options' kind, and both mean the same thing to the patient.
 */
interface UiQuestion {
  nodeId: string;
  prompt: string;
  promptHi: string | null;
  kind: 'free_text' | 'yes_no' | 'numeric_0_10';
  options: { value: string; label: { en: string; hi: string } }[];
}

/** Beat between the question finishing and the mic opening, so the kiosk
 *  is never listening while it is still talking and the patient gets a
 *  moment to take the question in. */
const ARM_DELAY_MS = 2000;

function localQuestionToUi(q: Question): UiQuestion {
  const kind: UiQuestion['kind'] =
    q.kind === 'yesno' ? 'yes_no' : q.kind === 'number' ? 'numeric_0_10' : 'free_text';
  return {
    nodeId: q.id,
    prompt: q.label.en,
    promptHi: q.label.hi,
    kind,
    options:
      q.options ??
      (q.kind === 'yesno'
        ? [
            { value: 'yes', label: { en: 'Yes', hi: 'हाँ' } },
            { value: 'no', label: { en: 'No', hi: 'नहीं' } },
          ]
        : []),
  };
}

function treeQuestionToUi(q: NonNullable<TreeState['question']>): UiQuestion {
  return {
    nodeId: q.nodeId,
    prompt: q.prompt,
    promptHi: q.promptHi,
    kind: q.kind,
    options: q.options ?? [],
  };
}

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

  // Mid-tree red-flag routing: a flag can fire on ANY free-text answer, not
  // only the chief complaint, and once one fires the patient must not be
  // walked through the rest of the form (§10 / Invariant 6) — they go
  // straight to a token, skipping the queue screen.
  const [redFlagObservations, setRedFlagObservations] = useState<string[]>([]);
  const [needsImmediateNurse, setNeedsImmediateNurse] = useState(false);
  const [checkingRedFlag, setCheckingRedFlag] = useState(false);
  const [submittingRedFlag, setSubmittingRedFlag] = useState(false);
  const [muted, setMuted] = useState(false);
  const [assignedCounter, setAssignedCounter] = useState<string | null>(null);

  // Backend-driven question tree (the real 140-node one). `usingLocalTree`
  // flips to true only if /v1/intake/tree/* is unreachable, in which case
  // the short static list takes over so the kiosk still works.
  const [treeState, setTreeState] = useState<TreeState | null>(null);
  const [usingLocalTree, setUsingLocalTree] = useState(false);
  const [treeBusy, setTreeBusy] = useState(false);

  const stratum = useMemo(() => {
    const n = parseFloat(ans.age);
    return isNaN(n) ? resolveStratum(null) : resolveStratum(n);
  }, [ans.age]);
  const questions = useMemo(() => questionsFor(stratum.stratum), [stratum.stratum]);

  // Whichever tree is driving, this is the question on screen right now.
  const currentQuestion: UiQuestion | null = useMemo(() => {
    if (usingLocalTree) {
      const q = questions[treeIndex];
      return q ? localQuestionToUi(q) : null;
    }
    return treeState?.question ? treeQuestionToUi(treeState.question) : null;
  }, [usingLocalTree, questions, treeIndex, treeState]);

  /**
   * The chief complaint, wherever it came from. The backend tree's own
   * extraction wins when present (it is the structurer's cleaned reading of
   * what the patient said); otherwise fall back to the raw answer text
   * under whichever node id the active tree uses -- `chief_complaint` in
   * the Python tree, `chief-complaint` in the static frontend one.
   */
  const chiefComplaint =
    treeState?.chiefComplaint
    || ans.answers['chief_complaint']
    || ans.answers['chief-complaint']
    || '';

  const treeProgress = usingLocalTree
    ? { i: treeIndex + 1, n: questions.length }
    : treeState?.progress ?? { i: 1, n: 1 };

  /** Open a session against the real backend tree; fall back to the static
   *  list if that is not reachable. */
  async function startTree() {
    setTreeBusy(true);
    try {
      const state = await api.treeStart({
        ageYears: ans.age ? parseFloat(ans.age) : undefined,
        medicalInfoConsent: consent.history,
        language: lang,
      });
      setTreeState(state);
      setUsingLocalTree(false);
    } catch (e) {
      console.warn('Backend question tree unavailable, using local fallback tree', e);
      setUsingLocalTree(true);
      setTreeIndex(0);
    } finally {
      setTreeBusy(false);
    }
  }

  /**
   * Submit one answer to whichever tree is active and act on what it says.
   * The backend tree owns branching, skip-what-was-already-said, and
   * red-flag truncation, so this only has to route the outcome.
   */
  async function submitTreeAnswer(text: string) {
    const trimmed = (text ?? '').trim();
    if (!trimmed || treeBusy) return;

    if (usingLocalTree) {
      const q = questions[treeIndex];
      if (q) updateAnswer(q.id, trimmed);
      if (q?.kind === 'text') {
        setCheckingRedFlag(true);
        const flagged = await checkAnswerForRedFlags(trimmed);
        setCheckingRedFlag(false);
        if (flagged) return;
      }
      if (treeIndex < questions.length - 1) setTreeIndex(i => i + 1);
      else next('pain');
      return;
    }

    if (!treeState?.sessionId) return;
    const nodeId = treeState.question?.nodeId;
    if (nodeId) updateAnswer(nodeId, trimmed);

    setTreeBusy(true);
    try {
      const nextState = await api.treeAnswer(treeState.sessionId, trimmed);
      setTreeState(nextState);

      if (nextState.redFlagObservations.length > 0) {
        handleRedFlagDetected(nextState.redFlagObservations);
      }
      // The tree truncated itself: red_flags.py already established this is
      // a nurse-now case, so stop asking and route immediately.
      if (nextState.stoppedForRedFlag) return;
      if (nextState.complete) next('pain');
    } catch (e) {
      console.warn('Tree answer failed', e);
    } finally {
      setTreeBusy(false);
    }
  }

  // Idle attract-loop on welcome screen — 8 s, so judges see it during pitch pauses.
  useEffect(() => {
    if (step !== 'welcome') { setShowAttract(false); return; }
    if (idleTimer.current) clearTimeout(idleTimer.current);
    idleTimer.current = setTimeout(() => setShowAttract(true), 8000);
    return () => { if (idleTimer.current) clearTimeout(idleTimer.current); };
  }, [step]);

  // Sync the mute button's initial state with whatever the control panel
  // (or a previous session on this device) already set.
  useEffect(() => {
    setMuted(isGlobalMuted());
  }, []);

  function toggleMute() {
    setMuted(prev => {
      const next = !prev;
      setGlobalMute(next);
      if (next) voice.cancelSpeech(); // silence anything already playing, not just future calls
      return next;
    });
  }

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
    // Live, client-side-only feedback while typing/speaking, on WHICHEVER
    // question is active — not just the chief complaint. The authoritative
    // check (the same fixed table the backend uses for every other turn)
    // runs on Continue, see checkAnswerForRedFlags below; this is only the
    // fast local pass so the interrupt can appear the instant a patient
    // finishes typing, without waiting on a network round trip.
    const flags = scanRedFlags(value);
    if (flags.length > 0) handleRedFlagDetected(flags.map(f => f.observation));
  }

  function handleRedFlagDetected(observations: string[]) {
    if (observations.length === 0) return;
    setRedFlag(observations[0]);
    setRedFlagObservations(prev => Array.from(new Set([...prev, ...observations])));
    setNeedsImmediateNurse(true);
  }

  // Authoritative red-flag check: runs intake/red_flags.py's fixed table via
  // /v1/structure. Called after ANY free-text answer in the tree — a red
  // flag can surface on question 2 or question 5 just as easily as on the
  // chief complaint, and per §10 / Invariant 6 the patient must not be
  // walked through the rest of the form once one fires.
  async function checkAnswerForRedFlags(text: string): Promise<boolean> {
    const trimmed = (text || '').trim();
    if (!trimmed) return false;
    if (redFlag) return true; // interrupt already showing from an earlier answer

    const clientFlags = scanRedFlags(trimmed);
    if (clientFlags.length > 0) {
      handleRedFlagDetected(clientFlags.map(f => f.observation));
      return true;
    }
    try {
      const structRes = await api.structureText(trimmed, lang);
      if (structRes.redFlags.length > 0) {
        handleRedFlagDetected(structRes.redFlags.map(f => f.observation));
        return true;
      }
    } catch (e) {
      // A failed check must not block a non-urgent patient from continuing
      // — it only means THIS turn's check is incomplete, not that anything
      // was ruled out. The next answer's check, and the final readback
      // pass in handleConfirm, both get another chance.
      console.warn('Red-flag check failed, continuing without it', e);
    }
    return false;
  }

  // Submits intake immediately and routes straight to the token screen,
  // skipping any remaining tree/pain/readback questions. Used once a red
  // flag has fired: the fixed table has already decided this is a
  // nurse-now case, so nothing downstream should re-ask the patient
  // anything before staff are alerted.
  async function submitForImmediateNurse() {
    if (submittingRedFlag) return;
    setSubmittingRedFlag(true);
    const complaintText = chiefComplaint || 'Reported during intake';
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
      redFlagsFired: redFlagObservations,
    };
    try {
      const res = await api.submitIntake(submission);
      setAssignedToken(res.token);
      setAssignedCounter(res.counter ?? null);
      setNeedsImmediateNurse(res.needsImmediateNurse ?? true);
    } catch (e) {
      console.error('Failed to submit intake (red-flag path)', e);
      setAssignedToken(Math.floor(Math.random() * 899 + 100).toString());
      setNeedsImmediateNurse(true);
    }
    setSubmittingRedFlag(false);
    setRedFlag(null);
    next('token');
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
    setRedFlagObservations([]);
    setNeedsImmediateNurse(false);
    setCheckingRedFlag(false);
    setSubmittingRedFlag(false);
    setAssignedToken(null);
    setAssignedCounter(null);
    setTreeState(null);
    setUsingLocalTree(false);
    setTreeBusy(false);
  }

  async function handleConfirm() {
    setReadbackConfirmed(true);
    const complaintText = chiefComplaint || 'No complaint';

    // Final safety pass before committing — catches anything the
    // per-question checks in the tree missed (e.g. a schema-hint field
    // that only revealed a symptom once read back in full). Skipped if a
    // flag already fired earlier, since that path already owns submission.
    if (redFlagObservations.length === 0) {
      const flagged = await checkAnswerForRedFlags(complaintText);
      if (flagged) {
        setReadbackConfirmed(false);
        return; // RedFlagInterrupt is now showing; its own button submits
      }
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
      redFlagsFired: redFlagObservations,
    };

    try {
      const res = await api.submitIntake(submission);
      setAssignedToken(res.token);
      setAssignedCounter(res.counter ?? null);
      setNeedsImmediateNurse(res.needsImmediateNurse ?? false);
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
        <div className="flex items-center gap-2 text-xs font-medium text-white/50">
          {/* Volume slider next to the mute toggle. The slider changes the
              TTS output loudness live and the value survives reload; the
              mute button is a hard off. See useVoice.setVolume. */}
          <div className="flex items-center gap-2 rounded-md border border-white/10 bg-white/[0.02] px-2 py-1.5">
            <button
              onClick={toggleMute}
              className="text-white/60 hover:text-white transition-colors"
              aria-label={muted ? t(lang, 'Turn sound on', 'आवाज़ चालू करें') : t(lang, 'Turn sound off', 'आवाज़ बंद करें')}
              aria-pressed={muted}
            >
              {muted || voice.volume === 0 ? (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                  <line x1="23" y1="9" x2="17" y2="15" />
                  <line x1="17" y1="9" x2="23" y2="15" />
                </svg>
              ) : (
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5" />
                  <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                  <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                </svg>
              )}
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={muted ? 0 : voice.volume}
              onChange={(e) => {
                const v = parseFloat(e.target.value);
                if (muted && v > 0) setMuted(false);
                voice.setVolume(v);
              }}
              aria-label={t(lang, 'Question voice volume', 'प्रश्न की आवाज़ का स्तर')}
              className="w-16 sm:w-20 accent-[#58A6FF] cursor-pointer"
            />
          </div>
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
                  onNext={() => { setTreeIndex(0); startTree(); next('tree'); }}
                  onBack={back}
                />
              )}

              {step === 'tree' && (
                <TreeStep
                  lang={lang}
                  question={currentQuestion}
                  value={currentQuestion ? ans.answers[currentQuestion.nodeId] ?? '' : ''}
                  onChange={(v) => currentQuestion && updateAnswer(currentQuestion.nodeId, v)}
                  onSubmitAnswer={submitTreeAnswer}
                  onBack={() => (usingLocalTree && treeIndex > 0 ? setTreeIndex(i => i - 1) : back())}
                  progress={treeProgress}
                  voice={voice}
                  checking={checkingRedFlag || treeBusy}
                  onRedFlagFromVoice={handleRedFlagDetected}
                  sourceLabel={usingLocalTree ? 'local' : 'clinical'}
                  plan={treeState?.plan}
                  answers={ans.answers}
                  branch={treeState?.branch}
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
                  chiefComplaint={chiefComplaint}
                />
              )}

              {step === 'token' && (
                <TokenStep
                  lang={lang}
                  assignedToken={assignedToken}
                  assignedCounter={assignedCounter}
                  needsImmediateNurse={needsImmediateNurse}
                  onReset={resetAll}
                  voice={voice}
                />
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
          <RedFlagInterrupt
            lang={lang}
            observation={redFlag}
            onAcknowledge={submitForImmediateNurse}
            submitting={submittingRedFlag}
            voice={voice}
          />
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
  lang, question, value, onChange, onSubmitAnswer, onBack, progress, voice, checking,
  onRedFlagFromVoice, sourceLabel, plan, answers, branch,
}: {
  lang: Lang;
  question: UiQuestion | null;
  value: string;
  onChange: (v: string) => void;
  /** Hands the answer to whichever tree is driving. The backend tree owns
   *  branching and red-flag truncation, so this screen never decides what
   *  comes next -- it only reports what the patient said. */
  onSubmitAnswer: (text: string) => void;
  onBack: () => void;
  progress: { i: number; n: number };
  voice: UseVoiceReturn;
  checking?: boolean;
  /** A voice answer that didn't match any on-screen option still gets sent
   * through the LLM structurer so a red flag buried in an off-script spoken
   * answer is never silently dropped just because it didn't match a button. */
  onRedFlagFromVoice?: (observations: string[]) => void;
  sourceLabel: 'clinical' | 'local';
  /** Snapshot of the plan for the demo tree-flow panel. */
  plan?: TreeState['plan'];
  answers: Record<string, string>;
  /** Matched ComplaintCategory, shown in the tree panel. */
  branch?: string | null;
}) {
  const [showTree, setShowTree] = useState(false);
  const [voiceHint, setVoiceHint] = useState<string | null>(null);
  const [remoteMatching, setRemoteMatching] = useState(false);
  // Where we are in the speak -> arm -> listen cycle. Drives the status
  // line so the patient is never guessing whether the kiosk is talking,
  // about to listen, or listening.
  const [micPhase, setMicPhase] = useState<'idle' | 'speaking' | 'arming' | 'listening'>('idle');
  const lastMatchedTranscript = useRef<string | null>(null);
  // The patient's own stop is the only thing that latches the mic off.
  // Everything else -- an auto-submit that fires end-of-answer, moving to
  // the next question, a network stall -- must not stop listening.
  const userExplicitlyStoppedRef = useRef(false);

  const hasOptions = !!question && question.options.length > 0;
  // Prefer a translation the backend shipped for this exact node; fall
  // back to the client-side translation table for the common prompts
  // whose Hindi is not yet in the Python tree; last resort English.
  const prompt = question
    ? (lang === 'hi'
        ? (question.promptHi ?? translatePrompt(question.prompt, 'hi'))
        : question.prompt)
    : '';

  /**
   * Consume a completed spoken transcript:
   *
   *   free-text  -> land in the textarea; auto-submit after a short settle
   *                 window (kiosk stays voice-first: no need to reach for a
   *                 button after speaking). Cancelled if listening stops or
   *                 a fresh transcript arrives first.
   *   options    -> two-tier matching. The local Jaccard matcher wins fast
   *                 when its score clears the threshold. If it doesn't, we
   *                 escalate to the SERVER matcher (Groq via
   *                 /v1/intake/tree/match-option): send the question, the
   *                 options, and what was actually said. Groq either picks
   *                 one of the exact option values or returns NONE, in
   *                 which case we show the "please choose one below" hint.
   *                 The LLM is only ever asked to pick, never to interpret.
   */
  useEffect(() => {
    const transcript = voice.finalTranscript;
    if (!question || !transcript || transcript === lastMatchedTranscript.current) return;
    lastMatchedTranscript.current = transcript;

    if (!hasOptions) {
      onChange(transcript);
      // Auto-submit only while listening: if the patient stopped the mic
      // themselves, they are typing/reviewing and should press Continue.
      if (voice.isListening) {
        const timer = setTimeout(() => onSubmitAnswer(transcript), 900);
        return () => clearTimeout(timer);
      }
      return;
    }

    const result = question.kind === 'yes_no'
      ? matchYesNo(transcript)
      : matchOption(transcript, question.options);
    const matchedValue = result.match
      ? (typeof result.match === 'string' ? result.match : result.match.value)
      : null;

    if (matchedValue && result.confidence >= MATCH_CONFIDENCE_THRESHOLD) {
      setVoiceHint(null);
      onChange(matchedValue);
      playCaptureConfirm();
      voice.resetTranscript();
      const timer = setTimeout(() => onSubmitAnswer(matchedValue), 650);
      return () => clearTimeout(timer);
    }

    // Below threshold: ask the server matcher (Groq) to pick from the
    // allowed set. Do NOT alter the answer or the transcript yet; the
    // patient stays on the question while the network round-trip happens.
    setVoiceHint(t(lang, 'Matching your answer…', 'आपका उत्तर मिलाया जा रहा है…'));
    setRemoteMatching(true);
    const cancelled = { current: false };
    api.matchOption({
      questionPrompt: prompt,
      patientText: transcript,
      options: question.options,
    })
      .then(res => {
        if (cancelled.current) return;
        setRemoteMatching(false);
        if (res.matched) {
          setVoiceHint(null);
          onChange(res.matched);
          playCaptureConfirm();
          voice.resetTranscript();
          setTimeout(() => onSubmitAnswer(res.matched!), 650);
        } else {
          voice.resetTranscript();
          setVoiceHint(t(lang,
            'I couldn’t match “' + transcript + '” to a choice. Please pick one below, or say it again.',
            '“' + transcript + '” को किसी विकल्प से मिलाया नहीं जा सका। कृपया नीचे से चुनें, या दोबारा बोलें।'));
        }
      })
      .catch(e => {
        if (cancelled.current) return;
        setRemoteMatching(false);
        console.warn('Server option-matcher failed', e);
        voice.resetTranscript();
        setVoiceHint(t(lang,
          'Please pick one of the choices below.',
          'कृपया नीचे दिए गए विकल्पों में से एक चुनें।'));
      });

    // Only after we know the local match failed do we ALSO run the safety
    // check that catches a red flag phrased as a non-option answer.
    api.structureText(transcript, lang)
      .then(res => {
        if (res.redFlags.length > 0) {
          onRedFlagFromVoice?.(res.redFlags.map(f => f.observation));
        }
      })
      .catch(e => console.warn('Low-confidence voice answer: structurer check failed', e));

    return () => { cancelled.current = true; };
  }, [voice.finalTranscript]);

  // Clear per-question voice state when the tree moves on, so a stale hint
  // or the previous question's transcript can't be matched against this one.
  useEffect(() => {
    setVoiceHint(null);
    lastMatchedTranscript.current = null;
  }, [question?.nodeId]);

  // Live-update the free-text answer from the browser recogniser's interim
  // stream. This is what makes the textarea "write as you speak" like the
  // Google Translate voice input the patient is used to -- until now the
  // textarea only updated once, when Whisper's final transcript landed
  // ~5-15 seconds after the utterance ended, which felt broken.
  //
  // The final Whisper result still wins (see the effect above): it is the
  // authoritative transcript, the interim is provisional. Both are only
  // written to the answer field, never to a badge or overlay.
  useEffect(() => {
    if (!question || hasOptions || !voice.isListening) return;
    if (!voice.transcript) return;
    onChange(voice.transcript);
  }, [voice.transcript, hasOptions, question?.nodeId, voice.isListening]);

  // Read the question aloud in the chosen language. Voice INPUT working is
  // not the same as the kiosk being usable without reading: a patient who
  // cannot read the screen still has to be told what is being asked, and
  // for a closed answer set, what the choices are.
  /**
   * The speak -> wait -> listen cycle, per question.
   *
   * Ordering matters and is the whole point: the microphone is CLOSED
   * while the kiosk is talking. Muting the transcript was not enough --
   * the recogniser still ran, so the kiosk kept hearing its own prompt
   * and answering itself. Now:
   *
   *   1. close the mic (if open) and read the question aloud
   *   2. when the audio finishes, wait ARM_DELAY_MS (2s) -- a beat for
   *      the patient to register the question before the mic opens
   *   3. open the mic; from there useVoice's own silence detector ends
   *      the answer after ~5s of quiet and the answer is submitted
   *
   * If the patient explicitly stopped the mic, none of this re-opens it.
   */
  useEffect(() => {
    if (!question) return;

    // Any audio captured up to this point belongs to the previous
    // question, and the mic must not be live while the prompt plays.
    voice.stopListening();
    setMicPhase('speaking');

    let armTimer: ReturnType<typeof setTimeout> | null = null;

    // `prompt` is already language-resolved (backend translation ->
    // client-side table -> English) so the TTS reads the same thing that
    // is on screen.
    let spoken = prompt;
    if (hasOptions) {
      const choices = question.options.map(o => o.label[lang]).join(t(lang, ', or ', ', या '));
      spoken += ' ' + choices + t(lang, '. Which one?', '. कौन सा?');
    }

    const openMic = () => {
      if (userExplicitlyStoppedRef.current) { setMicPhase('idle'); return; }
      setMicPhase('listening');
      voice.startListening();
    };

    voice.speak(spoken, lang, () => {
      // onEnd fires whether the utterance finished or errored. Give the
      // patient a beat, then open the mic.
      setMicPhase('arming');
      armTimer = setTimeout(openMic, ARM_DELAY_MS);
    });

    return () => {
      if (armTimer) clearTimeout(armTimer);
      voice.cancelSpeech();
    };
  }, [question?.nodeId, lang, prompt]);

  const toggleMic = () => {
    if (voice.isListening) {
      userExplicitlyStoppedRef.current = true;
      voice.stopListening();
      setMicPhase('idle');
    } else {
      userExplicitlyStoppedRef.current = false;
      voice.cancelSpeech(); // don't make them wait out the prompt
      voice.startListening();
      setMicPhase('listening');
    }
  };

  if (!question) {
    return (
      <StepLayout title={t(lang, 'Preparing your questions…', 'आपके प्रश्न तैयार हो रहे हैं…')} onBack={onBack}>
        <div className="flex justify-center py-12">
          <div className="h-10 w-10 rounded-full border-2 border-[#58A6FF]/30 border-t-[#58A6FF] animate-spin" />
        </div>
      </StepLayout>
    );
  }

  const canContinue = value.trim().length > 0 && !checking;

  return (
    <>
    <StepLayout
      title={prompt}
      onBack={onBack}
    >
      {/* No question count or percentage. Both are misleading: this tree
          branches and splices questions in as the patient answers, so a
          "3/12" number would move backwards mid-conversation and a "17%"
          would jump. An indeterminate activity bar (only while a request is
          in flight) is honest about what it actually knows. */}
      <div className="-mt-2 mb-6 h-1 rounded-full overflow-hidden bg-white/[0.05]">
        {checking && (
          <motion.div
            className="h-full w-1/3 rounded-full bg-gradient-to-r from-transparent via-[#58A6FF] to-transparent"
            initial={{ x: '-100%' }}
            animate={{ x: '300%' }}
            transition={{ repeat: Infinity, duration: 1.2, ease: 'linear' }}
          />
        )}
      </div>
      <div className="mb-6 flex items-center justify-between text-[10px] uppercase tracking-widest text-white/30">
        <span>{sourceLabel === 'clinical'
          ? t(lang, 'Clinical question set', 'क्लिनिकल प्रश्न सेट')
          : t(lang, 'Offline question set', 'ऑफ़लाइन प्रश्न सेट')}</span>
        <div className="flex items-center gap-3">
          {checking && <span className="text-[#58A6FF]/70 normal-case tracking-normal">{t(lang, 'Thinking…', 'सोच रहा है…')}</span>}
          {/* Demo aid: opens a side panel that shows the whole plan from
              top to bottom, with the current node highlighted. Not shown
              to a real patient in a real deployment, but useful when
              presenting the branching to a reviewer. */}
          {plan && plan.length > 0 && (
            <button
              type="button"
              onClick={() => setShowTree(true)}
              className="normal-case tracking-normal text-[#58A6FF]/80 hover:text-[#58A6FF] underline underline-offset-2 transition-colors"
            >
              {t(lang, 'Show tree', 'ट्री देखें')}
            </button>
          )}
        </div>
      </div>

      <div className="mb-7 flex flex-col items-center gap-3">
        <CockpitRing micLevel={voice.micLevel} isListening={voice.isListening} isRedFlag={false} size={150} />
        <button
          onClick={toggleMic}
          className="relative group"
          aria-label={voice.isListening
            ? t(lang, 'Stop voice input', 'आवाज़ इनपुट बंद करें')
            : t(lang, 'Start voice input', 'आवाज़ इनपुट शुरू करें')}
        >
          <VoiceStatusChip
            supported={voice.supported}
            isListening={voice.isListening}
            isSpeaking={voice.isSpeaking}
            error={voice.error}
            globalMuted={isGlobalMuted()}
          />
        </button>

        {/* Explicit status the patient can see instead of having to infer
            from the mic icon. The mic stays on until it is pressed again,
            AND a 5-second run of silence auto-submits the current text --
            saying so is what stops the kiosk from feeling unresponsive. */}
        {micPhase === 'speaking' && (
          <p className="text-[11px] text-white/40 text-center max-w-xs">
            {t(lang, 'Reading the question… the mic is off.', 'प्रश्न पढ़ा जा रहा है… माइक बंद है।')}
          </p>
        )}
        {micPhase === 'arming' && (
          <p className="text-[11px] text-[#7EE3C1]/80 text-center max-w-xs">
            {t(lang, 'Get ready — the mic opens in a moment.', 'तैयार हो जाइए — माइक अभी खुलेगा।')}
          </p>
        )}
        {micPhase === 'listening' && voice.isListening && (
          <p className="text-[11px] text-white/40 text-center max-w-xs">
            {t(lang,
              'Listening — pause for a few seconds when you’re done.',
              'सुन रहा है — बात पूरी हो जाए तो कुछ सेकंड रुकें।')}
          </p>
        )}
        {!voice.isListening && micPhase === 'idle' && (
          <p className="text-[11px] text-white/40 text-center max-w-xs">
            {t(lang,
              'Voice is off. You can press the mic, or type your answer below.',
              'आवाज़ बंद है। आप माइक दबा सकते हैं, या नीचे अपना उत्तर टाइप कर सकते हैं।')}
          </p>
        )}

        {voice.isTranscribing && (
          <div className="text-[11px] text-[#58A6FF]/70">{t(lang, 'Improving transcription…', 'लिखा सुधारा जा रहा है…')}</div>
        )}
        {remoteMatching && (
          <div className="flex items-center gap-2 text-[11px] text-[#58A6FF]/80">
            <span className="inline-block h-3 w-3 rounded-full border-2 border-[#58A6FF]/30 border-t-[#58A6FF] animate-spin" />
            {t(lang, 'Matching to a choice…', 'विकल्प से मिलाया जा रहा है…')}
          </div>
        )}
        {voiceHint && hasOptions && !remoteMatching && (
          <div className="text-sm text-center text-amber-400/90 max-w-sm px-3 py-2 rounded-lg border border-amber-400/20 bg-amber-400/[0.06]">
            {voiceHint}
          </div>
        )}
      </div>

      {!hasOptions && (
        <div className="space-y-3">
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            rows={3}
            placeholder={question.nodeId.includes('chief')
              ? t(lang, 'Describe what you feel…', 'आप जो महसूस कर रहे हैं वह बताइए…')
              : t(lang, 'Speak, or type here…', 'बोलें, या यहाँ लिखें…')}
            className="w-full p-4 rounded-xl border border-white/10 bg-white/[0.02] text-base text-white placeholder-white/20 focus:outline-none focus:border-[#58A6FF]/50 focus:bg-white/[0.04] transition-all resize-none"
          />
        </div>
      )}

      {hasOptions && (
        <div className={question.options.length <= 2 ? 'flex gap-3' : 'flex flex-col gap-2.5'}>
          {question.options.map((o) => {
            const active = value === o.value;
            return (
              <button
                key={o.value}
                onClick={() => { onChange(o.value); onSubmitAnswer(o.value); }}
                disabled={!!checking}
                className={`${question.options.length <= 2 ? 'flex-1 text-center' : 'text-left'} p-4 rounded-xl border text-base font-medium transition-all disabled:opacity-60 ${
                  active
                    ? 'bg-[#58A6FF] border-[#58A6FF] text-[#0A0D14] shadow-[0_0_20px_rgba(88,166,255,0.25)]'
                    : 'bg-white/[0.02] border-white/10 text-white/80 hover:bg-white/[0.06] hover:border-white/20'
                }`}
              >
                {o.label[lang]}
              </button>
            );
          })}
        </div>
      )}

      {!hasOptions && (
        <div className="mt-8">
          <BigButton onClick={() => onSubmitAnswer(value)} primary disabled={!canContinue}>
            {checking ? t(lang, 'Checking…', 'जांच हो रही है…') : t(lang, 'Continue', 'जारी रखें')}
          </BigButton>
        </div>
      )}
    </StepLayout>
    {showTree && plan && (
      <TreeFlowPanel
        lang={lang}
        plan={plan}
        answers={answers}
        branch={branch}
        onClose={() => setShowTree(false)}
      />
    )}
    </>
  );
}

/**
 * The decision tree, not just this patient's path.
 *
 * Two views:
 *   PATH   -- the plan as it stands for this patient: what was answered,
 *             what is being asked, what is still queued. This is the
 *             linear slice through the tree.
 *   TREE   -- every complaint category the tree can route to, each with
 *             its question block and conditional level-2 follow-ups. The
 *             matched category is expanded and highlighted; the rest are
 *             collapsed so the branching is visible without scrolling
 *             through 140 nodes.
 *
 * The TREE view is what makes the design legible to a reviewer: before
 * the chief complaint is answered the PATH view is just the seven shared
 * questions and shows none of the routing that is the actual system.
 */
function TreeFlowPanel({
  lang, plan, answers, branch, onClose,
}: {
  lang: Lang;
  plan: NonNullable<TreeState['plan']>;
  answers: Record<string, string>;
  branch: string | null | undefined;
  onClose: () => void;
}) {
  const [view, setView] = useState<'path' | 'tree'>('path');
  const [structure, setStructure] = useState<TreeStructure | null>(null);
  const [loadingStructure, setLoadingStructure] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(branch ?? null);
  const currentRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    if (view === 'path') currentRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }, [view]);

  // Fetch the full tree lazily -- it is a few hundred nodes and only the
  // TREE view needs it.
  useEffect(() => {
    if (view !== 'tree' || structure || loadingStructure) return;
    setLoadingStructure(true);
    api.treeStructure()
      .then(s => { setStructure(s); setExpanded(e => e ?? branch ?? null); })
      .catch(e => console.warn('Could not load tree structure', e))
      .finally(() => setLoadingStructure(false));
  }, [view, structure, loadingStructure, branch]);

  const label = (n: { prompt: string; promptHi: string | null }) =>
    (lang === 'hi' && n.promptHi) ? n.promptHi : n.prompt;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-lg h-full bg-[#0F131C] border-l border-white/10 shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-6 pt-5 pb-3 border-b border-white/10">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="text-lg font-semibold text-white tracking-tight">
                {t(lang, 'Question tree', 'प्रश्न ट्री')}
              </h3>
              {branch && (
                <p className="text-xs text-white/50 mt-1">
                  {t(lang, 'Matched category:', 'मिली श्रेणी:')}{' '}
                  <span className="text-[#7EE3C1] font-medium">{branch}</span>
                </p>
              )}
            </div>
            <button onClick={onClose} className="text-white/40 hover:text-white p-2 -mt-1">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
            </button>
          </div>

          <div className="mt-4 flex gap-1 p-1 rounded-lg bg-white/[0.03] border border-white/5">
            {(['path', 'tree'] as const).map(v => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`flex-1 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  view === v ? 'bg-[#58A6FF] text-[#0A0D14]' : 'text-white/50 hover:text-white/80'
                }`}
              >
                {v === 'path'
                  ? t(lang, 'This patient', 'यह मरीज़')
                  : t(lang, 'All branches', 'सभी शाखाएँ')}
              </button>
            ))}
          </div>
        </div>

        {view === 'path' && (
          <>
            <ol className="flex-1 overflow-y-auto p-6 space-y-2">
              {plan.map((n, i) => {
                const isCurrent = n.status === 'current';
                const isDone = n.status === 'done';
                const answer = answers[n.nodeId];
                return (
                  <li key={`${n.nodeId}-${i}`} ref={isCurrent ? currentRef : undefined} className="relative">
                    {i < plan.length - 1 && (
                      <div className="absolute left-3 top-8 bottom-[-8px] w-px bg-white/10" />
                    )}
                    <div className={`flex gap-3 items-start rounded-xl p-3 border transition-colors ${
                      isCurrent ? 'bg-[#58A6FF]/10 border-[#58A6FF]/50'
                        : isDone ? 'bg-white/[0.02] border-white/5'
                        : 'bg-transparent border-white/5'
                    }`}>
                      <div className={`w-6 h-6 shrink-0 rounded-full flex items-center justify-center text-[10px] font-bold ${
                        isCurrent ? 'bg-[#58A6FF] text-[#0A0D14]'
                          : isDone ? 'bg-[#7EE3C1]/20 text-[#7EE3C1] border border-[#7EE3C1]/40'
                          : 'bg-white/[0.03] text-white/30 border border-white/10'
                      }`}>
                        {isDone ? '✓' : i + 1}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className={`text-sm ${isCurrent ? 'text-white font-medium' : isDone ? 'text-white/70' : 'text-white/40'}`}>
                          {label(n)}
                        </div>
                        {isDone && answer && (
                          <div className="text-[11px] italic text-[#7EE3C1]/80 mt-1 truncate">“{answer}”</div>
                        )}
                        <div className="text-[10px] uppercase tracking-widest text-white/25 mt-1">
                          {n.nodeId}{n.kind !== 'free_text' && ` · ${n.kind.replace('_', '/')}`}
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ol>
            <div className="px-6 py-3 border-t border-white/10 bg-black/20 text-[11px] text-white/40 flex items-center justify-between">
              <span>{plan.filter(n => n.status === 'done').length} / {plan.length} {t(lang, 'answered', 'उत्तरित')}</span>
              <span>{plan.filter(n => n.status === 'upcoming').length} {t(lang, 'to go', 'बाकी')}</span>
            </div>
          </>
        )}

        {view === 'tree' && (
          <div className="flex-1 overflow-y-auto p-6">
            {loadingStructure && (
              <div className="flex justify-center py-10">
                <div className="h-8 w-8 rounded-full border-2 border-[#58A6FF]/30 border-t-[#58A6FF] animate-spin" />
              </div>
            )}
            {structure && (
              <div className="space-y-5">
                <section>
                  <h4 className="text-[10px] uppercase tracking-widest text-white/35 mb-2">
                    {t(lang, 'Asked of everyone', 'सबसे पूछा जाता है')}
                  </h4>
                  <div className="space-y-1.5">
                    {structure.opening.map(n => (
                      <div key={n.nodeId} className="text-sm text-white/70 rounded-lg px-3 py-2 bg-white/[0.02] border border-white/5">
                        {label(n)}
                      </div>
                    ))}
                  </div>
                </section>

                <section>
                  <h4 className="text-[10px] uppercase tracking-widest text-white/35 mb-2">
                    {t(lang, 'Then one of these branches', 'फिर इनमें से एक शाखा')}
                    <span className="ml-2 text-white/25 normal-case tracking-normal">
                      ({structure.categories.length})
                    </span>
                  </h4>
                  <div className="space-y-1.5">
                    {structure.categories.map(c => {
                      const isActive = c.name === branch;
                      const isOpen = expanded === c.name;
                      return (
                        <div
                          key={c.name}
                          className={`rounded-lg border overflow-hidden transition-colors ${
                            isActive ? 'border-[#7EE3C1]/50 bg-[#7EE3C1]/[0.06]' : 'border-white/5 bg-white/[0.02]'
                          }`}
                        >
                          <button
                            onClick={() => setExpanded(isOpen ? null : c.name)}
                            className="w-full px-3 py-2.5 flex items-center justify-between text-left"
                          >
                            <span className="flex items-center gap-2 min-w-0">
                              {isActive && (
                                <span className="shrink-0 text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#7EE3C1] text-[#0A0D14]">
                                  {t(lang, 'matched', 'मिला')}
                                </span>
                              )}
                              <span className={`text-sm truncate ${isActive ? 'text-white font-medium' : 'text-white/70'}`}>
                                {c.name.replace(/_/g, ' ')}
                              </span>
                            </span>
                            <span className="shrink-0 flex items-center gap-2 text-[10px] text-white/30">
                              {c.questions.length}
                              <svg
                                width="12" height="12" viewBox="0 0 24 24" fill="none"
                                stroke="currentColor" strokeWidth="2.5"
                                className={`transition-transform ${isOpen ? 'rotate-90' : ''}`}
                              >
                                <path d="M9 18l6-6-6-6" />
                              </svg>
                            </span>
                          </button>

                          {isOpen && (
                            <div className="px-3 pb-3 space-y-1.5 border-t border-white/5 pt-2.5">
                              {c.keywordSample.length > 0 && (
                                <p className="text-[10px] text-white/30 mb-2">
                                  {t(lang, 'Triggers on:', 'इन पर चलती है:')}{' '}
                                  <span className="text-white/45">{c.keywordSample.join(' · ')}</span>
                                </p>
                              )}
                              {c.questions.map(q => (
                                <div key={q.nodeId}>
                                  <div className="text-[13px] text-white/65 pl-2 border-l-2 border-white/10 py-0.5">
                                    {label(q)}
                                  </div>
                                  {q.followUps.length > 0 && (
                                    <div className="ml-4 mt-1 space-y-1">
                                      <p className="text-[10px] text-[#58A6FF]/60">
                                        {t(lang, 'only if answer mentions:', 'तभी अगर उत्तर में हो:')}{' '}
                                        {q.followUpTriggers.slice(0, 4).join(', ') || t(lang, 'yes', 'हाँ')}
                                      </p>
                                      {q.followUps.map(f => (
                                        <div key={f.nodeId} className="text-[12px] text-white/45 pl-2 border-l-2 border-[#58A6FF]/25 py-0.5">
                                          {label(f)}
                                        </div>
                                      ))}
                                    </div>
                                  )}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </section>

                <section>
                  <h4 className="text-[10px] uppercase tracking-widest text-white/35 mb-2">
                    {t(lang, 'Then, by age group', 'फिर, आयु वर्ग के अनुसार')}
                  </h4>
                  <div className="space-y-2">
                    {(['adult', 'paediatric', 'geriatric'] as const).map(k => (
                      <div key={k} className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2.5">
                        <div className="text-[11px] uppercase tracking-wider text-white/40 mb-1.5">{k}</div>
                        {structure.tails[k].map(n => (
                          <div key={n.nodeId} className="text-[13px] text-white/60 pl-2 border-l-2 border-white/10 py-0.5">
                            {label(n)}
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
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
  lang, ans, stratumLabel, confirmed, onFix, onConfirm, voice, chiefComplaint,
}: {
  lang: Lang;
  ans: Answers;
  chiefComplaint: string;
  stratumLabel: string;
  confirmed: boolean;
  onFix: () => void;
  onConfirm: () => void;
  voice: UseVoiceReturn;
}) {
  // Speak the summary once when this step mounts.
  useEffect(() => {
    const text = lang === 'hi'
      ? `कृपया देखें: उम्र ${ans.age}. मुख्य समस्या: ${chiefComplaint}. दर्द ${ans.pain ?? 0} बटा 10.`
      : `Please review. Age ${ans.age}. Chief complaint: ${chiefComplaint}. Pain ${ans.pain ?? 0} out of 10.`;
    voice.speak(text, lang);
    return () => voice.cancelSpeech();
  }, [lang, ans, voice]);

  const rows: { k: string; v: string }[] = [
    { k: t(lang, 'Age', 'उम्र'),                 v: ans.age || '—' },
    { k: t(lang, 'Sex', 'लिंग'),                 v: ans.sex || '—' },
    { k: t(lang, 'Stratum', 'श्रेणी'),           v: stratumLabel },
    { k: t(lang, 'Chief complaint', 'मुख्य समस्या'),  v: chiefComplaint || '—' },
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

function TokenStep({
  lang, onReset, voice, assignedToken, assignedCounter, needsImmediateNurse,
}: {
  lang: Lang;
  assignedToken: string | null;
  /** Where to physically go ("Counter 3" / "Triage Bay"). A number alone
   *  tells a patient they are queued but not where to stand. */
  assignedCounter: string | null;
  needsImmediateNurse: boolean;
  onReset: () => void;
  voice: UseVoiceReturn;
}) {
  const token = assignedToken || '---';
  useEffect(() => {
    if (token === '---') return;
    const where = assignedCounter
      ? (lang === 'hi' ? ` कृपया ${assignedCounter} पर जाएँ।` : ` Please go to ${assignedCounter}.`)
      : '';
    const text = needsImmediateNurse
      ? (lang === 'hi'
          ? `आपका टोकन है ${token}. एक कर्मचारी अभी आपके पास आ रहा है।`
          : `Token ${token}. A staff member is coming to you right now.`)
      : (lang === 'hi'
          ? `आपका टोकन है ${token}.${where} कृपया बोर्ड देखें. अगर आपको खराब लग रहा है, तो यह बटन दबाएं.`
          : `Token ${token}.${where} Watch the board. If anything feels worse, press this button.`);
    voice.speak(text, lang);
    playCommitSettle();
    return () => voice.cancelSpeech();
  }, [token, lang, voice, needsImmediateNurse, assignedCounter]);

  return (
    <div className="text-center space-y-8 pt-4">
      <div className="bg-white/[0.02] border border-white/10 rounded-2xl p-8 shadow-sm flex items-center justify-center mx-auto max-w-[280px]">
        <Mascot pose="token" size={180} className="drop-shadow-xl" alt="Token issued" />
      </div>
      <div>
        <div className="text-xs uppercase tracking-widest text-[#58A6FF] font-semibold">{t(lang, 'Your token', 'आपका टोकन')}</div>
        <div className="text-8xl font-bold tabular-nums tracking-tighter text-white drop-shadow-sm mt-2">{token}</div>
      </div>

      {/* Where to go. Given equal billing with the token because a number
          without a destination is not actionable in a busy waiting area. */}
      {assignedCounter && (
        <div className="mx-auto max-w-[300px] rounded-2xl border border-[#7EE3C1]/30 bg-[#7EE3C1]/[0.07] px-6 py-5">
          <div className="text-xs uppercase tracking-widest text-[#7EE3C1] font-semibold">
            {needsImmediateNurse ? t(lang, 'Go to', 'यहाँ जाएँ') : t(lang, 'Please go to', 'कृपया यहाँ जाएँ')}
          </div>
          <div className="text-3xl font-bold text-white mt-1.5 tracking-tight">{assignedCounter}</div>
        </div>
      )}
      {needsImmediateNurse ? (
        <p className="text-lg text-white/90 font-semibold">
          {t(lang, 'A staff member is coming to you now.', 'एक कर्मचारी अभी आपके पास आ रहा है।')}
        </p>
      ) : (
        <p className="text-lg text-white/50 font-medium">
          {t(lang, 'Watch the board. Someone will call your number.', 'बोर्ड देखें. कोई आपका नंबर पुकारेगा।')}
        </p>
      )}
      {!needsImmediateNurse && (
        <div className="pt-4">
          <button
            className="w-full py-4 rounded-xl text-lg font-bold border border-[#DF423D]/50 bg-[#DF423D]/10 text-[#DF423D] hover:bg-[#DF423D]/20 transition-all shadow-sm"
          >
            {t(lang, 'I feel worse', 'मुझे और बुरा लग रहा है')}
          </button>
        </div>
      )}
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

function RedFlagInterrupt({
  lang, observation, onAcknowledge, voice, submitting,
}: {
  lang: Lang;
  observation: string;
  onAcknowledge: () => void;
  voice: UseVoiceReturn;
  submitting?: boolean;
}) {
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
            disabled={submitting}
            className="w-full px-6 py-4 rounded-xl text-lg font-semibold bg-[#58A6FF] text-[#0A0D14] hover:bg-[#3b8fdc] transition-all shadow-sm disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {submitting
              ? t(lang, 'Getting your token…', 'आपका टोकन लिया जा रहा है…')
              : t(lang, 'OK — get help now', 'ठीक है — अभी मदद लें')}
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
