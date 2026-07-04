# SIS Imports API

API for importing data from Student Information Systems

### A SisImportData object looks like:

``` example
{
  // The type of SIS import
  "import_type": "instructure_csv",
  // Which files were included in the SIS import
  "supplied_batches": ["term", "course", "section", "user", "enrollment"],
  // The number of rows processed for each type of import
  "counts": null
}
```

### A SisImportStatistic object looks like:

``` example
{
  // This is the number of items that were created.
  "created": 18,
  // This is the number of items that marked as completed. This only applies to
  // courses and enrollments.
  "concluded": 3,
  // This is the number of Enrollments that were marked as 'inactive'. This only
  // applies to enrollments.
  "deactivated": 1,
  // This is the number of items that were set to an active state from a
  // completed, inactive, or deleted state.
  "restored": 2,
  // This is the number of items that were deleted.
  "deleted": 40
}
```

### A SisImportStatistics object looks like:

``` example
{
  // This is the total number of items that were changed in the sis import. There
  // are a few caveats that can cause this number to not add up to the individual
  // counts. There are some state changes that happen that have no impact to the
  // object. An example would be changing a course from 'created' to 'claimed'.
  // Both of these would be considered an active course, but would increment this
  // counter. In this example the course would not increment the created or
  // restored counters for course statistic.
  "total_state_changes": 382,
  // This contains that statistics for accounts.
  "Account": null,
  // This contains that statistics for terms.
  "EnrollmentTerm": null,
  // This contains that statistics for communication channels. This is an indirect
  // effect from creating or deleting a user.
  "CommunicationChannel": null,
  // This contains that statistics for abstract courses.
  "AbstractCourse": null,
  // This contains that statistics for courses.
  "Course": null,
  // This contains that statistics for course sections.
  "CourseSection": null,
  // This contains that statistics for enrollments.
  "Enrollment": null,
  // This contains that statistics for group categories.
  "GroupCategory": null,
  // This contains that statistics for groups.
  "Group": null,
  // This contains that statistics for group memberships. This can be a direct
  // impact from the import or indirect from an enrollment being deleted.
  "GroupMembership": null,
  // This contains that statistics for pseudonyms. Pseudonyms are logins for
  // users, and are the object that ties an enrollment to a user. This would be
  // impacted from the user importer.
  "Pseudonym": null,
  // This contains that statistics for user observers.
  "UserObserver": null,
  // This contains that statistics for account users.
  "AccountUser": null
}
```

### A SisImportCounts object looks like:

``` example
{
  "accounts": 0,
  "terms": 3,
  "abstract_courses": 0,
  "courses": 121,
  "sections": 278,
  "xlists": 0,
  "users": 346,
  "enrollments": 1542,
  "groups": 0,
  "group_memberships": 0,
  "grade_publishing_results": 0,
  // the number of courses that were removed because they were not included in the
  // batch for batch_mode imports. Only included if courses were deleted
  "batch_courses_deleted": 11,
  // the number of sections that were removed because they were not included in
  // the batch for batch_mode imports. Only included if sections were deleted
  "batch_sections_deleted": 0,
  // the number of enrollments that were removed because they were not included in
  // the batch for batch_mode imports. Only included if enrollments were deleted
  "batch_enrollments_deleted": 150,
  "error_count": 0,
  "warning_count": 0
}
```

### A SisImport object looks like:

