> Demonstration output. The model's replies were scripted. Run without --demo for a live result.

# Supplier invoices

6 files read. 2 ready to import, 3 to query before paying, 1 duplicate, 0 for a person to read.

## Ready to import

| Supplier | Invoice | Date | Total inc GST | GST |
|---|---|---|---:|---:|
| Ironbark Plumbing Pty Ltd | INV-20417 | 03/10/2026 | $2,856.70 | $259.70 |
| Gumleaf Office Supplies | 77812 | 06/10/2026 | $285.70 | $24.30 |

Total $3,142.40, including $284.00 GST you can claim on your BAS. The lines are in `bills-import.csv`.

## Query before paying

**Coastal Courier Co., C-3391** ($152.46)
- ABN 28 322 761 078 fails the ATO check digit test, so it is probably mistyped. Confirm it on ABN Lookup before paying.

**Wattle Electrical Services, WE-1188** ($1,382.00)
- GST is $132.00 but 10% of the taxable amount ($1,250.00) is $125.00

**Kookaburra Cleaning (Jess Moran), 0042** ($340.00)
- No ABN quoted on an invoice over $75.00. Under the ATO's no-ABN withholding rules you may need to withhold 47% ($159.80) unless an exception applies. Ask for their ABN.

## Duplicates, not imported

- `06-ironbark-plumbing-resent.txt` repeats Ironbark Plumbing Pty Ltd INV-20417 from `01-ironbark-plumbing.txt`.

## What the checks caught

- Gumleaf Office Supplies: the model's first reading did not match the invoice and was corrected.
- Coastal Courier Co.: ABN failed the check digit test.
- Wattle Electrical Services: the supplier's GST arithmetic is wrong (GST is $132.00 but 10% of the taxable amount ($1,250.00) is $125.00).
- Kookaburra Cleaning (Jess Moran): removed a tax file number before the invoice reached the model.
- Kookaburra Cleaning (Jess Moran): no ABN quoted, so withholding may apply.
- Ironbark Plumbing Pty Ltd: the same invoice arrived twice. Only one copy is in the import file.

Checks run in plain code: tax file number redaction, ABN check digits, GST recalculation, line totals and duplicate detection. A check digit pass shows an ABN is well formed, not that it is registered. Confirm new suppliers on ABN Lookup.