import { useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, type ImportResult } from "../api";

interface Props {
  open: boolean;
  onClose: () => void;
  onImported: () => void;
}

export function ImportDialog({ open, onClose, onImported }: Props) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [year, setYear] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);

  useEffect(() => {
    const el = dialog.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const parsedYear = year.trim() ? Number(year) : undefined;
      setResult(await api.importCsv(file, parsedYear));
      onImported();
    } catch (err) {
      setError(err instanceof ApiError ? err : new ApiError("Import failed.", null));
    } finally {
      setBusy(false);
    }
  };

  return (
    <dialog ref={dialog} className="dialog" onClose={onClose} aria-labelledby="import-title">
      <form onSubmit={submit}>
        <h2 id="import-title">Import a statement</h2>
        <p className="muted">Choose a CSV with date, description and amount columns. Dates like 09/29 need a year below.</p>
        <label className="field">
          <span>CSV file</span>
          <input type="file" accept=".csv,text/csv" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        <label className="field">
          <span>Year for dates without one</span>
          <input type="number" inputMode="numeric" min={2000} max={2100} placeholder="Optional, e.g. 2026" value={year} onChange={(e) => setYear(e.target.value)} />
        </label>
        {error && (
          <div className="notice error" role="alert">
            <p>{error.message}</p>
            {error.rowErrors.length > 0 && (
              <ul>
                {error.rowErrors.slice(0, 5).map((r) => <li key={r.line}>Line {r.line}: {r.message}</li>)}
              </ul>
            )}
          </div>
        )}
        {result && (
          <div className="notice ok" role="status">
            <p>Imported {result.imported} transactions and categorized {result.categorized}.{result.skipped_rows > 0 ? ` ${result.skipped_rows} rows were skipped.` : ""}</p>
            {result.warning && <p>{result.warning}</p>}
          </div>
        )}
        <div className="dialog-actions">
          <button type="button" className="btn ghost" onClick={onClose}>{result ? "Done" : "Cancel"}</button>
          <button type="submit" className="btn primary" disabled={!file || busy}>{busy ? "Importing..." : "Import"}</button>
        </div>
      </form>
    </dialog>
  );
}
