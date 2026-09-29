import { PageHeader } from "../components/ui";
import ReportBuilder from "./research/ReportBuilder";

export default function Reports({ pid }: { pid: string }) {
  return (
    <div className="stack">
      <PageHeader eyebrow="Reports" title="Reports that cite their evidence"
        description="Every statement links to an evidence record. Drafts are labeled, model-written wording is marked, and a finalized report is locked." />
      <ReportBuilder pid={pid} kinds={["research_report", "executive_summary", "decision_memo", "methods_appendix", "experiment_brief"]} />
    </div>
  );
}
