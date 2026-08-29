'use client';

import Link from 'next/link';
import dynamic from 'next/dynamic';
import { VideoBackground } from '@/components/ui/VideoBackground';
import { GlassCard } from '@/components/ui/GlassCard';
import { StatCounter } from '@/components/ui/StatCounter';
import { SectionHeading } from '@/components/ui/SectionHeading';
import { VideoClip } from '@/components/ui/VideoClip';
import { FeatureRow } from '@/components/ui/FeatureRow';
import { Mascot } from '@/components/mascot/Mascot';

/* ── 3D components: dynamic import, no SSR (WebGL) ── */
const MascotScene = dynamic(() => import('@/components/3d/MascotScene'), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center w-full h-full">
      <Mascot pose="pose-01" size={280} priority />
    </div>
  ),
});

/* ── Data ── */
const surfaces = [
  { href: '/board',   label: 'Nurse Board',    desc: 'The queue — three time facts per card; breaches glow',       device: 'Projector' },
  { href: '/intake',  label: 'Patient Intake', desc: 'Four-step branch, typed tree, voice — in Hindi or English',  device: 'Tablet' },
  { href: '/hall',    label: 'Waiting Hall',   desc: 'Public display — token numbers only, no names, no acuity',   device: 'Wall Display' },
  { href: '/control', label: 'Judge Control',  desc: 'R slider, surge rate, simulation speed, scenario jump',      device: 'Laptop' },
  { href: '/audit',   label: 'Audit Ledger',   desc: 'Override records rendered verbatim, trust panel, model card', device: 'Laptop' },
] as const;

const timelineSteps = [
  { title: 'Arrive',     desc: 'Walk in, approach the kiosk, choose your language — Hindi, English, or both.',                     video: '/media/videos/clips/hero-arrival.mp4' },
  { title: 'Speak',      desc: 'Tell MediPilot what\'s wrong. It extracts structure — it never decides acuity.',                    video: '/media/videos/clips/voice-interaction.mp4' },
  { title: 'Assess',     desc: 'Vitals measured, age-aware thresholds applied, red flags caught in under a second.',                video: '/media/videos/clips/age-stratification.mp4' },
  { title: 'Prioritize', desc: 'Continuous re-scoring every 60 seconds. The sickest patient is always seen first.',                 video: '/media/videos/clips/nurse-board.mp4' },
] as const;

