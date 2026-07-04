# ePub Exports API

API for exporting courses as an ePub

### A CourseEpubExport object looks like:

``` example
// Combination of a Course & EpubExport.
{
  // the unique identifier for the course
  "id": 101,
  // the name for the course
  "name": "Maths 101",
  // ePub export API object
  "epub_export": null
}
```

### An EpubExport object looks like:

``` example
{
  // the unique identifier for the export
  "id": 101,
  // the date and time this export was requested
  "created_at": "2014-01-01T00:00:00Z",
  // attachment api object for the export ePub (not present until the export
  // completes)
  "attachment": {"url":"https:\/\/example.com\/api\/v1\/attachments\/789?download_frd=1\u0026verifier=bG9sY2F0cyEh"},
  // The api endpoint for polling the current progress
  "progress_url": "https://example.com/api/v1/progress/4",
  // The ID of the user who started the export
  "user_id": 4,
  // Current state of the ePub export: created exporting exported generating
  // generated failed
  "workflow_state": "exported"
}
```

## List courses with their latest ePub export

### GET /api/v1/epub_exports

**Scope:** `url:GET|/api/v1/epub_exports`

A paginated list of all courses a user is actively participating in, and the latest ePub export associated with the user & course.

Returns a list of [CourseEpubExport](e_pub_exports.html#CourseEpubExport) objects

## Create ePub Export

### POST /api/v1/courses/:course_id/epub_exports

**Scope:** `url:POST|/api/v1/courses/:course_id/epub_exports`

Begin an ePub export for a course.

You can use the [Progress API](progress.html#method.progress.show "Progress API") to track the progress of the export. The export’s progress is linked to with the *progress_url* value.

When the export completes, use the [Show content export](e_pub_exports.html#method.epub_exports.show "Show content export") endpoint to retrieve a download URL for the exported content.

Returns an [EpubExport](e_pub_exports.html#EpubExport) object

## Show ePub export

### GET /api/v1/courses/:course_id/epub_exports/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/epub_exports/:id`

Get information about a single ePub export.

Returns an [EpubExport](e_pub_exports.html#EpubExport) object
