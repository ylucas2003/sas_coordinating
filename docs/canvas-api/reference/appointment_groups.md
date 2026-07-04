# Appointment Groups API

API for creating, accessing and updating appointment groups. Appointment groups provide a way of creating a bundle of time slots that users can sign up for (e.g. "Office Hours" or "Meet with professor about Final Project"). Both time slots and reservations of time slots are stored as Calendar Events.

### An Appointment object looks like:

``` example
// Date and time for an appointment
{
  // The appointment identifier.
  "id": 987,
  // Start time for the appointment
  "start_at": "2012-07-20T15:00:00-06:00",
  // End time for the appointment
  "end_at": "2012-07-20T15:00:00-06:00"
}
```

### An AppointmentGroup object looks like:

``` example
{
  // The ID of the appointment group
  "id": 543,
  // The title of the appointment group
  "title": "Final Presentation",
  // The start of the first time slot in the appointment group
  "start_at": "2012-07-20T15:00:00-06:00",
  // The end of the last time slot in the appointment group
  "end_at": "2012-07-20T17:00:00-06:00",
  // The text description of the appointment group
  "description": "Es muy importante",
  // The location name of the appointment group
  "location_name": "El Tigre Chino's office",
  // The address of the appointment group's location
  "location_address": "Room 234",
  // The number of participant who have reserved slots (see include[] argument)
  "participant_count": 2,
  // The start and end times of slots reserved by the current user as well as the
  // id of the calendar event for the reservation (see include[] argument)
  "reserved_times": [{"id":987,"start_at":"2012-07-20T15:00:00-06:00","end_at":"2012-07-20T15:00:00-06:00"}],
  // Boolean indicating whether observer users should be able to sign-up for an
  // appointment
  "allow_observer_signup": false,
  // The context codes (i.e. courses) this appointment group belongs to. Only
  // people in these courses will be eligible to sign up.
  "context_codes": ["course_123"],
  // The sub-context codes (i.e. course sections and group categories) this
  // appointment group is restricted to
  "sub_context_codes": [course_section_234],
  // Current state of the appointment group ('pending', 'active' or 'deleted').
  // 'pending' indicates that it has not been published yet and is invisible to
  // participants.
  "workflow_state": "active",
  // Boolean indicating whether the current user needs to sign up for this
  // appointment group (i.e. it's reservable and the
  // min_appointments_per_participant limit has not been met by this user).
  "requiring_action": true,
  // Number of time slots in this appointment group
  "appointments_count": 2,
  // Calendar Events representing the time slots (see include[] argument) Refer to
  // the Calendar Events API for more information
  "appointments": [],
  // Newly created time slots (same format as appointments above). Only returned
  // in Create/Update responses where new time slots have been added
  "new_appointments": [],
  // Maximum number of time slots a user may register for, or null if no limit
  "max_appointments_per_participant": 1,
  // Minimum number of time slots a user must register for. If not set, users do
  // not need to sign up for any time slots
  "min_appointments_per_participant": 1,
  // Maximum number of participants that may register for each time slot, or null
  // if no limit
  "participants_per_appointment": 1,
  // 'private' means participants cannot see who has signed up for a particular
  // time slot, 'protected' means that they can
  "participant_visibility": "private",
  // Indicates how participants sign up for the appointment group, either as
  // individuals ('User') or in student groups ('Group'). Related to
  // sub_context_codes (i.e. 'Group' signups always have a single group category)
  "participant_type": "User",
  // URL for this appointment group (to update, delete, etc.)
  "url": "https://example.com/api/v1/appointment_groups/543",
  // URL for a user to view this appointment group
  "html_url": "http://example.com/appointment_groups/1",
  // When the appointment group was created
  "created_at": "2012-07-13T10:55:20-06:00",
  // When the appointment group was last updated
  "updated_at": "2012-07-13T10:55:20-06:00"
}
```

## List appointment groups

### GET /api/v1/appointment_groups

**Scope:** `url:GET|/api/v1/appointment_groups`

