# Accounts API

API for accessing account data.

### An Account object looks like:

``` example
{
  // the ID of the Account object
  "id": 2,
  // The display name of the account
  "name": "Canvas Account",
  // The UUID of the account
  "uuid": "WvAHhY5FINzq5IyRIJybGeiXyFkG3SqHUPb7jZY5",
  // The account's parent ID, or null if this is the root account
  "parent_account_id": 1,
  // The ID of the root account, or null if this is the root account
  "root_account_id": 1,
  // The storage quota for the account in megabytes, if not otherwise specified
  "default_storage_quota_mb": 500,
  // The storage quota for a user in the account in megabytes, if not otherwise
  // specified
  "default_user_storage_quota_mb": 50,
  // The storage quota for a group in the account in megabytes, if not otherwise
  // specified
  "default_group_storage_quota_mb": 50,
  // The default time zone of the account. Allowed time zones are
  // {http://www.iana.org/time-zones IANA time zones} or friendlier
  // {http://api.rubyonrails.org/classes/ActiveSupport/TimeZone.html Ruby on Rails
  // time zones}.
  "default_time_zone": "America/Denver",
  // The account's identifier in the Student Information System. Only included if
  // the user has permission to view SIS information.
  "sis_account_id": "123xyz",
  // The account's identifier in the Student Information System. Only included if
  // the user has permission to view SIS information.
  "integration_id": "123xyz",
  // The id of the SIS import if created through SIS. Only included if the user
  // has permission to manage SIS information.
  "sis_import_id": 12,
  // The number of courses directly under the account (available via include)
  "course_count": 10,
  // The number of sub-accounts directly under the account (available via include)
  "sub_account_count": 10,
  // The account's identifier that is sent as context_id in LTI launches.
  "lti_guid": "123xyz",
  // The state of the account. Can be 'active' or 'deleted'.
  "workflow_state": "active"
}
```

### A TermsOfService object looks like:

``` example
{
  // Terms Of Service id
  "id": 1,
  // The given type for the Terms of Service
  "terms_type": "default",
  // Boolean dictating if the user must accept Terms of Service
  "passive": false,
  // The id of the root account that owns the Terms of Service
  "account_id": 1,
  // Content of the Terms of Service
  "content": "To be or not to be that is the question",
  // The type of self registration allowed
  "self_registration_type": "["none", "observer", "all"]"
}
```

### A HelpLink object looks like:

``` example
{
  // The ID of the help link
  "id": "instructor_question",
  // The name of the help link
  "text": "Ask Your Instructor a Question",
  // The description of the help link
  "subtext": "Questions are submitted to your instructor",
  // The URL of the help link
  "url": "#teacher_feedback",
  // The type of the help link
  "type": "default",
  // The roles that have access to this help link
  "available_to": ["user", "student", "teacher", "admin", "observer", "unenrolled"]
}
```

### A HelpLinks object looks like:

``` example
{
  // Help link button title
  "help_link_name": "Help And Policies",
  // Help link button icon
  "help_link_icon": "help",
  // Help links defined by the account. Could include default help links.
  "custom_help_links": [{"id":"link1","text":"Custom Link!","subtext":"Something something.","url":"https:\/\/google.com","type":"custom","available_to":["user","student","teacher","admin","observer","unenrolled"],"is_featured":true,"is_new":false,"feature_headline":"Check this out!"}],
  // Default help links provided when account has not set help links of their own.
  "default_help_links": [{"available_to":["student"],"text":"Ask Your Instructor a Question","subtext":"Questions are submitted to your instructor","url":"#teacher_feedback","type":"default","id":"instructor_question","is_featured":false,"is_new":true,"feature_headline":""}, {"available_to":["user","student","teacher","admin","observer","unenrolled"],"text":"Search the Canvas Guides","subtext":"Find answers to common questions","url":"https:\/\/community.canvaslms.com\/t5\/Guides\/ct-p\/guides","type":"default","id":"search_the_canvas_guides","is_featured":false,"is_new":false,"feature_headline":""}, {"available_to":["user","student","teacher","admin","observer","unenrolled"],"text":"Report a Problem","subtext":"If Canvas misbehaves, tell us about it","url":"#create_ticket","type":"default","id":"report_a_problem","is_featured":false,"is_new":false,"feature_headline":""}]
}
```