``` example
{
  // The unique identifier for the SIS import.
  "id": 1,
  // The date the SIS import was created.
  "created_at": "2013-12-01T23:59:00-06:00",
  // The date the SIS import finished. Returns null if not finished.
  "ended_at": "2013-12-02T00:03:21-06:00",
  // The date the SIS import was last updated.
  "updated_at": "2013-12-02T00:03:21-06:00",
  // The current state of the SIS import.
  // - 'initializing': The SIS import is being created, if this gets stuck in
  // initializing, it will not import and will continue on to next import.
  // - 'created': The SIS import has been created.
  // - 'importing': The SIS import is currently processing.
  // - 'cleanup_batch': The SIS import is currently cleaning up courses, sections,
  // and enrollments not included in the batch for batch_mode imports.
  // - 'imported': The SIS import has completed successfully.
  // - 'imported_with_messages': The SIS import completed with errors or warnings.
  // - 'aborted': The SIS import was aborted.
  // - 'failed_with_messages': The SIS import failed with errors.
  // - 'failed': The SIS import failed.
  // - 'restoring': The SIS import is restoring states of imported items.
  // - 'partially_restored': The SIS import is restored some of the states of
  // imported items. This is generally due to passing a param like undelete only.
  // - 'restored': The SIS import is restored all of the states of imported items.
  "workflow_state": "imported",
  // data
  "data": null,
  // statistics
  "statistics": null,
  // The progress of the SIS import. The progress will reset when using batch_mode
  // and have a different progress for the cleanup stage
  "progress": "100",
  // The errors_attachment api object of the SIS import. Only available if there
  // are errors or warning and import has completed.
  "errors_attachment": null,
  // The user that initiated the sis_batch. See the Users API for details.
  "user": null,
  // Only imports that are complete will get this data. An array of
  // CSV_file/warning_message pairs.
  "processing_warnings": [["students.csv", "user John Doe has already claimed john_doe's requested login information, skipping"]],
  // An array of CSV_file/error_message pairs.
  "processing_errors": [["students.csv", "Error while importing CSV. Please contact support."]],
  // Whether the import was run in batch mode.
  "batch_mode": true,
  // The term the batch was limited to.
  "batch_mode_term_id": "1234",
  // Enables batch mode against all terms in term file. Requires change_threshold
  // to be set.
  "multi_term_batch_mode": false,
  // When set the import will skip any deletes.
  "skip_deletes": false,
  // Whether UI changes were overridden.
  "override_sis_stickiness": false,
  // Whether stickiness was added to the batch changes.
  "add_sis_stickiness": false,
  // Whether stickiness was cleared.
  "clear_sis_stickiness": false,
  // Whether a diffing job failed because the threshold limit got exceeded.
  "diffing_threshold_exceeded": true,
  // The identifier of the data set that this SIS batch diffs against
  "diffing_data_set_identifier": "account-5-enrollments",
  // Whether diffing remaster data was enabled.
  "diffing_remaster": false,
  // The ID of the SIS Import that this import was diffed against
  "diffed_against_import_id": 1,
  // An array of CSV files for processing
  "csv_attachments": []
}
```

## Get SIS import list

### GET /api/v1/accounts/:account_id/sis_imports

**Scope:** `url:GET|/api/v1/accounts/:account_id/sis_imports`

Returns the list of SIS imports for an account

Example:

``` code
curl https://<canvas>/api/v1/accounts/<account_id>/sis_imports \
  -H 'Authorization: Bearer <token>'
```

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
<td>created_since</td>
<td></td>
<td>DateTime</td>
<td class="param-desc"><p>If set, only shows imports created after the specified date (use ISO8601 format)</p></td>
</tr>
<tr class="request-param">
<td>created_before</td>
<td></td>
<td>DateTime</td>
<td class="param-desc"><p>If set, only shows imports created before the specified date (use ISO8601 format)</p></td>
</tr>
<tr class="request-param">
<td>workflow_state[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If set, only returns imports that are in the given state.</p>
<p>Allowed values: <code class="enum">initializing</code>, <code class="enum">created</code>, <code class="enum">importing</code>, <code class="enum">cleanup_batch</code>, <code class="enum">imported</code>, <code class="enum">imported_with_messages</code>, <code class="enum">aborted</code>, <code class="enum">failed</code>, <code class="enum">failed_with_messages</code>, <code class="enum">restoring</code>, <code class="enum">partially_restored</code>, <code class="enum">restored</code></p></td>
</tr>
</tbody>
</table>

Returns a list of [SisImport](sis_imports.html#SisImport) objects

## Get the current importing SIS import

### GET /api/v1/accounts/:account_id/sis_imports/importing

**Scope:** `url:GET|/api/v1/accounts/:account_id/sis_imports/importing`

Returns the SIS imports that are currently processing for an account. If no imports are running, will return an empty array.

Example:

``` code
curl https://<canvas>/api/v1/accounts/<account_id>/sis_imports/importing \
  -H 'Authorization: Bearer <token>'
```

Returns a [SisImport](sis_imports.html#SisImport) object

## Import SIS data

### POST /api/v1/accounts/:account_id/sis_imports

**Scope:** `url:POST|/api/v1/accounts/:account_id/sis_imports`

Import SIS data into Canvas. Must be on a root account with SIS imports enabled.

For more information on the format that’s expected here, please see the “SIS CSV” section in the API docs.

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
<td class="param-desc"><p>Choose the data format for reading SIS data. With a standard Canvas install, this option can only be ‘instructure_csv’, and if unprovided, will be assumed to be so. Can be part of the query string.</p></td>
</tr>
<tr class="request-param">
<td>attachment</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>There are two ways to post SIS import data - either via a multipart/form-data form-field-style attachment, or via a non-multipart raw post request.</p>
<p>‘attachment’ is required for multipart/form-data style posts. Assumed to be SIS data from a file upload form field named ‘attachment’.</p>
<p>Examples:</p>
`curl -F attachment=@<filename> -H "Authorization: Bearer <token>" \
    https://<canvas>/api/v1/accounts/<account_id>/sis_imports.json?import_type=instructure_csv`
<p>If you decide to do a raw post, you can skip the ‘attachment’ argument, but you will then be required to provide a suitable Content-Type header. You are encouraged to also provide the ‘extension’ argument.</p>
<p>Examples:</p>
`curl -H 'Content-Type: application/octet-stream' --data-binary @<filename>.zip \
    -H "Authorization: Bearer <token>" \
    https://<canvas>/api/v1/accounts/<account_id>/sis_imports.json?import_type=instructure_csv&extension=zip

curl -H 'Content-Type: application/zip' --data-binary @<filename>.zip \
    -H "Authorization: Bearer <token>" \
    https://<canvas>/api/v1/accounts/<account_id>/sis_imports.json?import_type=instructure_csv

curl -H 'Content-Type: text/csv' --data-binary @<filename>.csv \
    -H "Authorization: Bearer <token>" \
    https://<canvas>/api/v1/accounts/<account_id>/sis_imports.json?import_type=instructure_csv

curl -H 'Content-Type: text/csv' --data-binary @<filename>.csv \
    -H "Authorization: Bearer <token>" \
    https://<canvas>/api/v1/accounts/<account_id>/sis_imports.json?import_type=instructure_csv&batch_mode=1&batch_mode_term_id=15`
<p>If the attachment is a zip file, the uncompressed file(s) cannot be 100x larger than the zip, or the import will fail. For example, if the zip file is 1KB but the total size of the uncompressed file(s) is 100KB or greater the import will fail. There is a hard cap of 50 GB.</p></td>
</tr>
<tr class="request-param">
<td>extension</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Recommended for raw post request style imports. This field will be used to distinguish between zip, xml, csv, and other file format extensions that would usually be provided with the filename in the multipart post request scenario. If not provided, this value will be inferred from the Content-Type, falling back to zip-file format if all else fails.</p></td>
</tr>
<tr class="request-param">
<td>batch_mode</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If set, this SIS import will be run in batch mode, deleting any data previously imported via SIS that is not present in this latest import. See the SIS CSV Format page for details. Batch mode cannot be used with diffing.</p></td>
</tr>
<tr class="request-param">
<td>batch_mode_term_id</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Limit deletions to only this term. Required if batch mode is enabled.</p></td>
</tr>
<tr class="request-param">
<td>multi_term_batch_mode</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Runs batch mode against all terms in terms file. Requires change_threshold.</p></td>
</tr>
<tr class="request-param">
<td>skip_deletes</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>When set the import will skip any deletes. This does not account for objects that are deleted during the batch mode cleanup process.</p></td>
</tr>
<tr class="request-param">
<td>override_sis_stickiness</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Default is false. If true, any fields containing “sticky” or UI changes will be overridden. See SIS CSV Format documentation for information on which fields can have SIS stickiness</p></td>
</tr>
<tr class="request-param">
<td>add_sis_stickiness</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>This option, if present, will process all changes as if they were UI changes. This means that “stickiness” will be added to changed fields. This option is only processed if ‘override_sis_stickiness’ is also provided.</p></td>
</tr>
<tr class="request-param">
<td>clear_sis_stickiness</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>This option, if present, will clear “stickiness” from all fields touched by this import. Requires that ‘override_sis_stickiness’ is also provided. If ‘add_sis_stickiness’ is also provided, ‘clear_sis_stickiness’ will overrule the behavior of ‘add_sis_stickiness’</p></td>
</tr>
<tr class="request-param">
<td>update_sis_id_if_login_claimed</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>This option, if present, will override the old (or non-existent) non-matching SIS ID with the new SIS ID in the upload, if a pseudonym is found from the login field and the SIS ID doesn’t match.</p></td>
</tr>
<tr class="request-param">
<td>diffing_data_set_identifier</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If set on a CSV import, Canvas will attempt to optimize the SIS import by comparing this set of CSVs to the previous set that has the same data set identifier, and only applying the difference between the two. See the SIS CSV Format documentation for more details. Diffing cannot be used with batch_mode</p></td>
</tr>
<tr class="request-param">
<td>diffing_remaster_data_set</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, and diffing_data_set_identifier is sent, this SIS import will be part of the data set, but diffing will not be performed. See the SIS CSV Format documentation for details.</p></td>
</tr>
<tr class="request-param">
<td>diffing_drop_status</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If diffing_drop_status is passed, this SIS import will use this status for enrollments that are not included in the sis_batch. Defaults to ‘deleted’</p>
<p>Allowed values: <code class="enum">deleted</code>, <code class="enum">completed</code>, <code class="enum">inactive</code></p></td>
</tr>
<tr class="request-param">
<td>diffing_user_remove_status</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>For users removed from one batch to the next one using the same diffing_data_set_identifier, set their status to the value of this argument. Defaults to ‘deleted’.</p>
<p>Allowed values: <code class="enum">deleted</code>, <code class="enum">suspended</code></p></td>
</tr>
<tr class="request-param">
<td>batch_mode_enrollment_drop_status</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If batch_mode_enrollment_drop_status is passed, this SIS import will use this status for enrollments that are not included in the sis_batch. This will have an effect if multi_term_batch_mode is set. Defaults to ‘deleted’ This will still mark courses and sections that are not included in the sis_batch as deleted, and subsequently enrollments in the deleted courses and sections as deleted.</p>
<p>Allowed values: <code class="enum">deleted</code>, <code class="enum">completed</code>, <code class="enum">inactive</code></p></td>
</tr>
<tr class="request-param">
<td>change_threshold</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>If set with batch_mode, the batch cleanup process will not run if the number of items deleted is higher than the percentage set. If set to 10 and a term has 200 enrollments, and batch would delete more than 20 of the enrollments the batch will abort before the enrollments are deleted. The change_threshold will be evaluated for course, sections, and enrollments independently. If set with diffing, diffing will not be performed if the files are greater than the threshold as a percent. If set to 5 and the file is more than 5% smaller or more than 5% larger than the file that is being compared to, diffing will not be performed. If the files are less than 5%, diffing will be performed. The way the percent is calculated is by taking the size of the current import and dividing it by the size of the previous import. The formula used is: |(1 - current_file_size / previous_file_size)| * 100 See the SIS CSV Format documentation for more details. Required for multi_term_batch_mode.</p></td>
</tr>
<tr class="request-param">
<td>diff_row_count_threshold</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>If set with diffing, diffing will not be performed if the number of rows to be run in the fully calculated diff import exceeds the threshold.</p></td>
</tr>
</tbody>
</table>

Returns a [SisImport](sis_imports.html#SisImport) object

## Get SIS import status

### GET /api/v1/accounts/:account_id/sis_imports/:id

**Scope:** `url:GET|/api/v1/accounts/:account_id/sis_imports/:id`

Get the status of an already created SIS import.

``` code
Examples:
  curl https://<canvas>/api/v1/accounts/<account_id>/sis_imports/<sis_import_id> \
      -H 'Authorization: Bearer <token>'
```

Returns a [SisImport](sis_imports.html#SisImport) object

## Restore workflow_states of SIS imported items

### PUT /api/v1/accounts/:account_id/sis_imports/:id/restore_states

**Scope:** `url:PUT|/api/v1/accounts/:account_id/sis_imports/:id/restore_states`

This will restore the the workflow_state for all the items that changed their workflow_state during the import being restored. This will restore states for items imported with the following importers: accounts.csv terms.csv courses.csv sections.csv group_categories.csv groups.csv users.csv admins.csv This also restores states for other items that changed during the import. An example would be if an enrollment was deleted from a sis import and the group_membership was also deleted as a result of the enrollment deletion, both items would be restored when the sis batch is restored.

Restore data is retained for 30 days post-import. This endpoint is unavailable after that time.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| batch_mode |  | boolean | If set, will only restore items that were deleted from batch_mode. |
| undelete_only |  | boolean | If set, will only restore items that were deleted. This will ignore any items that were created or modified. |
| unconclude_only |  | boolean | If set, will only restore enrollments that were concluded. This will ignore any items that were created or deleted. |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/<account_id>/sis_imports/<sis_import_id>/restore_states \
  -H 'Authorization: Bearer <token>'
```

Returns a [Progress](progress.html#Progress) object

## Abort SIS import

### PUT /api/v1/accounts/:account_id/sis_imports/:id/abort

**Scope:** `url:PUT|/api/v1/accounts/:account_id/sis_imports/:id/abort`

Abort a SIS import that has not completed.

Aborting a sis batch that is running can take some time for every process to see the abort event. Subsequent sis batches begin to process 10 minutes after the abort to allow each process to clean up properly.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/<account_id>/sis_imports/<sis_import_id>/abort \
  -H 'Authorization: Bearer <token>'
```

Returns a [SisImport](sis_imports.html#SisImport) object

## Abort all pending SIS imports

### PUT /api/v1/accounts/:account_id/sis_imports/abort_all_pending

**Scope:** `url:PUT|/api/v1/accounts/:account_id/sis_imports/abort_all_pending`

Abort already created but not processed or processing SIS imports.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/<account_id>/sis_imports/abort_all_pending \
  -H 'Authorization: Bearer <token>'
```
