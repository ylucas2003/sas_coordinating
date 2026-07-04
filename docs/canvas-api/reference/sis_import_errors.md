# SIS Import Errors API

### A SisImportError object looks like:

``` example
{
  // The unique identifier for the SIS import.
  "sis_import_id": 1,
  // The file where the error message occurred.
  "file": "courses.csv",
  // The error message that from the record.
  "message": "No short_name given for course C001",
  // The contents of the line that had the error.
  "row_info": "account_1, Sub account 1,, active ",
  // The line number where the error occurred. Some Importers do not yet support
  // this. This is a 1 based index starting with the header row.
  "row": 34
}
```

## Get SIS import error list

### GET /api/v1/accounts/:account_id/sis_imports/:id/errors

**Scope:** `url:GET|/api/v1/accounts/:account_id/sis_imports/:id/errors`

### GET /api/v1/accounts/:account_id/sis_import_errors

**Scope:** `url:GET|/api/v1/accounts/:account_id/sis_import_errors`

Returns the list of SIS import errors for an account or a SIS import. Import errors are only stored for 30 days.

Example:

``` code
curl 'https://<canvas>/api/v1/accounts/<account_id>/sis_imports/<id>/sis_import_errors' \
  -H "Authorization: Bearer <token>"
```

Example:

``` code
curl 'https://<canvas>/api/v1/accounts/<account_id>/sis_import_errors' \
  -H "Authorization: Bearer <token>"
```

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| failure |  | boolean | If set, only shows errors on a sis import that would cause a failure. |

Returns a list of [SisImportError](sis_import_errors.html#SisImportError) objects
