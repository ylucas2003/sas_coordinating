# Content Exports API

API for exporting courses and course content

### A ContentExport object looks like:

``` example
{
  // the unique identifier for the export
  "id": 101,
  // the date and time this export was requested
  "created_at": "2014-01-01T00:00:00Z",
  // the type of content migration: 'common_cartridge' or 'qti'
  "export_type": "common_cartridge",
  // attachment api object for the export package (not present before the export
  // completes or after it becomes unavailable for download.)
  "attachment": {"url":"https:\/\/example.com\/api\/v1\/attachments\/789?download_frd=1\u0026verifier=bG9sY2F0cyEh"},
  // The api endpoint for polling the current progress
  "progress_url": "https://example.com/api/v1/progress/4",
  // The ID of the user who started the export
  "user_id": 4,
  // Current state of the content migration: created exporting exported failed
  "workflow_state": "exported"
}
```

## List content exports

### GET /api/v1/courses/:course_id/content_exports

**Scope:** `url:GET|/api/v1/courses/:course_id/content_exports`

### GET /api/v1/groups/:group_id/content_exports

**Scope:** `url:GET|/api/v1/groups/:group_id/content_exports`

### GET /api/v1/users/:user_id/content_exports

**Scope:** `url:GET|/api/v1/users/:user_id/content_exports`

A paginated list of the past and pending content export jobs for a course, group, or user. Exports are returned newest first.

Returns a list of [ContentExport](content_exports.html#ContentExport) objects

## Show content export

### GET /api/v1/courses/:course_id/content_exports/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/content_exports/:id`

### GET /api/v1/groups/:group_id/content_exports/:id

**Scope:** `url:GET|/api/v1/groups/:group_id/content_exports/:id`

### GET /api/v1/users/:user_id/content_exports/:id

**Scope:** `url:GET|/api/v1/users/:user_id/content_exports/:id`

Get information about a single content export.

Returns a [ContentExport](content_exports.html#ContentExport) object

## Export content

### POST /api/v1/courses/:course_id/content_exports

**Scope:** `url:POST|/api/v1/courses/:course_id/content_exports`

### POST /api/v1/groups/:group_id/content_exports

**Scope:** `url:POST|/api/v1/groups/:group_id/content_exports`

### POST /api/v1/users/:user_id/content_exports

**Scope:** `url:POST|/api/v1/users/:user_id/content_exports`

Begin a content export job for a course, group, or user.

You can use the [Progress API](progress.html#method.progress.show "Progress API") to track the progress of the export. The migration’s progress is linked to with the *progress_url* value.

When the export completes, use the [Show content export](content_exports.html#method.content_exports_api.show "Show content export") endpoint to retrieve a download URL for the exported content.

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
<td>export_type</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><dl>
<dt>“common_cartridge”</dt>
<dd>
<p>Export the contents of the course in the Common Cartridge (.imscc) format</p>
</dd>
<dt>“qti”</dt>
<dd>
<p>Export quizzes from a course in the QTI format</p>
</dd>
<dt>“zip”</dt>
<dd>
<p>Export files from a course, group, or user in a zip file</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">common_cartridge</code>, <code class="enum">qti</code>, <code class="enum">zip</code></p></td>
</tr>
<tr class="request-param">
<td>skip_notifications</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Don’t send the notifications about the export to the user. Default: false</p></td>
</tr>
<tr class="request-param">
<td>select</td>
<td></td>
<td>Hash</td>
<td class="param-desc"><p>The select parameter allows exporting specific data. The keys are object types like ‘files’, ‘folders’, ‘pages’, etc. The value for each key is a list of object ids. An id can be an integer or a string.</p>
<p>Multiple object types can be selected in the same call. However, not all object types are valid for every export_type. Common Cartridge supports all object types. Zip and QTI only support the object types as described below.</p>
<dl>
<dt>“folders”</dt>
<dd>
<p>Also supported for zip export_type.</p>
</dd>
<dt>“files”</dt>
<dd>
<p>Also supported for zip export_type.</p>
</dd>
<dt>“quizzes”</dt>
<dd>
<p>Also supported for qti export_type.</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">folders</code>, <code class="enum">files</code>, <code class="enum">attachments</code>, <code class="enum">quizzes</code>, <code class="enum">assignments</code>, <code class="enum">announcements</code>, <code class="enum">calendar_events</code>, <code class="enum">discussion_topics</code>, <code class="enum">modules</code>, <code class="enum">module_items</code>, <code class="enum">pages</code>, <code class="enum">rubrics</code></p></td>
</tr>
</tbody>
</table>

Returns a [ContentExport](content_exports.html#ContentExport) object
