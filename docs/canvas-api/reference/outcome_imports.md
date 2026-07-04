# Outcome Imports API

API for importing outcome data

### An OutcomeImportData object looks like:

``` example
{
  // The type of outcome import
  "import_type": "instructure_csv"
}
```

### An OutcomeImport object looks like:

``` example
{
  // The unique identifier for the outcome import.
  "id": 1,
  // The unique identifier for the group into which the outcomes will be imported
  // to, or NULL.
  "learning_outcome_group_id": 1,
  // The date the outcome import was created.
  "created_at": "2013-12-01T23:59:00-06:00",
  // The date the outcome import finished. Returns null if not finished.
  "ended_at": "2013-12-02T00:03:21-06:00",
  // The date the outcome import was last updated.
  "updated_at": "2013-12-02T00:03:21-06:00",
  // The current state of the outcome import.
  // - 'created': The outcome import has been created.
  // - 'importing': The outcome import is currently processing.
  // - 'succeeded': The outcome import has completed successfully.
  // - 'failed': The outcome import failed.
  "workflow_state": "imported",
  // See the OutcomeImportData specification above.
  "data": null,
  // The progress of the outcome import.
  "progress": "100",
  // The user that initiated the outcome_import. See the Users API for details.
  "user": null,
  // An array of row number / error message pairs. Returns the first 25 errors.
  "processing_errors": [[1, "Missing required fields: title"]]
}
```

## Import Outcomes

### POST /api/v1/accounts/:account_id/outcome_imports(/group/:learning_outcome_group_id)

**Scope:** `url:POST|/api/v1/accounts/:account_id/outcome_imports(/group/:learning_outcome_group_id)`

### POST /api/v1/courses/:course_id/outcome_imports(/group/:learning_outcome_group_id)

**Scope:** `url:POST|/api/v1/courses/:course_id/outcome_imports(/group/:learning_outcome_group_id)`

Import outcomes into Canvas.

For more information on the format that’s expected here, please see the “Outcomes CSV” section in the API docs.

#### Request Parameters:

<table class="request-params">
<colgroup>
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
<col style="width: 25%" />
</colgroup>
<thead>
<tr>
<th class="param-name">Parameter</th>
<th class="param-req"></th>
<th class="param-type">Type</th>
<th class="param-desc">Description</th>
</tr>
</thead>
<tbody>
<tr class="request-param">
<td>import_type</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Choose the data format for reading outcome data. With a standard Canvas install, this option can only be ‘instructure_csv’, and if unprovided, will be assumed to be so. Can be part of the query string.</p></td>
</tr>
<tr class="request-param">
<td>attachment</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>There are two ways to post outcome import data - either via a multipart/form-data form-field-style attachment, or via a non-multipart raw post request.</p>
<p>‘attachment’ is required for multipart/form-data style posts. Assumed to be outcome data from a file upload form field named ‘attachment’.</p>
<p>Examples:</p>
`curl -F attachment=@<filename> -H "Authorization: Bearer <token>" \
    'https://<canvas>/api/v1/accounts/<account_id>/outcome_imports?import_type=instructure_csv'
curl -F attachment=@<filename> -H "Authorization: Bearer <token>" \
    'https://<canvas>/api/v1/courses/<course_id>/outcome_imports?import_type=instructure_csv'`
<p>If you decide to do a raw post, you can skip the ‘attachment’ argument, but you will then be required to provide a suitable Content-Type header. You are encouraged to also provide the ‘extension’ argument.</p>
<p>Examples:</p>
`curl -H 'Content-Type: text/csv' --data-binary @<filename>.csv \
    -H "Authorization: Bearer <token>" \
    'https://<canvas>/api/v1/accounts/<account_id>/outcome_imports?import_type=instructure_csv'

curl -H 'Content-Type: text/csv' --data-binary @<filename>.csv \
    -H "Authorization: Bearer <token>" \
    'https://<canvas>/api/v1/courses/<course_id>/outcome_imports?import_type=instructure_csv'`</td>
</tr>
<tr class="request-param">
<td>extension</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Recommended for raw post request style imports. This field will be used to distinguish between csv and other file format extensions that would usually be provided with the filename in the multipart post request scenario. If not provided, this value will be inferred from the Content-Type, falling back to csv-file format if all else fails.</p></td>
</tr>
</tbody>
</table>

Returns an [OutcomeImport](outcome_imports.html#OutcomeImport) object

## Get Outcome import status

### GET /api/v1/accounts/:account_id/outcome_imports/:id

**Scope:** `url:GET|/api/v1/accounts/:account_id/outcome_imports/:id`

### GET /api/v1/courses/:course_id/outcome_imports/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/outcome_imports/:id`

Get the status of an already created Outcome import. Pass ‘latest’ for the outcome import id for the latest import.

``` code
Examples:
  curl 'https://<canvas>/api/v1/accounts/<account_id>/outcome_imports/<outcome_import_id>' \
      -H "Authorization: Bearer <token>"
  curl 'https://<canvas>/api/v1/courses/<course_id>/outcome_imports/<outcome_import_id>' \
      -H "Authorization: Bearer <token>"
```

Returns an [OutcomeImport](outcome_imports.html#OutcomeImport) object

## Get IDs of outcome groups created after successful import

### GET /api/v1/accounts/:account_id/outcome_imports/:id/created_group_ids

**Scope:** `url:GET|/api/v1/accounts/:account_id/outcome_imports/:id/created_group_ids`

### GET /api/v1/courses/:course_id/outcome_imports/:id/created_group_ids

**Scope:** `url:GET|/api/v1/courses/:course_id/outcome_imports/:id/created_group_ids`

Get the IDs of the outcome groups created after a successful import. Pass ‘latest’ for the outcome import id for the latest import.

``` code
Examples:
  curl 'https://<canvas>/api/v1/accounts/<account_id>/outcome_imports/outcomes_group_ids/<outcome_import_id>' \
      -H "Authorization: Bearer <token>"
  curl 'https://<canvas>/api/v1/courses/<course_id>/outcome_imports/outcome_group_ids/<outcome_import_id>' \
      -H "Authorization: Bearer <token>"
```
