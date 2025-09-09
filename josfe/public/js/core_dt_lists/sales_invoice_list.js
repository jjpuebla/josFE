frappe.listview_settings["Sales Invoice"] = {
  onload(listview) {
    console.log("🎨 josfe: paint + min/max widths + (optional) ID-first");

    // ---------- 1) Styles: per-column color + min/max widths ----------
    const STYLE_ID = "josfe-si-list-paint-and-widths";
    if (!document.getElementById(STYLE_ID)) {
      const style = document.createElement("style");
      style.id = STYLE_ID;
      style.textContent = `
        /*— Generic cell outline for visibility —*/
        .list-view-container .list-row .list-row-col { outline: 1px dashed rgba(0,0,0,.06); }

        /* TITLE (first column with subject) */
        // .list-row-head .list-row-col.list-subject { background: #ffefd5; }
        // .list-row .list-row-col.list-subject { background: #fff7e6; }
        .list-row .list-row-col.list-subject,
        .list-row-head .list-row-col.list-subject {
          flex: 2 1 auto; min-width: 200px; max-width: 220px;
        }

        /* TAGS */
        // .list-row-head .list-row-col.tag-col { background: #e6f7ff; }
        // .list-row .list-row-col.tag-col { background: #f0fbff; }
        .list-row .list-row-col.tag-col,
        .list-row-head .list-row-col.tag-col {
          flex: 0 1 auto; min-width: 90px; max-width: 160px;
        }

        /* TAX ID (header is span[data-sort-by="tax_id"]; rows use data-filter^="tax_id,=") */
        // .list-row-head .list-row-col:has(span[data-sort-by="tax_id"]) { background: #e3ffe3; }
        // .list-row .list-row-col:has(a[data-filter^="tax_id,="]) { background: #f3fff3; }
        .list-row .list-row-col:has(a[data-filter^="tax_id,="]),
        .list-row-head .list-row-col:has(span[data-sort-by="tax_id"]) {
          flex: 1 1 auto; min-width: 140px; max-width: 220px;
        }

        /* DATE (posting_date) */
        // .list-row-head .list-row-col:has(span[data-sort-by="posting_date"]) { background: #e6e6ff; }
        // .list-row .list-row-col:has(a[data-filter^="posting_date,="]) { background: #f0f0ff; }
        .list-row .list-row-col:has(a[data-filter^="posting_date,="]),
        .list-row-head .list-row-col:has(span[data-sort-by="posting_date"]) {
          flex: 0 1 auto; min-width: 100px; max-width: 110px;
        }

        /* GRAND TOTAL */
        // .list-row-head .list-row-col:has(span[data-sort-by="grand_total"]) { background: #d0ebff; }
        // .list-row .list-row-col:has(a[data-filter^="grand_total,="]) { background: #e7f5ff; }
        .list-row .list-row-col:has(a[data-filter^="grand_total,="]),
        .list-row-head .list-row-col:has(span[data-sort-by="grand_total"]) {
          flex: 0 1 auto; min-width: 90px; max-width: 110px;
          text-align: right;
        }

        /* STATUS (header has plain <span>Status</span>; rows have .indicator-pill) */
        // .list-row-head .list-row-col:not(.list-subject):not(.tag-col):not(:has([data-sort-by])) { background: #f3f0ff; }
        // .list-row .list-row-col:has(.indicator-pill) { background: #faf5ff; }
        .list-row .list-row-col:has(.indicator-pill),
        .list-row-head .list-row-col:not(.list-subject):not(.tag-col):not(:has([data-sort-by])) {
          flex: 0 1 auto; min-width: 80px; max-width: 90px;
        }

        /* NRO> FACTURA */
        .list-row-head .list-row-col:has([data-sort-by="custom_sri_serie"]) { font-weight: 800 }
        .list-row .list-row-col:has(a[data-filter^="custom_sri_serie,="]) { font-weight: 800}
        .list-row .list-row-col:has(a[data-filter^="custom_sri_serie,="]),
        .list-row-head .list-row-col:has([data-sort-by="custom_sri_serie"]) {
          flex: 0 1 auto; min-width: 160px; max-width: 240px;
        }

        /* ID (name) */
        // .list-row-head .list-row-col:has([data-sort-by="name"]) { background: #ffd6d6; }
        // .list-row .list-row-col:has(a[data-filter^="name,="]) { background: #ffecec; }
        .list-row-head .list-row-col:has([data-sort-by="name"]),
        .list-row .list-row-col:has(a[data-filter^="name,="]) {
        display: none !important;
        .list-row .list-row-col:has(a[data-filter^="name,="]),
        .list-row-head .list-row-col:has([data-sort-by="name"]) {
          flex: 0 1 auto; min-width: 160px; max-width: 240px;
        }
      `;
      document.head.appendChild(style);
   }


  }
};
