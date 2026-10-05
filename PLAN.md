# Garment Manufacturing Leakage Analytics: SaaS Plan

A multi-tenant platform that ingests a garment factory's operational and financial
data, computes efficiency and cost metrics across the full production flow, and
produces a report that says what is healthy, what is leaking money, and what to
improve. One codebase serves N clients; each client only uploads their data and
reads their report.

---

## 1. The process (expanded from the paper)

Your paper maps the real flow. Expanded with the decision points and the data each
stage produces:

| # | Stage | What happens | Key question / planning | Data it produces |
|---|-------|--------------|------------------------|------------------|
| 1 | Enquiry | Customer asks for a quote | Can we make it, at what price, by when? | Enquiry count, quoted price, quoted lead time |
| 2 | PO / Order | Enquiry converts to a confirmed order | Which enquiries convert? Why do we lose the rest? | Order value, style, quantity, due date |
| 3 | Sales | Order booked into the system | Is the margin we quoted still real? | Booked margin, customer, order terms |
| 4 | PPC (Production Planning & Control) | Capacity check, material plan, line allocation, schedule | Do we have fabric, machines, hours? Which line, which week? | Planned output, planned material, line load |
| 5 | Production | Cutting, stitching, assembly | Are we hitting planned output? Where is the bottleneck? | Actual output/hour, WIP, machine hours, labour hours |
| 6 | Further process | Washing, printing, embroidery, finishing | In-house or outsourced? Cost and delay of each | Process cost, rejection at each step |
| 7 | Quality | Inspection, rework, rejection | How many defects per hundred units? | Defect rate (DHU), rework hours, reject count |
| 8 | Dispatch | Packing, shipping | Are we shipping on time and complete? | Dispatch date vs due date, short-ship count |
| 9 | Bill | Invoice raised | Does the invoice match the order? | Invoiced amount, discounts, deductions |
| 10 | Accounts | Payment, receivables | Are we actually getting paid, on time? | Received amount, outstanding, days-to-pay |
| 11 | P&L | Cost vs revenue per order and per period | Where did the quoted margin go? | Actual cost breakdown, realized margin |

Cost formula from the paper, made measurable:

```
Selling price = Raw Material + Labour + Electricity + Machinery + Wastage + Profit
```

The whole product exists to answer one question: **for each of those six buckets,
is the client spending more than they should, and where?**

---

## 2. Leakage detection: the actual possibilities

This is the core value. Each leakage below = a metric + a benchmark + a flag.

### Raw material / fabric
- **Fabric utilization %** = fabric consumed in garment / fabric issued. Low = marker
  or cutting waste.
- **Cut-to-ship ratio** = pieces shipped / pieces cut. Gap = rejects + loss.
- **Dead / slow-moving RM stock** = inventory sitting beyond N days. Locked cash.
- **RM price variance** = actual purchase price vs standard/last price. Buying too high.

### Labour
- **Line efficiency %** = (standard minutes produced / minutes paid) x 100. The single
  most important garment-industry number. Built on SAM (Standard Allowed Minutes) per
  style.
- **Rework / rejection rate** = rework hours / total hours. Hidden labour cost.
- **Idle time** = paid hours with no output (line changeover, waiting for material).
- **Overtime cost ratio** = OT cost / total labour cost. High = bad planning, not
  bad luck.
- **Absenteeism impact** on planned vs actual output.

### Electricity / utilities
- **kWh per garment** and **utility cost per garment**, trended over time and
  compared across lines/months. A rising number with flat output = a leak.
- **Peak vs off-peak consumption** if the tariff is time-of-day based.
- **Cost per operating machine hour.**

### Machinery
- **Machine downtime %** and **OEE** (availability x performance x quality) if data
  allows; start with downtime hours and maintenance cost per machine.
- **Throughput per machine** vs capacity.

### Production flow
- **Planned vs actual output** per line per day. The headline variance.
- **WIP bottleneck**: which stage has pieces piling up.
- **Cycle time vs takt time** (needed pace to hit the due date).

### Quality
- **DHU** (defects per hundred units) and **right-first-time %**.
- **Cost of poor quality** = rework + rejects + customer deductions.

### Dispatch & delivery
- **On-time-in-full (OTIF) %**.
- **Order-to-dispatch lead time** vs quoted lead time.

### Financial / margin (ties it all together)
- **Quoted margin vs realized margin per order.** The money question. Shows exactly
  which of the six cost buckets ate the margin.
- **Cost per garment breakdown**, order by order.
- **Gross margin by customer / by style.** Which customers or products actually make
  money.
- **Enquiry-to-order conversion %.** Growth lever: lost revenue at the top of funnel.
- **Receivables aging / days-to-pay.** Cash leak even when the order was profitable.

### Growth / enhancement signals (not just leaks)
- Styles and customers with the best margin -> do more of these.
- Lines/processes consistently above benchmark -> replicate their method.
- Capacity headroom -> can take more orders without new investment.

---

## 3. How the report works

Keep it dumb and rule-based first. No ML until the rules are boring and proven.

1. Client uploads data (section 5).
2. Engine computes every metric above that the client's data supports.
3. Each metric is compared to a benchmark: the client's own past period, an
   industry threshold, or a target they set.
