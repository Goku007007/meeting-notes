import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import {
  ArrowRight,
  Brain,
  CheckCheck,
  FileText,
  ListChecks,
  MessageSquareText,
  ShieldCheck,
  Upload,
  Zap,
} from "lucide-react";

import { Button } from "@/components/ui/button";

type Metric = {
  icon: LucideIcon;
  value: string;
  label: string;
};

type Capability = {
  icon: LucideIcon;
  title: string;
  description: string;
  footnote: string;
};

const metrics: Metric[] = [
  { icon: Brain, value: "RAG", label: "Powered retrieval" },
  { icon: FileText, value: "100%", label: "Citation-backed" },
  { icon: Zap, value: "<60s", label: "To first insight" },
  { icon: ShieldCheck, value: "0", label: "Hallucinations" },
];

const capabilities: Capability[] = [
  {
    icon: Upload,
    title: "Upload & Index",
    description: "Drop notes, transcripts, and agendas. We chunk and embed for grounded retrieval.",
    footnote: ".txt .pdf .docx .pptx .xlsx + more",
  },
  {
    icon: MessageSquareText,
    title: "Ask Anything",
    description: "Ask plain-language questions and get direct answers tied to real evidence.",
    footnote: "RAG-powered, citation-backed",
  },
  {
    icon: ListChecks,
    title: "Extract & Verify",
    description: "Pull decisions, owners, action items, and open issues linked to source chunks.",
    footnote: "Structured artifacts with evidence",
  },
];

const steps = [
  {
    number: "01",
    title: "Create a meeting",
    description: "Start a new meeting session and name it. No account needed.",
  },
  {
    number: "02",
    title: "Upload documents",
    description: "Attach transcripts, notes, or agendas. They get chunked, embedded, and indexed.",
  },
  {
    number: "03",
    title: "Ask & Verify",
    description: "Ask cited questions and run Verify to extract decisions, tasks, and issues.",
  },
];

function WorkspacePreview() {
  return (
    <div className="relative mt-16 rounded-[28px] border border-slate-200/80 bg-white/95 shadow-[0_18px_60px_rgba(14,22,43,0.08)]">
      <div className="flex items-center gap-2 border-b border-slate-200 px-5 py-3">
        <span className="h-3 w-3 rounded-full bg-red-400" />
        <span className="h-3 w-3 rounded-full bg-amber-400" />
        <span className="h-3 w-3 rounded-full bg-lime-500" />
        <span className="ml-4 font-mono text-xs text-slate-400">meetingnotes.app</span>
      </div>

      <div className="grid min-h-[470px] grid-cols-1 lg:grid-cols-[1.05fr_2.5fr_1.15fr]">
        <aside className="space-y-4 border-b border-slate-200 bg-slate-50/40 p-4 lg:border-b-0 lg:border-r">
          <p className="text-center text-sm font-semibold text-slate-500">meeting-notes</p>
          <div className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-left text-sm text-slate-700">
            Home
          </div>
          <div className="h-10 rounded-xl border border-slate-200 bg-white" />
          <div className="rounded-xl bg-emerald-500 px-4 py-2 text-sm font-semibold text-white">New meeting</div>
          <div className="h-9 rounded-xl border border-slate-200 bg-white" />
          <div className="rounded-xl border border-emerald-400 bg-white px-4 py-3 text-left">
            <p className="text-sm font-semibold text-slate-900">f</p>
            <p className="mt-1 text-xs text-slate-400">2/24/2026</p>
          </div>
          <div className="h-6 w-full rounded-full bg-slate-200" />
          <div className="h-6 w-3/4 rounded-full bg-slate-200" />
        </aside>

        <section className="border-b border-slate-200 p-4 lg:border-b-0 lg:border-r">
          <h3 className="text-center text-2xl font-semibold text-slate-900">Chat</h3>
          <div className="mt-4 flex flex-wrap gap-2">
            <span className="rounded-full border border-slate-200 bg-white px-4 py-2 text-xs text-slate-600">
              What did we decide?
            </span>
            <span className="rounded-full border border-slate-200 bg-white px-4 py-2 text-xs text-slate-600">
              Action items & owners?
            </span>
            <span className="rounded-full border border-slate-200 bg-white px-4 py-2 text-xs text-slate-600">
              What&apos;s still unclear?
            </span>
          </div>

          <div className="mt-4 rounded-full border border-slate-300 bg-white px-4 py-2 text-center text-sm text-slate-700">
            What are the action items from yesterday&apos;s meeting?
          </div>

          <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-emerald-50/35">
            <div className="flex items-start gap-3 border-b border-slate-200 px-4 py-4">
              <CheckCheck className="mt-1 h-5 w-5 text-emerald-500" />
              <div className="space-y-2">
                <p className="text-sm text-slate-700">John will present the new project plan by next Monday.</p>
                <span className="inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500">
                  Budget Review Transcript @ 23:54
                </span>
              </div>
            </div>
            <div className="flex items-start gap-3 px-4 py-4">
              <CheckCheck className="mt-1 h-5 w-5 text-emerald-500" />
              <div className="space-y-2">
                <p className="text-sm text-slate-700">Sarah will compile the budget report by Friday.</p>
                <span className="inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-500">
                  Budget Review Transcript @ 23:54
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 rounded-2xl border border-slate-200 bg-white p-3">
            <div className="h-14 rounded-lg bg-slate-50" />
            <div className="mt-3 flex items-center justify-between">
              <span className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-600">Attach</span>
              <span className="rounded-full bg-emerald-500 px-4 py-1 text-xs font-semibold text-white">Send</span>
            </div>
          </div>
        </section>

        <aside className="space-y-4 p-4">
          <div className="flex items-center gap-2 text-xs">
            <span className="rounded-full bg-emerald-500 px-4 py-2 font-semibold text-white">Verify</span>
            <span className="text-slate-400">Tasks</span>
            <span className="text-slate-400">Issues</span>
            <span className="text-slate-400">Docs</span>
          </div>
          <h4 className="text-2xl font-semibold text-slate-900">Verify</h4>
          <p className="text-xs text-slate-500">Extracted action items from indexed meeting notes.</p>
          <div className="flex items-center gap-3">
            <span className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Run Verify</span>
            <span className="text-slate-400">...</span>
          </div>
          <div className="h-2 rounded-full bg-slate-200">
            <div className="h-full w-3/4 rounded-full bg-emerald-500" />
          </div>
          <div className="space-y-2 rounded-xl border border-slate-200 bg-white p-3">
            <p className="text-sm font-semibold text-slate-700">Action items</p>
            <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">Budget Review Transcript @ 23:54</div>
            <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">Budget Review Transcript @ 23:54</div>
          </div>
        </aside>
      </div>
    </div>
  );
}

