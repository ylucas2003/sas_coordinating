# Blueprint Courses API

Configure blueprint courses

### A BlueprintTemplate object looks like:

``` example
{
  // The ID of the template.
  "id": 1,
  // The ID of the Course the template belongs to.
  "course_id": 2,
  // Time when the last export was completed
  "last_export_completed_at": "2013-08-28T23:59:00-06:00",
  // Number of associated courses for the template
  "associated_course_count": 3,
  // Details of the latest migration
  "latest_migration": null
}
```

### A BlueprintMigration object looks like:

``` example
{
  // The ID of the migration.
  "id": 1,
  // The ID of the template the migration belongs to. Only present when querying a
  // blueprint course.
  "template_id": 2,
  // The ID of the associated course's blueprint subscription. Only present when
  // querying a course associated with a blueprint.
  "subscription_id": 101,
  // The ID of the user who queued the migration.
  "user_id": 3,
  // Current state of the content migration: queued, exporting, imports_queued,
  // completed, exports_failed, imports_failed
  "workflow_state": "running",
  // Time when the migration was queued
  "created_at": "2013-08-28T23:59:00-06:00",
  // Time when the exports begun
  "exports_started_at": "2013-08-28T23:59:00-06:00",
  // Time when the exports were completed and imports were queued
  "imports_queued_at": "2013-08-28T23:59:00-06:00",
  // Time when the imports were completed
  "imports_completed_at": "2013-08-28T23:59:00-06:00",
  // User-specified comment describing changes made in this operation
  "comment": "Fixed spelling in question 3 of midterm exam"
}
```

### A BlueprintRestriction object looks like:

``` example
// A set of restrictions on editing for copied objects in associated courses
{
  // Restriction on main content (e.g. title, description).
  "content": true,
  // Restriction on points possible for assignments and graded learning objects
  "points": true,
  // Restriction on due dates for assignments and graded learning objects
  "due_dates": false,
  // Restriction on availability dates for an object
  "availability_dates": true
}
```

### A ChangeRecord object looks like:

``` example
// Describes a learning object change propagated to associated courses from a
// blueprint course
{
  // The ID of the learning object that was changed in the blueprint course.
  "asset_id": 2,
  // The type of the learning object that was changed in the blueprint course.
  // One of 'assignment', 'attachment', 'discussion_topic', 'external_tool',
  // 'quiz', 'wiki_page', 'syllabus', or 'settings'.  For 'syllabus' or
  // 'settings', the asset_id is the course id.
  "asset_type": "assignment",
  // The name of the learning object that was changed in the blueprint course.
  "asset_name": "Some Assignment",
  // The type of change; one of 'created', 'updated', 'deleted'
  "change_type": "created",
  // The URL of the changed object
  "html_url": "https://canvas.example.com/courses/101/assignments/2",
  // Whether the object is locked in the blueprint
  "locked": false,
  // A list of ExceptionRecords for linked courses that did not receive this
  // update.
  "exceptions": [{"course_id":101,"conflicting_changes":["points"]}]
}
```

### An ExceptionRecord object looks like:

``` example
// Lists associated courses that did not receive a change propagated from a
// blueprint
{
  // The ID of the associated course
  "course_id": 101,
  // A list of change classes in the associated course's copy of the item that
  // prevented a blueprint change from being applied. One or more of ['content',
  // 'points', 'due_dates', 'availability_dates'].
  "conflicting_changes": ["points"]
}
```

### A BlueprintSubscription object looks like:

``` example
// Associates a course with a blueprint
{
  // The ID of the blueprint course subscription
  "id": 101,
  // The ID of the blueprint template the associated course is subscribed to
  "template_id": 1,
  // The blueprint course subscribed to
  "blueprint_course": {"id":2,"name":"Biology 100 Blueprint","course_code":"BIOL 100 BP","term_name":"Default term"}
}
```

## Get blueprint information

### GET /api/v1/courses/:course_id/blueprint_templates/:template_id

**Scope:** `url:GET|/api/v1/courses/:course_id/blueprint_templates/:template_id`

Using ‘default’ as the template_id should suffice for the current implmentation (as there should be only one template per course). However, using specific template ids may become necessary in the future

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/1/blueprint_templates/default \
  -H 'Authorization: Bearer <ACCESS_TOKEN>'