## List accounts

### GET /api/v1/accounts

**Scope:** `url:GET|/api/v1/accounts`

A paginated list of accounts that the current user can view or manage. Typically, students and even teachers will get an empty list in response, only account admins can view the accounts that they are in.

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
<td class="param-desc"><p>Array of additional information to include.</p>
<dl>
<dt>“lti_guid”</dt>
<dd>
<p>the ‘tool_consumer_instance_guid’ that will be sent for this account on LTI launches</p>
</dd>
<dt>“registration_settings”</dt>
<dd>
<p>returns info about the privacy policy and terms of use</p>
</dd>
<dt>“services”</dt>
<dd>
<p>returns services and whether they are enabled (requires account management permissions)</p>
</dd>
<dt>“course_count”</dt>
<dd>
<p>returns the number of courses directly under each account</p>
</dd>
<dt>“sub_account_count”</dt>
<dd>
<p>returns the number of sub-accounts directly under each account</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">lti_guid</code>, <code class="enum">registration_settings</code>, <code class="enum">services</code>, <code class="enum">course_count</code>, <code class="enum">sub_account_count</code></p></td>
</tr>
</tbody>
</table>

Returns a list of [Account](accounts_(lti).html#Account) objects

## Get accounts that admins can manage

### GET /api/v1/manageable_accounts

**Scope:** `url:GET|/api/v1/manageable_accounts`

A paginated list of accounts where the current user has permission to create or manage courses. List will be empty for students and teachers as only admins can view which accounts they are in.

Returns a list of [Account](accounts_(lti).html#Account) objects

## Get accounts that users can create courses in

### GET /api/v1/course_creation_accounts

**Scope:** `url:GET|/api/v1/course_creation_accounts`

A paginated list of accounts where the current user has permission to create courses.

Returns a list of [Account](accounts_(lti).html#Account) objects

## List accounts for course admins

### GET /api/v1/course_accounts

**Scope:** `url:GET|/api/v1/course_accounts`

A paginated list of accounts that the current user can view through their admin course enrollments. (Teacher, TA, or designer enrollments). Only returns “id”, “name”, “workflow_state”, “root_account_id” and “parent_account_id”

Returns a list of [Account](accounts_(lti).html#Account) objects

## Get a single account

### GET /api/v1/accounts/:id

**Scope:** `url:GET|/api/v1/accounts/:id`

Retrieve information on an individual account, given by id or sis sis_account_id.

Returns an [Account](accounts_(lti).html#Account) object

## Settings

### GET /api/v1/accounts/:account_id/settings

**Scope:** `url:GET|/api/v1/accounts/:account_id/settings`

Returns a JSON object containing a subset of settings for the specified account. It’s possible an empty set will be returned if no settings are applicable. The caller must be an Account admin with the manage_account_settings permission.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/<account_id>/settings \
  -H 'Authorization: Bearer <token>'
```

#### Example Response:

####

``` example
{"microsoft_sync_enabled": true, "microsoft_sync_login_attribute_suffix": false}
```

## List environment settings

### GET /api/v1/settings/environment

**Scope:** `url:GET|/api/v1/settings/environment`

Return a hash of global settings for the root account This is the same information supplied to the web interface as `ENV.SETTINGS`.

#### Example Request:

####

``` example
curl 'http://<canvas>/api/v1/settings/environment' \
  -H "Authorization: Bearer <token>"
```

#### Example Response:

####

``` example
{ "calendar_contexts_limit": 10, "open_registration": false, ...}
```

## Permissions

### GET /api/v1/accounts/:account_id/permissions

**Scope:** `url:GET|/api/v1/accounts/:account_id/permissions`

Returns permission information for the calling user and the given account. You may use ‘self\` as the account id to check permissions against the domain root account. The caller must have an account role or admin (teacher/TA/designer) enrollment in a course in the account.

See also the [Course](courses.html#method.courses.permissions "Course") and [Group](groups.html#method.groups.permissions "Group") counterparts.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| permissions\[\] |  | string | List of permissions to check against the authenticated user. Permission names are documented in the [Create a role](roles.html#method.role_overrides.add_role "Create a role") endpoint. |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/self/permissions \
  -H 'Authorization: Bearer <token>' \
  -d 'permissions[]=manage_account_memberships' \
  -d 'permissions[]=become_user'
```

#### Example Response:

####

``` example
{'manage_account_memberships': 'false', 'become_user': 'true'}
```

## Get the sub-accounts of an account

### GET /api/v1/accounts/:account_id/sub_accounts

**Scope:** `url:GET|/api/v1/accounts/:account_id/sub_accounts`

List accounts that are sub-accounts of the given account.

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
<td>recursive</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, the entire account tree underneath this account will be returned (though still paginated). If false, only direct sub-accounts of this account will be returned. Defaults to false.</p></td>
</tr>
<tr class="request-param">
<td>order</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Sorts the accounts by id or name. Only applies when recursive is false. Defaults to id.</p>
<p>Allowed values: <code class="enum">id</code>, <code class="enum">name</code></p></td>
</tr>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Array of additional information to include.</p>
<dl>
<dt>“course_count”</dt>
<dd>
<p>returns the number of courses directly under each account</p>
</dd>
<dt>“sub_account_count”</dt>
<dd>
<p>returns the number of sub-accounts directly under each account</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">course_count</code>, <code class="enum">sub_account_count</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/<account_id>/sub_accounts \
     -H 'Authorization: Bearer <token>'
```

Returns a list of [Account](accounts_(lti).html#Account) objects

## Get the Terms of Service

### GET /api/v1/accounts/:account_id/terms_of_service

**Scope:** `url:GET|/api/v1/accounts/:account_id/terms_of_service`

Returns the terms of service for that account

Returns a [TermsOfService](accounts.html#TermsOfService) object

## Get help links

### GET /api/v1/accounts/:account_id/help_links

**Scope:** `url:GET|/api/v1/accounts/:account_id/help_links`

Returns the help links for that account

Returns a [HelpLinks](accounts.html#HelpLinks) object

## Get the manually-created courses sub-account for the domain root account

### GET /api/v1/manually_created_courses_account

**Scope:** `url:GET|/api/v1/manually_created_courses_account`

## List active courses in an account

### GET /api/v1/accounts/:account_id/courses

**Scope:** `url:GET|/api/v1/accounts/:account_id/courses`

Retrieve a paginated list of courses in this account.

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
<td>with_enrollments</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, include only courses with at least one enrollment. If false, include only courses with no enrollments. If not present, do not filter on course enrollment status.</p></td>
</tr>
<tr class="request-param">
<td>enrollment_type[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If set, only return courses that have at least one user enrolled in in the course with one of the specified enrollment types.</p>
<p>Allowed values: <code class="enum">teacher</code>, <code class="enum">student</code>, <code class="enum">ta</code>, <code class="enum">observer</code>, <code class="enum">designer</code></p></td>
</tr>
<tr class="request-param">
<td>published</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, include only published courses. If false, exclude published courses. If not present, do not filter on published status.</p></td>
</tr>
<tr class="request-param">
<td>completed</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, include only completed courses (these may be in state ‘completed’, or their enrollment term may have ended). If false, exclude completed courses. If not present, do not filter on completed status.</p></td>
</tr>
<tr class="request-param">
<td>blueprint</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, include only blueprint courses. If false, exclude them. If not present, do not filter on this basis.</p></td>
</tr>
<tr class="request-param">
<td>blueprint_associated</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, include only courses that inherit content from a blueprint course. If false, exclude them. If not present, do not filter on this basis.</p></td>
</tr>
<tr class="request-param">
<td>public</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, include only public courses. If false, exclude them. If not present, do not filter on this basis.</p></td>
</tr>
<tr class="request-param">
<td>by_teachers[]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>List of User IDs of teachers; if supplied, include only courses taught by one of the referenced users.</p></td>
</tr>
<tr class="request-param">
<td>by_subaccounts[]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>List of Account IDs; if supplied, include only courses associated with one of the referenced subaccounts.</p></td>
</tr>
<tr class="request-param">
<td>hide_enrollmentless_courses</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If present, only return courses that have at least one enrollment. Equivalent to ‘with_enrollments=true’; retained for compatibility.</p></td>
</tr>
<tr class="request-param">
<td>state[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If set, only return courses that are in the given state(s). By default, all states but “deleted” are returned.</p>
<p>Allowed values: <code class="enum">created</code>, <code class="enum">claimed</code>, <code class="enum">available</code>, <code class="enum">completed</code>, <code class="enum">deleted</code>, <code class="enum">all</code></p></td>
</tr>
<tr class="request-param">
<td>enrollment_term_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>If set, only includes courses from the specified term.</p></td>
</tr>
<tr class="request-param">
<td>search_term</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The partial course name, code, or full ID to match and return in the results list. Must be at least 3 characters.</p></td>
</tr>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><ul>
<li><p>All explanations can be seen in the Course API index documentation</p></li>
<li><p>“sections”, “needs_grading_count” and “total_scores” are not valid options at the account level</p></li>
</ul>
<p>Allowed values: <code class="enum">syllabus_body</code>, <code class="enum">term</code>, <code class="enum">course_progress</code>, <code class="enum">storage_quota_used_mb</code>, <code class="enum">total_students</code>, <code class="enum">teachers</code>, <code class="enum">account_name</code>, <code class="enum">concluded</code>, <code class="enum">post_manually</code></p></td>
</tr>
<tr class="request-param">
<td>sort</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The column to sort results by.</p>
<p>Allowed values: <code class="enum">course_status</code>, <code class="enum">course_name</code>, <code class="enum">sis_course_id</code>, <code class="enum">teacher</code>, <code class="enum">account_name</code></p></td>
</tr>
<tr class="request-param">
<td>order</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The order to sort the given column by.</p>
<p>Allowed values: <code class="enum">asc</code>, <code class="enum">desc</code></p></td>
</tr>
<tr class="request-param">
<td>search_by</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The filter to search by. “course” searches for course names, course codes, and SIS IDs. “teacher” searches for teacher names</p>
<p>Allowed values: <code class="enum">course</code>, <code class="enum">teacher</code></p></td>
</tr>
<tr class="request-param">
<td>starts_before</td>
<td></td>
<td>Date</td>
<td class="param-desc"><p>If set, only return courses that start before the value (inclusive) or their enrollment term starts before the value (inclusive) or both the course’s start_at and the enrollment term’s start_at are set to null. The value should be formatted as: yyyy-mm-dd or ISO 8601 YYYY-MM-DDTHH:MM:SSZ.</p></td>
</tr>
<tr class="request-param">
<td>ends_after</td>
<td></td>
<td>Date</td>
<td class="param-desc"><p>If set, only return courses that end after the value (inclusive) or their enrollment term ends after the value (inclusive) or both the course’s end_at and the enrollment term’s end_at are set to null. The value should be formatted as: yyyy-mm-dd or ISO 8601 YYYY-MM-DDTHH:MM:SSZ.</p></td>
</tr>
<tr class="request-param">
<td>homeroom</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If set, only return homeroom courses.</p></td>
</tr>
</tbody>
</table>

Returns a list of [Course](courses.html#Course) objects

## Update an account

### PUT /api/v1/accounts/:id

**Scope:** `url:PUT|/api/v1/accounts/:id`

Update an existing account.

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
<td>account[name]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Updates the account name</p></td>
</tr>
<tr class="request-param">
<td>account[sis_account_id]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Updates the account sis_account_id Must have manage_sis permission and must not be a root_account.</p></td>
</tr>
<tr class="request-param">
<td>account[default_time_zone]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The default time zone of the account. Allowed time zones are IANA time zones or friendlier Ruby on Rails time zones.</p></td>
</tr>
<tr class="request-param">
<td>account[default_storage_quota_mb]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The default course storage quota to be used, if not otherwise specified.</p></td>
</tr>
<tr class="request-param">
<td>account[default_user_storage_quota_mb]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The default user storage quota to be used, if not otherwise specified.</p></td>
</tr>
<tr class="request-param">
<td>account[default_group_storage_quota_mb]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The default group storage quota to be used, if not otherwise specified.</p></td>
</tr>
<tr class="request-param">
<td>account[course_template_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The ID of a course to be used as a template for all newly created courses. Empty means to inherit the setting from parent account, 0 means to not use a template even if a parent account has one set. The course must be marked as a template.</p></td>
</tr>
<tr class="request-param">
<td>account[parent_account_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The ID of a parent account to move the account to. The new parent account must be in the same root account as the original. The hierarchy of sub-accounts will be preserved in the new parent account. The caller must be an administrator in both the original parent account and the new parent account.</p></td>
</tr>
<tr class="request-param">
<td>account[settings][restrict_student_past_view][value]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Restrict students from viewing courses after end date</p></td>
</tr>
<tr class="request-param">
<td>account[settings][restrict_student_past_view][locked]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Lock this setting for sub-accounts and courses</p></td>
</tr>
<tr class="request-param">
<td>account[settings][restrict_student_future_view][value]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Restrict students from viewing courses before start date</p></td>
</tr>
<tr class="request-param">
<td>account[settings][microsoft_sync_enabled]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Determines whether this account has Microsoft Teams Sync enabled or not.</p>
<p>Note that if you are altering Microsoft Teams sync settings you must enable the Microsoft Group enrollment syncing feature flag. In addition, if you are enabling Microsoft Teams sync, you must also specify a tenant, login attribute, and a remote attribute. Specifying a suffix to use is optional.</p></td>
</tr>
<tr class="request-param">
<td>account[settings][microsoft_sync_tenant]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The tenant this account should use when using Microsoft Teams Sync. This should be an Azure Active Directory domain name.</p></td>
</tr>
<tr class="request-param">
<td>account[settings][microsoft_sync_login_attribute]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The attribute this account should use to lookup users when using Microsoft Teams Sync. Must be one of “sub”, “email”, “oid”, “preferred_username”, or “integration_id”.</p></td>
</tr>
<tr class="request-param">
<td>account[settings][microsoft_sync_login_attribute_suffix]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A suffix that will be appended to the result of the login attribute when associating Canvas users with Microsoft users. Must be under 255 characters and contain no whitespace. This field is optional.</p></td>
</tr>
<tr class="request-param">
<td>account[settings][microsoft_sync_remote_attribute]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The Active Directory attribute to use when associating Canvas users with Microsoft users. Must be one of “mail”, “mailNickname”, or “userPrincipalName”.</p></td>
</tr>
<tr class="request-param">
<td>account[settings][restrict_student_future_view][locked]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Lock this setting for sub-accounts and courses</p></td>
</tr>
<tr class="request-param">
<td>account[settings][lock_all_announcements][value]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Disable comments on announcements</p></td>
</tr>
<tr class="request-param">
<td>account[settings][lock_all_announcements][locked]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Lock this setting for sub-accounts and courses</p></td>
</tr>
<tr class="request-param">
<td>account[settings][usage_rights_required][value]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Copyright and license information must be provided for files before they are published.</p></td>
</tr>
<tr class="request-param">
<td>account[settings][usage_rights_required][locked]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Lock this setting for sub-accounts and courses</p></td>
</tr>
<tr class="request-param">
<td>account[settings][restrict_student_future_listing][value]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Restrict students from viewing future enrollments in course list</p></td>
</tr>
<tr class="request-param">
<td>account[settings][restrict_student_future_listing][locked]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Lock this setting for sub-accounts and courses</p></td>
</tr>
<tr class="request-param">
<td>account[settings][conditional_release][value]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Enable or disable individual learning paths for students based on assessment</p></td>
</tr>
<tr class="request-param">
<td>account[settings][conditional_release][locked]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Lock this setting for sub-accounts and courses</p></td>
</tr>
<tr class="request-param">
<td>account[settings][password_policy]</td>
<td></td>
<td>Hash</td>
<td class="param-desc"><p>Hash of optional password policy configuration parameters for a root account</p>
<dl>
<dt><code>allow_login_suspension</code> boolean</dt>
<dd>
<p>Allow suspension of user logins upon reaching maximum_login_attempts</p>
</dd>
<dt><code>require_number_characters</code> boolean</dt>
<dd>
<p>Require the use of number characters when setting up a new password</p>
</dd>
<dt><code>require_symbol_characters</code> boolean</dt>
<dd>
<p>Require the use of symbol characters when setting up a new password</p>
</dd>
<dt><code>minimum_character_length</code> integer</dt>
<dd>
<p>Minimum number of characters required for a new password</p>
</dd>
<dt><code>maximum_login_attempts</code> integer</dt>
<dd>
<p>Maximum number of login attempts before a user is locked out</p>
</dd>
</dl>
<p><em>Required</em> feature option:</p>
`Enhance password options`</td>
</tr>
<tr class="request-param">
<td>account[settings][enable_as_k5_account][value]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Enable or disable Canvas for Elementary for this account</p></td>
</tr>
<tr class="request-param">
<td>account[settings][use_classic_font_in_k5][value]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not the classic font is used on the dashboard. Only applies if enable_as_k5_account is true.</p></td>
</tr>
<tr class="request-param">
<td>account[settings][horizon_account][value]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Enable or disable Canvas Career for this account</p></td>
</tr>
<tr class="request-param">
<td>override_sis_stickiness</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Default is true. If false, any fields containing “sticky” changes will not be updated. See SIS CSV Format documentation for information on which fields can have SIS stickiness</p></td>
</tr>
<tr class="request-param">
<td>account[settings][lock_outcome_proficiency][value]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><dl>
<dt>DEPRECATED</dt>
<dd>
<p>Restrict instructors from changing mastery scale</p>
</dd>
</dl></td>
</tr>
<tr class="request-param">
<td>account[lock_outcome_proficiency][locked]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><dl>
<dt>DEPRECATED</dt>
<dd>
<p>Lock this setting for sub-accounts and courses</p>
</dd>
</dl></td>
</tr>
<tr class="request-param">
<td>account[settings][lock_proficiency_calculation][value]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><dl>
<dt>DEPRECATED</dt>
<dd>
<p>Restrict instructors from changing proficiency calculation method</p>
</dd>
</dl></td>
</tr>
<tr class="request-param">
<td>account[lock_proficiency_calculation][locked]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><dl>
<dt>DEPRECATED</dt>
<dd>
<p>Lock this setting for sub-accounts and courses</p>
</dd>
</dl></td>
</tr>
<tr class="request-param">
<td>account[services]</td>
<td></td>
<td>Hash</td>
<td class="param-desc"><p>Give this a set of keys and boolean values to enable or disable services matching the keys</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/<account_id> \
  -X PUT \
  -H 'Authorization: Bearer <token>' \
  -d 'account[name]=New account name' \
  -d 'account[default_time_zone]=Mountain Time (US & Canada)' \
  -d 'account[default_storage_quota_mb]=450'
```

Returns an [Account](accounts_(lti).html#Account) object

## Delete a user from the root account

### DELETE /api/v1/accounts/:account_id/users/:user_id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/users/:user_id`

Delete a user record from a Canvas root account. If a user is associated with multiple root accounts (in a multi-tenant instance of Canvas), this action will NOT remove them from the other accounts.

WARNING: This API will allow a user to remove themselves from the account. If they do this, they won’t be able to make API calls or log into Canvas at that account.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/3/users/5 \
  -H 'Authorization: Bearer <ACCESS_TOKEN>' \
  -X DELETE
```

Returns an [User](users.html#User) object

## Restore a deleted user from a root account

### PUT /api/v1/accounts/:account_id/users/:user_id/restore

**Scope:** `url:PUT|/api/v1/accounts/:account_id/users/:user_id/restore`

Restore a user record along with the most recently deleted pseudonym from a Canvas root account.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/3/users/5/restore \
  -H 'Authorization: Bearer <ACCESS_TOKEN>' \
  -X PUT
```

Returns an [User](users.html#User) object

## Create a new sub-account

### POST /api/v1/accounts/:account_id/sub_accounts

**Scope:** `url:POST|/api/v1/accounts/:account_id/sub_accounts`

Add a new sub-account to a given account.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| account\[name\] | Required | string | The name of the new sub-account. |
| account\[sis_account_id\] |  | string | The account’s identifier in the Student Information System. |
| account\[default_storage_quota_mb\] |  | integer | The default course storage quota to be used, if not otherwise specified. |
| account\[default_user_storage_quota_mb\] |  | integer | The default user storage quota to be used, if not otherwise specified. |
| account\[default_group_storage_quota_mb\] |  | integer | The default group storage quota to be used, if not otherwise specified. |

Returns an [Account](accounts_(lti).html#Account) object

## Delete a sub-account

### DELETE /api/v1/accounts/:account_id/sub_accounts/:id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/sub_accounts/:id`

Cannot delete an account with active courses or active sub_accounts. Cannot delete a root_account

Returns an [Account](accounts_(lti).html#Account) object
