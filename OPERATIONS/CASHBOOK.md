# Cashbook export for Excel

Start with a UTF-8 CSV you own. Use positive amounts with a separate `income` or `expense` column and ISO dates such as `2026-11-26`.

```csv
date,description,category,currency,flow,amount
2026-11-26,Example payment,Sales,USD,income,100.00
2026-11-26,Example supplies,Materials,USD,expense,25.50
```

Choose an exact file and authorize it through [Guardian](GUARDIAN.md) for your export purpose. Export to a new file inside an existing `MEMORY/` or `PROJECTS/` folder.

```text
python TOOLS/homestead.py cashbook MEMORY/ledger.csv --out MEMORY/cashbook.xlsx --csv-out MEMORY/shareable.csv --purpose "Prepare cashbook for Excel"
```

Use repeatable `--column field=your-header` options if your CSV uses other headings. For a single-currency log without a currency column, use `--currency USD` or your own currency code. Categories and descriptions are yours. The workbook contains a summary per currency and the transaction rows. Amounts are numeric, and descriptions or categories beginning with formula characters are plain text.

The CSV remains your source. Add `--csv-out` for a second, normalized CSV from the same rows. The export uses standard UTF-8 CSV with a byte-order marker for spreadsheet compatibility. Text that looks like a spreadsheet formula gets a leading apostrophe in the exported CSV. If you correct a row, export a fresh workbook. Existing files are kept. Transactions in different currencies are totaled separately, and the workbook carries the data you chose to export.
