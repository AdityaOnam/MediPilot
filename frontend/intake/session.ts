'use client';

import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { INITIAL_SESSION, type BranchId, type SessionState } from './tree/types';
import * as engine from './tree/engine';

/**
 * The one React context holding SessionState. Every step component reads
 * `session` and calls the actions below — nothing mutates SessionState
 * directly, everything routes through engine.ts's pure reducers so the
 * reducers stay unit-testable without React.
 */
export interface IntakeActions {
  setLang: (lang: 'en' | 'hi') => void;
  goTo: (step: SessionState['step']) => void;
  setCompanion: (assisted: boolean) => void;
  setHumanOffer: (wantsHuman: boolean) => void;
  setConsent: (consent: { listen: boolean; records: boolean }) => void;
  setBasics: (ageYears: number | null, sex: SessionState['sex']) => void;
  setChiefComplaint: (text: string) => void;
  submitAnswer: (text: string) => void;
  /** Groq's branch classification, applied only if the patient has not
   *  yet answered anything in the branch. */
  refineBranch: (branchId: BranchId) => void;
  /** Tier-B observe result: red-flag codes and volunteered fields. */
  applyObserved: (codes: string[], fields: Record<string, string>) => void;
  /** Records fragmented speech as an observation for the nurse. Never
   *  escalates on its own. */
  noteSpeechEffort: () => void;
  setPainScore: (score: number) => void;
  confirmReadback: () => void;
  issueToken: (token: string, counter: string | null, requiredVitals?: string[]) => void;
  /** Undo the last answer and re-ask it. See engine.goBackOne. */
  goBackOne: () => void;
  reset: () => void;
}

const SessionContext = createContext<{ session: SessionState; actions: IntakeActions } | null>(null);

export function useIntakeSession() {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useIntakeSession must be used within IntakeSessionProvider');
  return ctx;
}

export function useIntakeSessionValue(): { session: SessionState; actions: IntakeActions } {
  const [session, setSession] = useState<SessionState>(INITIAL_SESSION);

  const setLang = useCallback((lang: 'en' | 'hi') => setSession((s) => engine.setLang(s, lang)), []);
  const goTo = useCallback((step: SessionState['step']) => setSession((s) => engine.goTo(s, step)), []);
  const setCompanion = useCallback((assisted: boolean) => setSession((s) => engine.setCompanion(s, assisted)), []);
  const setHumanOffer = useCallback((wantsHuman: boolean) => setSession((s) => engine.setHumanOffer(s, wantsHuman)), []);
  const setConsent = useCallback(
    (consent: { listen: boolean; records: boolean }) => setSession((s) => engine.setConsent(s, consent)),
    [],
  );
  const setBasics = useCallback(
    (ageYears: number | null, sex: SessionState['sex']) => setSession((s) => engine.setBasics(s, ageYears, sex)),
    [],
  );
  const setChiefComplaint = useCallback(
    (text: string) => setSession((s) => engine.setChiefComplaintAndBranch(s, text)),
    [],
  );
  const submitAnswer = useCallback((text: string) => setSession((s) => engine.submitAnswer(s, text)), []);
  const refineBranch = useCallback(
    (branchId: BranchId) => setSession((s) => engine.refineBranch(s, branchId)),
    [],
  );
  const applyObserved = useCallback(
    (codes: string[], fields: Record<string, string>) =>
      setSession((s) => engine.applyObserved(s, codes, fields)),
    [],
  );
  const setPainScore = useCallback((score: number) => setSession((s) => engine.setPainScore(s, score)), []);
  const confirmReadback = useCallback(() => setSession((s) => engine.confirmReadback(s)), []);
  const issueToken = useCallback(
    (token: string, counter: string | null, requiredVitals: string[] = []) =>
      setSession((s) => engine.issueToken(s, token, counter, requiredVitals)),
    [],
  );
  const noteSpeechEffort = useCallback(() => setSession((s) => engine.noteSpeechEffort(s)), []);
  const goBackOne = useCallback(() => setSession((s) => engine.goBackOne(s)), []);
  const reset = useCallback(() => setSession(INITIAL_SESSION), []);

  const actions = useMemo<IntakeActions>(
    () => ({
      setLang, goTo, setCompanion, setHumanOffer, setConsent, setBasics,
      setChiefComplaint, submitAnswer, refineBranch, applyObserved, noteSpeechEffort,
      setPainScore, confirmReadback, issueToken, goBackOne, reset,
    }),
    [setLang, goTo, setCompanion, setHumanOffer, setConsent, setBasics,
      setChiefComplaint, submitAnswer, refineBranch, applyObserved, noteSpeechEffort,
      setPainScore, confirmReadback, issueToken, goBackOne, reset],
  );

  return { session, actions };
}

export { SessionContext };
