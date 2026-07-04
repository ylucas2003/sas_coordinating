# Grade Change Log API

Query audit log of grade change events.

For each endpoint, a compound document is returned. The primary collection of event objects is paginated, ordered by date descending. Secondary collections of assignments, courses, students and graders related to the returned events are also included. Refer to the Assignment, Courses, and Users APIs for descriptions of the objects in those collections.

### A GradeChangeEventLinks object looks like:

``` example
{
  // ID of the assignment associated with the event
  "assignment": 2319,
  // ID of the course associated with the event. will match the context_id in the
  // associated assignment if the context type for the assignment is a course
  "course": 2319,
  // ID of the student associated with the event. will match the user_id in the
  // associated submission.
  "student": 2319,
  // ID of the grader associated with the event. will match the grader_id in the
  // associated submission.
  "grader": 2319,
  // ID of the page view during the event if it exists.
  "page_view": "e2b76430-27a5-0131-3ca1-48e0eb13f29b"
}
```

### A GradeChangeEvent object looks like:

``` example
{
  // ID of the event.
  "id": "e2b76430-27a5-0131-3ca1-48e0eb13f29b",
  // timestamp of the event
  "created_at": "2012-07-19T15:00:00-06:00",
  // GradeChange event type
  "event_type": "grade_change",
  // Boolean indicating whether the submission was excused after the change.
  "excused_after": true,
  // Boolean indicating whether the submission was excused before the change.
  "excused_before": false,
  // The grade after the change.
  "grade_after": "8",
  // The grade before the change.
  "grade_before": "8",
  // Boolean indicating whether the student name was visible when the grade was
  // given. Could be null if the grade change record was created before this
  // feature existed.
  "graded_anonymously": true,
  // Version Number of the grade change submission.
  "version_number": "1",
  // The unique request id of the request during the grade change.
  "request_id": "e2b76430-27a5-0131-3ca1-48e0eb13f29b",
  "links": null
}
```

## Query by assignment

### GET /api/v1/audit/grade_change/assignments/:assignment_id

**Scope:** `url:GET|/api/v1/audit/grade_change/assignments/:assignment_id`

List grade change events for a given assignment.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| start_time |  | DateTime | The beginning of the time range from which you want events. |
| end_time |  | DateTime | The end of the time range from which you want events. |

Returns a list of [GradeChangeEvent](grade_change_log.html#GradeChangeEvent) objects

## Query by course

### GET /api/v1/audit/grade_change/courses/:course_id

**Scope:** `url:GET|/api/v1/audit/grade_change/courses/:course_id`

List grade change events for a given course.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| start_time |  | DateTime | The beginning of the time range from which you want events. |
| end_time |  | DateTime | The end of the time range from which you want events. |

Returns a list of [GradeChangeEvent](grade_change_log.html#GradeChangeEvent) objects

## Query by student

### GET /api/v1/audit/grade_change/students/:student_id

**Scope:** `url:GET|/api/v1/audit/grade_change/students/:student_id`

List grade change events for a given student.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| start_time |  | DateTime | The beginning of the time range from which you want events. |
| end_time |  | DateTime | The end of the time range from which you want events. |

Returns a list of [GradeChangeEvent](grade_change_log.html#GradeChangeEvent) objects

## Query by grader

### GET /api/v1/audit/grade_change/graders/:grader_id

**Scope:** `url:GET|/api/v1/audit/grade_change/graders/:grader_id`

List grade change events for a given grader.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| start_time |  | DateTime | The beginning of the time range from which you want events. |
| end_time |  | DateTime | The end of the time range from which you want events. |

Returns a list of [GradeChangeEvent](grade_change_log.html#GradeChangeEvent) objects

## Advanced query

### GET /api/v1/audit/grade_change

**Scope:** `url:GET|/api/v1/audit/grade_change`

List grade change events satisfying all given parameters. Teachers may query for events in courses they teach. Queries without `course_id` require account administrator rights.

At least one of `course_id`, `assignment_id`, `student_id`, or `grader_id` must be specified.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| course_id |  | integer | Restrict query to events in the specified course. |
| assignment_id |  | integer | Restrict query to the given assignment. If “override” is given, query the course final grade override instead. |
| student_id |  | integer | User id of a student to search grading events for. |
| grader_id |  | integer | User id of a grader to search grading events for. |
| start_time |  | DateTime | The beginning of the time range from which you want events. |
| end_time |  | DateTime | The end of the time range from which you want events. |

Returns a list of [GradeChangeEvent](grade_change_log.html#GradeChangeEvent) objects
