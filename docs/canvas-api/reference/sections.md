# Sections API

API for accessing section information.

### A Section object looks like:

``` example
{
  // The unique identifier for the section.
  "id": 1,
  // The name of the section.
  "name": "Section A",
  // The sis id of the section. This field is only included if the user has
  // permission to view SIS information.
  "sis_section_id": "s34643",
  // Optional: The integration ID of the section. This field is only included if
  // the user has permission to view SIS information.
  "integration_id": "3452342345",
  // The unique identifier for the SIS import if created through SIS. This field
  // is only included if the user has permission to manage SIS information.
  "sis_import_id": 47,
  // The unique Canvas identifier for the course in which the section belongs
  "course_id": 7,
  // The unique SIS identifier for the course in which the section belongs. This
  // field is only included if the user has permission to view SIS information.
  "sis_course_id": "7",
  // the start date for the section, if applicable
  "start_at": "2012-06-01T00:00:00-06:00",
  // the end date for the section, if applicable
  "end_at": null,
  // Restrict user enrollments to the start and end dates of the section
  "restrict_enrollments_to_section_dates": null,
  // The unique identifier of the original course of a cross-listed section
  "nonxlist_course_id": null,
  // optional: the total number of active and invited students in the section
  "total_students": 13
}
```

## List course sections

### GET /api/v1/courses/:course_id/sections

**Scope:** `url:GET|/api/v1/courses/:course_id/sections`

A paginated list of the list of sections for this course.

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
<li><p>“students”: Associations to include with the group. Note: this is only available if you have permission to view users or grades in the course</p></li>
<li><p>“avatar_url”: Include the avatar URLs for students returned.</p></li>
<li><p>“enrollments”: If ‘students’ is also included, return the section enrollment for each student</p></li>
<li><p>“total_students”: Returns the total amount of active and invited students for the course section</p></li>
<li><p>“passback_status”: Include the grade passback status.</p></li>
<li><p>“permissions”: Include whether section grants :manage_calendar permission to the caller</p></li>
</ul>
<p>Allowed values: <code class="enum">students</code>, <code class="enum">avatar_url</code>, <code class="enum">enrollments</code>, <code class="enum">total_students</code>, <code class="enum">passback_status</code>, <code class="enum">permissions</code></p></td>
</tr>
<tr class="request-param">
<td>search_term</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>When included, searches course sections for the term. Returns only matching results. Term must be at least 2 characters.</p></td>
</tr>
</tbody>
</table>

Returns a list of [Section](sections.html#Section) objects

## Create course section

### POST /api/v1/courses/:course_id/sections

**Scope:** `url:POST|/api/v1/courses/:course_id/sections`

Creates a new section for this course.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| course_section\[name\] |  | string | The name of the section |
| course_section\[sis_section_id\] |  | string | The sis ID of the section. Must have manage_sis permission to set. This is ignored if caller does not have permission to set. |
| course_section\[integration_id\] |  | string | The integration_id of the section. Must have manage_sis permission to set. This is ignored if caller does not have permission to set. |
| course_section\[start_at\] |  | DateTime | Section start date in ISO8601 format, e.g. 2011-01-01T01:00Z |
| course_section\[end_at\] |  | DateTime | Section end date in ISO8601 format. e.g. 2011-01-01T01:00Z |
| course_section\[restrict_enrollments_to_section_dates\] |  | boolean | Set to true to restrict user enrollments to the start and end dates of the section. |
| enable_sis_reactivation |  | boolean | When true, will first try to re-activate a deleted section with matching sis_section_id if possible. |

Returns a [Section](sections.html#Section) object

## Cross-list a Section

### POST /api/v1/sections/:id/crosslist/:new_course_id

**Scope:** `url:POST|/api/v1/sections/:id/crosslist/:new_course_id`

Move the Section to another course. The new course may be in a different account (department), but must belong to the same root account (institution).

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| override_sis_stickiness |  | boolean | Default is true. If false, any fields containing “sticky” changes will not be updated. See SIS CSV Format documentation for information on which fields can have SIS stickiness |

Returns a [Section](sections.html#Section) object

## De-cross-list a Section

### DELETE /api/v1/sections/:id/crosslist

**Scope:** `url:DELETE|/api/v1/sections/:id/crosslist`

Undo cross-listing of a Section, returning it to its original course.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| override_sis_stickiness |  | boolean | Default is true. If false, any fields containing “sticky” changes will not be updated. See SIS CSV Format documentation for information on which fields can have SIS stickiness |

Returns a [Section](sections.html#Section) object

## Edit a section

### PUT /api/v1/sections/:id

**Scope:** `url:PUT|/api/v1/sections/:id`

Modify an existing section.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| course_section\[name\] |  | string | The name of the section |
| course_section\[sis_section_id\] |  | string | The sis ID of the section. Must have manage_sis permission to set. |
| course_section\[integration_id\] |  | string | The integration_id of the section. Must have manage_sis permission to set. |
| course_section\[start_at\] |  | DateTime | Section start date in ISO8601 format, e.g. 2011-01-01T01:00Z |
| course_section\[end_at\] |  | DateTime | Section end date in ISO8601 format. e.g. 2011-01-01T01:00Z |
| course_section\[restrict_enrollments_to_section_dates\] |  | boolean | Set to true to restrict user enrollments to the start and end dates of the section. |
| override_sis_stickiness |  | boolean | Default is true. If false, any fields containing “sticky” changes will not be updated. See SIS CSV Format documentation for information on which fields can have SIS stickiness |

Returns a [Section](sections.html#Section) object

## Get section information

### GET /api/v1/courses/:course_id/sections/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/sections/:id`

### GET /api/v1/sections/:id

**Scope:** `url:GET|/api/v1/sections/:id`

Gets details about a specific section

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
<li><p>“students”: Associations to include with the group. Note: this is only available if you have permission to view users or grades in the course</p></li>
<li><p>“avatar_url”: Include the avatar URLs for students returned.</p></li>
<li><p>“enrollments”: If ‘students’ is also included, return the section enrollment for each student</p></li>
<li><p>“total_students”: Returns the total amount of active and invited students for the course section</p></li>
<li><p>“passback_status”: Include the grade passback status.</p></li>
<li><p>“permissions”: Include whether section grants :manage_calendar permission to the caller</p></li>
</ul>
<p>Allowed values: <code class="enum">students</code>, <code class="enum">avatar_url</code>, <code class="enum">enrollments</code>, <code class="enum">total_students</code>, <code class="enum">passback_status</code>, <code class="enum">permissions</code></p></td>
</tr>
</tbody>
</table>

Returns a [Section](sections.html#Section) object

## Delete a section

### DELETE /api/v1/sections/:id

**Scope:** `url:DELETE|/api/v1/sections/:id`

Delete an existing section. Returns the former Section.

Returns a [Section](sections.html#Section) object
