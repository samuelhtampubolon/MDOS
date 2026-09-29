import { useMemo, useState, type FormEvent } from "react";
import { api, download, errorMessage } from "../../api/client";
import { useProjectMutation, useResearch, useSurvey } from "../../api/hooks";
import type { Question, Survey } from "../../api/types";
import { Badge, Callout, Card, Empty, Icon, StatusBadge, useToast } from "../../components/ui";

type Lang = "en" | "id" | "both";

const QTYPE_LABELS: Record<string, string> = {
  single: "Single choice", multi: "Multiple choice", likert: "Likert scale", numeric: "Number", text: "Open text",
  price: "Price", info: "Information",
};

const EXPORTS = [
  { format: "xlsform", label: "XLSForm", hint: "For KoboToolbox and ODK", file: "survey_xlsform.xlsx" },
  { format: "markdown", label: "Printable (Markdown)", hint: "Bilingual paper or review copy", file: "survey.md" },
  { format: "codebook", label: "Codebook (CSV)", hint: "Variable names, labels and codes", file: "codebook.csv" },
];

export default function Questionnaire({ pid }: { pid: string }) {
  const { data: research } = useResearch(pid);
  const sid = research?.surveys[0]?.id;
  const { data: survey } = useSurvey(pid, sid);
  const [lang, setLang] = useState<Lang>("both");
  const sections = useMemo(() => {
    const groups: { name: string; questions: Question[] }[] = [];
    for (const q of [...(survey?.questions ?? [])].sort((a, b) => a.position - b.position)) {
      const last = groups[groups.length - 1];
      if (last && last.name === (q.section || "General")) last.questions.push(q);
      else groups.push({ name: q.section || "General", questions: [q] });
    }
    return groups;
  }, [survey]);
  if (!research) return null;
  if (!sid) {
    return <Empty title="No questionnaire yet">The Questionnaire agent drafts a bilingual survey when you run the design agents and approve the package.</Empty>;
  }
  if (!survey) return null;
  return (
    <div className="stack">
      <SurveyHeader pid={pid} survey={survey} />
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="tabs" role="tablist" aria-label="Question language" style={{ marginBottom: 0 }}>
          {([["both", "English and Indonesian"], ["en", "English"], ["id", "Bahasa Indonesia"]] as [Lang, string][]).map(([k, label]) => (
            <button key={k} role="tab" aria-selected={lang === k} className={`tab ${lang === k ? "active" : ""}`} onClick={() => setLang(k)}>{label}</button>
          ))}
        </div>
        <span className="small muted">{survey.questions.length} questions in {sections.length} sections</span>
      </div>
      {sections.map((s) => (
        <Card key={s.name} title={s.name} subtitle={`${s.questions.length} question${s.questions.length === 1 ? "" : "s"}`}>
          <div className="stack">
            {s.questions.map((q) => <QuestionRow key={q.id} pid={pid} survey={survey} q={q} lang={lang} />)}
          </div>
        </Card>
      ))}
      {survey.status === "draft" && <AddQuestion pid={pid} survey={survey} sections={sections.map((s) => s.name)} />}
    </div>
  );
}

