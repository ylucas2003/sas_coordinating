# Courses API

API for accessing course information.

### A Term object looks like:

``` example
{
  "id": 1,
  "name": "Default Term",
  "start_at": "2012-06-01T00:00:00-06:00",
  "end_at": null
}
```

### A CourseProgress object looks like:

``` example
{
  // total number of requirements from all modules
  "requirement_count": 10,
  // total number of requirements the user has completed from all modules
  "requirement_completed_count": 1,
  // url to next module item that has an unmet requirement. null if the user has
  // completed the course or the current module does not require sequential
  // progress
  "next_requirement_url": "http://localhost/courses/1/modules/items/2",
  // date the course was completed. null if the course has not been completed by
  // this user
  "completed_at": "2013-06-01T00:00:00-06:00"
}
```

### A Course object looks like:

``` example
{
  // the unique identifier for the course
  "id": 370663,
  // the SIS identifier for the course, if defined. This field is only included if
  // the user has permission to view SIS information.
  "sis_course_id": null,
  // the UUID of the course
  "uuid": "WvAHhY5FINzq5IyRIJybGeiXyFkG3SqHUPb7jZY5",
  // the integration identifier for the course, if defined. This field is only
  // included if the user has permission to view SIS information.
  "integration_id": null,
  // the unique identifier for the SIS import. This field is only included if the
  // user has permission to manage SIS information.
  "sis_import_id": 34,
  // the full name of the course. If the requesting user has set a nickname for
  // the course, the nickname will be shown here.
  "name": "InstructureCon 2012",
  // the course code
  "course_code": "INSTCON12",
  // the actual course name. This field is returned only if the requesting user
  // has set a nickname for the course.
  "original_name": "InstructureCon-2012-01",
  // the current state of the course, also known as ‘status’.  The value will be
  // one of the following values: 'unpublished', 'available', 'completed', or
  // 'deleted'.  NOTE: When fetching a singular course that has a 'deleted'
  // workflow state value, an error will be returned with a message of 'The
  // specified resource does not exist.'
  "workflow_state": "available",
  // the account associated with the course
  "account_id": 81259,
  // the root account associated with the course
  "root_account_id": 81259,
  // the enrollment term associated with the course
  "enrollment_term_id": 34,
  // A list of grading periods associated with the course
  "grading_periods": null,
  // the grading standard associated with the course
  "grading_standard_id": 25,
  // the grade_passback_setting set on the course
  "grade_passback_setting": "nightly_sync",
  // the date the course was created.
  "created_at": "2012-05-01T00:00:00-06:00",
  // the start date for the course, if applicable
  "start_at": "2012-06-01T00:00:00-06:00",
  // the end date for the course, if applicable
  "end_at": "2012-09-01T00:00:00-06:00",
  // the course-set locale, if applicable
  "locale": "en",
  // A list of enrollments linking the current user to the course. for student
  // enrollments, grading information may be included if include[]=total_scores
  "enrollments": null,
  // optional: the total number of active and invited students in the course
  "total_students": 32,
  // course calendar
  "calendar": null,
  // the type of page that users will see when they first visit the course -
  // 'feed': Recent Activity Dashboard - 'wiki': Wiki Front Page - 'modules':
  // Course Modules/Sections Page - 'assignments': Course Assignments List -
  // 'syllabus': Course Syllabus Page other types may be added in the future
  "default_view": "feed",
  // optional: user-generated HTML for the course syllabus
  "syllabus_body": "<p>syllabus html goes here</p>",
  // optional: the number of submissions needing grading returned only if the
  // current user has grading rights and include[]=needs_grading_count
  "needs_grading_count": 17,
  // optional: the enrollment term object for the course returned only if
  // include[]=term
  "term": null,
  // optional: information on progress through the course returned only if
  // include[]=course_progress
  "course_progress": null,
  // weight final grade based on assignment group percentages
  "apply_assignment_group_weights": true,
  // optional: the permissions the user has for the course. returned only for a
  // single course and include[]=permissions
  "permissions": {"create_discussion_topic":true,"create_announcement":true},
  "is_public": true,
  "is_public_to_auth_users": true,
  "public_syllabus": true,
  "public_syllabus_to_auth": true,
  // optional: the public description of the course
  "public_description": "Come one, come all to InstructureCon 2012!",
  "storage_quota_mb": 5,
  "storage_quota_used_mb": 5,
  "hide_final_grades": false,
  "license": "Creative Commons",
  "allow_student_assignment_edits": false,
  "allow_wiki_comments": false,
  "allow_student_forum_attachments": false,
  "open_enrollment": true,
  "self_enrollment": false,
  "restrict_enrollments_to_course_dates": false,
  "course_format": "online",
  // optional: this will be true if this user is currently prevented from viewing
  // the course because of date restriction settings
  "access_restricted_by_date": false,
  // The course's IANA time zone name.
  "time_zone": "America/Denver",
  // optional: whether the course is set as a Blueprint Course (blueprint fields
  // require the Blueprint Courses feature)
  "blueprint": true,
  // optional: Set of restrictions applied to all locked course objects
  "blueprint_restrictions": {"content":true,"points":true,"due_dates":false,"availability_dates":false},
  // optional: Sets of restrictions differentiated by object type applied to
  // locked course objects
  "blueprint_restrictions_by_object_type": {"assignment":{"content":true,"points":true},"wiki_page":{"content":true}},
  // optional: whether the course is set as a template (requires the Course
  // Templates feature)
  "template": true
}
```

### A CalendarLink object looks like:

``` example
{
  // The URL of the calendar in ICS format
  "ics": "https://canvas.instructure.com/feeds/calendars/course_abcdef.ics"
}
```

## List your courses

### GET /api/v1/courses

**Scope:** `url:GET|/api/v1/courses`

