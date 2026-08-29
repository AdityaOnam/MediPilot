'use client';

import { SessionContext, useIntakeSessionValue } from './session';
import { NurseCall } from './components/NurseCall';
import { Welcome } from './components/steps/Welcome';
import { Companion } from './components/steps/Companion';
import { HumanOffer } from './components/steps/HumanOffer';
import { Consent } from './components/steps/Consent';
import { Basics } from './components/steps/Basics';
import { Conversation } from './components/steps/Conversation';
import { Pain } from './components/steps/Pain';
import { Readback } from './components/steps/Readback';
import { Token } from './components/steps/Token';
import { HumanLane } from './components/steps/HumanLane';

/**
 * The root component. Provides the session context and routes between the
 * nine steps. A fired red flag wins over whatever `step` says — NurseCall
 * renders in its place regardless of where the patient was in the tree
 * (Part 4: every clinical question stops immediately).
 */
export default function IntakeApp() {
  const value = useIntakeSessionValue();
  const { session } = value;

  return (
    <SessionContext.Provider value={value}>
      {session.needsImmediateNurse ? <NurseCall /> : <StepRouter step={session.step} />}
    </SessionContext.Provider>
  );
}

function StepRouter({ step }: { step: ReturnType<typeof useIntakeSessionValue>['session']['step'] }) {
  switch (step) {
    case 'welcome':
      return <Welcome />;
    case 'companion':
      return <Companion />;
    case 'human-offer':
      return <HumanOffer />;
    case 'consent':
      return <Consent />;
    case 'basics':
      return <Basics />;
    case 'conversation':
      return <Conversation />;
    case 'pain':
      return <Pain />;
    case 'readback':
      return <Readback />;
    case 'token':
      return <Token />;
    case 'human-lane':
      return <HumanLane />;
    default:
      return null;
  }
}