```

Returns a [BlueprintTemplate](blueprint_courses.html#BlueprintTemplate) object

## Get associated course information

### GET /api/v1/courses/:course_id/blueprint_templates/:template_id/associated_courses

**Scope:** `url:GET|/api/v1/courses/:course_id/blueprint_templates/:template_id/associated_courses`

Returns a list of courses that are configured to receive updates from this blueprint

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/1/blueprint_templates/default/associated_courses \
  -H 'Authorization: Bearer <ACCESS_TOKEN>'
```

Returns a list of [Course](courses.html#Course) objects

## Update associated courses

### PUT /api/v1/courses/:course_id/blueprint_templates/:template_id/update_associations

**Scope:** `url:PUT|/api/v1/courses/:course_id/blueprint_templates/:template_id/update_associations`

Send a list of course ids to add or remove new associations for the template. Cannot add courses that do not belong to the blueprint course’s account. Also cannot add other blueprint courses or courses that already have an association with another blueprint course.

After associating new courses, [start a sync](blueprint_courses.html#method.master_courses/master_templates.queue_migration "start a sync") to populate their contents from the blueprint.

#### Request Parameters:

| Parameter            |     | Type  | Description                             |
|----------------------|-----|-------|-----------------------------------------|
| course_ids_to_add    |     | Array | Courses to add as associated courses    |
| course_ids_to_remove |     | Array | Courses to remove as associated courses |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/1/blueprint_templates/default/update_associations \
-X PUT \
-H 'Authorization: Bearer <token>' \
-d 'course_ids_to_add[]=1' \
-d 'course_ids_to_remove[]=2' \
```

## Begin a migration to push to associated courses

### POST /api/v1/courses/:course_id/blueprint_templates/:template_id/migrations

**Scope:** `url:POST|/api/v1/courses/:course_id/blueprint_templates/:template_id/migrations`

Begins a migration to push recently updated content to all associated courses. Only one migration can be running at a time.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| comment |  | string | An optional comment to be included in the sync history. |
| send_notification |  | boolean | Send a notification to the calling user when the sync completes. |
| copy_settings |  | boolean | Whether course settings should be copied over to associated courses. Defaults to true for newly associated courses. |
| send_item_notifications |  | boolean | By default, new-item notifications are suppressed in blueprint syncs. If this option is set, teachers and students may receive notifications for items such as announcements and assignments that are created in associated courses (subject to the usual notification settings). This option requires the Blueprint Item Notifications feature to be enabled. |
| publish_after_initial_sync |  | boolean | If set, newly associated courses will be automatically published after the sync completes |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/1/blueprint_templates/default/migrations \
-X POST \
-F 'comment=Fixed spelling in question 3 of midterm exam' \
-F 'send_notification=true' \
-H 'Authorization: Bearer <token>'
```

Returns a [BlueprintMigration](blueprint_courses.html#BlueprintMigration) object

## Set or remove restrictions on a blueprint course object

### PUT /api/v1/courses/:course_id/blueprint_templates/:template_id/restrict_item

**Scope:** `url:PUT|/api/v1/courses/:course_id/blueprint_templates/:template_id/restrict_item`

If a blueprint course object is restricted, editing will be limited for copies in associated courses.

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
<td>content_type</td>
<td></td>
<td>string</td>
<td class="param-desc"><dl>
<dt>String, “assignment”|“attachment”|“discussion_topic”|“external_tool”|“lti-quiz”|“quiz”|“wiki_page”</dt>
<dd>
<p>The type of the object.</p>
</dd>
</dl></td>
</tr>
<tr class="request-param">
<td>content_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The ID of the object.</p></td>
</tr>
<tr class="request-param">
<td>restricted</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether to apply restrictions.</p></td>
</tr>
<tr class="request-param">
<td>restrictions</td>
<td></td>
<td>BlueprintRestriction</td>
<td class="param-desc"><p>(Optional) If the object is restricted, this specifies a set of restrictions. If not specified, the course-level restrictions will be used. See Course API update documentation</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/1/blueprint_templates/default/restrict_item \
-X PUT \
-H 'Authorization: Bearer <token>' \
-d 'content_type=assignment' \
-d 'content_id=2' \
-d 'restricted=true'
```

## Get unsynced changes

### GET /api/v1/courses/:course_id/blueprint_templates/:template_id/unsynced_changes

**Scope:** `url:GET|/api/v1/courses/:course_id/blueprint_templates/:template_id/unsynced_changes`

Retrieve a list of learning objects that have changed since the last blueprint sync operation. If no syncs have been completed, a ChangeRecord with a change_type of `initial_sync` is returned.

Returns a list of [ChangeRecord](blueprint_courses.html#ChangeRecord) objects

## List blueprint migrations

### GET /api/v1/courses/:course_id/blueprint_templates/:template_id/migrations

**Scope:** `url:GET|/api/v1/courses/:course_id/blueprint_templates/:template_id/migrations`

Shows a paginated list of migrations for the template, starting with the most recent. This endpoint can be called on a blueprint course. See also [the associated course side](blueprint_courses.html#method.master_courses/master_templates.imports_index "the associated course side").

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/1/blueprint_templates/default/migrations \
-H 'Authorization: Bearer <token>'
```

Returns a list of [BlueprintMigration](blueprint_courses.html#BlueprintMigration) objects

## Show a blueprint migration

### GET /api/v1/courses/:course_id/blueprint_templates/:template_id/migrations/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/blueprint_templates/:template_id/migrations/:id`

Shows the status of a migration. This endpoint can be called on a blueprint course. See also [the associated course side](blueprint_courses.html#method.master_courses/master_templates.imports_show "the associated course side").

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/1/blueprint_templates/default/migrations/:id \
-H 'Authorization: Bearer <token>'
```

Returns a [BlueprintMigration](blueprint_courses.html#BlueprintMigration) object

## Get migration details

### GET /api/v1/courses/:course_id/blueprint_templates/:template_id/migrations/:id/details

**Scope:** `url:GET|/api/v1/courses/:course_id/blueprint_templates/:template_id/migrations/:id/details`

Show the changes that were propagated in a blueprint migration. This endpoint can be called on a blueprint course. See also [the associated course side](blueprint_courses.html#method.master_courses/master_templates.import_details "the associated course side").

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/1/blueprint_templates/default/migrations/2/details \
-H 'Authorization: Bearer <token>'
```

Returns a list of [ChangeRecord](blueprint_courses.html#ChangeRecord) objects

## List blueprint subscriptions

### GET /api/v1/courses/:course_id/blueprint_subscriptions

**Scope:** `url:GET|/api/v1/courses/:course_id/blueprint_subscriptions`

Returns a list of blueprint subscriptions for the given course. (Currently a course may have no more than one.)

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/2/blueprint_subscriptions \
-H 'Authorization: Bearer <token>'
```

Returns a list of [BlueprintSubscription](blueprint_courses.html#BlueprintSubscription) objects

## List blueprint imports

### GET /api/v1/courses/:course_id/blueprint_subscriptions/:subscription_id/migrations

**Scope:** `url:GET|/api/v1/courses/:course_id/blueprint_subscriptions/:subscription_id/migrations`

Shows a paginated list of migrations imported into a course associated with a blueprint, starting with the most recent. See also [the blueprint course side](blueprint_courses.html#method.master_courses/master_templates.migrations_index "the blueprint course side").

Use ‘default’ as the subscription_id to use the currently active blueprint subscription.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/2/blueprint_subscriptions/default/migrations \
-H 'Authorization: Bearer <token>'
```

Returns a list of [BlueprintMigration](blueprint_courses.html#BlueprintMigration) objects

## Show a blueprint import

### GET /api/v1/courses/:course_id/blueprint_subscriptions/:subscription_id/migrations/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/blueprint_subscriptions/:subscription_id/migrations/:id`

Shows the status of an import into a course associated with a blueprint. See also [the blueprint course side](blueprint_courses.html#method.master_courses/master_templates.migrations_show "the blueprint course side").

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/2/blueprint_subscriptions/default/migrations/:id \
-H 'Authorization: Bearer <token>'
```

Returns a [BlueprintMigration](blueprint_courses.html#BlueprintMigration) object

## Get import details

### GET /api/v1/courses/:course_id/blueprint_subscriptions/:subscription_id/migrations/:id/details

**Scope:** `url:GET|/api/v1/courses/:course_id/blueprint_subscriptions/:subscription_id/migrations/:id/details`

Show the changes that were propagated to a course associated with a blueprint. See also [the blueprint course side](blueprint_courses.html#method.master_courses/master_templates.migration_details "the blueprint course side").

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/2/blueprint_subscriptions/default/7/details \
-H 'Authorization: Bearer <token>'
```

Returns a list of [ChangeRecord](blueprint_courses.html#ChangeRecord) objects
