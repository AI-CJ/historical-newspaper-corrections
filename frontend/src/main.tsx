import {useEffect, useState} from "react";
import {createRoot} from "react-dom/client";
import sample from "../../data/evening-star-1870-01-01.json";
import {RevisionHistory} from "./RevisionHistory";
import "./style.css";

type Page = {
  id: number; title: string; issue_date: string; page_number: number;
  scan_url: string; catalog_url: string;
};
type Block = {
  id: number; position: number; original_text: string; transcription: string; version: number;
};
type Detail = Page & {blocks: Block[]};
type Conflict = {current_text: string; current_version: number};

async function read<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error("Could not load the newspaper page.");
  return response.json();
}

function Scan({page}: {page: Page}) {
  const [zoom, setZoom] = useState(false);
  const [failed, setFailed] = useState(false);
  return <section aria-label="Newspaper scan">
    <header><h2>Page scan</h2><button disabled={failed} aria-pressed={zoom}
      onClick={() => setZoom(!zoom)}>{zoom ? "Fit page" : "Enlarge scan"}</button></header>
    <div className="scan" tabIndex={0} aria-label="Scrollable scan">
      {failed ? <p>The scan could not load. Open the source below to view the original.</p> :
        <img className={zoom ? "enlarged" : ""} src={page.scan_url === sample.scan_url ? "./scans/evening-star-1870-01-01.webp" : page.scan_url}
          alt={page.title + ", page " + page.page_number} onError={() => setFailed(true)}/>}
    </div>
    <a href={page.catalog_url} target="_blank" rel="noreferrer">View at the Library of Congress ↗</a>
  </section>;
}

function Workspace({page, catalog}: {page: Detail; catalog: Page[]}) {
  const [blocks, setBlocks] = useState(page.blocks);
  const [index, setIndex] = useState(0);
  const block = blocks[index];
  const [draft, setDraft] = useState(block?.transcription ?? "");
  const [conflict, setConflict] = useState<Conflict | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const dirty = !!block && draft !== block.transcription;

  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  function selectPassage(next: number) {
    if (dirty && !window.confirm("Discard your unsaved passage changes?")) return;
    setIndex(next);
    setDraft(blocks[next].transcription);
    setConflict(null);
    setNotice("");
  }

  function updateBlock(version: number, transcription: string) {
    setBlocks(previous => previous.map(b => b.id === block.id ? {...b, version, transcription} : b));
  }

  async function save() {
    setBusy(true);
    setNotice("");
    try {
      const response = await fetch(`/blocks/${block.id}/revisions`, {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({base_version: block.version, transcription: draft})
      });
      if (response.status === 409) {
        setConflict((await response.json()).detail);
        return;
      }
      if (!response.ok) throw new Error("Save failed. Your draft is still here.");
      const revision = await response.json();
      updateBlock(revision.version, revision.transcription);
      setNotice(`Saved version ${revision.version}.`);
    } catch {
      setNotice("Could not confirm the save. Your draft is still here.");
    } finally {
      setBusy(false);
    }
  }

  return <main>
    <div className="title"><p>Newspaper transcription desk</p><h1>{page.title}</h1>
      <span>{page.issue_date} · Page {page.page_number}</span>
      <a href={`/pages/${page.id}/export`} download>Download saved text</a>
      {catalog.length > 1 && <label>Newspaper page <select disabled={busy} value={page.id}
        onChange={e => location.assign("?page=" + e.target.value)}>
        {catalog.map(p => <option key={p.id} value={p.id}>{p.title} · {p.issue_date} · Page {p.page_number}</option>)}
      </select></label>}
    </div>
    <div className="columns"><Scan page={page}/>
      <section aria-label="Passage editor"><header><h2>Transcription</h2>
        {block && <select aria-label="Passage" value={index} disabled={busy}
          onChange={e => selectPassage(Number(e.target.value))}>
          {blocks.map((b, i) => <option key={b.id} value={i}>Passage {b.position} of {blocks.length}</option>)}
        </select>}</header>
        {block ? <>
          <h3>Original OCR</h3><pre>{block.original_text}</pre>
          <label htmlFor="draft">Corrected transcription</label>
          <textarea id="draft" value={draft} disabled={busy} onChange={e => {
            setDraft(e.target.value); setNotice("");
          }}/>
          {conflict && <aside role="alert"><strong>Another edit was saved.</strong>
            <p>Compare your draft with saved version {conflict.current_version}.</p>
            <pre>{conflict.current_text}</pre>
            <button onClick={() => {
              updateBlock(conflict.current_version, conflict.current_text);
              setConflict(null); setNotice("Review your draft before saving.");
            }}>Continue with my draft</button>
          </aside>}
          <div className="actions"><button className="save" onClick={save}
            disabled={busy || !!conflict || !dirty || !draft.trim()}>{busy ? "Saving…" : "Save correction"}</button>
            <span>Version {block.version}</span></div>
          <p role="status">{notice}</p>
          <RevisionHistory key={block.id} blockId={block.id}
            version={conflict?.current_version ?? block.version}/>
        </> : <p>This page has no OCR passages.</p>}
      </section>
    </div>
  </main>;
}

async function start() {
  const root = createRoot(document.getElementById("root")!);
  root.render(<main>Loading newspaper…</main>);
  try {
    const catalog = await read<Page[]>("/pages");
    if (!catalog.length) {
      root.render(<main>No newspaper pages have been imported.</main>);
      return;
    }
    const selected = new URLSearchParams(location.search).get("page") ?? catalog[0].id;
    const page = await read<Detail>("/pages/" + encodeURIComponent(selected));
    root.render(<Workspace page={page} catalog={catalog}/>);
  } catch {
    root.render(<main role="alert">Could not open the newspaper. <a href="./">Open the first page</a></main>);
  }
}
void start();
