import type { Transaction } from "../api";
import { dollarsExact, shortDate } from "../format";

const SOURCE_LABEL: Record<Transaction["category_source"], string> = {
  none: "",
  rules: "Rule",
  model: "Model",
  user: "You",
};

export function TransactionsTable({ rows }: { rows: Transaction[] }) {
  return (
    <section className="card" id="transactions" aria-labelledby="tx-title">
      <header className="card-head">
        <h2 id="tx-title">Recent transactions</h2>
      </header>
      {rows.length === 0 ? (
        <p className="empty">Nothing here yet. Import a statement to see your transactions.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Description</th>
                <th scope="col">Category</th>
                <th scope="col" className="num">Amount</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((t) => (
                <tr key={t.id}>
                  <td>{shortDate(t.posted_on)}</td>
                  <td className="desc">{t.description}</td>
                  <td>
                    {t.category ?? <span className="muted">Uncategorized</span>}
                    {SOURCE_LABEL[t.category_source] && <span className="tag" title="How this category was chosen">{SOURCE_LABEL[t.category_source]}</span>}
                  </td>
                  <td className="num">{t.amount_cents > 0 ? "+" : ""}{t.amount_cents < 0 ? "-" : ""}{dollarsExact(t.amount_cents)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
