import { useGraph } from "../api/hooks";
import { LineageGraph } from "../components/LineageGraph";
import { Card, PageHeader } from "../components/ui";
import DataWorkspace from "./research/DataWorkspace";

export default function DataPage({ pid }: { pid: string }) {
  const { data: graph } = useGraph(pid);
  return (
    <div className="stack">
      <PageHeader eyebrow="Data" title="Datasets, versions and lineage"
        description="Upload survey responses, reviews or sales data. Every cleaning step creates a new version, and every result traces back to the version it came from." />
      <DataWorkspace pid={pid} />
      {graph && graph.nodes.some((n) => n.kind === "dataset") && (
        <Card>
          <LineageGraph data={graph} title="Data lineage" only={["dataset", "dataset_version", "analysis", "evidence"]}
            subtitle="From each upload through its versions to the analyses and evidence built on it. Click an item to trace it." />
        </Card>
      )}
    </div>
  );
}