4. A rule assigns a status: **Good** (at/above benchmark), **Watch** (slipping),
   **Leak** (below threshold, with the rupee/dollar impact estimated).
5. Report = ranked list of leaks by money impact, plus the healthy areas, plus
   concrete "improve this" actions tied to each leak.

The ranking by money impact is what makes it worth paying for. "You lost
approx ₹X this month to fabric wastage on style Y" beats a dashboard of numbers.

> How the data arrives: factories have messy Excel or paper, rarely clean files.
> An **AI normalizer** (an LLM for messy spreadsheets, a vision model for photos
> of paper) sits in front of ingestion and rewrites whatever the client has into
> the standard template (section 5). Everything downstream never sees the mess.
> One hard rule: on money fields (prices, costs, quantities) the AI flags
> low-confidence reads for a human to confirm, it never silently guesses a number
> that feeds a P&L. ERP **API** integrations are a future option, not now.
>
> For v1 the ABC test data is hand-built clean, so the AI normalizer is stubbed
> and added once the pipeline is proven.

---

## 4. SaaS architecture (lazy, grows later)

Functionality-first, no UI yet, as you asked.

```
Messy Excel / CSV / photo of paper
        |
   AI normalizer (LLM + vision)  -> rewrites anything into the standard template,
                                    flags low-confidence money fields for human check
        |
   Ingestion + validation  (reject bad rows, report what was rejected)
        |
   One Postgres DB, every table carries tenant_id   <- multi-tenant
        |
   Metrics engine (pandas): computes KPIs per tenant per period
        |
   Rules engine: metric vs benchmark -> Good/Watch/Leak + money impact
        |
   Report output: JSON + PDF/HTML   (UI reads this later)
```

Deliberate simplifications for v1, with when to upgrade:

- **Single shared database, `tenant_id` column on every table.** Not a database
  per client. Upgrade to per-tenant DB only if a large client demands data
  isolation or you hit scale pain.
- **Template upload, not integrations.** Build an ERP connector only when a paying
  client has one.
- **Rule table, not ML.** A benchmarks/thresholds table the client can tune. Add
  prediction only after the rules are trusted.
- **Batch, not real-time.** Upload -> report. No live streaming from the floor
  until a client needs it.
- **Reports stored as files + JSON.** No fancy report builder yet.

---

## 5. Data intake format

One workbook per client per period, one sheet per data type. These sheets are the
contract: get them right and every metric above is computable.

- **orders**: order_id, customer, style, qty, order_date, due_date, quoted_price, quoted_cost
- **production**: date, line, style, planned_qty, actual_qty, machine_hours, labour_hours
- **material**: style, fabric_issued, fabric_consumed, rm_cost, rm_standard_cost
- **labour**: date, line, workers, hours_paid, overtime_hours, labour_cost, SAM_per_piece
- **quality**: date, line, style, inspected_qty, defect_qty, rework_hours, reject_qty
- **utilities**: period, line_or_plant, kWh, utility_cost, output_qty
- **dispatch**: order_id, dispatch_date, dispatched_qty
- **accounts**: order_id, invoiced_amount, received_amount, received_date

Ship a blank template with these columns + validation (required fields, number
types, date formats). Reject and report bad rows instead of silently dropping them;
bad data is itself a finding the factory should see.

---

## 6. Language & stack recommendation

**Python.** It is the correct and lazy choice here, not just a default:

- The whole product is data ingestion, tabular computation, and reporting.
  **pandas** does the metrics engine in a fraction of the code of any alternative.
- **openpyxl** reads/writes the Excel templates factories already live in.
- **FastAPI** when you expose an API / the thin UI later. Small, typed, fast to
  stand up. Skip it entirely for the first offline version if clients just send
  files.
- **PostgreSQL** for multi-tenant storage. One DB, `tenant_id` everywhere.
- **PDF/HTML report**: start with an HTML template rendered to PDF (WeasyPrint or
  similar). No report-builder dependency.

Why not the alternatives: a JS/Node stack would force you to hand-roll the data
math that pandas gives free. Java/C# is heavier than this needs. R is great for
stats but weaker for building a product and serving it. Python wins on both the
analytics and the "ship a service" axes, so you do not split the stack.

Suggested v1 shape:

```
ingest.py      load + validate the workbook into Postgres
metrics.py     pandas functions, one per KPI, returns numbers per tenant/period
rules.py       metric + benchmark -> status + money impact
report.py      assemble JSON, render HTML/PDF
benchmarks     a table (not code) of thresholds, tunable per tenant
```

No framework, no UI, no ML in v1. Prove the metrics and the money-ranked report on
two or three real clients' data first. Everything else scaffolds from there.

---

## 7. Suggested build order

1. Lock the intake template with 2-3 real clients' actual data. This surfaces what
   data truly exists before you write an engine against data that does not.
2. Build `ingest.py` + validation. Getting dirty real data in cleanly is 50% of the
   work.
3. Build `metrics.py` for the money-heavy KPIs first: quoted vs realized margin,
   fabric utilization, line efficiency, planned vs actual output.
4. Build `rules.py` + the benchmarks table. Produce the money-ranked leak list.
5. Build `report.py`. Ship the first client a real report. Iterate on what they
   found useful.
6. Only then: multi-tenant API, auth, a UI, more KPIs, ERP integrations, any ML.