Retrieve the paginated list of appointment groups that can be reserved or managed by the current user.

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
<td>scope</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Defaults to “reservable”</p>
<p>Allowed values: <code class="enum">reservable</code>, <code class="enum">manageable</code></p></td>
</tr>
<tr class="request-param">
<td>context_codes[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Array of context codes used to limit returned results.</p></td>
</tr>
<tr class="request-param">
<td>include_past_appointments</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Defaults to false. If true, includes past appointment groups</p></td>
</tr>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Array of additional information to include.</p>
<dl>
<dt>“appointments”</dt>
<dd>
<p>calendar event time slots for this appointment group</p>
</dd>
<dt>“child_events”</dt>
<dd>
<p>reservations of those time slots</p>
</dd>
<dt>“participant_count”</dt>
<dd>
<p>number of reservations</p>
</dd>
<dt>“reserved_times”</dt>
<dd>
<p>the event id, start time and end time of reservations the current user has made)</p>
</dd>
<dt>“all_context_codes”</dt>
<dd>
<p>all context codes associated with this appointment group</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">appointments</code>, <code class="enum">child_events</code>, <code class="enum">participant_count</code>, <code class="enum">reserved_times</code>, <code class="enum">all_context_codes</code></p></td>
</tr>
</tbody>
</table>

## Create an appointment group

### POST /api/v1/appointment_groups

**Scope:** `url:POST|/api/v1/appointment_groups`

Create and return a new appointment group. If new_appointments are specified, the response will return a new_appointments array (same format as appointments array, see “List appointment groups” action)

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
<td>appointment_group[context_codes][]</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>Array of context codes (courses, e.g. course_1) this group should be linked to (1 or more). Users in the course(s) with appropriate permissions will be able to sign up for this appointment group.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[sub_context_codes][]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Array of sub context codes (course sections or a single group category) this group should be linked to. Used to limit the appointment group to particular sections. If a group category is specified, students will sign up in groups and the participant_type will be “Group” instead of “User”.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[title]</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>Short title for the appointment group.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[description]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Longer text description of the appointment group.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[location_name]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Location name of the appointment group.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[location_address]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Location address.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[publish]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Indicates whether this appointment group should be published (i.e. made available for signup). Once published, an appointment group cannot be unpublished. Defaults to false.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[participants_per_appointment]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Maximum number of participants that may register for each time slot. Defaults to null (no limit).</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[min_appointments_per_participant]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Minimum number of time slots a user must register for. If not set, users do not need to sign up for any time slots.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[max_appointments_per_participant]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Maximum number of time slots a user may register for.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[new_appointments][X][]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Nested array of start time/end time pairs indicating time slots for this appointment group. Refer to the example request.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[participant_visibility]</td>
<td></td>
<td>string</td>
<td class="param-desc"><dl>
<dt>“private”</dt>
<dd>
<p>participants cannot see who has signed up for a particular time slot</p>
</dd>
<dt>“protected”</dt>
<dd>
<p>participants can see who has signed up. Defaults to “private”.</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">private</code>, <code class="enum">protected</code></p></td>
</tr>
<tr class="request-param">
<td>appointment_group[allow_observer_signup]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether observer users can sign-up for an appointment. Defaults to false.</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/appointment_groups.json' \
     -X POST \
     -F 'appointment_group[context_codes][]=course_123' \
     -F 'appointment_group[sub_context_codes][]=course_section_234' \
     -F 'appointment_group[title]=Final Presentation' \
     -F 'appointment_group[participants_per_appointment]=1' \
     -F 'appointment_group[min_appointments_per_participant]=1' \
     -F 'appointment_group[max_appointments_per_participant]=1' \
     -F 'appointment_group[new_appointments][0][]=2012-07-19T21:00:00Z' \
     -F 'appointment_group[new_appointments][0][]=2012-07-19T22:00:00Z' \
     -F 'appointment_group[new_appointments][1][]=2012-07-19T22:00:00Z' \
     -F 'appointment_group[new_appointments][1][]=2012-07-19T23:00:00Z' \
     -H "Authorization: Bearer <token>"
