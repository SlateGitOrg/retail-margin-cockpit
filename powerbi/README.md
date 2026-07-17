# Power BI semantic model & report

This folder holds the *semantic model* (the part that's fully specified,
version-controlled, and testable) and documents the *report* (the part
that, in the real product, is a `.pbix` built in Power BI Desktop on top
of that model). See the root README's "Why there's no .pbix" note for why
the report itself is documented rather than shipped as a binary.

## Files

| File | What it is |
|---|---|
| `measures.dax` | The full DAX measure library, hand-written, organized by folder (Sales & Margin, Inventory Health, Time Intelligence, RLS). Paste-able straight into Power BI Desktop's modeling view. |
| `model.bim` | A TMSL (Tabular Model Scripting Language) definition of the semantic model: every table, column, relationship, the same measures as `measures.dax` (kept in sync by `scripts/build_model_bim.py`), and the two RLS roles. Openable in Tabular Editor, or usable as the source for a `Model.bim`-based Power BI Desktop project. |

Regenerate `model.bim`'s measures after editing `measures.dax`:

```bash
python scripts/build_model_bim.py
```

`tests/test_dax_measures.py` and `tests/test_model_bim.py` enforce that the
two files never drift apart and that both are syntactically well-formed.

## Report pages (4, interconnected)

1. **Executive Overview** -- KPI cards (Gross Revenue, Gross Margin %,
   Gross Revenue YoY %, Inventory Turns), a revenue-by-month line chart
   with a PY comparison line, and a small multiples bar chart of Gross
   Margin % by category. A card shows `[Current User Region]` so a
   Regional Manager can see at a glance which slice of the model they're
   viewing under RLS.
2. **Margin Deep Dive** -- Gross Margin % and Effective Discount % by
   category/subcategory in a matrix, a scatter of product-level margin %
   vs. units sold (bubble = revenue) to spot high-volume/low-margin SKUs,
   and the `Revenue Below Margin Floor` KPI trended by month. **Drillthrough**
   from any product point/matrix cell to page 4 (Product Detail) passing
   `product_id` as the drillthrough filter.
3. **Channel Performance** -- Gross Revenue, Gross Margin %, and YoY %
   by channel and region, plus a bookmark-driven toggle between "Retail
   Stores" and "Digital + Wholesale" channel groupings (two bookmarks
   swapping a channel-type slicer selection and a matching visual-level
   filter, wired to a bookmark navigator button group). This is the page
   where the Regional Manager RLS role is most visible: a scoped user
   only ever sees their region's row in every visual here.
4. **Product & Inventory Detail** (drillthrough target) -- Sell-Through
   %, Inventory Turns, Stockout Rate %, and Weeks of Supply for the
   product selected via drillthrough (or filtered directly via the page's
   product slicer), with a small-multiples on-hand-units-over-time chart
   per channel and a "back" button to return to Margin Deep Dive.

## Row-level security

Two roles are defined in `model.bim`:

- **Regional Manager** -- dynamic RLS. The `dim_channel` table permission
  filters rows to the region looked up for `USERPRINCIPALNAME()` in
  `dim_user_region_map`; a mapped region of `"ALL"` (the HQ case) removes
  the filter entirely. Because the filter lives on `dim_channel` and both
  fact tables relate to it, every visual sliced by channel/region is
  automatically scoped -- no per-visual filtering required.
- **HQ Analyst** -- no table permissions; unrestricted read.

To test as a specific regional manager in Power BI Desktop: **Modeling ->
View As -> Roles -> Regional Manager -> Other user** and enter one of the
sample emails from `dim_user_region_map` (e.g.
`ben.osei@retailco.example` for Midwest-only; `dana.wu@retailco.example`
for the unrestricted `ALL` case).

## Bookmarks

- `bm_channel_view_retail` / `bm_channel_view_digital` on Channel
  Performance (described above).
- `bm_margin_alert_on` / `bm_margin_alert_off` on Margin Deep Dive,
  toggling visibility of the `Revenue Below Margin Floor` KPI card and an
  accompanying warning-colored border, for a "call out the risk" view
  used in the monthly finance review.
