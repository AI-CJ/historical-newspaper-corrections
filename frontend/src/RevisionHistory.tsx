import {useEffect, useState} from "react";

type Revision = {
  version: number;
  saved_at: string;
  transcription: string;
};

const formatTime = new Intl.DateTimeFormat(undefined, {
  year: "numeric", month: "short", day: "numeric",
  hour: "numeric", minute: "2-digit", second: "2-digit", timeZoneName: "short"
});

function SavedRevisions({blockId}: {blockId: number}) {
  const [revisions, setRevisions] = useState<Revision[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch(`/blocks/${blockId}/revisions`, {signal: controller.signal});
        if (!response.ok) throw new Error("History request failed");
        const rows: Revision[] = await response.json();
        if (!controller.signal.aborted) setRevisions(rows);
      } catch {
        if (!controller.signal.aborted) setFailed(true);
      }
    }
    void load();
    return () => controller.abort();
  }, [blockId]);

  if (failed) return <p role="alert">Could not load history. Close and reopen it to retry.</p>;
  if (!revisions) return <p>Loading history…</p>;
  if (!revisions.length) return <p>No saved corrections for this passage.</p>;
  return <ol className="revisions">
    {revisions.map(revision => <li key={revision.version}>
      <strong>Version {revision.version}</strong>{" · "}
      <time dateTime={revision.saved_at}>{formatTime.format(new Date(revision.saved_at))}</time>
      <pre>{revision.transcription}</pre>
    </li>)}
  </ol>;
}

export function RevisionHistory({blockId, version}: {blockId: number; version: number}) {
  const [open, setOpen] = useState(false);
  return <details className="history" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Revision history</summary>
    {open && <SavedRevisions key={version} blockId={blockId}/>}
  </details>;
}