```

## Get a single appointment group

### GET /api/v1/appointment_groups/:id

**Scope:** `url:GET|/api/v1/appointment_groups/:id`

Returns information for a single appointment group

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
<td class="param-desc"><p>Array of additional information to include. See include[] argument of “List appointment groups” action.</p>
<dl>
<dt>“child_events”</dt>
<dd>
<p>reservations of time slots time slots</p>
</dd>
<dt>“appointments”</dt>
<dd>
<p>will always be returned</p>
</dd>
<dt>“all_context_codes”</dt>
<dd>
<p>all context codes associated with this appointment group</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">child_events</code>, <code class="enum">appointments</code>, <code class="enum">all_context_codes</code></p></td>
</tr>
</tbody>
</table>

## Update an appointment group

### PUT /api/v1/appointment_groups/:id

**Scope:** `url:PUT|/api/v1/appointment_groups/:id`

Update and return an appointment group. If new_appointments are specified, the response will return a new_appointments array (same format as appointments array, see “List appointment groups” action).

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
<td>appointment_group[context_codes][]</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>Array of context codes (courses, e.g. course_1) this group should be linked to (1 or more). Users in the course(s) with appropriate permissions will be able to sign up for this appointment group.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[sub_context_codes][]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Array of sub context codes (course sections or a single group category) this group should be linked to. Used to limit the appointment group to particular sections. If a group category is specified, students will sign up in groups and the participant_type will be “Group” instead of “User”.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[title]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Short title for the appointment group.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[description]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Longer text description of the appointment group.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[location_name]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Location name of the appointment group.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[location_address]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Location address.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[publish]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Indicates whether this appointment group should be published (i.e. made available for signup). Once published, an appointment group cannot be unpublished. Defaults to false.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[participants_per_appointment]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Maximum number of participants that may register for each time slot. Defaults to null (no limit).</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[min_appointments_per_participant]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Minimum number of time slots a user must register for. If not set, users do not need to sign up for any time slots.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[max_appointments_per_participant]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Maximum number of time slots a user may register for.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[new_appointments][X][]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Nested array of start time/end time pairs indicating time slots for this appointment group. Refer to the example request.</p></td>
</tr>
<tr class="request-param">
<td>appointment_group[participant_visibility]</td>
<td></td>
<td>string</td>
<td class="param-desc"><dl>
<dt>“private”</dt>
<dd>
<p>participants cannot see who has signed up for a particular time slot</p>
</dd>
<dt>“protected”</dt>
<dd>
<p>participants can see who has signed up. Defaults to “private”.</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">private</code>, <code class="enum">protected</code></p></td>
</tr>
<tr class="request-param">
<td>appointment_group[allow_observer_signup]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether observer users can sign-up for an appointment.</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/appointment_groups/543.json' \
     -X PUT \
     -F 'appointment_group[publish]=1' \
     -H "Authorization: Bearer <token>"
```

## Delete an appointment group

### DELETE /api/v1/appointment_groups/:id

**Scope:** `url:DELETE|/api/v1/appointment_groups/:id`

Delete an appointment group (and associated time slots and reservations) and return the deleted group

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| cancel_reason |  | string | Reason for deleting/canceling the appointment group. |

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/appointment_groups/543.json' \
     -X DELETE \
     -F 'cancel_reason=El Tigre Chino got fired' \
     -H "Authorization: Bearer <token>"
```

## List user participants

### GET /api/v1/appointment_groups/:id/users

**Scope:** `url:GET|/api/v1/appointment_groups/:id/users`

A paginated list of users that are (or may be) participating in this appointment group. Refer to the Users API for the response fields. Returns no results for appointment groups with the “Group” participant_type.

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
<td>registration_status</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Limits results to the a given participation status, defaults to “all”</p>
<p>Allowed values: <code class="enum">all</code>, <code class="enum">registered</code>, <code class="enum">registered</code></p></td>
</tr>
</tbody>
</table>

## List student group participants

### GET /api/v1/appointment_groups/:id/groups

**Scope:** `url:GET|/api/v1/appointment_groups/:id/groups`

A paginated list of student groups that are (or may be) participating in this appointment group. Refer to the Groups API for the response fields. Returns no results for appointment groups with the “User” participant_type.

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
<td>registration_status</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Limits results to the a given participation status, defaults to “all”</p>
<p>Allowed values: <code class="enum">all</code>, <code class="enum">registered</code>, <code class="enum">registered</code></p></td>
</tr>
</tbody>
</table>

## Get next appointment

### GET /api/v1/appointment_groups/next_appointment

**Scope:** `url:GET|/api/v1/appointment_groups/next_appointment`

Return the next appointment available to sign up for. The appointment is returned in a one-element array. If no future appointments are available, an empty array is returned.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| appointment_group_ids\[\] |  | string | List of ids of appointment groups to search. |

Returns a list of [CalendarEvent](calendar_events.html#CalendarEvent) objects
