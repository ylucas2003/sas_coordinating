# Assignment Groups API

API for accessing Assignment Group and Assignment information.

### A GradingRules object looks like:

``` example
{
  // Number of lowest scores to be dropped for each user.
  "drop_lowest": 1,
  // Number of highest scores to be dropped for each user.
  "drop_highest": 1,
  // Assignment IDs that should never be dropped.
  "never_drop": [33, 17, 24]
}
```

### An AssignmentGroup object looks like:

``` example
{
  // the id of the Assignment Group
  "id": 1,
  // the name of the Assignment Group
  "name": "group2",
  // the position of the Assignment Group
  "position": 7,
  // the weight of the Assignment Group
  "group_weight": 20,
  // the sis source id of the Assignment Group
  "sis_source_id": "1234",
  // the integration data of the Assignment Group
  "integration_data": {"5678":"0954"},
  // the assignments in this Assignment Group (see the Assignment API for a
  // detailed list of fields)
  "assignments": [],
  // the grading rules that this Assignment Group has
  "rules": null
}
```

## List assignment groups

### GET /api/v1/courses/:course_id/assignment_groups

**Scope:** `url:GET|/api/v1/courses/:course_id/assignment_groups`

Returns the paginated list of assignment groups for the current context. The returned groups are sorted by their position field.

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
<td class="param-desc"><p>Associations to include with the group. “discussion_topic”, “all_dates”, “can_edit”, “assignment_visibility” &amp; “submission” are only valid if “assignments” is also included. “score_statistics” requires that the “assignments” and “submission” options are included. The “assignment_visibility” option additionally requires that the Differentiated Assignments course feature be turned on. If “observed_users” is passed along with “assignments” and “submission”, submissions for observed users will also be included as an array.</p>
<p>Allowed values: <code class="enum">assignments</code>, <code class="enum">discussion_topic</code>, <code class="enum">all_dates</code>, <code class="enum">assignment_visibility</code>, <code class="enum">overrides</code>, <code class="enum">submission</code>, <code class="enum">observed_users</code>, <code class="enum">can_edit</code>, <code class="enum">score_statistics</code></p></td>
</tr>
<tr class="request-param">
<td>assignment_ids[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If “assignments” are included, optionally return only assignments having their ID in this array. This argument may also be passed as a comma separated string.</p></td>
</tr>
<tr class="request-param">
<td>exclude_assignment_submission_types[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If “assignments” are included, those with the specified submission types will be excluded from the assignment groups.</p>
<p>Allowed values: <code class="enum">online_quiz</code>, <code class="enum">discussion_topic</code>, <code class="enum">wiki_page</code>, <code class="enum">external_tool</code></p></td>
</tr>
<tr class="request-param">
<td>override_assignment_dates</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Apply assignment overrides for each assignment, defaults to true.</p></td>
</tr>
<tr class="request-param">
<td>grading_period_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the grading period in which assignment groups are being requested (Requires grading periods to exist.)</p></td>
</tr>
<tr class="request-param">
<td>scope_assignments_to_student</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, all assignments returned will apply to the current user in the specified grading period. If assignments apply to other students in the specified grading period, but not the current user, they will not be returned. (Requires the grading_period_id argument and grading periods to exist. In addition, the current user must be a student.)</p></td>
</tr>
</tbody>
</table>

Returns a list of [AssignmentGroup](assignment_groups.html#AssignmentGroup) objects

## Get an Assignment Group

### GET /api/v1/courses/:course_id/assignment_groups/:assignment_group_id

**Scope:** `url:GET|/api/v1/courses/:course_id/assignment_groups/:assignment_group_id`

Returns the assignment group with the given id.

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
<td class="param-desc"><p>Associations to include with the group. “discussion_topic” and “assignment_visibility” and “submission” are only valid if “assignments” is also included. “score_statistics” is only valid if “submission” and “assignments” are also included. The “assignment_visibility” option additionally requires that the Differentiated Assignments course feature be turned on.</p>
<p>Allowed values: <code class="enum">assignments</code>, <code class="enum">discussion_topic</code>, <code class="enum">assignment_visibility</code>, <code class="enum">submission</code>, <code class="enum">score_statistics</code></p></td>
</tr>
<tr class="request-param">
<td>override_assignment_dates</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Apply assignment overrides for each assignment, defaults to true.</p></td>
</tr>
<tr class="request-param">
<td>grading_period_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the grading period in which assignment groups are being requested (Requires grading periods to exist on the account)</p></td>
</tr>
</tbody>
</table>

Returns an [AssignmentGroup](assignment_groups.html#AssignmentGroup) object

## Create an Assignment Group

### POST /api/v1/courses/:course_id/assignment_groups

**Scope:** `url:POST|/api/v1/courses/:course_id/assignment_groups`

Create a new assignment group for this course.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| name |  | string | The assignment group’s name |
| position |  | integer | The position of this assignment group in relation to the other assignment groups |
| group_weight |  | number | The percent of the total grade that this assignment group represents |
| sis_source_id |  | string | The sis source id of the Assignment Group |
| integration_data |  | Object | The integration data of the Assignment Group |

Returns an [AssignmentGroup](assignment_groups.html#AssignmentGroup) object

## Edit an Assignment Group

### PUT /api/v1/courses/:course_id/assignment_groups/:assignment_group_id

**Scope:** `url:PUT|/api/v1/courses/:course_id/assignment_groups/:assignment_group_id`

Modify an existing Assignment Group.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| name |  | string | The assignment group’s name |
| position |  | integer | The position of this assignment group in relation to the other assignment groups |
| group_weight |  | number | The percent of the total grade that this assignment group represents |
| sis_source_id |  | string | The sis source id of the Assignment Group |
| integration_data |  | Object | The integration data of the Assignment Group |
| rules |  | string | The grading rules that are applied within this assignment group See the Assignment Group object definition for format |

Returns an [AssignmentGroup](assignment_groups.html#AssignmentGroup) object

## Destroy an Assignment Group

### DELETE /api/v1/courses/:course_id/assignment_groups/:assignment_group_id

**Scope:** `url:DELETE|/api/v1/courses/:course_id/assignment_groups/:assignment_group_id`

Deletes the assignment group with the given id.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| move_assignments_to |  | integer | The ID of an active Assignment Group to which the assignments that are currently assigned to the destroyed Assignment Group will be assigned. NOTE: If this argument is not provided, any assignments in this Assignment Group will be deleted. |

Returns an [AssignmentGroup](assignment_groups.html#AssignmentGroup) object
