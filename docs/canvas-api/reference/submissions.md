# Submissions API

API for accessing and updating submissions for an assignment. The submission id in these URLs is the id of the student in the course, there is no separate submission id exposed in these APIs.

All submission actions can be performed with either the course id, or the course section id. SIS ids can be used, prefixed by "sis_course_id:" or "sis_section_id:" as described in the API documentation on SIS IDs.

### A MediaComment object looks like:

``` example
{
  "content-type": "audio/mp4",
  "display_name": "something",
  "media_id": "3232",
  "media_type": "audio",
  "url": "http://example.com/media_url"
}
```

### A SubmissionComment object looks like:

``` example
{
  "id": 37,
  "author_id": 134,
  "author_name": "Toph Beifong",
  // Abbreviated user object UserDisplay (see users API).
  "author": "{}",
  "comment": "Well here's the thing...",
  "created_at": "2012-01-01T01:00:00Z",
  "edited_at": "2012-01-02T01:00:00Z",
  "media_comment": null
}
```

### A Submission object looks like:

``` example
{
  // The submission's assignment id
  "assignment_id": 23,
  // The submission's assignment (see the assignments API) (optional)
  "assignment": null,
  // The submission's course (see the course API) (optional)
  "course": null,
  // This is the submission attempt number.
  "attempt": 1,
  // The content of the submission, if it was submitted directly in a text field.
  "body": "There are three factors too...",
  // The grade for the submission, translated into the assignment grading scheme
  // (so a letter grade, for example).
  "grade": "A-",
  // A boolean flag which is false if the student has re-submitted since the
  // submission was last graded.
  "grade_matches_current_submission": true,
  // URL to the submission. This will require the user to log in.
  "html_url": "http://example.com/courses/255/assignments/543/submissions/134",
  // URL to the submission preview. This will require the user to log in.
  "preview_url": "http://example.com/courses/255/assignments/543/submissions/134?preview=1",
  // The raw score
  "score": 13.5,
  // Associated comments for a submission (optional)
  "submission_comments": null,
  // The types of submission ex:
  // ('online_text_entry'|'online_url'|'online_upload'|'online_quiz'|'media_record
  // ing'|'student_annotation')
  "submission_type": "online_text_entry",
  // The timestamp when the assignment was submitted
  "submitted_at": "2012-01-01T01:00:00Z",
  // The URL of the submission (for 'online_url' submissions).
  "url": null,
  // The id of the user who created the submission
  "user_id": 134,
  // The id of the user who graded the submission. This will be null for
  // submissions that haven't been graded yet. It will be a positive number if a
  // real user has graded the submission and a negative number if the submission
  // was graded by a process (e.g. Quiz autograder and autograding LTI tools).
  // Specifically autograded quizzes set grader_id to the negative of the quiz id.
  // Submissions autograded by LTI tools set grader_id to the negative of the tool
  // id.
  "grader_id": 86,
  "graded_at": "2012-01-02T03:05:34Z",
  // The submissions user (see user API) (optional)
  "user": null,
  // Whether the submission was made after the applicable due date
  "late": false,
  // Whether the assignment is visible to the user who submitted the assignment.
  // Submissions where `assignment_visible` is false no longer count towards the
  // student's grade and the assignment can no longer be accessed by the student.
  // `assignment_visible` becomes false for submissions that do not have a grade
  // and whose assignment is no longer assigned to the student's section.
  "assignment_visible": true,
  // Whether the assignment is excused.  Excused assignments have no impact on a
  // user's grade.
  "excused": true,
  // Whether the assignment is missing.
  "missing": true,
  // The status of the submission in relation to the late policy. Can be late,
  // missing, extended, none, or null.
  "late_policy_status": "missing",
  // The amount of points automatically deducted from the score by the
  // missing/late policy for a late or missing assignment.
  "points_deducted": 12.3,
  // The amount of time, in seconds, that an submission is late by.
  "seconds_late": 300,
  // The current state of the submission
  "workflow_state": "submitted",
  // Extra submission attempts allowed for the given user and assignment.
  "extra_attempts": 10,
  // A unique short ID identifying this submission without reference to the owning
  // user. Only included if the caller has administrator access for the current
  // account.
  "anonymous_id": "acJ4Q",
  // The date this submission was posted to the student, or nil if it has not been
  // posted.
  "posted_at": "2020-01-02T11:10:30Z",
  // The read status of this submission for the given user (optional). Including
  // read_status will mark submission(s) as read.
  "read_status": "read",
  // This indicates whether the submission has been reassigned by the instructor.
  "redo_request": true
}
```

## Submit an assignment

### POST /api/v1/courses/:course_id/assignments/:assignment_id/submissions

**Scope:** `url:POST|/api/v1/courses/:course_id/assignments/:assignment_id/submissions`

### POST /api/v1/sections/:section_id/assignments/:assignment_id/submissions

**Scope:** `url:POST|/api/v1/sections/:section_id/assignments/:assignment_id/submissions`

Make a submission for an assignment. You must be actively enrolled as a student in the course/section to do this. Concluded and pending enrollments are not permitted.

All online turn-in submission types are supported in this API. However, there are a few things that are not yet supported:

- Files can be submitted based on a file ID of a user or group file or through the [file upload API](submissions.html#method.submissions_api.create_file "file upload API"). However, there is no API yet for listing the user and group files.

- Media comments can be submitted, however, there is no API yet for creating a media comment to submit.

- Integration with Google Docs is not yet supported.

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
<td>comment[text_comment]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Include a textual comment with the submission.</p></td>
</tr>
<tr class="request-param">
<td>submission[group_comment]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not this comment should be sent to the entire group (defaults to false). Ignored if this is not a group assignment or if no text_comment is provided.</p></td>
</tr>
<tr class="request-param">
<td>submission[submission_type]</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The type of submission being made. The assignment submission_types must include this submission type as an allowed option, or the submission will be rejected with a 400 error.</p>
<p>The submission_type given determines which of the following parameters is used. For instance, to submit a URL, submission [submission_type] must be set to “online_url”, otherwise the submission [url] parameter will be ignored.</p>
<p>“basic_lti_launch” requires the assignment submission_type “online” or “external_tool”</p>
<p>Allowed values: <code class="enum">online_text_entry</code>, <code class="enum">online_url</code>, <code class="enum">online_upload</code>, <code class="enum">media_recording</code>, <code class="enum">basic_lti_launch</code>, <code class="enum">student_annotation</code></p></td>
</tr>
<tr class="request-param">
<td>submission[body]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Submit the assignment as an HTML document snippet. Note this HTML snippet will be sanitized using the same ruleset as a submission made from the Canvas web UI. The sanitized HTML will be returned in the response as the submission body. Requires a submission_type of “online_text_entry”.</p></td>
</tr>
<tr class="request-param">
<td>submission[url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Submit the assignment as a URL. The URL scheme must be “http” or “https”, no “ftp” or other URL schemes are allowed. If no scheme is given (e.g. “www.example.com”) then “http” will be assumed. Requires a submission_type of “online_url” or “basic_lti_launch”.</p></td>
</tr>
<tr class="request-param">
<td>submission[file_ids][]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Submit the assignment as a set of one or more previously uploaded files residing in the submitting user’s files section (or the group’s files section, for group assignments).</p>
<p>To upload a new file to submit, see the submissions Upload a file API.</p>
<p>Requires a submission_type of “online_upload”.</p></td>
</tr>
<tr class="request-param">
<td>submission[media_comment_id]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The media comment id to submit. Media comment ids can be submitted via this API, however, note that there is not yet an API to generate or list existing media comments, so this functionality is currently of limited use.</p>
<p>Requires a submission_type of “media_recording”.</p></td>
</tr>
<tr class="request-param">
<td>submission[media_comment_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The type of media comment being submitted.</p>
<p>Allowed values: <code class="enum">audio</code>, <code class="enum">video</code></p></td>
</tr>
<tr class="request-param">
<td>submission[user_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Submit on behalf of the given user. Requires grading permission.</p></td>
</tr>
<tr class="request-param">
<td>submission[annotatable_attachment_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The Attachment ID of the document being annotated. This should match the annotatable_attachment_id on the assignment.</p>
<p>Requires a submission_type of “student_annotation”.</p></td>
</tr>
<tr class="request-param">
<td>submission[submitted_at]</td>
<td></td>
<td>DateTime</td>
<td class="param-desc"><p>Choose the time the submission is listed as submitted at. Requires grading permission.</p></td>
</tr>
</tbody>
</table>

## List assignment submissions

### GET /api/v1/courses/:course_id/assignments/:assignment_id/submissions

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/submissions`

### GET /api/v1/sections/:section_id/assignments/:assignment_id/submissions

**Scope:** `url:GET|/api/v1/sections/:section_id/assignments/:assignment_id/submissions`

A paginated list of all existing submissions for an assignment.

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
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Associations to include with the group. “group” will add group_id and group_name.</p>
<p>Allowed values: <code class="enum">submission_history</code>, <code class="enum">submission_comments</code>, <code class="enum">submission_html_comments</code>, <code class="enum">rubric_assessment</code>, <code class="enum">assignment</code>, <code class="enum">visibility</code>, <code class="enum">course</code>, <code class="enum">user</code>, <code class="enum">group</code>, <code class="enum">read_status</code>, <code class="enum">student_entered_score</code></p></td>
</tr>
<tr class="request-param">
<td>grouped</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If this argument is true, the response will be grouped by student groups.</p></td>
</tr>
</tbody>
</table>

#### API response field:

-  assignment_id

  The unique identifier for the assignment.

-  user_id

  The id of the user who submitted the assignment.

-  grader_id

  The id of the user who graded the submission. This will be null for submissions that haven’t been graded yet. It will be a positive number if a real user has graded the submission and a negative number if the submission was graded by a process (e.g. Quiz autograder and autograding LTI tools). Specifically autograded quizzes set grader_id to the negative of the quiz id. Submissions autograded by LTI tools set grader_id to the negative of the tool id.

-  canvadoc_document_id

  The id for the canvadoc document associated with this submission, if it was a file upload.

-  submitted_at

  The timestamp when the assignment was submitted, if an actual submission has been made.

-  score

  The raw score for the assignment submission.

-  attempt

  If multiple submissions have been made, this is the attempt number.

-  body

  The content of the submission, if it was submitted directly in a text field.

-  grade

  The grade for the submission, translated into the assignment grading scheme (so a letter grade, for example).

-  grade_matches_current_submission

  A boolean flag which is false if the student has re-submitted since the submission was last graded.

-  preview_url

  Link to the URL in canvas where the submission can be previewed. This will require the user to log in.

-  redo_request

  If the submission was reassigned

-  url

  If the submission was made as a URL.

-  late

  Whether the submission was made after the applicable due date.

-  assignment_visible

  Whether this assignment is visible to the user who submitted the assignment.

-  workflow_state

  The current status of the submission. Possible values: “submitted”, “unsubmitted”, “graded”, “pending_review”

Returns a list of [Submission](what_if_grades.html#Submission) objects

## List submissions for multiple assignments

### GET /api/v1/courses/:course_id/students/submissions

**Scope:** `url:GET|/api/v1/courses/:course_id/students/submissions`

### GET /api/v1/sections/:section_id/students/submissions

**Scope:** `url:GET|/api/v1/sections/:section_id/students/submissions`

A paginated list of all existing submissions for a given set of students and assignments.

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
<td>student_ids[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>List of student ids to return submissions for. If this argument is omitted, return submissions for the calling user. Students may only list their own submissions. Observers may only list those of associated students. The special id “all” will return submissions for all students in the course/section as appropriate.</p></td>
</tr>
<tr class="request-param">
<td>assignment_ids[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>List of assignments to return submissions for. If none are given, submissions for all assignments are returned.</p></td>
</tr>
<tr class="request-param">
<td>grouped</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If this argument is present, the response will be grouped by student, rather than a flat array of submissions.</p></td>
</tr>
<tr class="request-param">
<td>post_to_sis</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If this argument is set to true, the response will only include submissions for assignments that have the post_to_sis flag set to true and user enrollments that were added through sis.</p></td>
</tr>
<tr class="request-param">
<td>submitted_since</td>
<td></td>
<td>DateTime</td>
<td class="param-desc"><p>If this argument is set, the response will only include submissions that were submitted after the specified date_time. This will exclude submissions that do not have a submitted_at which will exclude unsubmitted submissions. The value must be formatted as ISO 8601 YYYY-MM-DDTHH:MM:SSZ.</p></td>
</tr>
<tr class="request-param">
<td>graded_since</td>
<td></td>
<td>DateTime</td>
<td class="param-desc"><p>If this argument is set, the response will only include submissions that were graded after the specified date_time. This will exclude submissions that have not been graded. The value must be formatted as ISO 8601 YYYY-MM-DDTHH:MM:SSZ.</p></td>
</tr>
<tr class="request-param">
<td>grading_period_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the grading period in which submissions are being requested (Requires grading periods to exist on the account)</p></td>
</tr>
<tr class="request-param">
<td>workflow_state</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The current status of the submission</p>
<p>Allowed values: <code class="enum">submitted</code>, <code class="enum">unsubmitted</code>, <code class="enum">graded</code>, <code class="enum">pending_review</code></p></td>
</tr>
<tr class="request-param">
<td>enrollment_state</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The current state of the enrollments. If omitted will include all enrollments that are not deleted.</p>
<p>Allowed values: <code class="enum">active</code>, <code class="enum">concluded</code></p></td>
</tr>
<tr class="request-param">
<td>state_based_on_date</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If omitted it is set to true. When set to false it will ignore the effective state of the student enrollments and use the workflow_state for the enrollments. The argument is ignored unless enrollment_state argument is also passed.</p></td>
</tr>
<tr class="request-param">
<td>order</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The order submissions will be returned in. Defaults to “id”. Doesn’t affect results for “grouped” mode.</p>
<p>Allowed values: <code class="enum">id</code>, <code class="enum">graded_at</code></p></td>
</tr>
<tr class="request-param">
<td>order_direction</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Determines whether ordered results are returned in ascending or descending order. Defaults to “ascending”. Doesn’t affect results for “grouped” mode.</p>
<p>Allowed values: <code class="enum">ascending</code>, <code class="enum">descending</code></p></td>
</tr>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Associations to include with the group. ‘total_scores` requires the `grouped` argument.</p>
<p>Allowed values: <code class="enum">submission_history</code>, <code class="enum">submission_comments</code>, <code class="enum">submission_html_comments</code>, <code class="enum">rubric_assessment</code>, <code class="enum">assignment</code>, <code class="enum">total_scores</code>, <code class="enum">visibility</code>, <code class="enum">course</code>, <code class="enum">user</code>, <code class="enum">sub_assignment_submissions</code>, <code class="enum">student_entered_score</code></p></td>
</tr>
</tbody>
</table>

#### Example Response:

####

``` example
# Without grouped:

[
  { "assignment_id": 100, grade: 5, "user_id": 1, ... },
  { "assignment_id": 101, grade: 6, "user_id": 2, ... }

# With grouped:

[
  {
    "user_id": 1,
    "submissions": [
      { "assignment_id": 100, grade: 5, ... },
      { "assignment_id": 101, grade: 6, ... }
    ]
  }
]
```

## Get a single submission

### GET /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id`

### GET /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id

**Scope:** `url:GET|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id`

Get a single submission, based on user id.

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
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Associations to include with the group.</p>
<p>Allowed values: <code class="enum">submission_history</code>, <code class="enum">submission_comments</code>, <code class="enum">submission_html_comments</code>, <code class="enum">rubric_assessment</code>, <code class="enum">full_rubric_assessment</code>, <code class="enum">visibility</code>, <code class="enum">course</code>, <code class="enum">user</code>, <code class="enum">read_status</code>, <code class="enum">student_entered_score</code></p></td>
</tr>
</tbody>
</table>

## Get a single submission by anonymous id

### GET /api/v1/courses/:course_id/assignments/:assignment_id/anonymous_submissions/:anonymous_id

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/anonymous_submissions/:anonymous_id`

### GET /api/v1/sections/:section_id/assignments/:assignment_id/anonymous_submissions/:anonymous_id

**Scope:** `url:GET|/api/v1/sections/:section_id/assignments/:assignment_id/anonymous_submissions/:anonymous_id`

Get a single submission, based on the submission’s anonymous id.

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
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Associations to include with the group.</p>
<p>Allowed values: <code class="enum">submission_history</code>, <code class="enum">submission_comments</code>, <code class="enum">rubric_assessment</code>, <code class="enum">full_rubric_assessment</code>, <code class="enum">visibility</code>, <code class="enum">course</code>, <code class="enum">user</code>, <code class="enum">read_status</code></p></td>
</tr>
</tbody>
</table>

## Upload a file

### POST /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/files

**Scope:** `url:POST|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/files`

### POST /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/files

**Scope:** `url:POST|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/files`

Upload a file to a submission.

This API endpoint is the first step in uploading a file to a submission as a student. See the [File Upload Documentation](file_uploads.html "File Upload Documentation") for details on the file upload workflow.

The final step of the file upload workflow will return the attachment data, including the new file id. The caller can then POST to submit the `online_upload` assignment with these file ids.

## Grade or comment on a submission

### PUT /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id

**Scope:** `url:PUT|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id`

### PUT /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id

**Scope:** `url:PUT|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id`

Comment on and/or update the grading for a student’s assignment submission. If any submission or rubric_assessment arguments are provided, the user must have permission to manage grades in the appropriate context (course or section).

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
<td>comment[text_comment]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Add a textual comment to the submission.</p></td>
</tr>
<tr class="request-param">
<td>comment[attempt]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The attempt number (starts at 1) to associate the comment with.</p></td>
</tr>
<tr class="request-param">
<td>comment[group_comment]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not this comment should be sent to the entire group (defaults to false). Ignored if this is not a group assignment or if no text_comment is provided.</p></td>
</tr>
<tr class="request-param">
<td>comment[media_comment_id]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Add an audio/video comment to the submission. Media comments can be added via this API, however, note that there is not yet an API to generate or list existing media comments, so this functionality is currently of limited use.</p></td>
</tr>
<tr class="request-param">
<td>comment[media_comment_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The type of media comment being added.</p>
<p>Allowed values: <code class="enum">audio</code>, <code class="enum">video</code></p></td>
</tr>
<tr class="request-param">
<td>comment[file_ids][]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Attach files to this comment that were previously uploaded using the Submission Comment API’s files action</p></td>
</tr>
<tr class="request-param">
<td>include[visibility]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Whether this assignment is visible to the owner of the submission</p></td>
</tr>
<tr class="request-param">
<td>prefer_points_over_scheme</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Treat posted_grade as points if the value matches a grading scheme value</p></td>
</tr>
<tr class="request-param">
<td>submission[posted_grade]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Assign a score to the submission, updating both the “score” and “grade” fields on the submission record. This parameter can be passed in a few different formats:</p>
<dl>
<dt>points</dt>
<dd>
<p>A floating point or integral value, such as “13.5”. The grade</p>
</dd>
</dl>
`will be interpreted directly as the score of the assignment.
Values above assignment.points_possible are allowed, for awarding
extra credit.`
<dl>
<dt>percentage</dt>
<dd>
<p>A floating point value appended with a percent sign, such as</p>
</dd>
</dl>
`"40%". The grade will be interpreted as a percentage score on the
assignment, where 100% == assignment.points_possible. Values above 100%
are allowed, for awarding extra credit.`
<dl>
<dt>letter grade</dt>
<dd>
<p>A letter grade, following the assignment’s defined letter</p>
</dd>
</dl>
`grading scheme. For example, "A-". The resulting score will be the high
end of the defined range for the letter grade. For instance, if "B" is
defined as 86% to 84%, a letter grade of "B" will be worth 86%. The
letter grade will be rejected if the assignment does not have a defined
letter grading scheme. For more fine-grained control of scores, pass in
points or percentage rather than the letter grade.`
<dl>
<dt>“pass/complete/fail/incomplete”</dt>
<dd>
<p>A string value of “pass” or “complete”</p>
</dd>
</dl>
`will give a score of 100%. "fail" or "incomplete" will give a score of
0.`
<p>Note that assignments with grading_type of “pass_fail” can only be assigned a score of 0 or assignment.points_possible, nothing inbetween. If a posted_grade in the “points” or “percentage” format is sent, the grade will only be accepted if the grade equals one of those two values.</p></td>
</tr>
<tr class="request-param">
<td>submission[excuse]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Sets the “excused” status of an assignment.</p></td>
</tr>
<tr class="request-param">
<td>submission[late_policy_status]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Sets the late policy status to either “late”, “missing”, “extended”, “none”, or null.</p>
`NB: "extended" values can only be set in the UI when the "UI features for 'extended' Submissions" Account Feature is on`</td>
</tr>
<tr class="request-param">
<td>submission[sticker]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Sets the sticker for the submission.</p>
<p>Allowed values: <code class="enum">apple</code>, <code class="enum">basketball</code>, <code class="enum">bell</code>, <code class="enum">book</code>, <code class="enum">bookbag</code>, <code class="enum">briefcase</code>, <code class="enum">bus</code>, <code class="enum">calendar</code>, <code class="enum">chem</code>, <code class="enum">design</code>, <code class="enum">pencil</code>, <code class="enum">beaker</code>, <code class="enum">paintbrush</code>, <code class="enum">computer</code>, <code class="enum">column</code>, <code class="enum">pen</code>, <code class="enum">tablet</code>, <code class="enum">telescope</code>, <code class="enum">calculator</code>, <code class="enum">paperclip</code>, <code class="enum">composite_notebook</code>, <code class="enum">scissors</code>, <code class="enum">ruler</code>, <code class="enum">clock</code>, <code class="enum">globe</code>, <code class="enum">grad</code>, <code class="enum">gym</code>, <code class="enum">mail</code>, <code class="enum">microscope</code>, <code class="enum">mouse</code>, <code class="enum">music</code>, <code class="enum">notebook</code>, <code class="enum">page</code>, <code class="enum">panda1</code>, <code class="enum">panda2</code>, <code class="enum">panda3</code>, <code class="enum">panda4</code>, <code class="enum">panda5</code>, <code class="enum">panda6</code>, <code class="enum">panda7</code>, <code class="enum">panda8</code>, <code class="enum">panda9</code>, <code class="enum">presentation</code>, <code class="enum">science</code>, <code class="enum">science2</code>, <code class="enum">star</code>, <code class="enum">tag</code>, <code class="enum">tape</code>, <code class="enum">target</code>, <code class="enum">trophy</code></p></td>
</tr>
<tr class="request-param">
<td>submission[seconds_late_override]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Sets the seconds late if late policy status is “late”</p></td>
</tr>
<tr class="request-param">
<td>rubric_assessment</td>
<td></td>
<td>RubricAssessment</td>
<td class="param-desc"><p>Assign a rubric assessment to this assignment submission. The sub-parameters here depend on the rubric for the assignment. The general format is, for each row in the rubric:</p>
<p>The points awarded for this row.</p>
`rubric_assessment[criterion_id][points]`
<p>The rating id for the row.</p>
`rubric_assessment[criterion_id][rating_id]`
<p>Comments to add for this row.</p>
`rubric_assessment[criterion_id][comments]`
<p>For example, if the assignment rubric is (in JSON format):</p>
`[
  {
    'id': 'crit1',
    'points': 10,
    'description': 'Criterion 1',
    'ratings':
    [
      { 'id': 'rat1', 'description': 'Good', 'points': 10 },
      { 'id': 'rat2', 'description': 'Poor', 'points': 3 }
    ]
  },
  {
    'id': 'crit2',
    'points': 5,
    'description': 'Criterion 2',
    'ratings':
    [
      { 'id': 'rat1', 'description': 'Exemplary', 'points': 5 },
      { 'id': 'rat2', 'description': 'Complete', 'points': 5 },
      { 'id': 'rat3', 'description': 'Incomplete', 'points': 0 }
    ]
  }
]`
<p>Then a possible set of values for rubric_assessment would be:</p>
`rubric_assessment[crit1][points]=3&rubric_assessment[crit1][rating_id]=rat1&rubric_assessment[crit2][points]=5&rubric_assessment[crit2][rating_id]=rat2&rubric_assessment[crit2][comments]=Well%20Done.`</td>
</tr>
</tbody>
</table>

## Grade or comment on a submission by anonymous id

### PUT /api/v1/courses/:course_id/assignments/:assignment_id/anonymous_submissions/:anonymous_id

**Scope:** `url:PUT|/api/v1/courses/:course_id/assignments/:assignment_id/anonymous_submissions/:anonymous_id`

### PUT /api/v1/sections/:section_id/assignments/:assignment_id/anonymous_submissions/:anonymous_id

**Scope:** `url:PUT|/api/v1/sections/:section_id/assignments/:assignment_id/anonymous_submissions/:anonymous_id`

Comment on and/or update the grading for a student’s assignment submission, fetching the submission by anonymous id (instead of user id). If any submission or rubric_assessment arguments are provided, the user must have permission to manage grades in the appropriate context (course or section).

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
<td>comment[text_comment]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Add a textual comment to the submission.</p></td>
</tr>
<tr class="request-param">
<td>comment[group_comment]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not this comment should be sent to the entire group (defaults to false). Ignored if this is not a group assignment or if no text_comment is provided.</p></td>
</tr>
<tr class="request-param">
<td>comment[media_comment_id]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Add an audio/video comment to the submission. Media comments can be added via this API, however, note that there is not yet an API to generate or list existing media comments, so this functionality is currently of limited use.</p></td>
</tr>
<tr class="request-param">
<td>comment[media_comment_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The type of media comment being added.</p>
<p>Allowed values: <code class="enum">audio</code>, <code class="enum">video</code></p></td>
</tr>
<tr class="request-param">
<td>comment[file_ids][]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Attach files to this comment that were previously uploaded using the Submission Comment API’s files action</p></td>
</tr>
<tr class="request-param">
<td>include[visibility]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Whether this assignment is visible to the owner of the submission</p></td>
</tr>
<tr class="request-param">
<td>submission[posted_grade]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Assign a score to the submission, updating both the “score” and “grade” fields on the submission record. This parameter can be passed in a few different formats:</p>
<dl>
<dt>points</dt>
<dd>
<p>A floating point or integral value, such as “13.5”. The grade</p>
</dd>
</dl>
`will be interpreted directly as the score of the assignment.
Values above assignment.points_possible are allowed, for awarding
extra credit.`
<dl>
<dt>percentage</dt>
<dd>
<p>A floating point value appended with a percent sign, such as</p>
</dd>
</dl>
`"40%". The grade will be interpreted as a percentage score on the
assignment, where 100% == assignment.points_possible. Values above 100%
are allowed, for awarding extra credit.`
<dl>
<dt>letter grade</dt>
<dd>
<p>A letter grade, following the assignment’s defined letter</p>
</dd>
</dl>
`grading scheme. For example, "A-". The resulting score will be the high
end of the defined range for the letter grade. For instance, if "B" is
defined as 86% to 84%, a letter grade of "B" will be worth 86%. The
letter grade will be rejected if the assignment does not have a defined
letter grading scheme. For more fine-grained control of scores, pass in
points or percentage rather than the letter grade.`
<dl>
<dt>“pass/complete/fail/incomplete”</dt>
<dd>
<p>A string value of “pass” or “complete”</p>
</dd>
</dl>
`will give a score of 100%. "fail" or "incomplete" will give a score of
0.`
<p>Note that assignments with grading_type of “pass_fail” can only be assigned a score of 0 or assignment.points_possible, nothing inbetween. If a posted_grade in the “points” or “percentage” format is sent, the grade will only be accepted if the grade equals one of those two values.</p></td>
</tr>
<tr class="request-param">
<td>submission[excuse]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Sets the “excused” status of an assignment.</p></td>
</tr>
<tr class="request-param">
<td>submission[late_policy_status]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Sets the late policy status to either “late”, “missing”, “extended”, “none”, or null.</p>
`NB: "extended" values can only be set in the UI when the "UI features for 'extended' Submissions" Account Feature is on`</td>
</tr>
<tr class="request-param">
<td>submission[seconds_late_override]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Sets the seconds late if late policy status is “late”</p></td>
</tr>
<tr class="request-param">
<td>rubric_assessment</td>
<td></td>
<td>RubricAssessment</td>
<td class="param-desc"><p>Assign a rubric assessment to this assignment submission. The sub-parameters here depend on the rubric for the assignment. The general format is, for each row in the rubric:</p>
<p>The points awarded for this row.</p>
`rubric_assessment[criterion_id][points]`
<p>The rating id for the row.</p>
`rubric_assessment[criterion_id][rating_id]`
<p>Comments to add for this row.</p>
`rubric_assessment[criterion_id][comments]`
<p>For example, if the assignment rubric is (in JSON format):</p>
`[
  {
    'id': 'crit1',
    'points': 10,
    'description': 'Criterion 1',
    'ratings':
    [
      { 'id': 'rat1', 'description': 'Good', 'points': 10 },
      { 'id': 'rat2', 'description': 'Poor', 'points': 3 }
    ]
  },
  {
    'id': 'crit2',
    'points': 5,
    'description': 'Criterion 2',
    'ratings':
    [
      { 'id': 'rat1', 'description': 'Exemplary', 'points': 5 },
      { 'id': 'rat2', 'description': 'Complete', 'points': 5 },
      { 'id': 'rat3', 'description': 'Incomplete', 'points': 0 }
    ]
  }
]`
<p>Then a possible set of values for rubric_assessment would be:</p>
`rubric_assessment[crit1][points]=3&rubric_assessment[crit1][rating_id]=rat1&rubric_assessment[crit2][points]=5&rubric_assessment[crit2][rating_id]=rat2&rubric_assessment[crit2][comments]=Well%20Done.`</td>
</tr>
</tbody>
</table>

## List gradeable students

### GET /api/v1/courses/:course_id/assignments/:assignment_id/gradeable_students

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/gradeable_students`

A paginated list of students eligible to submit the assignment. The caller must have permission to view grades.

If anonymous grading is enabled for the current assignment and the allow_new_anonymous_id parameter is passed, the returned data will not include any values identifying the student, but will instead include an assignment-specific anonymous ID for each student.

Section-limited instructors will only see students in their own sections.

Returns a list of [UserDisplay](users.html#UserDisplay) objects

## List multiple assignments gradeable students

### GET /api/v1/courses/:course_id/assignments/gradeable_students

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/gradeable_students`

A paginated list of students eligible to submit a list of assignments. The caller must have permission to view grades for the requested course.

Section-limited instructors will only see students in their own sections.

#### Request Parameters:

| Parameter          |     | Type   | Description                 |
|--------------------|-----|--------|-----------------------------|
| assignment_ids\[\] |     | string | Assignments being requested |

#### Example Response:

####

``` example
A [UserDisplay] with an extra assignment_ids field to indicate what assignments
that user can submit

[
  {
    "id": 2,
    "display_name": "Display Name",
    "avatar_image_url": "http://avatar-image-url.jpeg",
    "html_url": "http://canvas.com",
    "assignment_ids": [1, 2, 3]
  }
]
```

## Grade or comment on multiple submissions

### POST /api/v1/courses/:course_id/submissions/update_grades

**Scope:** `url:POST|/api/v1/courses/:course_id/submissions/update_grades`

### POST /api/v1/courses/:course_id/assignments/:assignment_id/submissions/update_grades

**Scope:** `url:POST|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/update_grades`

### POST /api/v1/sections/:section_id/submissions/update_grades

**Scope:** `url:POST|/api/v1/sections/:section_id/submissions/update_grades`

### POST /api/v1/sections/:section_id/assignments/:assignment_id/submissions/update_grades

**Scope:** `url:POST|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/update_grades`

Update the grading and comments on multiple student’s assignment submissions in an asynchronous job.

The user must have permission to manage grades in the appropriate context (course or section).

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
<td>grade_data[&lt;student_id&gt;][posted_grade]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>See documentation for the posted_grade argument in the Submissions Update documentation</p></td>
</tr>
<tr class="request-param">
<td>grade_data[&lt;student_id&gt;][excuse]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>See documentation for the excuse argument in the Submissions Update documentation</p></td>
</tr>
<tr class="request-param">
<td>grade_data[&lt;student_id&gt;][rubric_assessment]</td>
<td></td>
<td>RubricAssessment</td>
<td class="param-desc"><p>See documentation for the rubric_assessment argument in the Submissions Update documentation</p></td>
</tr>
<tr class="request-param">
<td>grade_data[&lt;student_id&gt;][text_comment]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>no description</p></td>
</tr>
<tr class="request-param">
<td>grade_data[&lt;student_id&gt;][group_comment]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>no description</p></td>
</tr>
<tr class="request-param">
<td>grade_data[&lt;student_id&gt;][media_comment_id]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>no description</p></td>
</tr>
<tr class="request-param">
<td>grade_data[&lt;student_id&gt;][media_comment_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>no description</p>
<p>Allowed values: <code class="enum">audio</code>, <code class="enum">video</code></p></td>
</tr>
<tr class="request-param">
<td>grade_data[&lt;student_id&gt;][file_ids][]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>See documentation for the comment[] arguments in the Submissions Update documentation</p></td>
</tr>
<tr class="request-param">
<td>grade_data[&lt;assignment_id&gt;][&lt;student_id&gt;]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Specifies which assignment to grade. This argument is not necessary when using the assignment-specific endpoints.</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/1/assignments/2/submissions/update_grades' \
     -X POST \
     -F 'grade_data[3][posted_grade]=88' \
     -F 'grade_data[4][posted_grade]=95' \
     -H "Authorization: Bearer <token>"
```

Returns a [Progress](progress.html#Progress) object

## Mark submission as read

### PUT /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/read

**Scope:** `url:PUT|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/read`

### PUT /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/read

**Scope:** `url:PUT|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/read`

No request fields are necessary.

On success, the response will be 204 No Content with an empty body.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/<course_id>/assignments/<assignment_id>/submissions/<user_id>/read.json' \
     -X PUT \
     -H "Authorization: Bearer <token>" \
     -H "Content-Length: 0"
```

## Mark submission as unread

### DELETE /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/read

**Scope:** `url:DELETE|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/read`

### DELETE /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/read

**Scope:** `url:DELETE|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/read`

No request fields are necessary.

On success, the response will be 204 No Content with an empty body.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/<course_id>/assignments/<assignment_id>/submissions/<user_id>/read.json' \
     -X DELETE \
     -H "Authorization: Bearer <token>"
```

## Mark bulk submissions as read

### PUT /api/v1/courses/:course_id/submissions/bulk_mark_read

**Scope:** `url:PUT|/api/v1/courses/:course_id/submissions/bulk_mark_read`

### PUT /api/v1/sections/:section_id/submissions/bulk_mark_read

**Scope:** `url:PUT|/api/v1/sections/:section_id/submissions/bulk_mark_read`

Accepts a string array of submission ids. Loops through and marks each submission as read

On success, the response will be 204 No Content with an empty body.

#### Request Parameters:

| Parameter         |     | Type   | Description    |
|-------------------|-----|--------|----------------|
| submissionIds\[\] |     | string | no description |

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/<course_id>/submissions/bulk_mark_read.json' \
     -X PUT \
     -H "Authorization: Bearer <token>" \
     -H "Content-Length: 0" \
     -F 'submissionIds=['88']'
```

## Mark submission item as read

### PUT /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/read/:item

**Scope:** `url:PUT|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/read/:item`

### PUT /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/read/:item

**Scope:** `url:PUT|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/read/:item`

No request fields are necessary.

A submission item can be “grade”, “comment” or “rubric”

On success, the response will be 204 No Content with an empty body.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/<course_id>/assignments/<assignment_id>/submissions/<user_id>/read/<item>.json' \
     -X PUT \
     -H "Authorization: Bearer <token>" \
     -H "Content-Length: 0"
```

## Clear unread status for all submissions.

### PUT /api/v1/courses/:course_id/submissions/:user_id/clear_unread

**Scope:** `url:PUT|/api/v1/courses/:course_id/submissions/:user_id/clear_unread`

### PUT /api/v1/sections/:section_id/submissions/:user_id/clear_unread

**Scope:** `url:PUT|/api/v1/sections/:section_id/submissions/:user_id/clear_unread`

Site-admin-only endpoint.

No request fields are necessary.

On success, the response will be 204 No Content with an empty body.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/<course_id>/submissions/<user_id>/clear_unread.json' \
     -X PUT \
     -H "Authorization: Bearer <token>" \
     -H "Content-Length: 0"
```

## Get rubric assessments read state

### GET /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/rubric_comments/read

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/rubric_comments/read`

### GET /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/rubric_assessments/read

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/rubric_assessments/read`

### GET /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/rubric_comments/read

**Scope:** `url:GET|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/rubric_comments/read`

### GET /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/rubric_assessments/read

**Scope:** `url:GET|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/rubric_assessments/read`

Return whether new rubric comments/grading made on a submission have been seen by the student being assessed.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/<course_id>/assignments/<assignment_id>/submissions/<user_id>/rubric_comments/read' \
     -H "Authorization: Bearer <token>"

# or

curl 'https://<canvas>/api/v1/courses/<course_id>/assignments/<assignment_id>/submissions/<user_id>/rubric_assessments/read' \
     -H "Authorization: Bearer <token>"
```

#### Example Response:

####

``` example
{
  "read": false
}
```

## Mark rubric assessments as read

### PUT /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/rubric_comments/read

**Scope:** `url:PUT|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/rubric_comments/read`

### PUT /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/rubric_assessments/read

**Scope:** `url:PUT|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/rubric_assessments/read`

### PUT /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/rubric_comments/read

**Scope:** `url:PUT|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/rubric_comments/read`

### PUT /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/rubric_assessments/read

**Scope:** `url:PUT|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/rubric_assessments/read`

Indicate that rubric comments/grading made on a submission have been read by the student being assessed. Only the student who owns the submission can use this endpoint.

NOTE: Rubric assessments will be marked as read automatically when they are viewed in Canvas web.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/<course_id>/assignments/<assignment_id>/submissions/<user_id>/rubric_comments/read' \
     -X PUT \
     -H "Authorization: Bearer <token>" \
     -H "Content-Length: 0"

# or

curl 'https://<canvas>/api/v1/courses/<course_id>/assignments/<assignment_id>/submissions/<user_id>/rubric_assessments/read' \
     -X PUT \
     -H "Authorization: Bearer <token>" \
     -H "Content-Length: 0"
```

#### Example Response:

####

``` example
{
  "read": true
}
```

## Get document annotations read state

### GET /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/document_annotations/read

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/document_annotations/read`

### GET /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/document_annotations/read

**Scope:** `url:GET|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/document_annotations/read`

Return whether annotations made on a submitted document have been read by the student

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/<course_id>/assignments/<assignment_id>/submissions/<user_id>/document_annotations/read' \
     -H "Authorization: Bearer <token>"
```

#### Example Response:

####

``` example
{
  "read": false
}
```

## Mark document annotations as read

### PUT /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/document_annotations/read

**Scope:** `url:PUT|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:user_id/document_annotations/read`

### PUT /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/document_annotations/read

**Scope:** `url:PUT|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:user_id/document_annotations/read`

Indicate that annotations made on a submitted document have been read by the student. Only the student who owns the submission can use this endpoint.

NOTE: Document annotations will be marked as read automatically when they are viewed in Canvas web.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/<course_id>/assignments/<assignment_id>/submissions/<user_id>/document_annotations/read' \
     -X PUT \
     -H "Authorization: Bearer <token>" \
     -H "Content-Length: 0"
```

#### Example Response:

####

``` example
{
  "read": true
}
```

## Submission Summary

### GET /api/v1/courses/:course_id/assignments/:assignment_id/submission_summary

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/submission_summary`

### GET /api/v1/sections/:section_id/assignments/:assignment_id/submission_summary

**Scope:** `url:GET|/api/v1/sections/:section_id/assignments/:assignment_id/submission_summary`

Returns the number of submissions for the given assignment based on gradeable students that fall into three categories: graded, ungraded, not submitted.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| grouped |  | boolean | If this argument is true, the response will take into account student groups. |

#### Example Response:

####

``` example
{
  "graded": 5,
  "ungraded": 10,
  "not_submitted": 42
}
```
