# Roles API

API for managing account- and course-level roles, and their associated permissions.

### A RolePermissions object looks like:

``` example
{
  // Whether the role has the permission
  "enabled": true,
  // Whether the permission is locked by this role
  "locked": false,
  // Whether the permission applies to the account this role is in. Only present
  // if enabled is true
  "applies_to_self": true,
  // Whether the permission cascades down to sub accounts of the account this role
  // is in. Only present if enabled is true
  "applies_to_descendants": false,
  // Whether the permission can be modified in this role (i.e. whether the
  // permission is locked by an upstream role).
  "readonly": false,
  // Whether the value of enabled is specified explicitly by this role, or
  // inherited from an upstream role.
  "explicit": true,
  // The value that would have been inherited from upstream if the role had not
  // explicitly set a value. Only present if explicit is true.
  "prior_default": false
}
```

### A Role object looks like:

``` example
{
  // The id of the role
  "id": 1,
  // The label of the role.
  "label": "New Role",
  // The label of the role. (Deprecated alias for 'label')
  "role": "New Role",
  // The role type that is being used as a base for this role. For account-level
  // roles, this is 'AccountMembership'. For course-level roles, it is an
  // enrollment type.
  "base_role_type": "AccountMembership",
  // Whether this role applies to account memberships (i.e., not linked to an
  // enrollment in a course).
  "is_account_role": true,
  // JSON representation of the account the role is defined in.
  "account": {"id":1019,"name":"CGNU","parent_account_id":73,"root_account_id":1,"sis_account_id":"cgnu"},
  // The state of the role: 'active', 'inactive', or 'built_in'
  "workflow_state": "active",
  // The date and time the role was created.
  "created_at": "2020-12-01T16:20:00-06:00",
  // The date and time the role was last updated.
  "last_updated_at": "2023-10-31T23:59:00-06:00",
  // A dictionary of permissions keyed by name (see permissions input parameter in
  // the 'Create a role' API).
  "permissions": {"read_course_content":{"enabled":true,"locked":false,"readonly":false,"explicit":true,"prior_default":false},"read_course_list":{"enabled":true,"locked":true,"readonly":true,"explicit":false},"read_question_banks":{"enabled":false,"locked":true,"readonly":false,"explicit":true,"prior_default":false},"read_reports":{"enabled":true,"locked":false,"readonly":false,"explicit":false}}
}
```

## List roles

### GET /api/v1/accounts/:account_id/roles

**Scope:** `url:GET|/api/v1/accounts/:account_id/roles`