Returns the paginated list of active courses for the current user.

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
<td>enrollment_type</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>When set, only return courses where the user is enrolled as this type. For example, set to “teacher” to return only courses where the user is enrolled as a Teacher. This argument is ignored if enrollment_role is given.</p>
<p>Allowed values: <code class="enum">teacher</code>, <code class="enum">student</code>, <code class="enum">ta</code>, <code class="enum">observer</code>, <code class="enum">designer</code></p></td>
</tr>
<tr class="request-param">
<td>enrollment_role</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Deprecated When set, only return courses where the user is enrolled with the specified course-level role. This can be a role created with the Add Role API or a base role type of ‘StudentEnrollment’, ‘TeacherEnrollment’, ‘TaEnrollment’, ‘ObserverEnrollment’, or ‘DesignerEnrollment’.</p></td>
</tr>
<tr class="request-param">
<td>enrollment_role_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>When set, only return courses where the user is enrolled with the specified course-level role. This can be a role created with the Add Role API or a built_in role type of ‘StudentEnrollment’, ‘TeacherEnrollment’, ‘TaEnrollment’, ‘ObserverEnrollment’, or ‘DesignerEnrollment’.</p></td>
</tr>
<tr class="request-param">
<td>enrollment_state</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>When set, only return courses where the user has an enrollment with the given state. This will respect section/course/term date overrides.</p>
<p>Allowed values: <code class="enum">active</code>, <code class="enum">invited_or_pending</code>, <code class="enum">completed</code></p></td>
</tr>
<tr class="request-param">
<td>exclude_blueprint_courses</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>When set, only return courses that are not configured as blueprint courses.</p></td>
</tr>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><ul>
<li><p>“needs_grading_count”: Optional information to include with each Course. When needs_grading_count is given, and the current user has grading rights, the total number of submissions needing grading for all assignments is returned.</p></li>
<li><p>“syllabus_body”: Optional information to include with each Course. When syllabus_body is given the user-generated html for the course syllabus is returned.</p></li>
<li><p>“public_description”: Optional information to include with each Course. When public_description is given the user-generated text for the course public description is returned.</p></li>
<li><p>“total_scores”: Optional information to include with each Course. When total_scores is given, any student enrollments will also include the fields ‘computed_current_score’, ‘computed_final_score’, ‘computed_current_grade’, and ‘computed_final_grade’, as well as (if the user has permission) ‘unposted_current_score’, ‘unposted_final_score’, ‘unposted_current_grade’, and ‘unposted_final_grade’ (see Enrollment documentation for more information on these fields). This argument is ignored if the course is configured to hide final grades.</p></li>
<li><p>“current_grading_period_scores”: Optional information to include with each Course. When current_grading_period_scores is given and total_scores is given, any student enrollments will also include the fields ‘has_grading_periods’, ‘totals_for_all_grading_periods_option’, ‘current_grading_period_title’, ‘current_grading_period_id’, current_period_computed_current_score’, ‘current_period_computed_final_score’, ‘current_period_computed_current_grade’, and ‘current_period_computed_final_grade’, as well as (if the user has permission) ‘current_period_unposted_current_score’, ‘current_period_unposted_final_score’, ‘current_period_unposted_current_grade’, and ‘current_period_unposted_final_grade’ (see Enrollment documentation for more information on these fields). In addition, when this argument is passed, the course will have a ‘has_grading_periods’ attribute on it. This argument is ignored if the total_scores argument is not included. If the course is configured to hide final grades, the following fields are not returned: ‘totals_for_all_grading_periods_option’, ‘current_period_computed_current_score’, ‘current_period_computed_final_score’, ‘current_period_computed_current_grade’, ‘current_period_computed_final_grade’, ‘current_period_unposted_current_score’, ‘current_period_unposted_final_score’, ‘current_period_unposted_current_grade’, and ‘current_period_unposted_final_grade’</p></li>
<li><p>“grading_periods”: Optional information to include with each Course. When grading_periods is given, a list of the grading periods associated with each course is returned.</p></li>
<li><p>“term”: Optional information to include with each Course. When term is given, the information for the enrollment term for each course is returned.</p></li>
<li><p>“account”: Optional information to include with each Course. When account is given, the account json for each course is returned.</p></li>
<li><p>“course_progress”: Optional information to include with each Course. When course_progress is given, each course will include a ‘course_progress’ object with the fields: ‘requirement_count’, an integer specifying the total number of requirements in the course, ‘requirement_completed_count’, an integer specifying the total number of requirements in this course that have been completed, and ‘next_requirement_url’, a string url to the next requirement item, and ‘completed_at’, the date the course was completed (null if incomplete). ‘next_requirement_url’ will be null if all requirements have been completed or the current module does not require sequential progress. “course_progress” will return an error message if the course is not module based or the user is not enrolled as a student in the course.</p></li>
<li><p>“sections”: Section enrollment information to include with each Course. Returns an array of hashes containing the section ID (id), section name (name), start and end dates (start_at, end_at), as well as the enrollment type (enrollment_role, e.g. ‘StudentEnrollment’).</p></li>
<li><p>“storage_quota_used_mb”: The amount of storage space used by the files in this course</p></li>
<li><p>“total_students”: Optional information to include with each Course. Returns an integer for the total amount of active and invited students.</p></li>
<li><p>“passback_status”: Include the grade passback_status</p></li>
<li><p>“favorites”: Optional information to include with each Course. Indicates if the user has marked the course as a favorite course.</p></li>
<li><p>“teachers”: Teacher information to include with each Course. Returns an array of hashes containing the UserDisplay information for each teacher in the course.</p></li>
<li><p>“observed_users”: Optional information to include with each Course. Will include data for observed users if the current user has an observer enrollment.</p></li>
<li><p>“tabs”: Optional information to include with each Course. Will include the list of tabs configured for each course. See the List available tabs API for more information.</p></li>
<li><p>“course_image”: Optional information to include with each Course. Returns course image url if a course image has been set.</p></li>
<li><p>“banner_image”: Optional information to include with each Course. Returns course banner image url if the course is a Canvas for Elementary subject and a banner image has been set.</p></li>
<li><p>“concluded”: Optional information to include with each Course. Indicates whether the course has been concluded, taking course and term dates into account.</p></li>
<li><p>“post_manually”: Optional information to include with each Course. Returns true if the course post policy is set to Manually post grades. Returns false if the the course post policy is set to Automatically post grades.</p></li>
</ul>
<p>Allowed values: <code class="enum">needs_grading_count</code>, <code class="enum">syllabus_body</code>, <code class="enum">public_description</code>, <code class="enum">total_scores</code>, <code class="enum">current_grading_period_scores</code>, <code class="enum">grading_periods</code>, <code class="enum">term</code>, <code class="enum">account</code>, <code class="enum">course_progress</code>, <code class="enum">sections</code>, <code class="enum">storage_quota_used_mb</code>, <code class="enum">total_students</code>, <code class="enum">passback_status</code>, <code class="enum">favorites</code>, <code class="enum">teachers</code>, <code class="enum">observed_users</code>, <code class="enum">course_image</code>, <code class="enum">banner_image</code>, <code class="enum">concluded</code>, <code class="enum">post_manually</code></p></td>
</tr>
<tr class="request-param">
<td>state[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If set, only return courses that are in the given state(s). By default, “available” is returned for students and observers, and anything except “deleted”, for all other enrollment types</p>
<p>Allowed values: <code class="enum">unpublished</code>, <code class="enum">available</code>, <code class="enum">completed</code>, <code class="enum">deleted</code></p></td>
</tr>
</tbody>
</table>

Returns a list of [Course](courses.html#Course) objects

## List courses for a user

### GET /api/v1/users/:user_id/courses

**Scope:** `url:GET|/api/v1/users/:user_id/courses`

Returns a paginated list of active courses for this user. To view the course list for a user other than yourself, you must be either an observer of that user or an administrator.

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
<td class="param-desc"><ul>
<li><p>“needs_grading_count”: Optional information to include with each Course. When needs_grading_count is given, and the current user has grading rights, the total number of submissions needing grading for all assignments is returned.</p></li>
<li><p>“syllabus_body”: Optional information to include with each Course. When syllabus_body is given the user-generated html for the course syllabus is returned.</p></li>
<li><p>“public_description”: Optional information to include with each Course. When public_description is given the user-generated text for the course public description is returned.</p></li>
<li><p>“total_scores”: Optional information to include with each Course. When total_scores is given, any student enrollments will also include the fields ‘computed_current_score’, ‘computed_final_score’, ‘computed_current_grade’, and ‘computed_final_grade’ (see Enrollment documentation for more information on these fields). This argument is ignored if the course is configured to hide final grades.</p></li>
<li><p>“current_grading_period_scores”: Optional information to include with each Course. When current_grading_period_scores is given and total_scores is given, any student enrollments will also include the fields ‘has_grading_periods’, ‘totals_for_all_grading_periods_option’, ‘current_grading_period_title’, ‘current_grading_period_id’, current_period_computed_current_score’, ‘current_period_computed_final_score’, ‘current_period_computed_current_grade’, and ‘current_period_computed_final_grade’, as well as (if the user has permission) ‘current_period_unposted_current_score’, ‘current_period_unposted_final_score’, ‘current_period_unposted_current_grade’, and ‘current_period_unposted_final_grade’ (see Enrollment documentation for more information on these fields). In addition, when this argument is passed, the course will have a ‘has_grading_periods’ attribute on it. This argument is ignored if the course is configured to hide final grades or if the total_scores argument is not included.</p></li>
<li><p>“grading_periods”: Optional information to include with each Course. When grading_periods is given, a list of the grading periods associated with each course is returned.</p></li>
<li><p>“term”: Optional information to include with each Course. When term is given, the information for the enrollment term for each course is returned.</p></li>
<li><p>“account”: Optional information to include with each Course. When account is given, the account json for each course is returned.</p></li>
<li><p>“course_progress”: Optional information to include with each Course. When course_progress is given, each course will include a ‘course_progress’ object with the fields: ‘requirement_count’, an integer specifying the total number of requirements in the course, ‘requirement_completed_count’, an integer specifying the total number of requirements in this course that have been completed, and ‘next_requirement_url’, a string url to the next requirement item, and ‘completed_at’, the date the course was completed (null if incomplete). ‘next_requirement_url’ will be null if all requirements have been completed or the current module does not require sequential progress. “course_progress” will return an error message if the course is not module based or the user is not enrolled as a student in the course.</p></li>
<li><p>“sections”: Section enrollment information to include with each Course. Returns an array of hashes containing the section ID (id), section name (name), start and end dates (start_at, end_at), as well as the enrollment type (enrollment_role, e.g. ‘StudentEnrollment’).</p></li>
<li><p>“storage_quota_used_mb”: The amount of storage space used by the files in this course</p></li>
<li><p>“total_students”: Optional information to include with each Course. Returns an integer for the total amount of active and invited students.</p></li>
<li><p>“passback_status”: Include the grade passback_status</p></li>
<li><p>“favorites”: Optional information to include with each Course. Indicates if the user has marked the course as a favorite course.</p></li>
<li><p>“teachers”: Teacher information to include with each Course. Returns an array of hashes containing the UserDisplay information for each teacher in the course.</p></li>
<li><p>“observed_users”: Optional information to include with each Course. Will include data for observed users if the current user has an observer enrollment.</p></li>
<li><p>“tabs”: Optional information to include with each Course. Will include the list of tabs configured for each course. See the List available tabs API for more information.</p></li>
<li><p>“course_image”: Optional information to include with each Course. Returns course image url if a course image has been set.</p></li>
<li><p>“banner_image”: Optional information to include with each Course. Returns course banner image url if the course is a Canvas for Elementary subject and a banner image has been set.</p></li>
<li><p>“concluded”: Optional information to include with each Course. Indicates whether the course has been concluded, taking course and term dates into account.</p></li>
<li><p>“post_manually”: Optional information to include with each Course. Returns true if the course post policy is set to “Manually”. Returns false if the the course post policy is set to “Automatically”.</p></li>
</ul>
<p>Allowed values: <code class="enum">needs_grading_count</code>, <code class="enum">syllabus_body</code>, <code class="enum">public_description</code>, <code class="enum">total_scores</code>, <code class="enum">current_grading_period_scores</code>, <code class="enum">grading_periods</code>, <code class="enum">term</code>, <code class="enum">account</code>, <code class="enum">course_progress</code>, <code class="enum">sections</code>, <code class="enum">storage_quota_used_mb</code>, <code class="enum">total_students</code>, <code class="enum">passback_status</code>, <code class="enum">favorites</code>, <code class="enum">teachers</code>, <code class="enum">observed_users</code>, <code class="enum">course_image</code>, <code class="enum">banner_image</code>, <code class="enum">concluded</code>, <code class="enum">post_manually</code></p></td>
</tr>
<tr class="request-param">
<td>state[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If set, only return courses that are in the given state(s). By default, “available” is returned for students and observers, and anything except “deleted”, for all other enrollment types</p>
<p>Allowed values: <code class="enum">unpublished</code>, <code class="enum">available</code>, <code class="enum">completed</code>, <code class="enum">deleted</code></p></td>
</tr>
<tr class="request-param">
<td>enrollment_state</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>When set, only return courses where the user has an enrollment with the given state. This will respect section/course/term date overrides.</p>
<p>Allowed values: <code class="enum">active</code>, <code class="enum">invited_or_pending</code>, <code class="enum">completed</code></p></td>
</tr>
<tr class="request-param">
<td>homeroom</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If set, only return homeroom courses.</p></td>
</tr>
<tr class="request-param">
<td>account_id</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If set, only include courses associated with this account</p></td>
</tr>
</tbody>
</table>

Returns a list of [Course](courses.html#Course) objects

## Get user progress

### GET /api/v1/courses/:course_id/users/:user_id/progress

**Scope:** `url:GET|/api/v1/courses/:course_id/users/:user_id/progress`

Return progress information for the user and course

You can supply `self` as the user_id to query your own progress in a course. To query another user’s progress, you must be a teacher in the course, an administrator, or a linked observer of the user.

Returns a [CourseProgress](courses.html#CourseProgress) object

## Create a new course

### POST /api/v1/accounts/:account_id/courses

**Scope:** `url:POST|/api/v1/accounts/:account_id/courses`

Create a new course

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
<td>course[name]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The name of the course. If omitted, the course will be named “Unnamed Course.”</p></td>
</tr>
<tr class="request-param">
<td>course[course_code]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The course code for the course.</p></td>
</tr>
<tr class="request-param">
<td>course[start_at]</td>
<td></td>
<td>DateTime</td>
<td class="param-desc"><p>Course start date in ISO8601 format, e.g. 2011-01-01T01:00Z This value is ignored unless ‘restrict_enrollments_to_course_dates’ is set to true.</p></td>
</tr>
<tr class="request-param">
<td>course[end_at]</td>
<td></td>
<td>DateTime</td>
<td class="param-desc"><p>Course end date in ISO8601 format. e.g. 2011-01-01T01:00Z This value is ignored unless ‘restrict_enrollments_to_course_dates’ is set to true.</p></td>
</tr>
<tr class="request-param">
<td>course[license]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The name of the licensing. Should be one of the following abbreviations (a descriptive name is included in parenthesis for reference):</p>
<ul>
<li><p>‘private’ (Private Copyrighted)</p></li>
<li><p>‘cc_by_nc_nd’ (CC Attribution Non-Commercial No Derivatives)</p></li>
<li><p>‘cc_by_nc_sa’ (CC Attribution Non-Commercial Share Alike)</p></li>
<li><p>‘cc_by_nc’ (CC Attribution Non-Commercial)</p></li>
<li><p>‘cc_by_nd’ (CC Attribution No Derivatives)</p></li>
<li><p>‘cc_by_sa’ (CC Attribution Share Alike)</p></li>
<li><p>‘cc_by’ (CC Attribution)</p></li>
<li><p>‘public_domain’ (Public Domain).</p></li>
</ul></td>
</tr>
<tr class="request-param">
<td>course[is_public]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true if course is public to both authenticated and unauthenticated users.</p></td>
</tr>
<tr class="request-param">
<td>course[is_public_to_auth_users]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true if course is public only to authenticated users.</p></td>
</tr>
<tr class="request-param">
<td>course[public_syllabus]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true to make the course syllabus public.</p></td>
</tr>
<tr class="request-param">
<td>course[public_syllabus_to_auth]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true to make the course syllabus public for authenticated users.</p></td>
</tr>
<tr class="request-param">
<td>course[public_description]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A publicly visible description of the course.</p></td>
</tr>
<tr class="request-param">
<td>course[allow_student_wiki_edits]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, students will be able to modify the course wiki.</p></td>
</tr>
<tr class="request-param">
<td>course[allow_wiki_comments]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, course members will be able to comment on wiki pages.</p></td>
</tr>
<tr class="request-param">
<td>course[allow_student_forum_attachments]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, students can attach files to forum posts.</p></td>
</tr>
<tr class="request-param">
<td>course[open_enrollment]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true if the course is open enrollment.</p></td>
</tr>
<tr class="request-param">
<td>course[self_enrollment]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true if the course is self enrollment.</p></td>
</tr>
<tr class="request-param">
<td>course[restrict_enrollments_to_course_dates]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true to restrict user enrollments to the start and end dates of the course. This value must be set to true in order to specify a course start date and/or end date.</p></td>
</tr>
<tr class="request-param">
<td>course[term_id]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The unique ID of the term to create to course in.</p></td>
</tr>
<tr class="request-param">
<td>course[sis_course_id]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The unique SIS identifier.</p></td>
</tr>
<tr class="request-param">
<td>course[integration_id]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The unique Integration identifier.</p></td>
</tr>
<tr class="request-param">
<td>course[hide_final_grades]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If this option is set to true, the totals in student grades summary will be hidden.</p></td>
</tr>
<tr class="request-param">
<td>course[apply_assignment_group_weights]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true to weight final grade based on assignment groups percentages.</p></td>
</tr>
<tr class="request-param">
<td>course[time_zone]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The time zone for the course. Allowed time zones are IANA time zones or friendlier Ruby on Rails time zones.</p></td>
</tr>
<tr class="request-param">
<td>offer</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If this option is set to true, the course will be available to students immediately.</p></td>
</tr>
<tr class="request-param">
<td>enroll_me</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true to enroll the current user as the teacher.</p></td>
</tr>
<tr class="request-param">
<td>course[default_view]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The type of page that users will see when they first visit the course</p>
<ul>
<li><p>‘feed’ Recent Activity Dashboard</p></li>
<li><p>‘modules’ Course Modules/Sections Page</p></li>
<li><p>‘assignments’ Course Assignments List</p></li>
<li><p>‘syllabus’ Course Syllabus Page</p></li>
</ul>
<p>other types may be added in the future</p>
<p>Allowed values: <code class="enum">feed</code>, <code class="enum">wiki</code>, <code class="enum">modules</code>, <code class="enum">syllabus</code>, <code class="enum">assignments</code></p></td>
</tr>
<tr class="request-param">
<td>course[syllabus_body]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The syllabus body for the course</p></td>
</tr>
<tr class="request-param">
<td>course[grading_standard_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The grading standard id to set for the course. If no value is provided for this argument the current grading_standard will be un-set from this course.</p></td>
</tr>
<tr class="request-param">
<td>course[grade_passback_setting]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Optional. The grade_passback_setting for the course. Only ‘nightly_sync’, ‘disabled’, and ” are allowed</p></td>
</tr>
<tr class="request-param">
<td>course[course_format]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Optional. Specifies the format of the course. (Should be ‘on_campus’, ‘online’, or ‘blended’)</p></td>
</tr>
<tr class="request-param">
<td>course[post_manually]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Default is false. When true, all grades in the course must be posted manually, and will not be automatically posted. When false, all grades in the course will be automatically posted.</p></td>
</tr>
<tr class="request-param">
<td>enable_sis_reactivation</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>When true, will first try to re-activate a deleted course with matching sis_course_id if possible.</p></td>
</tr>
</tbody>
</table>

Returns a [Course](courses.html#Course) object

## Upload a file

### POST /api/v1/courses/:course_id/files

**Scope:** `url:POST|/api/v1/courses/:course_id/files`

Upload a file to the course.

This API endpoint is the first step in uploading a file to a course. See the [File Upload Documentation](file_uploads.html "File Upload Documentation") for details on the file upload workflow.

Only those with the “Manage Files” permission on a course can upload files to the course. By default, this is Teachers, TAs and Designers.

## List students

### GET /api/v1/courses/:course_id/students

**Scope:** `url:GET|/api/v1/courses/:course_id/students`

Returns the paginated list of students enrolled in this course.

DEPRECATED: Please use the [course users](courses.html#method.courses.users "course users") endpoint and pass “student” as the enrollment_type.

Returns a list of [User](users.html#User) objects

## List users in course

### GET /api/v1/courses/:course_id/users

**Scope:** `url:GET|/api/v1/courses/:course_id/users`

### GET /api/v1/courses/:course_id/search_users

**Scope:** `url:GET|/api/v1/courses/:course_id/search_users`

Returns the paginated list of users in this course. And optionally the user’s enrollments in the course.

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
<td>search_term</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The partial name or full ID of the users to match and return in the results list.</p></td>
</tr>
<tr class="request-param">
<td>sort</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>When set, sort the results of the search based on the given field.</p>
<p>Allowed values: <code class="enum">username</code>, <code class="enum">last_login</code>, <code class="enum">email</code>, <code class="enum">sis_id</code></p></td>
</tr>
<tr class="request-param">
<td>enrollment_type[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>When set, only return users where the user is enrolled as this type. “student_view” implies include[]=test_student. This argument is ignored if enrollment_role is given.</p>
<p>Allowed values: <code class="enum">teacher</code>, <code class="enum">student</code>, <code class="enum">student_view</code>, <code class="enum">ta</code>, <code class="enum">observer</code>, <code class="enum">designer</code></p></td>
</tr>
<tr class="request-param">
<td>enrollment_role</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Deprecated When set, only return users enrolled with the specified course-level role. This can be a role created with the Add Role API or a base role type of ‘StudentEnrollment’, ‘TeacherEnrollment’, ‘TaEnrollment’, ‘ObserverEnrollment’, or ‘DesignerEnrollment’.</p></td>
</tr>
<tr class="request-param">
<td>enrollment_role_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>When set, only return courses where the user is enrolled with the specified course-level role. This can be a role created with the Add Role API or a built_in role id with type ‘StudentEnrollment’, ‘TeacherEnrollment’, ‘TaEnrollment’, ‘ObserverEnrollment’, or ‘DesignerEnrollment’.</p></td>
</tr>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><ul>
<li><p>“enrollments”:</p></li>
</ul>
<p>Optionally include with each Course the user’s current and invited enrollments. If the user is enrolled as a student, and the account has permission to manage or view all grades, each enrollment will include a ‘grades’ key with ‘current_score’, ‘final_score’, ‘current_grade’ and ‘final_grade’ values.</p>
<ul>
<li><p>“locked”: Optionally include whether an enrollment is locked.</p></li>
<li><p>“avatar_url”: Optionally include avatar_url.</p></li>
<li><p>“bio”: Optionally include each user’s bio.</p></li>
<li><p>“test_student”: Optionally include the course’s Test Student,</p></li>
</ul>
<p>if present. Default is to not include Test Student.</p>
<ul>
<li><p>“custom_links”: Optionally include plugin-supplied custom links for each student,</p></li>
</ul>
<p>such as analytics information</p>
<ul>
<li><p>“current_grading_period_scores”: if enrollments is included as</p></li>
</ul>
<p>well as this directive, the scores returned in the enrollment will be for the current grading period if there is one. A ‘grading_period_id’ value will also be included with the scores. if grading_period_id is nil there is no current grading period and the score is a total score.</p>
<ul>
<li><p>“uuid”: Optionally include the users uuid</p></li>
</ul>
<p>Allowed values: <code class="enum">enrollments</code>, <code class="enum">locked</code>, <code class="enum">avatar_url</code>, <code class="enum">test_student</code>, <code class="enum">bio</code>, <code class="enum">custom_links</code>, <code class="enum">current_grading_period_scores</code>, <code class="enum">uuid</code></p></td>
</tr>
<tr class="request-param">
<td>user_id</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If this parameter is given and it corresponds to a user in the course, the <code>page</code> parameter will be ignored and the page containing the specified user will be returned instead.</p></td>
</tr>
<tr class="request-param">
<td>user_ids[]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>If included, the course users set will only include users with IDs specified by the param. Note: this will not work in conjunction with the “user_id” argument but multiple user_ids can be included.</p></td>
</tr>
<tr class="request-param">
<td>enrollment_state[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>When set, only return users where the enrollment workflow state is of one of the given types. “active” and “invited” enrollments are returned by default.</p>
<p>Allowed values: <code class="enum">active</code>, <code class="enum">invited</code>, <code class="enum">rejected</code>, <code class="enum">completed</code>, <code class="enum">inactive</code></p></td>
</tr>
</tbody>
</table>

Returns a list of [User](users.html#User) objects

## List recently logged in students

### GET /api/v1/courses/:course_id/recent_students

**Scope:** `url:GET|/api/v1/courses/:course_id/recent_students`

Returns the paginated list of users in this course, ordered by how recently they have logged in. The records include the ‘last_login’ field which contains a timestamp of the last time that user logged into canvas. The querying user must have the ‘View usage reports’ permission.

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
     https://<canvas>/api/v1/courses/<course_id>/recent_users
```

Returns a list of [User](users.html#User) objects

## Get single user

### GET /api/v1/courses/:course_id/users/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/users/:id`

Return information on a single user.

Accepts the same include\[\] parameters as the :users: action, and returns a single user with the same fields as that action.

Returns an [User](users.html#User) object

## Search for content share users

### GET /api/v1/courses/:course_id/content_share_users

**Scope:** `url:GET|/api/v1/courses/:course_id/content_share_users`

Returns a paginated list of users you can share content with. Requires the content share feature and the user must have the manage content permission for the course.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| search_term | Required | string | Term used to find users. Will search available share users with the search term in their name. |

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
     https://<canvas>/api/v1/courses/<course_id>/content_share_users \
     -d 'search_term=smith'
```

Returns a list of [User](users.html#User) objects

## Preview processed html

### POST /api/v1/courses/:course_id/preview_html

**Scope:** `url:POST|/api/v1/courses/:course_id/preview_html`

Preview html content processed for this course

#### Request Parameters:

| Parameter |     | Type   | Description                 |
|-----------|-----|--------|-----------------------------|
| html      |     | string | The html content to process |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/<course_id>/preview_html \
     -F 'html=<p><badhtml></badhtml>processed html</p>' \
     -H 'Authorization: Bearer <token>'
```

#### Example Response:

####

``` example
{
  "html": "<p>processed html</p>"
}
```

## Course activity stream

### GET /api/v1/courses/:course_id/activity_stream

**Scope:** `url:GET|/api/v1/courses/:course_id/activity_stream`

Returns the current user’s course-specific activity stream, paginated.

For full documentation, see the API documentation for the user activity stream, in the user api.

## Course activity stream summary

### GET /api/v1/courses/:course_id/activity_stream/summary

**Scope:** `url:GET|/api/v1/courses/:course_id/activity_stream/summary`

Returns a summary of the current user’s course-specific activity stream.

For full documentation, see the API documentation for the user activity stream summary, in the user api.

## Course TODO items

### GET /api/v1/courses/:course_id/todo

**Scope:** `url:GET|/api/v1/courses/:course_id/todo`

Returns the current user’s course-specific todo items.

For full documentation, see the API documentation for the user todo items, in the user api.

## Delete/Conclude a course

### DELETE /api/v1/courses/:id

**Scope:** `url:DELETE|/api/v1/courses/:id`

Delete or conclude an existing course

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
<td>event</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The action to take on the course.</p>
<p>Allowed values: <code class="enum">delete</code>, <code class="enum">conclude</code></p></td>
</tr>
</tbody>
</table>

#### Example Response:

####

``` example
{ "delete": "true" }
```

## Get course settings

### GET /api/v1/courses/:course_id/settings

**Scope:** `url:GET|/api/v1/courses/:course_id/settings`

Returns some of a course’s settings.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/<course_id>/settings \
  -X GET \
  -H 'Authorization: Bearer <token>'
```

#### Example Response:

####

``` example
{
  "allow_student_discussion_topics": true,
  "allow_student_forum_attachments": false,
  "allow_student_discussion_editing": true,
  "grading_standard_enabled": true,
  "grading_standard_id": 137,
  "allow_student_organized_groups": true,
  "hide_final_grades": false,
  "hide_distribution_graphs": false,
  "hide_sections_on_course_users_page": false,
  "lock_all_announcements": true,
  "usage_rights_required": false,
  "homeroom_course": false,
  "default_due_time": "23:59:59",
  "conditional_release": false
}
```

## Update course settings

### PUT /api/v1/courses/:course_id/settings

**Scope:** `url:PUT|/api/v1/courses/:course_id/settings`

Can update the following course settings:

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| allow_final_grade_override |  | boolean | Let student final grades for a grading period or the total grades for the course be overridden |
| allow_student_discussion_topics |  | boolean | Let students create discussion topics |
| allow_student_forum_attachments |  | boolean | Let students attach files to discussions |
| allow_student_discussion_editing |  | boolean | Let students edit or delete their own discussion replies |
| allow_student_organized_groups |  | boolean | Let students organize their own groups |
| allow_student_discussion_reporting |  | boolean | Let students report offensive discussion content |
| allow_student_anonymous_discussion_topics |  | boolean | Let students create anonymous discussion topics |
| filter_speed_grader_by_student_group |  | boolean | Filter SpeedGrader to only the selected student group |
| hide_final_grades |  | boolean | Hide totals in student grades summary |
| hide_distribution_graphs |  | boolean | Hide grade distribution graphs from students |
| hide_sections_on_course_users_page |  | boolean | Disallow students from viewing students in sections they do not belong to |
| lock_all_announcements |  | boolean | Disable comments on announcements |
| usage_rights_required |  | boolean | Copyright and license information must be provided for files before they are published. |
| restrict_student_past_view |  | boolean | Restrict students from viewing courses after end date |
| restrict_student_future_view |  | boolean | Restrict students from viewing courses before start date |
| show_announcements_on_home_page |  | boolean | Show the most recent announcements on the Course home page (if a Wiki, defaults to five announcements, configurable via home_page_announcement_limit). Canvas for Elementary subjects ignore this setting. |
| home_page_announcement_limit |  | integer | Limit the number of announcements on the home page if enabled via show_announcements_on_home_page |
| syllabus_course_summary |  | boolean | Show the course summary (list of assignments and calendar events) on the syllabus page. Default is true. |
| default_due_time |  | string | Set the default due time for assignments. This is the time that will be pre-selected in the Canvas user interface when setting a due date for an assignment. It does not change when any existing assignment is due. It should be given in 24-hour HH:MM:SS format. The default is “23:59:59”. Use “inherit” to inherit the account setting. |
| conditional_release |  | boolean | Enable or disable individual learning paths for students based on assessment |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/<course_id>/settings \
  -X PUT \
  -H 'Authorization: Bearer <token>' \
  -d 'allow_student_discussion_topics=false'
```

## Return test student for course

### GET /api/v1/courses/:course_id/student_view_student

**Scope:** `url:GET|/api/v1/courses/:course_id/student_view_student`

Returns information for a test student in this course. Creates a test student if one does not already exist for the course. The caller must have permission to access the course’s student view.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/<course_id>/student_view_student \
  -X GET \
  -H 'Authorization: Bearer <token>'
```

Returns an [User](users.html#User) object

## Get a single course

### GET /api/v1/courses/:id

**Scope:** `url:GET|/api/v1/courses/:id`

### GET /api/v1/accounts/:account_id/courses/:id

**Scope:** `url:GET|/api/v1/accounts/:account_id/courses/:id`

Return information on a single course.

Accepts the same include\[\] parameters as the list action plus:

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
<td class="param-desc"><ul>
<li><p>“all_courses”: Also search recently deleted courses.</p></li>
<li><p>“permissions”: Include permissions the current user has for the course.</p></li>
<li><p>“observed_users”: Include observed users in the enrollments</p></li>
<li><p>“course_image”: Include course image url if a course image has been set</p></li>
<li><p>“banner_image”: Include course banner image url if the course is a Canvas for Elementary subject and a banner image has been set</p></li>
<li><p>“concluded”: Optional information to include with Course. Indicates whether the course has been concluded, taking course and term dates into account.</p></li>
<li><p>“lti_context_id”: Include course LTI tool id.</p></li>
<li><p>“post_manually”: Include course post policy. If the post policy is manually post grades, the value will be true. If the post policy is automatically post grades, the value will be false.</p></li>
</ul>
<p>Allowed values: <code class="enum">needs_grading_count</code>, <code class="enum">syllabus_body</code>, <code class="enum">public_description</code>, <code class="enum">total_scores</code>, <code class="enum">current_grading_period_scores</code>, <code class="enum">term</code>, <code class="enum">account</code>, <code class="enum">course_progress</code>, <code class="enum">sections</code>, <code class="enum">storage_quota_used_mb</code>, <code class="enum">total_students</code>, <code class="enum">passback_status</code>, <code class="enum">favorites</code>, <code class="enum">teachers</code>, <code class="enum">observed_users</code>, <code class="enum">all_courses</code>, <code class="enum">permissions</code>, <code class="enum">course_image</code>, <code class="enum">banner_image</code>, <code class="enum">concluded</code>, <code class="enum">lti_context_id</code>, <code class="enum">post_manually</code></p></td>
</tr>
<tr class="request-param">
<td>teacher_limit</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The maximum number of teacher enrollments to show. If the course contains more teachers than this, instead of giving the teacher enrollments, the count of teachers will be given under a <em>teacher_count</em> key.</p></td>
</tr>
</tbody>
</table>

Returns a [Course](courses.html#Course) object

## Update a course

### PUT /api/v1/courses/:id

**Scope:** `url:PUT|/api/v1/courses/:id`

Update an existing course.

Arguments are the same as Courses#create, with a few exceptions (enroll_me).

If a user has content management rights, but not full course editing rights, the only attribute editable through this endpoint will be “syllabus_body”

If an account has set prevent_course_availability_editing_by_teachers, a teacher cannot change [course](start_at), [course](conclude_at), or [course](restrict_enrollments_to_course_dates) here.

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
<td>course[account_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The unique ID of the account to move the course to.</p></td>
</tr>
<tr class="request-param">
<td>course[name]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The name of the course. If omitted, the course will be named “Unnamed Course.”</p></td>
</tr>
<tr class="request-param">
<td>course[course_code]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The course code for the course.</p></td>
</tr>
<tr class="request-param">
<td>course[start_at]</td>
<td></td>
<td>DateTime</td>
<td class="param-desc"><p>Course start date in ISO8601 format, e.g. 2011-01-01T01:00Z This value is ignored unless ‘restrict_enrollments_to_course_dates’ is set to true, or the course is already published.</p></td>
</tr>
<tr class="request-param">
<td>course[end_at]</td>
<td></td>
<td>DateTime</td>
<td class="param-desc"><p>Course end date in ISO8601 format. e.g. 2011-01-01T01:00Z This value is ignored unless ‘restrict_enrollments_to_course_dates’ is set to true.</p></td>
</tr>
<tr class="request-param">
<td>course[license]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The name of the licensing. Should be one of the following abbreviations (a descriptive name is included in parenthesis for reference):</p>
<ul>
<li><p>‘private’ (Private Copyrighted)</p></li>
<li><p>‘cc_by_nc_nd’ (CC Attribution Non-Commercial No Derivatives)</p></li>
<li><p>‘cc_by_nc_sa’ (CC Attribution Non-Commercial Share Alike)</p></li>
<li><p>‘cc_by_nc’ (CC Attribution Non-Commercial)</p></li>
<li><p>‘cc_by_nd’ (CC Attribution No Derivatives)</p></li>
<li><p>‘cc_by_sa’ (CC Attribution Share Alike)</p></li>
<li><p>‘cc_by’ (CC Attribution)</p></li>
<li><p>‘public_domain’ (Public Domain).</p></li>
</ul></td>
</tr>
<tr class="request-param">
<td>course[is_public]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true if course is public to both authenticated and unauthenticated users.</p></td>
</tr>
<tr class="request-param">
<td>course[is_public_to_auth_users]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true if course is public only to authenticated users.</p></td>
</tr>
<tr class="request-param">
<td>course[public_syllabus]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true to make the course syllabus public.</p></td>
</tr>
<tr class="request-param">
<td>course[public_syllabus_to_auth]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true to make the course syllabus to public for authenticated users.</p></td>
</tr>
<tr class="request-param">
<td>course[public_description]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A publicly visible description of the course.</p></td>
</tr>
<tr class="request-param">
<td>course[allow_student_wiki_edits]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, students will be able to modify the course wiki.</p></td>
</tr>
<tr class="request-param">
<td>course[allow_wiki_comments]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, course members will be able to comment on wiki pages.</p></td>
</tr>
<tr class="request-param">
<td>course[allow_student_forum_attachments]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, students can attach files to forum posts.</p></td>
</tr>
<tr class="request-param">
<td>course[open_enrollment]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true if the course is open enrollment.</p></td>
</tr>
<tr class="request-param">
<td>course[self_enrollment]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true if the course is self enrollment.</p></td>
</tr>
<tr class="request-param">
<td>course[restrict_enrollments_to_course_dates]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true to restrict user enrollments to the start and end dates of the course. Setting this value to false will remove the course end date (if it exists), as well as the course start date (if the course is unpublished).</p></td>
</tr>
<tr class="request-param">
<td>course[term_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The unique ID of the term to create to course in.</p></td>
</tr>
<tr class="request-param">
<td>course[sis_course_id]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The unique SIS identifier.</p></td>
</tr>
<tr class="request-param">
<td>course[integration_id]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The unique Integration identifier.</p></td>
</tr>
<tr class="request-param">
<td>course[hide_final_grades]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If this option is set to true, the totals in student grades summary will be hidden.</p></td>
</tr>
<tr class="request-param">
<td>course[time_zone]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The time zone for the course. Allowed time zones are IANA time zones or friendlier Ruby on Rails time zones.</p></td>
</tr>
<tr class="request-param">
<td>course[apply_assignment_group_weights]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set to true to weight final grade based on assignment groups percentages.</p></td>
</tr>
<tr class="request-param">
<td>course[storage_quota_mb]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Set the storage quota for the course, in megabytes. The caller must have the “Manage storage quotas” account permission.</p></td>
</tr>
<tr class="request-param">
<td>offer</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If this option is set to true, the course will be available to students immediately.</p></td>
</tr>
<tr class="request-param">
<td>course[event]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The action to take on each course.</p>
<ul>
<li><p>‘claim’ makes a course no longer visible to students. This action is also called “unpublish” on the web site. A course cannot be unpublished if students have received graded submissions.</p></li>
<li><p>‘offer’ makes a course visible to students. This action is also called “publish” on the web site.</p></li>
<li><p>‘conclude’ prevents future enrollments and makes a course read-only for all participants. The course still appears in prior-enrollment lists.</p></li>
<li><p>‘delete’ completely removes the course from the web site (including course menus and prior-enrollment lists). All enrollments are deleted. Course content may be physically deleted at a future date.</p></li>
<li><p>‘undelete’ attempts to recover a course that has been deleted. This action requires account administrative rights. (Recovery is not guaranteed; please conclude rather than delete a course if there is any possibility the course will be used again.) The recovered course will be unpublished. Deleted enrollments will not be recovered.</p></li>
</ul>
<p>Allowed values: <code class="enum">claim</code>, <code class="enum">offer</code>, <code class="enum">conclude</code>, <code class="enum">delete</code>, <code class="enum">undelete</code></p></td>
</tr>
<tr class="request-param">
<td>course[default_view]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The type of page that users will see when they first visit the course</p>
<ul>
<li><p>‘feed’ Recent Activity Dashboard</p></li>
<li><p>‘wiki’ Wiki Front Page</p></li>
<li><p>‘modules’ Course Modules/Sections Page</p></li>
<li><p>‘assignments’ Course Assignments List</p></li>
<li><p>‘syllabus’ Course Syllabus Page</p></li>
</ul>
<p>other types may be added in the future</p>
<p>Allowed values: <code class="enum">feed</code>, <code class="enum">wiki</code>, <code class="enum">modules</code>, <code class="enum">syllabus</code>, <code class="enum">assignments</code></p></td>
</tr>
<tr class="request-param">
<td>course[syllabus_body]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The syllabus body for the course</p></td>
</tr>
<tr class="request-param">
<td>course[syllabus_course_summary]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Optional. Indicates whether the Course Summary (consisting of the course’s assignments and calendar events) is displayed on the syllabus page. Defaults to <code>true</code>.</p></td>
</tr>
<tr class="request-param">
<td>course[grading_standard_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The grading standard id to set for the course. If no value is provided for this argument the current grading_standard will be un-set from this course.</p></td>
</tr>
<tr class="request-param">
<td>course[grade_passback_setting]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Optional. The grade_passback_setting for the course. Only ‘nightly_sync’ and ” are allowed</p></td>
</tr>
<tr class="request-param">
<td>course[course_format]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Optional. Specifies the format of the course. (Should be either ‘on_campus’ or ‘online’)</p></td>
</tr>
<tr class="request-param">
<td>course[image_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>This is a file ID corresponding to an image file in the course that will be used as the course image. This will clear the course’s image_url setting if set. If you attempt to provide image_url and image_id in a request it will fail.</p></td>
</tr>
<tr class="request-param">
<td>course[image_url]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>This is a URL to an image to be used as the course image. This will clear the course’s image_id setting if set. If you attempt to provide image_url and image_id in a request it will fail.</p></td>
</tr>
<tr class="request-param">
<td>course[remove_image]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If this option is set to true, the course image url and course image ID are both set to nil</p></td>
</tr>
<tr class="request-param">
<td>course[remove_banner_image]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If this option is set to true, the course banner image url and course banner image ID are both set to nil</p></td>
</tr>
<tr class="request-param">
<td>course[blueprint]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Sets the course as a blueprint course.</p></td>
</tr>
<tr class="request-param">
<td>course[blueprint_restrictions]</td>
<td></td>
<td>BlueprintRestriction</td>
<td class="param-desc"><p>Sets a default set to apply to blueprint course objects when restricted, unless <em>use_blueprint_restrictions_by_object_type</em> is enabled. See the Blueprint Restriction documentation</p></td>
</tr>
<tr class="request-param">
<td>course[use_blueprint_restrictions_by_object_type]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>When enabled, the <em>blueprint_restrictions</em> parameter will be ignored in favor of the <em>blueprint_restrictions_by_object_type</em> parameter</p></td>
</tr>
<tr class="request-param">
<td>course[blueprint_restrictions_by_object_type]</td>
<td></td>
<td>multiple BlueprintRestrictions</td>
<td class="param-desc"><p>Allows setting multiple Blueprint Restriction to apply to blueprint course objects of the matching type when restricted. The possible object types are “assignment”, “attachment”, “discussion_topic”, “quiz” and “wiki_page”. Example usage:</p>
`course[blueprint_restrictions_by_object_type][assignment][content]=1`</td>
</tr>
<tr class="request-param">
<td>course[homeroom_course]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Sets the course as a homeroom course. The setting takes effect only when the course is associated with a Canvas for Elementary-enabled account.</p></td>
</tr>
<tr class="request-param">
<td>course[sync_enrollments_from_homeroom]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Syncs enrollments from the homeroom that is set in homeroom_course_id. The setting only takes effect when the course is associated with a Canvas for Elementary-enabled account and sync_enrollments_from_homeroom is enabled.</p></td>
</tr>
<tr class="request-param">
<td>course[homeroom_course_id]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Sets the Homeroom Course id to be used with sync_enrollments_from_homeroom. The setting only takes effect when the course is associated with a Canvas for Elementary-enabled account and sync_enrollments_from_homeroom is enabled.</p></td>
</tr>
<tr class="request-param">
<td>course[template]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Enable or disable the course as a template that can be selected by an account</p></td>
</tr>
<tr class="request-param">
<td>course[course_color]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Sets a color in hex code format to be associated with the course. The setting takes effect only when the course is associated with a Canvas for Elementary-enabled account.</p></td>
</tr>
<tr class="request-param">
<td>course[friendly_name]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Set a friendly name for the course. If this is provided and the course is associated with a Canvas for Elementary account, it will be shown instead of the course name. This setting takes priority over course nicknames defined by individual users.</p></td>
</tr>
<tr class="request-param">
<td>course[enable_course_paces]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Enable or disable Course Pacing for the course. This setting only has an effect when the Course Pacing feature flag is enabled for the sub-account. Otherwise, Course Pacing are always disabled.</p></td>
</tr>
<tr class="request-param">
<td>course[conditional_release]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Enable or disable individual learning paths for students based on assessment</p></td>
</tr>
<tr class="request-param">
<td>course[post_manually]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>When true, all grades in the course will be posted manually. When false, all grades in the course will be automatically posted. Use with caution as this setting will override any assignment level post policy.</p></td>
</tr>
<tr class="request-param">
<td>override_sis_stickiness</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Default is true. If false, any fields containing “sticky” changes will not be updated. See SIS CSV Format documentation for information on which fields can have SIS stickiness</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/<course_id> \
  -X PUT \
  -H 'Authorization: Bearer <token>' \
  -d 'course[name]=New course name' \
  -d 'course[start_at]=2012-05-05T00:00:00Z'
```

#### Example Response:

####

``` example
{
  "name": "New course name",
  "course_code": "COURSE-001",
  "start_at": "2012-05-05T00:00:00Z",
  "end_at": "2012-08-05T23:59:59Z",
  "sis_course_id": "12345"
}
```

## Update courses

### PUT /api/v1/accounts/:account_id/courses

**Scope:** `url:PUT|/api/v1/accounts/:account_id/courses`

Update multiple courses in an account. Operates asynchronously; use the [progress endpoint](progress.html#method.progress.show "progress endpoint") to query the status of an operation.

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
<td>course_ids[]</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>List of ids of courses to update. At most 500 courses may be updated in one call.</p></td>
</tr>
<tr class="request-param">
<td>event</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The action to take on each course. Must be one of ‘offer’, ‘conclude’, ‘delete’, or ‘undelete’.</p>
<ul>
<li><p>‘offer’ makes a course visible to students. This action is also called “publish” on the web site.</p></li>
<li><p>‘conclude’ prevents future enrollments and makes a course read-only for all participants. The course still appears in prior-enrollment lists.</p></li>
<li><p>‘delete’ completely removes the course from the web site (including course menus and prior-enrollment lists). All enrollments are deleted. Course content may be physically deleted at a future date.</p></li>
<li><p>‘undelete’ attempts to recover a course that has been deleted. (Recovery is not guaranteed; please conclude rather than delete a course if there is any possibility the course will be used again.) The recovered course will be unpublished. Deleted enrollments will not be recovered.</p></li>
</ul>
<p>Allowed values: <code class="enum">offer</code>, <code class="enum">conclude</code>, <code class="enum">delete</code>, <code class="enum">undelete</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/<account_id>/courses \
  -X PUT \
  -H 'Authorization: Bearer <token>' \
  -d 'event=offer' \
  -d 'course_ids[]=1' \
  -d 'course_ids[]=2'
```

Returns a [Progress](progress.html#Progress) object

## Reset a course

### POST /api/v1/courses/:course_id/reset_content

**Scope:** `url:POST|/api/v1/courses/:course_id/reset_content`

Deletes the current course, and creates a new equivalent course with no content, but all sections and users moved over.

Returns a [Course](courses.html#Course) object

## Get effective due dates

### GET /api/v1/courses/:course_id/effective_due_dates

**Scope:** `url:GET|/api/v1/courses/:course_id/effective_due_dates`

For each assignment in the course, returns each assigned student’s ID and their corresponding due date along with some grading period data. Returns a collection with keys representing assignment IDs and values as a collection containing keys representing student IDs and values representing the student’s effective due_at, the grading_period_id of which the due_at falls in, and whether or not the grading period is closed (in_closed_grading_period)

The list of assignment IDs for which effective student due dates are requested. If not provided, all assignments in the course will be used.

#### Request Parameters:

| Parameter          |     | Type   | Description    |
|--------------------|-----|--------|----------------|
| assignment_ids\[\] |     | string | no description |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/<course_id>/effective_due_dates
  -X GET \
  -H 'Authorization: Bearer <token>'
```

#### Example Response:

####

``` example
{
  "1": {
     "14": { "due_at": "2015-09-05", "grading_period_id": null, "in_closed_grading_period": false },
     "15": { due_at: null, "grading_period_id": 3, "in_closed_grading_period": true }
  },
  "2": {
     "14": { "due_at": "2015-08-05", "grading_period_id": 3, "in_closed_grading_period": true }
  }
}
```

## Permissions

### GET /api/v1/courses/:course_id/permissions

**Scope:** `url:GET|/api/v1/courses/:course_id/permissions`

Returns permission information for the calling user in the given course. See also the [Account](accounts.html#method.accounts.permissions "Account") and [Group](groups.html#method.groups.permissions "Group") counterparts.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| permissions\[\] |  | string | List of permissions to check against the authenticated user. Permission names are documented in the [Create a role](roles.html#method.role_overrides.add_role "Create a role") endpoint. |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/<course_id>/permissions \
  -H 'Authorization: Bearer <token>' \
  -d 'permissions[]=manage_grades'
  -d 'permissions[]=send_messages'
```

#### Example Response:

####

``` example
{'manage_grades': 'false', 'send_messages': 'true'}
```

## Get bulk user progress

### GET /api/v1/courses/:course_id/bulk_user_progress

**Scope:** `url:GET|/api/v1/courses/:course_id/bulk_user_progress`

Returns progress information for all users enrolled in the given course.

You must be a user who has permission to view all grades in the course (such as a teacher or administrator).

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/<course_id>/bulk_user_progress \
  -H 'Authorization: Bearer <token>'
```

#### Example Response:

####

``` example
[
  {
    "id": 1,
    "display_name": "Test Student 1",
    "avatar_image_url": "https://<canvas>/images/messages/avatar-50.png",
    "html_url": "https://<canvas>/courses/1/users/1",
    "pronouns": null,
    "progress": {
      "requirement_count": 2,
      "requirement_completed_count": 1,
      "next_requirement_url": "https://<canvas>/courses/<course_id>/modules/items/<item_id>",
      "completed_at": null
    }
  },
  {
    "id": 2,
    "display_name": "Test Student 2",
    "avatar_image_url": "https://<canvas>/images/messages/avatar-50.png",
    "html_url": "https://<canvas>/courses/1/users/2",
    "pronouns": null,
    "progress": {
      "requirement_count": 2,
      "requirement_completed_count": 2,
      "next_requirement_url": null,
      "completed_at": "2021-08-10T16:26:08Z"
    }
  }
]
```

## Remove quiz migration alert

### POST /api/v1/courses/:id/dismiss_migration_limitation_message

**Scope:** `url:POST|/api/v1/courses/:id/dismiss_migration_limitation_message`

Remove alert about the limitations of quiz migrations that is displayed to a user in a course

you must be logged in to use this endpoint

#### Example Response:

####

``` example
{ "success": "true" }
```

## Get course copy status

### GET /api/v1/courses/:course_id/course_copy/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/course_copy/:id`

DEPRECATED: Please use the [Content Migrations API](content_migrations.html#method.content_migrations.create "Content Migrations API")

Retrieve the status of a course copy

#### API response field:

-  id

  The unique identifier for the course copy.

-  created_at

  The time that the copy was initiated.

-  progress

  The progress of the copy as an integer. It is null before the copying starts, and 100 when finished.

-  workflow_state

  The current status of the course copy. Possible values: “created”, “started”, “completed”, “failed”

-  status_url

  The url for the course copy status API endpoint.

#### Example Response:

####

``` example
{'progress':100, 'workflow_state':'completed', 'id':257, 'created_at':'2011-11-17T16:50:06Z', 'status_url':'/api/v1/courses/9457/course_copy/257'}
```

## Copy course content

### POST /api/v1/courses/:course_id/course_copy

**Scope:** `url:POST|/api/v1/courses/:course_id/course_copy`

DEPRECATED: Please use the [Content Migrations API](content_migrations.html#method.content_migrations.create "Content Migrations API")

Copies content from one course into another. The default is to copy all course content. You can control specific types to copy by using either the ‘except’ option or the ‘only’ option.

The response is the same as the course copy status endpoint

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
<td>source_course</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>ID or SIS-ID of the course to copy the content from</p></td>
</tr>
<tr class="request-param">
<td>except[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A list of the course content types to exclude, all areas not listed will be copied.</p>
<p>Allowed values: <code class="enum">course_settings</code>, <code class="enum">assignments</code>, <code class="enum">external_tools</code>, <code class="enum">files</code>, <code class="enum">topics</code>, <code class="enum">calendar_events</code>, <code class="enum">quizzes</code>, <code class="enum">wiki_pages</code>, <code class="enum">modules</code>, <code class="enum">outcomes</code></p></td>
</tr>
<tr class="request-param">
<td>only[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A list of the course content types to copy, all areas not listed will not be copied.</p>
<p>Allowed values: <code class="enum">course_settings</code>, <code class="enum">assignments</code>, <code class="enum">external_tools</code>, <code class="enum">files</code>, <code class="enum">topics</code>, <code class="enum">calendar_events</code>, <code class="enum">quizzes</code>, <code class="enum">wiki_pages</code>, <code class="enum">modules</code>, <code class="enum">outcomes</code></p></td>
</tr>
</tbody>
</table>