function SurveyHeader({ pid, survey }: { pid: string; survey: Survey }) {
  const toast = useToast();
  const setStatus = useProjectMutation(pid, (status: string) => api.patch(`/projects/${pid}/surveys/${survey.id}`, { status }));
  const change = (status: string, message: string) =>
    setStatus.mutate(status, { onSuccess: () => toast(message), onError: (e) => toast(errorMessage(e), "error") });
  const exportAs = async (format: string, file: string) => {
    try {
      await download(`/projects/${pid}/surveys/${survey.id}/export?format=${format}`, file);
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  };
  return (
    <Card title={survey.title} subtitle={`Version ${survey.version} · languages: ${survey.languages.join(", ").toUpperCase()}`}
      actions={<StatusBadge status={survey.status} />}>
      <div className="grid grid-2">
        <div className="stack-sm">
          <div><div className="small muted">Introduction</div><div className="secondary">{survey.introduction}</div></div>
          <div><div className="small muted">Consent</div><div className="secondary small">{survey.consent_text}</div></div>
          {survey.status === "draft" ? (
            <Callout tone="warning">
              Pilot the questionnaire with 5 to 10 people from the target population, fix unclear wording, then approve it.
              Have a native speaker check the Indonesian wording before fieldwork.
              <div style={{ marginTop: 8 }}>
                <button className="btn sm good" disabled={setStatus.isPending} onClick={() => change("approved", "Questionnaire approved for fieldwork.")}>
                  <Icon name="check" size={12} />Approve after pilot</button>
              </div>
            </Callout>
          ) : survey.status === "approved" ? (
            <div className="row">
              <button className="btn sm" onClick={() => change("fielded", "Marked as in the field.")}>Mark as in the field</button>
              <button className="btn sm ghost" onClick={() => change("draft", "Back to draft. Editing is enabled.")}>Return to draft</button>
            </div>
          ) : survey.status === "fielded" ? (
            <button className="btn sm" onClick={() => change("closed", "Fieldwork closed.")}>Close fieldwork</button>
          ) : null}
        </div>
        <div className="stack-sm">
          <div className="small muted">Export</div>
          {EXPORTS.map((e) => (
            <div key={e.format} className="row" style={{ justifyContent: "space-between" }}>
              <div>
                <div style={{ fontWeight: 600 }}>{e.label}</div>
                <div className="small muted">{e.hint}</div>
              </div>
              <button className="btn sm" onClick={() => exportAs(e.format, e.file)}><Icon name="download" size={14} />Download</button>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}

function QuestionRow({ pid, survey, q, lang }: { pid: string; survey: Survey; q: Question; lang: Lang }) {
  const toast = useToast();
  const remove = useProjectMutation(pid, () => api.del(`/projects/${pid}/surveys/${survey.id}/questions/${q.id}`));
  const scale = q.scale as { min?: number; max?: number; labels?: string[]; labels_id?: string[]; currency?: string };
  const logic = q.logic as { terminate_if?: string; relevant?: string; show_if?: string };
  const showEn = lang !== "id";
  const showId = lang !== "en" && q.text_id;
  return (
    <div className="list-item" style={{ alignItems: "flex-start" }}>
      <code className="chip" style={{ minWidth: 92, justifyContent: "center" }}>{q.code}</code>
      <div className="grow stack-sm">
        {showEn && <div>{q.text}</div>}
        {showId && <div className={showEn ? "secondary" : ""} lang="id">{q.text_id}</div>}
        {q.options.length > 0 && (
          <div className="row" style={{ gap: 4 }}>
            {q.options.map((o) => (
              <span key={o.value} className="chip" title={`Stored as ${o.value}`}>
                {lang === "id" ? o.label_id ?? o.label : o.label}{lang === "both" && o.label_id && o.label_id !== o.label ? ` / ${o.label_id}` : ""}
              </span>
            ))}
          </div>
        )}
        {q.qtype === "likert" && scale.labels && (
          <div className="small muted">
            {scale.min} = {lang === "id" ? scale.labels_id?.[0] : scale.labels[0]} … {scale.max} = {lang === "id" ? scale.labels_id?.[scale.labels.length - 1] : scale.labels[scale.labels.length - 1]}
          </div>
        )}
        {(q.qtype === "numeric" || q.qtype === "price") && (scale.min !== undefined || scale.max !== undefined) && (
          <div className="small muted">Accepts {scale.currency ? `${scale.currency} ` : ""}{scale.min ?? "any"} to {scale.max ?? "any"}</div>
        )}
        {(logic.terminate_if || logic.relevant || logic.show_if) && (
          <div className="small" style={{ color: "var(--warning-text)" }}>
            <Icon name="flag" size={12} /> {logic.terminate_if ? `Ends the survey if the answer is "${logic.terminate_if}"` : `Shown when ${logic.relevant ?? logic.show_if}`}
          </div>
        )}
      </div>
      <div className="stack-sm" style={{ alignItems: "flex-end" }}>
        <Badge>{QTYPE_LABELS[q.qtype] ?? q.qtype}</Badge>
        {q.construct_code && <span className="small muted">Construct {q.construct_code}</span>}
        {!q.required && q.qtype !== "info" && <span className="small muted">Optional</span>}
        {survey.status === "draft" && (
          <button className="btn ghost sm icon" aria-label={`Delete question ${q.code}`}
            onClick={() => window.confirm(`Delete question ${q.code}?`) && remove.mutate(undefined, { onError: (e) => toast(errorMessage(e), "error") })}>
            <Icon name="trash" size={14} />
          </button>
        )}
      </div>
    </div>
  );
}

function AddQuestion({ pid, survey, sections }: { pid: string; survey: Survey; sections: string[] }) {
  const toast = useToast();
  const empty = { code: "", section: sections[0] ?? "", qtype: "single", text: "", text_id: "", options: "", required: true, scaleMax: 5 };
  const [form, setForm] = useState(empty);
  const add = useProjectMutation(pid, (body: Record<string, unknown>) => api.post(`/projects/${pid}/surveys/${survey.id}/questions`, body));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    const options = form.options.split("\n").map((line) => line.trim()).filter(Boolean).map((line) => {
      const [value, label, labelId] = line.split("|").map((s) => s.trim());
      return { value, label: label || value, label_id: labelId || label || value };
    });
    const scale = form.qtype === "likert"
      ? { min: 1, max: form.scaleMax, labels: form.scaleMax === 5 ? ["Strongly disagree", "Disagree", "Neutral", "Agree", "Strongly agree"] : undefined,
          labels_id: form.scaleMax === 5 ? ["Sangat tidak setuju", "Tidak setuju", "Netral", "Setuju", "Sangat setuju"] : undefined }
      : {};
    add.mutate({ code: form.code, section: form.section, qtype: form.qtype, text: form.text, text_id: form.text_id, options, scale, required: form.required }, {
      onSuccess: () => { toast(`Question ${form.code} added.`); setForm({ ...empty, section: form.section }); },
      onError: (err) => toast(errorMessage(err), "error"),
    });
  };
  const needsOptions = form.qtype === "single" || form.qtype === "multi";
  return (
    <Card title="Add a question" subtitle="Codes become variable names in the data, so keep them short, lowercase and stable.">
      <form className="stack-sm" onSubmit={submit}>
        <div className="grid grid-3">
          <div className="field"><label htmlFor="q-code">Code</label>
            <input id="q-code" className="input" required pattern="[A-Za-z][A-Za-z0-9_]*" placeholder="visit_reason" value={form.code}
              onChange={(e) => setForm({ ...form, code: e.target.value })} /></div>
          <div className="field"><label htmlFor="q-section">Section</label>
            <input id="q-section" className="input" list="q-sections" value={form.section} onChange={(e) => setForm({ ...form, section: e.target.value })} />
            <datalist id="q-sections">{sections.map((s) => <option key={s} value={s} />)}</datalist></div>
          <div className="field"><label htmlFor="q-type">Type</label>
            <select id="q-type" className="select" value={form.qtype} onChange={(e) => setForm({ ...form, qtype: e.target.value })}>
              {Object.entries(QTYPE_LABELS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select></div>
        </div>
        <div className="grid grid-2">
          <div className="field"><label htmlFor="q-text">Question (English)</label>
            <textarea id="q-text" className="textarea" required value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} /></div>
          <div className="field"><label htmlFor="q-text-id">Question (Bahasa Indonesia)</label>
            <textarea id="q-text-id" className="textarea" lang="id" value={form.text_id} onChange={(e) => setForm({ ...form, text_id: e.target.value })} /></div>
        </div>
        {needsOptions && (
          <div className="field"><label htmlFor="q-options">Options, one per line</label>
            <textarea id="q-options" className="textarea" placeholder={"Ya | Yes | Ya\nTidak | No | Tidak"} value={form.options}
              onChange={(e) => setForm({ ...form, options: e.target.value })} />
            <span className="hint">Format: stored value | English label | Indonesian label.</span></div>
        )}
        {form.qtype === "likert" && (
          <div className="field" style={{ maxWidth: 200 }}><label htmlFor="q-scale">Scale points</label>
            <select id="q-scale" className="select" value={form.scaleMax} onChange={(e) => setForm({ ...form, scaleMax: Number(e.target.value) })}>
              <option value={5}>1 to 5</option><option value={7}>1 to 7</option>
            </select></div>
        )}
        <label className="checkbox"><input type="checkbox" checked={form.required} onChange={(e) => setForm({ ...form, required: e.target.checked })} />Required</label>
        <div><button className="btn primary" disabled={add.isPending}><Icon name="plus" size={14} />Add question</button></div>
      </form>
    </Card>
  );
}
