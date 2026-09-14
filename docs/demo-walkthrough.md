# Enginex document-backed demo

## The story

The map opens a populated six-location portfolio: Al Rayyana, Gate, Arc,
The Bridges II, Sas Al Nakhl and Eastern Mangroves. A deterministic generator
adds 120 synthetic unit/lease records per location (720 records, 33 values each).
Its fixed reporting date is 14 September 2026. These records demonstrate scale;
they are not assertions about the actual properties or their tenants.

The original Al Rayyana asset, tenant rankings, vacancy rankings and summary
metrics are preserved. The summary charts are labelled demo assumptions and
remain separate from synthetic record totals. Contract values are never added
to either set of totals automatically.

The ten approved PDFs currently identify KEZAD warehouse premises. They also
carry a synthetic-test/anonymization notice. They demonstrate actual extraction
from anonymized test documents, not verified live commercial facts. Each gets
its own document-backed record with an unassigned map location. Do not assign
these contracts to a residential location merely to make the map look complete.

## Present the demo

1. Open the portfolio map and select any of the six locations. Open its metrics
   and record report. Point out the synthetic labels and reporting date.
2. Open **Contract workspace**. Upload up to ten approved anonymized PDFs, or
   choose **Browse storage** and select PDFs from `storagex`. Confirm the files
   are approved for the demo and leave **Extract with Astra** selected.
3. Open a document. Extraction is asynchronous and continues when the page is
   closed. The status panel offers a link to the results when ready.
4. Review an extracted value against its quotation and rendered source page.
   **Show page here** changes the preview; **Source PDF** opens the original PDF
   at the cited page. Confirm or reject the field after inspecting its context.
5. Expand **Associate with a location and record**. Select a record, choose the
   supported location (or keep **Unassigned / outside map**), and enter a reason.
   An intentional demo mapping must be described as such. The original premises,
   baseline values, previous extractions and association history are retained.
6. Open **Portfolio report → With documents**, or the linked record detail.
   Synthetic baseline values and extracted values have separate labels. A field
   can have multiple document values; conflicts are retained for review.
7. Open a PDF from the report. Export **values & sources** to obtain one CSV row
   per value with origin, review status, document title, page, quote and PDF URL.
   Synthetic rows have no PDF URL. Source links require an authenticated session.

## Additive data operations

`python manage.py populate_portfolio` is repeatable. It creates missing assets,
records, rankings and metrics with stable keys. It does not delete existing rows,
update existing values, reset users or assign contracts to locations. Do not use
`seed_demo` to refresh a populated workspace: the older starter command replaces
its sample rankings and can reset the optional demo user.

For an explicit batch import:

```sh
python manage.py ingest_contracts --directory /path/to/approved/pdfs --extract
# Or repeat --blob for each selected Azure blob:
python manage.py ingest_contracts --blob contract_01_anonymized.pdf --extract
```

Importing the same bytes under another filename reuses the existing document.
Azure imports and local uploads are retained in content-addressed snapshots at
`enginex/contracts/<sha256>.pdf` in the configured private container. Original
source blobs are not modified. A different PDF becomes a new document instead
of replacing earlier evidence.

## Processing and provenance

- The app stores documents, records, extraction runs, page text, extracted fields,
  review decisions and association history in PostgreSQL.
- PDF text is extracted per page with pypdf, then the numbered text is sent to the
  configured Astra deployment. This is an actual model call, not a canned result.
- A returned value must occur within its quotation, and the quotation must match
  the specified page after whitespace normalization. Invalid evidence is excluded.
  These checks establish traceability, not semantic correctness; human review is
  still needed, especially for OCR errors and contractual conditions.
- Missing dates are not calculated by the extractor. Alternative or conflicting
  provisions remain separate. The report uses the latest successful extraction;
  every earlier run remains available. A failed retry does not hide prior results.
- Re-extraction creates fresh, unreviewed evidence; review decisions are not copied
  across runs. Rejected fields stay in the extraction history but leave the report.
- The Container App starts the web process and two bounded extraction workers.
  Jobs are claimed from PostgreSQL. Queued jobs survive restarts; a run interrupted
  for over 15 minutes is marked failed and can be retried. No separate cloud queue
  or new Azure identity is required for this hackathon implementation.

## Explicit limits

- PDFs: 25 MB, 80 pages and 220,000 extracted text characters per document.
- OCR is not configured. Scanned PDFs with no usable text layer are rejected for
  extraction with an actionable message. Existing OCR text is used as supplied;
  image-only plans and signature pages are available visually but not interpreted.
- Values are stored verbatim. Normalized financial reconciliation, automatic
  lease matching, legal validation and cross-document amendment resolution are
  outside this demo. The current ten contracts need a supported manual location
  association or matching replacement documents before appearing under map assets.
- The CSV is an evidence export, not a merged financial ledger. Document-derived
  values are not automatically substituted into synthetic totals or chart metrics.
- Map tiles need browser internet access. Private PDF page previews use Poppler;
  original PDF page navigation depends on the viewer, with a rendered page preview
  provided in the application for consistent desktop and mobile use.
