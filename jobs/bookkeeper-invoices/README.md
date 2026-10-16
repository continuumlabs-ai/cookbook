# Bookkeeper: supplier invoices to Xero

Turns a folder of supplier invoices into a file you can import into Xero, and tells you which ones to query before you pay.

**For:** bookkeepers, accounts payable teams and practice managers who key in invoices every week.

## What it does

Each invoice is read into the same structure: supplier, ABN, invoice number, dates, lines, subtotal, GST and total. Then plain code checks it the way a careful bookkeeper would.

```
# Supplier invoices

6 files read. 2 ready to import, 3 to query before paying, 1 duplicate, 0 for a person to read.

## Query before paying

**Wattle Electrical Services, WE-1188** ($1,382.00)
- GST is $132.00 but 10% of the taxable amount ($1,250.00) is $125.00
```

Clean invoices go into `bills-import.csv`, in Xero's bills import layout. Everything else is listed with the reason.

## The checks

All of these run in plain code, using the shared [Australian checks](../../au/checks.py).

1. **Tax file numbers never reach the model.** Anything that passes the TFN check digit test is redacted first.
2. **The model's reading is checked against the invoice.** Every amount it reports must appear on the invoice. A misread figure is sent back once for correction.
3. **ABNs are tested against the ATO check digit.** A mistyped ABN is caught before you pay the wrong business.
4. **No ABN, no surprise.** An invoice over $75 with no ABN is flagged for the ATO's no-ABN withholding rules, with the 47% amount worked out.
5. **GST is recalculated.** 10% of the taxable amount, allowing for GST-free lines such as basic food. The supplier's arithmetic is never trusted.
6. **Lines must add up** to the subtotal.
7. **Duplicates are caught.** The same supplier and invoice number twice goes into the file once.

## Try it now

No key needed. Demo mode replays a scripted model run through this recipe's real code.

```bash
uv run jobs/bookkeeper-invoices/recipe.py --demo
```

Or read the [example report](example-output/report.md) and [import file](example-output/bills-import.csv).

## Run it

```bash
export CONTINUUM_API_KEY=your-key
uv run jobs/bookkeeper-invoices/recipe.py --folder path/to/invoices --terms 30
```

Invoices need to be text. Export PDFs to text first, or pair this with a document-reading step.

## Make it yours

- **Account codes.** Add a column mapping suppliers to your chart of accounts. The `AccountCode` column is left blank for you.
- **MYOB or QuickBooks.** Change `CSV_COLUMNS` and `import_csv` to match their import templates.
- **Supplier list.** Check ABNs against the suppliers you already pay, and flag new ones.
- **Check registration.** A check digit pass shows an ABN is well formed, not that it is active. Add a call to the ABN Lookup web service for new suppliers.

## Why keep it onshore

Invoices name your suppliers, your prices and sometimes your clients' bank details. Run on Continuum, every request is processed in Australian data centres and nothing is stored.

## Sample data

Every business, person and number in `data/invoices` is fictional. The ABNs were generated to pass or fail the check digit test and are not meant to identify any business. This recipe prepares work for a bookkeeper to review. It is not tax advice.
