import { useMemo, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { DailySpend } from "../api";
import { cumulative, daysInMonth, previousMonth } from "../derive";
import { dollars, monthName } from "../format";
import { useWidth } from "../hooks/useWidth";

interface Props {
  month: string;
  elapsedDays: number;
  dailyThis: DailySpend[];
  dailyPrev: DailySpend[];
}

const HEIGHT = 280;
const M = { top: 12, right: 16, bottom: 28, left: 52 };

function niceMax(cents: number): { max: number; step: number } {
  const d = Math.max(cents / 100, 10);
  const raw = d / 4;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((f) => f * mag).find((s) => s >= raw) ?? mag * 10;
  return { max: step * Math.ceil(d / step) * 100, step: step * 100 };
}

export function CumulativeChart({ month, elapsedDays, dailyThis, dailyPrev }: Props) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const [asTable, setAsTable] = useState(false);
  const prev = previousMonth(month);
  const days = daysInMonth(month);

  const thisRun = useMemo(() => cumulative(dailyThis, month, elapsedDays), [dailyThis, month, elapsedDays]);
  const prevRun = useMemo(() => cumulative(dailyPrev, prev, daysInMonth(prev)), [dailyPrev, prev]);
  const hasPrev = dailyPrev.length > 0;

  const lastThis = thisRun.filter((v): v is number => v !== null).at(-1) ?? 0;
  const lastPrev = hasPrev ? (prevRun.at(-1) ?? 0) : 0;
  const { max, step } = niceMax(Math.max(lastThis, lastPrev));

  const plotW = width - M.left - M.right;
  const plotH = HEIGHT - M.top - M.bottom;
  const x = (day: number) => M.left + ((day - 1) / Math.max(days - 1, 1)) * plotW;
  const y = (cents: number) => M.top + plotH - (cents / max) * plotH;

  const path = (run: (number | null)[], limit: number) => {
    let d = "";
    run.forEach((v, i) => {
      if (v === null || i + 1 > limit) return;
      d += `${d ? "L" : "M"}${x(i + 1).toFixed(1)},${y(v).toFixed(1)}`;
    });
    return d;
  };

  const ticks: number[] = [];
  for (let t = 0; t <= max; t += step) ticks.push(t);
  const xTicks = [1, 8, 15, 22, days].filter((d, i, a) => a.indexOf(d) === i && d <= days);

  const dayFromPointer = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - box.left - M.left) / plotW;
    return Math.min(days, Math.max(1, Math.round(ratio * (days - 1)) + 1));
  };
  const onKey = (e: KeyboardEvent<SVGSVGElement>) => {
    if (e.key === "ArrowRight") setHover((h) => Math.min(days, (h ?? 0) + 1));
    else if (e.key === "ArrowLeft") setHover((h) => Math.max(1, (h ?? days + 1) - 1));
    else if (e.key === "Escape") setHover(null);
    else return;
    e.preventDefault();
  };

  const thisName = monthName(month);
  const prevName = monthName(prev);
  const hv = hover !== null ? thisRun[hover - 1] : null;
  const hp = hover !== null && hasPrev ? prevRun[hover - 1] : null;
  const tipLeft = hover !== null ? Math.min(Math.max(x(hover) + 12, 8), width - 190) : 0;

  return (
    <section className="card" aria-labelledby="cum-title">
      <header className="card-head">
        <h2 id="cum-title">Cumulative spending</h2>
        <button type="button" className="link-btn" onClick={() => setAsTable((v) => !v)} aria-pressed={asTable}>
          {asTable ? "Show chart" : "Show table"}
        </button>
      </header>
      <ul className="legend" aria-label="Chart legend">
        <li><span className="swatch line this" aria-hidden="true" />{thisName}</li>
        {hasPrev && <li><span className="swatch line prev" aria-hidden="true" />{prevName}</li>}
      </ul>
      {asTable ? (
        <div className="table-wrap" tabIndex={0}>
          <table>
            <caption className="sr-only">Running total of spending by day</caption>
            <thead>
              <tr><th scope="col">Day</th><th scope="col" className="num">{thisName}</th>{hasPrev && <th scope="col" className="num">{prevName}</th>}</tr>
            </thead>
            <tbody>
              {thisRun.map((v, i) => (
                <tr key={i}>
                  <th scope="row">{i + 1}</th>
                  <td className="num">{v === null ? "" : dollars(v)}</td>
                  {hasPrev && <td className="num">{prevRun[i] === undefined ? "" : dollars(prevRun[i] as number)}</td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div ref={ref} className="chart-box">
          <svg
            width={width}
            height={HEIGHT}
            role="img"
            tabIndex={0}
            aria-label={`Running total for ${thisName}: ${dollars(lastThis)} so far${hasPrev ? `, compared with ${dollars(lastPrev)} for all of ${prevName}` : ""}. Use left and right arrow keys to read each day.`}
            onPointerMove={(e) => setHover(dayFromPointer(e))}
            onPointerLeave={() => setHover(null)}
            onKeyDown={onKey}
            onBlur={() => setHover(null)}
          >
            {ticks.map((t) => (
              <g key={t}>
                <line className="gl" x1={M.left} x2={width - M.right} y1={y(t)} y2={y(t)} />
                <text className="axis" x={M.left - 8} y={y(t) + 4} textAnchor="end">{dollars(t)}</text>
              </g>
            ))}
            {xTicks.map((d) => (
              <text key={d} className="axis" x={x(d)} y={HEIGHT - 8} textAnchor={d === 1 ? "start" : d === days ? "end" : "middle"}>{d}</text>
            ))}
            {hasPrev && <path className="series prev" d={path(prevRun, days)} />}
            <path className="series this" d={path(thisRun, elapsedDays)} />
            {hover !== null && (
              <g>
                <line className="crosshair" x1={x(hover)} x2={x(hover)} y1={M.top} y2={M.top + plotH} />
                {hp !== null && hp !== undefined && <circle className="dot prev" cx={x(hover)} cy={y(hp)} r={4} />}
                {hv !== null && hv !== undefined && <circle className="dot this" cx={x(hover)} cy={y(hv)} r={5} />}
              </g>
            )}
          </svg>
          {hover !== null && (
            <div className="tooltip" style={{ left: tipLeft, top: M.top }} role="status">
              <strong>{thisName} {hover}</strong>
              <span><i className="swatch dot this" aria-hidden="true" />{thisName}: {hv === null || hv === undefined ? "no data yet" : dollars(hv)}</span>
              {hp !== null && hp !== undefined && <span><i className="swatch dot prev" aria-hidden="true" />{prevName}: {dollars(hp)}</span>}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
