import type { Pace } from "../derive";
import { dollars, monthName, signedDollars } from "../format";
import { previousMonth } from "../derive";

interface Props {
  month: string;
  pace: Pace;
  count: number;
}

export function TotalSpentCard({ month, pace, count }: Props) {
  const prev = monthName(previousMonth(month));
  const { deltaCents } = pace;
  let comparison = `No ${prev} data to compare with`;
  let tone = "flat";
  if (deltaCents !== null) {
    tone = deltaCents > 0 ? "up" : deltaCents < 0 ? "down" : "flat";
    const words = deltaCents === 0 ? "the same as" : deltaCents > 0 ? "more than" : "less than";
    comparison = `${signedDollars(deltaCents)}, ${words} ${prev} by this point`;
  }
  return (
    <section className="card hero" aria-labelledby="hero-title">
      <h2 id="hero-title" className="hero-title">Total spent in {monthName(month)}</h2>
      <p className="hero-number" data-testid="total-spent">{dollars(pace.totalCents)}</p>
      <p className={`hero-delta ${tone}`}>{comparison}</p>
      <dl className="hero-facts">
        <div>
          <dt>Per day</dt>
          <dd>{dollars(pace.perDayCents)}</dd>
        </div>
        <div>
          <dt>Transactions</dt>
          <dd>{count}</dd>
        </div>
      </dl>
    </section>
  );
}
