import { useState } from "react";
import type { CategoryRow } from "../derive";
import { UNCATEGORIZED } from "../derive";
import { dollars, monthName, percent } from "../format";

interface Props {
  month: string;
  rows: CategoryRow[];
  totalCents: number;
}

const SIZE = 200;
const R = 78;
const STROKE = 26;
const CIRC = 2 * Math.PI * R;
const GAP = 2.5; // px of surface color between segments

export function colorVar(row: CategoryRow): string {
  if (row.slot !== null) return `var(--c${row.slot + 1})`;
  return row.name === UNCATEGORIZED ? "var(--c-uncat)" : "var(--c-other)";
}

export function Categories({ month, rows, totalCents }: Props) {
  const [active, setActive] = useState<string | null>(null);
  const current = rows.find((r) => r.name === active) ?? null;

  let offset = 0;
  const segments = rows.map((row) => {
    const length = row.share * CIRC;
    const seg = { row, length: Math.max(length - (rows.length > 1 ? GAP : 0), 0.5), offset };
    offset += length;
    return seg;
  });

  return (
    <section className="card" aria-labelledby="cat-title">
      <header className="card-head">
        <h2 id="cat-title">Where your money went</h2>
      </header>
      {rows.length === 0 ? (
        <p className="empty">No spending recorded for {monthName(month)}.</p>
      ) : (
        <div className="cat-layout">
          <div className="donut" onPointerLeave={() => setActive(null)}>
            <svg viewBox={`0 0 ${SIZE} ${SIZE}`} role="img" aria-label={`${monthName(month)} spending by category. The table beside this chart lists every amount.`}>
              <g transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}>
                {segments.map(({ row, length, offset: o }) => (
                  <circle
                    key={row.name}
                    cx={SIZE / 2}
                    cy={SIZE / 2}
                    r={R}
                    fill="none"
                    stroke={colorVar(row)}
                    strokeWidth={active === row.name ? STROKE + 4 : STROKE}
                    strokeDasharray={`${length} ${CIRC - length}`}
                    strokeDashoffset={-o}
                    opacity={active && active !== row.name ? 0.35 : 1}
                    onPointerEnter={() => setActive(row.name)}
                  />
                ))}
              </g>
            </svg>
            <div className="donut-center" aria-live="polite">
              <span className="donut-value">{dollars(current ? current.cents : totalCents)}</span>
              <span className="donut-label">{current ? `${current.name}, ${percent(current.share)}` : "Total"}</span>
            </div>
          </div>
          <table className="cat-table">
            <caption className="sr-only">Spending by category for {monthName(month)}</caption>
            <thead>
              <tr><th scope="col">Category</th><th scope="col" className="num">Share</th><th scope="col" className="num">Spent</th></tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.name}
                  className={active === row.name ? "active" : ""}
                  onPointerEnter={() => setActive(row.name)}
                  onPointerLeave={() => setActive(null)}
                >
                  <th scope="row"><span className="swatch box" style={{ background: colorVar(row) }} aria-hidden="true" />{row.name}</th>
                  <td className="num">{percent(row.share)}</td>
                  <td className="num">{dollars(row.cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