A paginated list of the roles available to an account.

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
<td>account_id</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The id of the account to retrieve roles for.</p></td>
</tr>
<tr class="request-param">
<td>state[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Filter by role state. If this argument is omitted, only ‘active’ roles are returned.</p>
<p>Allowed values: <code class="enum">active</code>, <code class="enum">inactive</code></p></td>
</tr>
<tr class="request-param">
<td>show_inherited</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If this argument is true, all roles inherited from parent accounts will be included.</p></td>
</tr>
</tbody>
</table>

Returns a list of [Role](roles.html#Role) objects

## Get a single role

### GET /api/v1/accounts/:account_id/roles/:id

**Scope:** `url:GET|/api/v1/accounts/:account_id/roles/:id`

Retrieve information about a single role

#### Request Parameters:

| Parameter  |          | Type    | Description                               |
|------------|----------|---------|-------------------------------------------|
| account_id | Required | string  | The id of the account containing the role |
| role_id    | Required | integer | The unique identifier for the role        |
| role       |          | string  | The name for the role                     |

Returns a [Role](roles.html#Role) object

## Create a new role

### POST /api/v1/accounts/:account_id/roles

**Scope:** `url:POST|/api/v1/accounts/:account_id/roles`

Create a new course-level or account-level role.

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
<td>label</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>Label for the role.</p></td>
</tr>
<tr class="request-param">
<td>role</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Deprecated alias for label.</p></td>
</tr>
<tr class="request-param">
<td>base_role_type</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Specifies the role type that will be used as a base for the permissions granted to this role.</p>
<p>Defaults to ‘AccountMembership’ if absent</p>
<p>Allowed values: <code class="enum">AccountMembership</code>, <code class="enum">StudentEnrollment</code>, <code class="enum">TeacherEnrollment</code>, <code class="enum">TaEnrollment</code>, <code class="enum">ObserverEnrollment</code>, <code class="enum">DesignerEnrollment</code></p></td>
</tr>
<tr class="request-param">
<td>permissions[&lt;X&gt;][explicit]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>no description</p></td>
</tr>
<tr class="request-param">
<td>permissions[&lt;X&gt;][enabled]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If explicit is 1 and enabled is 1, permission &lt;X&gt; will be explicitly granted to this role. If explicit is 1 and enabled has any other value (typically 0), permission &lt;X&gt; will be explicitly denied to this role. If explicit is any other value (typically 0) or absent, or if enabled is absent, the value for permission &lt;X&gt; will be inherited from upstream. Ignored if permission &lt;X&gt; is locked upstream (in an ancestor account).</p>
<p>May occur multiple times with unique values for &lt;X&gt;. Recognized permission names for &lt;X&gt; are:</p>
`[For Account-Level Roles Only]
become_user                      -- Users - act as
import_sis                       -- SIS Data - import
manage_account_memberships       -- Admins - add / remove
manage_account_settings          -- Account-level settings - manage
manage_alerts                    -- Global announcements - add / edit / delete
manage_catalog                   -- Catalog - manage
Manage Course Templates granular permissions
    add_course_template          -- Course Templates - add
    delete_course_template       -- Course Templates - delete
    edit_course_template         -- Course Templates - edit
manage_courses_add               -- Courses - add
manage_courses_admin             -- Courses - manage / update
manage_developer_keys            -- Developer keys - manage
manage_feature_flags             -- Feature Options - enable / disable
manage_master_courses            -- Blueprint Courses - add / edit / associate / delete
manage_role_overrides            -- Permissions - manage
manage_storage_quotas            -- Storage Quotas - manage
manage_sis                       -- SIS data - manage
Manage Temporary Enrollments granular permissions
    temporary_enrollments_add     -- Temporary Enrollments - add
    temporary_enrollments_edit    -- Temporary Enrollments - edit
    temporary_enrollments_delete  -- Temporary Enrollments - delete
manage_user_logins               -- Users - manage login details
manage_user_observers            -- Users - manage observers
moderate_user_content            -- Users - moderate content
read_course_content              -- Course Content - view
read_course_list                 -- Courses - view list
view_course_changes              -- Courses - view change logs
view_feature_flags               -- Feature Options - view
view_grade_changes               -- Grades - view change logs
view_notifications               -- Notifications - view
view_quiz_answer_audits          -- Quizzes - view submission log
view_statistics                  -- Statistics - view
undelete_courses                 -- Courses - undelete

[For both Account-Level and Course-Level roles]
 Note: Applicable enrollment types for course-level roles are given in brackets:
       S = student, T = teacher (instructor), A = TA, D = designer, O = observer.
       Lower-case letters indicate permissions that are off by default.
       A missing letter indicates the permission cannot be enabled for the role
       or any derived custom roles.
allow_course_admin_actions       -- [ Tad ] Users - allow administrative actions in courses
create_collaborations            -- [STADo] Student Collaborations - create
create_conferences               -- [STADo] Web conferences - create
create_forum                     -- [STADo] Discussions - create
generate_observer_pairing_code   -- [ tado] Users - Generate observer pairing codes for students
import_outcomes                  -- [ TaDo] Learning Outcomes - import
manage_account_banks             -- [ td  ] Item Banks - manage account
share_banks_with_subaccounts     -- [ tad ] Item Banks - share with subaccounts
Manage Assignments and Quizzes granular permissions
    manage_assignments_add       -- [ TADo] Assignments and Quizzes - add
    manage_assignments_edit      -- [ TADo] Assignments and Quizzes - edit / manage
    manage_assignments_delete    -- [ TADo] Assignments and Quizzes - delete
manage_calendar                  -- [sTADo] Course Calendar - add / edit / delete
Manage Course Content granular permissions
    manage_course_content_add    -- [ TADo] Course Content - add
    manage_course_content_edit   -- [ TADo] Course Content - edit
    manage_course_content_delete -- [ TADo] Course Content - delete
manage_course_visibility         -- [ TAD ] Course - change visibility
Manage Courses granular permissions
    manage_courses_conclude      -- [ TaD ] Courses - conclude
    manage_courses_delete        -- [ TaD ] Courses - delete
    manage_courses_publish       -- [ TaD ] Courses - publish
    manage_courses_reset         -- [ TaD ] Courses - reset
Manage Files granular permissions
    manage_files_add             -- [ TADo] Course Files - add
    manage_files_edit            -- [ TADo] Course Files - edit
    manage_files_delete          -- [ TADo] Course Files - delete
manage_grades                    -- [ TA  ] Grades - edit
Manage Groups granular permissions
    manage_groups_add            -- [ TAD ] Groups - add
    manage_groups_delete         -- [ TAD ] Groups - delete
    manage_groups_manage         -- [ TAD ] Groups - manage
manage_interaction_alerts        -- [ Ta  ] Alerts - add / edit / delete
manage_outcomes                  -- [sTaDo] Learning Outcomes - add / edit / delete
manage_proficiency_calculations  -- [ t d ] Outcome Proficiency Calculations - add / edit / delete
manage_proficiency_scales        -- [ t d ] Outcome Proficiency/Mastery Scales - add / edit / delete
Manage Sections granular permissions
    manage_sections_add          -- [ TaD ] Course Sections - add
    manage_sections_edit         -- [ TaD ] Course Sections - edit
    manage_sections_delete       -- [ TaD ] Course Sections - delete
manage_students                  -- [ TAD ] Users - manage students in courses
manage_rubrics                   -- [ TAD ] Rubrics - add / edit / delete
Manage Pages granular permissions
    manage_wiki_create           -- [ TADo] Pages - create
    manage_wiki_delete           -- [ TADo] Pages - delete
    manage_wiki_update           -- [ TADo] Pages - update
moderate_forum                   -- [sTADo] Discussions - moderate
post_to_forum                    -- [STADo] Discussions - post
read_announcements               -- [STADO] Announcements - view
read_email_addresses             -- [sTAdo] Users - view primary email address
read_forum                       -- [STADO] Discussions - view
read_question_banks              -- [ TADo] Question banks - view and link
read_reports                     -- [ TAD ] Reports - manage
read_roster                      -- [STADo] Users - view list
read_sis                         -- [sTa  ] SIS Data - read
select_final_grade               -- [ TA  ] Grades - select final grade for moderation
send_messages                    -- [STADo] Conversations - send messages to individual course members
send_messages_all                -- [sTADo] Conversations - send messages to entire class
Users - Teacher granular permissions
    add_teacher_to_course        -- [ Tad ] Add a teacher enrollment to a course
    remove_teacher_from_course   -- [ Tad ] Remove a Teacher enrollment from a course
Users - TA granular permissions
    add_ta_to_course             -- [ Tad ] Add a TA enrollment to a course
    remove_ta_from_course        -- [ Tad ] Remove a TA enrollment from a course
Users - Designer granular permissions
    add_designer_to_course       -- [ Tad ] Add a designer enrollment to a course
    remove_designer_from_course  -- [ Tad ] Remove a designer enrollment from a course
Users - Observer granular permissions
    add_observer_to_course       -- [ Tad ] Add an observer enrollment to a course
    remove_observer_from_course  -- [ Tad ] Remove an observer enrollment from a course
Users - Student granular permissions
    add_student_to_course        -- [ Tad ] Add a student enrollment to a course
    remove_student_from_course   -- [ Tad ] Remove a student enrollment from a course
view_all_grades                  -- [ TAd ] Grades - view all grades
view_analytics                   -- [sTA  ] Analytics - view pages
view_audit_trail                 -- [ t   ] Grades - view audit trail
view_group_pages                 -- [sTADo] Groups - view all student groups
view_user_logins                 -- [ TA  ] Users - view login IDs`
<p>Some of these permissions are applicable only for roles on the site admin account, on a root account, or for course-level roles with a particular base role type; if a specified permission is inapplicable, it will be ignored.</p>
<p>Additional permissions may exist based on installed plugins.</p>
<p>A comprehensive list of all permissions are available:</p>
<p>Course Permissions PDF: bit.ly/cnvs-course-permissions</p>
<p>Account Permissions PDF: bit.ly/cnvs-acct-permissions</p></td>
</tr>
<tr class="request-param">
<td>permissions[&lt;X&gt;][locked]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If the value is 1, permission &lt;X&gt; will be locked downstream (new roles in subaccounts cannot override the setting). For any other value, permission &lt;X&gt; is left unlocked. Ignored if permission &lt;X&gt; is already locked upstream. May occur multiple times with unique values for &lt;X&gt;.</p></td>
</tr>
<tr class="request-param">
<td>permissions[&lt;X&gt;][applies_to_self]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If the value is 1, permission &lt;X&gt; applies to the account this role is in. The default value is 1. Must be true if applies_to_descendants is false. This value is only returned if enabled is true.</p></td>
</tr>
<tr class="request-param">
<td>permissions[&lt;X&gt;][applies_to_descendants]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If the value is 1, permission &lt;X&gt; cascades down to sub accounts of the account this role is in. The default value is 1. Must be true if applies_to_self is false.This value is only returned if enabled is true.</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/accounts/<account_id>/roles.json' \
     -H "Authorization: Bearer <token>" \
     -F 'label=New Role' \
     -F 'permissions[read_course_content][explicit]=1' \
     -F 'permissions[read_course_content][enabled]=1' \
     -F 'permissions[read_course_list][locked]=1' \
     -F 'permissions[read_question_banks][explicit]=1' \
     -F 'permissions[read_question_banks][enabled]=0' \
     -F 'permissions[read_question_banks][locked]=1'
```

Returns a [Role](roles.html#Role) object

## Deactivate a role

### DELETE /api/v1/accounts/:account_id/roles/:id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/roles/:id`

Deactivates a custom role. This hides it in the user interface and prevents it from being assigned to new users. Existing users assigned to the role will continue to function with the same permissions they had previously. Built-in roles cannot be deactivated.

#### Request Parameters:

| Parameter |          | Type    | Description                        |
|-----------|----------|---------|------------------------------------|
| role_id   | Required | integer | The unique identifier for the role |
| role      |          | string  | The name for the role              |

Returns a [Role](roles.html#Role) object

## Activate a role

### POST /api/v1/accounts/:account_id/roles/:id/activate

**Scope:** `url:POST|/api/v1/accounts/:account_id/roles/:id/activate`

Re-activates an inactive role (allowing it to be assigned to new users)

#### Request Parameters:

| Parameter |          | Type       | Description                        |
|-----------|----------|------------|------------------------------------|
| role_id   | Required | integer    | The unique identifier for the role |
| role      |          | Deprecated | The name for the role              |

Returns a [Role](roles.html#Role) object

## Update a role

### PUT /api/v1/accounts/:account_id/roles/:id

**Scope:** `url:PUT|/api/v1/accounts/:account_id/roles/:id`

Update permissions for an existing role.

Recognized roles are:

- TeacherEnrollment

- StudentEnrollment

- TaEnrollment

- ObserverEnrollment

- DesignerEnrollment

- AccountAdmin

- Any previously created custom role

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| label |  | string | The label for the role. Can only change the label of a custom role that belongs directly to the account. |
| permissions\[\<X\>\]\[explicit\] |  | boolean | no description |
| permissions\[\<X\>\]\[enabled\] |  | boolean | These arguments are described in the documentation for the [add_role method](roles.html#method.role_overrides.add_role "add_role method"). |
| permissions\[\<X\>\]\[applies_to_self\] |  | boolean | If the value is 1, permission \<X\> applies to the account this role is in. The default value is 1. Must be true if applies_to_descendants is false. This value is only returned if enabled is true. |
| permissions\[\<X\>\]\[applies_to_descendants\] |  | boolean | If the value is 1, permission \<X\> cascades down to sub accounts of the account this role is in. The default value is 1. Must be true if applies_to_self is false.This value is only returned if enabled is true. |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/:account_id/roles/2 \
  -X PUT \
  -H 'Authorization: Bearer <access_token>' \
  -F 'label=New Role Name' \
  -F 'permissions[manage_groups][explicit]=1' \
  -F 'permissions[manage_groups][enabled]=1' \
  -F 'permissions[manage_groups][locked]=1' \
  -F 'permissions[send_messages][explicit]=1' \
  -F 'permissions[send_messages][enabled]=0'
```

Returns a [Role](roles.html#Role) object
