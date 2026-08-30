import type { ScoreResponse } from '@/lib/api/types';
import { BandChip } from './BandChip';
import { RedFlagBanner } from './RedFlagBanner';
import { ConfidenceBand } from './ConfidenceBand';
import { ExplanationChannels } from './ExplanationChannels';

interface Props {
  score: ScoreResponse;
}

/**
 * The AcuityCard for a scored (non-abstained) encounter.
 *
 * Dev-throws if the score is missing any of confidence, conformalSet,
 * inputsUsed — Invariant 2 (no naked scores). Enforced at the render boundary,
 * not by review convention, per FRONTEND_PLAN §3.
 */
export function AcuityCard({ score }: Props) {
  if (process.env.NODE_ENV !== 'production') {
    if (!score.confidence || !score.conformalSet || !score.inputsUsed) {
      throw new Error(
        `AcuityCard refuses to render a naked score for ${score.encounterId}. ` +
        `Missing: ${[
          !score.confidence && 'confidence',
          !score.conformalSet && 'conformalSet',
          !score.inputsUsed && 'inputsUsed',
        ].filter(Boolean).join(', ')}. See BACKEND_INTEGRATION_LOG §3 I-2.`
      );
    }
  }

  return (
    <div className="space-y-4">
      {score.redFlags && score.redFlags.length > 0 && (
        <RedFlagBanner flags={score.redFlags} />
      )}

      <div className="flex items-center justify-between">
        <BandChip band={score.effectiveBand} size="lg" />
        {score.suggestsReview && (
          <span
            className="text-xs px-2 py-1 rounded font-medium"
            style={{ background: 'var(--bg-raised)', color: 'var(--acuity-yellow)', border: '1px solid var(--acuity-yellow)' }}
          >
            Suggests review — {score.suggestsReviewReason ?? 'lower band believed'}
          </span>
        )}
      </div>

      {score.explanation && <ExplanationChannels explanation={score.explanation} />}

      <ConfidenceBand
        confidence={score.confidence!}
        conformalSet={score.conformalSet!}
        coverage={score.coverage}
        reducers={score.confidenceReducedBy}
      />

      <div className="text-xs pt-2 border-t flex items-center justify-between" style={{ borderColor: 'var(--line)', color: 'var(--text-dim)' }}>
        <span>Inputs used: {score.inputsUsed!.join(', ')}</span>
        <span>p* = {score.thresholdUsed.toFixed(4)} · R = {score.costRatioR}</span>
      </div>
    </div>
  );
}