export default function LandingPage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[#f4f8f9] text-slate-900">
      <div className="pointer-events-none absolute -left-10 top-[38rem] h-52 w-52 rounded-full bg-emerald-200/30 blur-[2px]" />
      <div className="pointer-events-none absolute -right-10 top-[30rem] h-40 w-40 rounded-full bg-emerald-200/25 blur-[2px]" />

      <section className="mx-auto max-w-7xl px-6 pb-12 pt-20 text-center md:pt-24">
        <h1 className="mx-auto max-w-5xl text-balance text-5xl font-semibold leading-[1.02] tracking-tight md:text-8xl">
          Turn meeting chaos
          <br />
          into{" "}
          <span className="relative text-emerald-500">
            clear action
            <span className="absolute bottom-1 left-0 h-3 w-full rounded-full bg-emerald-200/70 md:bottom-2 md:h-3.5" />
          </span>
        </h1>

        <p className="mx-auto mt-8 max-w-3xl text-balance text-2xl leading-relaxed text-slate-500">
          Upload transcripts, ask grounded questions, extract every decision and action item,{" "}
          <span className="font-semibold text-slate-700">all backed by exact citations.</span> No
          hallucinations, ever.
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Button asChild size="lg" className="h-14 rounded-2xl bg-emerald-500 px-10 text-lg hover:bg-emerald-600">
            <Link href="/workspace">
              Try the Demo <ArrowRight className="ml-2 h-5 w-5" />
            </Link>
          </Button>
          <Button asChild size="lg" variant="outline" className="h-14 rounded-2xl border-slate-300 px-10 text-lg">
            <Link href="https://github.com/Goku007007/meeting-notes" target="_blank" rel="noreferrer">
              View Source Code
            </Link>
          </Button>
        </div>

        <WorkspacePreview />
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-8 pt-10">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {metrics.map((metric) => {
            const Icon = metric.icon;
            return (
              <div
                key={metric.label}
                className="rounded-3xl border border-slate-200 bg-white/80 p-6 text-center shadow-sm"
              >
                <Icon className="mx-auto h-6 w-6 text-emerald-500" />
                <p className="mt-3 text-5xl font-semibold tracking-tight">{metric.value}</p>
                <p className="mt-1 text-xl text-slate-500">{metric.label}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-20">
        <p className="text-center text-sm font-semibold tracking-[0.22em] text-emerald-600 uppercase">
          Capabilities
        </p>
        <h2 className="mt-3 text-center text-6xl font-semibold tracking-tight">What it does</h2>
        <p className="mx-auto mt-4 max-w-3xl text-center text-3xl text-slate-500">
          Three steps. No fluff. Every answer grounded in your documents.
        </p>

        <div className="mt-12 grid gap-6 lg:grid-cols-3">
          {capabilities.map((capability) => {
            const Icon = capability.icon;
            return (
              <div
                key={capability.title}
                className="rounded-3xl border border-emerald-200/60 bg-emerald-50/40 p-8"
              >
                <div className="mb-6 inline-flex rounded-2xl bg-emerald-100 p-3 text-emerald-600">
                  <Icon className="h-7 w-7" />
                </div>
                <h3 className="text-4xl font-semibold tracking-tight">{capability.title}</h3>
                <p className="mt-3 text-2xl leading-relaxed text-slate-600">{capability.description}</p>
                <p className="mt-5 text-lg font-medium text-emerald-600">{capability.footnote}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-24">
        <div className="rounded-[30px] border border-slate-200 bg-white/85 p-8 shadow-sm md:p-14">
          <p className="text-center text-sm font-semibold tracking-[0.22em] text-emerald-600 uppercase">
            Getting Started
          </p>
          <h2 className="mt-2 text-center text-6xl font-semibold tracking-tight">How it works</h2>

          <div className="mx-auto mt-10 max-w-4xl space-y-8">
            {steps.map((step) => (
              <div key={step.number} className="grid gap-4 border-b border-slate-200 pb-8 md:grid-cols-[84px_1fr]">
                <div className="inline-flex h-20 w-20 items-center justify-center rounded-3xl bg-emerald-100 text-5xl font-semibold text-emerald-600">
                  {step.number}
                </div>
                <div>
                  <h3 className="text-5xl font-semibold tracking-tight">{step.title}</h3>
                  <p className="mt-3 text-3xl leading-relaxed text-slate-500">{step.description}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-12 text-center">
            <Button asChild size="lg" className="h-16 rounded-3xl bg-emerald-500 px-12 text-2xl hover:bg-emerald-600">
              <Link href="/workspace">
                Get Started Now <ArrowRight className="ml-3 h-6 w-6" />
              </Link>
            </Button>
          </div>
        </div>
      </section>
    </main>
  );
}