/* ── Page ── */
export default function LandingPage() {
  return (
    <div data-surface="landing" style={{ background: 'var(--bg)', color: 'var(--text)' }}>

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 1 — HERO
          ════════════════════════════════════════════════════════════════════ */}
      <section className="relative min-h-screen flex items-center overflow-hidden">
        {/* Video background */}
        <VideoBackground src="/media/videos/clips/hero-arrival.mp4" opacity={0.32} />
        {/* Gradient overlay for readability — warm paper, not a dark vignette */}
        <div className="absolute inset-0 bg-gradient-to-t from-[#FBF7F2] via-[#FBF7F2]/70 to-[#FBF7F2]/10 z-[1]" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#FBF7F2]/90 to-transparent z-[1]" />

        <div className="relative z-10 w-full max-w-7xl mx-auto px-6 md:px-12 py-20 flex flex-col lg:flex-row items-center gap-12">
          {/* Left: Copy */}
          <div className="flex-1 text-center lg:text-left">
            <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold tracking-tight leading-[1.1] mb-6">
              Your AI Copilot for{' '}
              <span className="bg-gradient-to-r from-[#DF423D] to-[#926A47] bg-clip-text text-transparent">
                Emergency Triage
              </span>
            </h1>
            <p className="text-xl md:text-2xl leading-relaxed mb-10 max-w-2xl" style={{ color: 'var(--text-dim)' }}>
              Continuous re-assessment. Age-aware. Transparent.
              <br className="hidden md:block" />
              The nurse always has the final say.
            </p>
            <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
              <Link
                href="/intake"
                className="px-8 py-4 rounded-xl font-semibold text-lg text-white bg-gradient-to-r from-[#DF423D] to-[#C23833] hover:from-[#E85950] hover:to-[#DF423D] transition-all shadow-lg shadow-[#DF423D]/20"
              >
                Try Intake Demo →
              </Link>
              <Link
                href="/board"
                className="px-8 py-4 rounded-xl font-semibold text-lg glass-light hover:glow-brand transition-all"
                style={{ color: 'var(--text)' }}
              >
                View Nurse Board
              </Link>
            </div>
          </div>

          {/* Right: 3D Mascot — hidden on mobile, static fallback shown instead */}
          <div className="hidden md:block flex-1 w-full max-w-md lg:max-w-lg h-[400px] md:h-[500px]">
            <MascotScene state="idle" className="w-full h-full" />
          </div>
          <div className="md:hidden flex justify-center">
            <Mascot pose="pose-01" size={200} priority />
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-2 animate-bounce">
          <span className="text-xs tracking-widest uppercase" style={{ color: 'var(--text-dim)' }}>Scroll</span>
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" className="opacity-50">
            <path d="M10 4v12M4 10l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 2 — THE PROBLEM
          ════════════════════════════════════════════════════════════════════ */}
      <section className="py-24 md:py-32 px-6 md:px-12 max-w-7xl mx-auto">
        <SectionHeading
          title="The Problem"
          subtitle="Emergency departments across India face systemic overload. Static triage scores decay the moment they're assigned."
        />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <GlassCard gradient light className="text-center glow-brand">
            <StatCounter value={4.8} decimals={1} suffix=" hrs" label="Average ED Wait Time" />
          </GlassCard>
          <GlassCard gradient light className="text-center glow-brand">
            <StatCounter prefix="1 : " value={40} label="Peak-Hour Nurse-to-Patient Ratio" />
          </GlassCard>
          <GlassCard gradient light className="text-center glow-brand">
            <StatCounter value={30} suffix="%" label="Preventable Mistriage Events" />
          </GlassCard>
        </div>
        <p className="text-center text-xs mt-6 tracking-wider uppercase" style={{ color: 'var(--text-dim)' }}>
          Illustrative
        </p>
      </section>

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 3 — HOW IT WORKS
          ════════════════════════════════════════════════════════════════════ */}
      <section className="py-24 md:py-32 px-6 md:px-12 max-w-7xl mx-auto">
        <SectionHeading
          title="How It Works"
          subtitle="Four steps from arrival to continuous prioritization."
        />

        {/* Timeline */}
        <div className="relative">
          {/* Timeline rail — visible on lg+. Three colours sampled from the
              logo (cross red, aviator leather, goggle steel), same as the
              gradient-border utility. */}
          <div className="hidden lg:block absolute top-[140px] left-0 right-0 h-[2px] bg-gradient-to-r from-[#DF423D] via-[#926A47] to-[#A7C4CC] opacity-30" />

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-8">
            {timelineSteps.map((step, i) => (
              <div key={step.title} className="relative flex flex-col items-center text-center">
                {/* Step number dot */}
                <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#DF423D] to-[#926A47] flex items-center justify-center text-sm font-bold mb-6 shadow-lg shadow-[#DF423D]/20 relative z-10 text-white">
                  {i + 1}
                </div>

                {/* Video thumbnail */}
                <VideoClip src={step.video} className="w-full mb-5" />

                <h3 className="text-xl font-bold mb-2">{step.title}</h3>
                <p className="text-sm leading-relaxed" style={{ color: 'var(--text-dim)' }}>
                  {step.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 4 — FEATURE HIGHLIGHTS
          ════════════════════════════════════════════════════════════════════ */}
      <section className="py-24 md:py-32 px-6 md:px-12 max-w-7xl mx-auto">
        <SectionHeading
          title="Built for Real Hospitals"
          subtitle="Every design decision answers a question a nurse, a patient, or a judge would actually ask."
        />

        <FeatureRow
          video="/media/videos/clips/nurse-assisted-intake_1.mp4"
          title="The Human Lane"
          text="Prefer a person? The nurse sits beside you, opens the same system on her tablet, and walks through the questions together. The technology adapts to the patient — never the other way around."
        />

        <FeatureRow
          video="/media/videos/clips/nurse-rounds.mp4"
          title="Everything at a Glance"
          text="Three explainability channels on every patient card. What drove this score, what was considered but didn't move it, and what was said verbatim. Every factor visible, every override recorded."
          reverse
        />

        <FeatureRow
          video="/media/videos/clips/age-stratification.mp4"
          title="Same Number, Different Meaning"
          text="38.5°C in a 3-year-old and a 75-year-old are not the same finding. Six age strata, each with independently calibrated thresholds. The model that ignores age gets one of them wrong and looks confident doing it."
        />

        <FeatureRow
          video="/media/videos/clips/red-flag-response.mp4"
          title="Red Flags — Instant, Deterministic"
          text="Eight hardcoded rules. Active labour, altered consciousness, chest pain with radiation, uncontrolled bleeding. If any fires, the patient bypasses the model entirely and goes straight to Red. No AI involved. No delay."
          reverse
        />

        <FeatureRow
          video="/media/videos/clips/surge-arrivals.mp4"
          title="Surge Mode — What Stretches, What Holds"
          text="At 3× normal load, Green and Yellow cadences stretch to buy time. Red cadences never stretch. The system refuses to relax what cannot be relaxed — and says so explicitly on screen."
        />

        <FeatureRow
          video="/media/videos/clips/nurse-override.mp4"
          title="The Nurse Closes Every Loop"
          text="One tap to override any recommendation. A 16-field legal record captures exactly why. The system's job is to surface the right patient — the human's job is to decide what happens next."
          reverse
        />
      </section>

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 5 — ARCHITECTURE
          ════════════════════════════════════════════════════════════════════ */}
      <section className="py-24 md:py-32 px-6 md:px-12 bg-white border-t" style={{ borderColor: 'var(--line)' }}>
        <div className="max-w-7xl mx-auto">
          <SectionHeading
            title="Under the Hood"
            subtitle="A 10-layer pipeline from voice to risk score."
          />

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-12 lg:gap-16 items-start mt-12">
            {/* Video */}
            <div className="relative rounded-xl overflow-hidden border shadow-lg bg-black" style={{ borderColor: 'var(--line)' }}>
              <VideoClip src="/media/videos/clips/architecture-flow.mp4" className="w-full h-auto aspect-[16/9]" />
            </div>

            {/* Text overlay */}
            <div className="flex flex-col gap-8">
              <div className="space-y-4">
                <p className="text-xl font-medium leading-relaxed" style={{ color: 'var(--text)' }}>
                  The language model extracts structure.
                </p>
                <p className="text-xl font-medium leading-relaxed" style={{ color: 'var(--text)' }}>
                  It is grammar-constrained to <span className="text-[#DF423D]">never produce a diagnosis or acuity level.</span>
                </p>
                <p className="text-base leading-relaxed" style={{ color: 'var(--text-dim)' }}>
                  That&apos;s enforced by the output schema, not a preference.
                </p>
              </div>

              {/* Technical Index */}
              <div className="flex flex-col gap-0 border-t" style={{ borderColor: 'var(--line)' }}>
                {[
                  { num: '01', label: 'Entry & Branch Gate' },
                  { num: '02', label: 'Language Detection & ASR' },
                  { num: '03', label: 'Age-Aware Question Tree' },
                  { num: '04', label: 'Grammar-Constrained LLM' },
                  { num: '05', label: 'Deterministic Red-Flag Table' },
                  { num: '06', label: 'Reliability Flags Assembler' },
                  { num: '07', label: 'PatientRecord Output Contract' },
                  { num: '08', label: 'Backend Risk Model' },
                ].map(layer => (
                  <div key={layer.num} className="flex items-center gap-6 py-3.5 border-b group" style={{ borderColor: 'var(--line)' }}>
                    <span className="font-mono text-sm group-hover:text-[#DF423D] transition-colors" style={{ color: 'var(--text-dim)' }}>{layer.num}</span>
                    <div className="w-1.5 h-1.5 rounded-full group-hover:bg-[#DF423D] transition-colors" style={{ background: 'var(--line)' }} />
                    <span className="text-sm font-medium group-hover:text-[color:var(--text)] transition-colors" style={{ color: 'var(--text-dim)' }}>{layer.label}</span>
                  </div>
                ))}
              </div>

              {/* Disclaimer */}
              <div className="mt-2 p-6 rounded-xl border" style={{ borderColor: 'rgba(223,66,61,0.2)', background: 'rgba(223,66,61,0.04)' }}>
                <h4 className="text-[10px] font-bold uppercase tracking-widest mb-4 flex items-center gap-2" style={{ color: '#926A47' }}>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                  System Constraint
                </h4>
                <div className="space-y-1 mb-5">
                  <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>No diagnosis.</p>
                  <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>No acuity band.</p>
                  <p className="text-sm font-medium" style={{ color: 'var(--text)' }}>No &quot;could this patient die&quot; field.</p>
                </div>
                <p className="text-xs leading-relaxed max-w-sm" style={{ color: 'var(--text-dim)' }}>
                  Grammar rejects any output outside the allowed schema.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 6 — SURFACES GRID
          ════════════════════════════════════════════════════════════════════ */}
      <section className="py-24 md:py-32 px-6 md:px-12 max-w-7xl mx-auto bg-white">
        <SectionHeading
          title="The Five Screens"
          subtitle="Each screen runs on a different device in a real ED. Click to explore."
        />

        <div className="mt-16">
          {/* Connecting Line */}
          <div className="hidden lg:block w-full h-px mb-10 relative" style={{ background: 'var(--line)' }}>
            <div className="absolute top-1/2 left-0 w-full flex justify-between px-12 -translate-y-1/2">
              {[0, 1, 2, 3, 4].map(i => (
                <div key={i} className="w-2 h-2 rounded-full ring-4 ring-white" style={{ background: 'var(--line)' }} />
              ))}
            </div>
          </div>

          <div className="grid gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-5">
            {surfaces.map((surface, i) => (
              <Link key={surface.href} href={surface.href} className="group block relative flex flex-col items-start text-left">
                <span className="font-mono text-xs mb-4 group-hover:text-[#DF423D] transition-colors" style={{ color: 'var(--text-dim)' }}>
                  {String(i + 1).padStart(2, '0')}
                </span>
                <div
                  className="w-10 h-10 mb-4 rounded-lg border flex items-center justify-center group-hover:bg-[#DF423D]/10 group-hover:border-[#DF423D]/30 transition-colors shadow-sm"
                  style={{ borderColor: 'var(--line)', background: 'var(--bg)' }}
                >
                  <SurfaceIcon href={surface.href} />
                </div>
                <h3 className="text-base font-semibold mb-3 transition-colors flex items-center gap-2" style={{ color: 'var(--text)' }}>
                  {surface.label}
                  <svg className="w-3.5 h-3.5 opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-[#DF423D]" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M5 12h14M12 5l7 7-7 7"/></svg>
                </h3>
                <div className="w-full h-px mb-4 group-hover:bg-[#DF423D]/30 transition-colors" style={{ background: 'var(--line)' }} />
                <p className="text-[13px] leading-relaxed mb-6 flex-1" style={{ color: 'var(--text-dim)' }}>
                  {surface.desc}
                </p>
                <div className="mt-auto text-[10px] font-mono uppercase tracking-wide transition-colors" style={{ color: 'var(--text-dim)' }}>
                  DEVICE · {surface.device.toUpperCase()}
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ════════════════════════════════════════════════════════════════════
          SECTION 7 — FOOTER
          ════════════════════════════════════════════════════════════════════ */}
      <footer className="border-t py-12 px-6 md:px-12 bg-white" style={{ borderColor: 'var(--line)' }}>
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-8">
          <div className="flex items-center gap-4">
            <Mascot pose="pose-01" size={32} />
            <div className="flex flex-col">
              <span className="font-semibold text-sm tracking-wide" style={{ color: 'var(--text)' }}>MediPilot</span>
              <span className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>Team 01 BIT · IIT Patna · Accenture Innovation Challenge 2026, Round 2</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}

/* One outline icon per surface — pulled out of the JSX above so the five
   near-identical grid cards above are generated from `surfaces` instead
   of being hand-duplicated five times. */
function SurfaceIcon({ href }: { href: (typeof surfaces)[number]['href'] }) {
  const common = {
    width: 18,
    height: 18,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 2,
  } as const;
  const className = 'transition-colors group-hover:text-[#DF423D]';
  const style = { color: 'var(--text-dim)' } as const;

  switch (href) {
    case '/board':
      return (
        <svg {...common} className={className} style={style}>
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <line x1="3" y1="9" x2="21" y2="9" />
          <line x1="9" y1="21" x2="9" y2="9" />
        </svg>
      );
    case '/intake':
      return (
        <svg {...common} className={className} style={style}>
          <path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2" />
          <rect x="8" y="2" width="8" height="4" rx="1" ry="1" />
        </svg>
      );
    case '/hall':
      return (
        <svg {...common} className={className} style={style}>
          <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
          <line x1="8" y1="21" x2="16" y2="21" />
          <line x1="12" y1="17" x2="12" y2="21" />
        </svg>
      );
    case '/control':
      return (
        <svg {...common} className={className} style={style}>
          <line x1="21" y1="4" x2="14" y2="4" />
          <line x1="10" y1="4" x2="3" y2="4" />
          <line x1="21" y1="12" x2="12" y2="12" />
          <line x1="8" y1="12" x2="3" y2="12" />
          <line x1="21" y1="20" x2="16" y2="20" />
          <line x1="12" y1="20" x2="3" y2="20" />
          <line x1="14" y1="1" x2="14" y2="7" />
          <line x1="8" y1="9" x2="8" y2="15" />
          <line x1="16" y1="17" x2="16" y2="23" />
        </svg>
      );
    case '/audit':
      return (
        <svg {...common} className={className} style={style}>
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
          <polyline points="14 2 14 8 20 8" />
          <line x1="16" y1="13" x2="8" y2="13" />
          <line x1="16" y1="17" x2="8" y2="17" />
          <polyline points="10 9 9 9 8 9" />
        </svg>
      );
  }
}
