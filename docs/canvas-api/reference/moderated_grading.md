# Moderated Grading API

API for viewing and adding students to the list of people in moderation for an assignment

API for manipulating provisional grades

Provisional grades are created by using the Submissions API endpoint "Grade or comment on a submission" with `provisional=true`. They can be viewed by using "List assignment submissions", "Get a single submission", or "List gradeable students" with `include[]=provisional_grades`. This API performs other operations on provisional grades for use with the Moderated Grading feature.

### A ProvisionalGrade object looks like:

``` example
{
  // The identifier for the provisional grade
  "provisional_grade_id": 23,
  // The numeric score
  "score": 90,
  // The grade
  "grade": "A-",
  // Whether the grade was applied to the most current submission (false if the
  // student resubmitted after grading)
  "grade_matches_current_submission": true,
  // When the grade was given
  "graded_at": "2015-11-01T00:03:21-06:00",
  // Whether this is the 'final' provisional grade created by the moderator
  "final": false,
  // A link to view this provisional grade in SpeedGrader
  "speedgrader_url": "http://www.example.com/courses/123/gradebook/speed_grader?..."
}
```

## List students selected for moderation

### GET /api/v1/courses/:course_id/assignments/:assignment_id/moderated_students

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/moderated_students`

Returns a paginated list of students selected for moderation

Returns a list of [User](users.html#User) objects

## Select students for moderation

### POST /api/v1/courses/:course_id/assignments/:assignment_id/moderated_students

**Scope:** `url:POST|/api/v1/courses/:course_id/assignments/:assignment_id/moderated_students`

Returns an array of users that were selected for moderation

#### Request Parameters:

| Parameter       |     | Type   | Description                                    |
|-----------------|-----|--------|------------------------------------------------|
| student_ids\[\] |     | number | user ids for students to select for moderation |

Returns a list of [User](users.html#User) objects

## Bulk select provisional grades

### PUT /api/v1/courses/:course_id/assignments/:assignment_id/provisional_grades/bulk_select

**Scope:** `url:PUT|/api/v1/courses/:course_id/assignments/:assignment_id/provisional_grades/bulk_select`

Choose which provisional grades will be received by associated students for an assignment. The caller must be the final grader for the assignment or an admin with :select_final_grade rights.

#### Example Response:

####

``` example
[{
  "assignment_id": 867,
  "student_id": 5309,
  "selected_provisional_grade_id": 53669
}]
```

## Show provisional grade status for a student

### GET /api/v1/courses/:course_id/assignments/:assignment_id/provisional_grades/status

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/provisional_grades/status`

Tell whether the student’s submission needs one or more provisional grades.

#### Request Parameters:

| Parameter  |     | Type    | Description                                  |
|------------|-----|---------|----------------------------------------------|
| student_id |     | integer | The id of the student to show the status for |

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/1/assignments/2/provisional_grades/status?student_id=1'
```

#### Example Response:

####

``` example
{ "needs_provisional_grade": false }
```

## Select provisional grade

### PUT /api/v1/courses/:course_id/assignments/:assignment_id/provisional_grades/:provisional_grade_id/select

**Scope:** `url:PUT|/api/v1/courses/:course_id/assignments/:assignment_id/provisional_grades/:provisional_grade_id/select`

Choose which provisional grade the student should receive for a submission. The caller must be the final grader for the assignment or an admin with :select_final_grade rights.

#### Example Response:

####

``` example
{
  "assignment_id": 867,
  "student_id": 5309,
  "selected_provisional_grade_id": 53669
}
```

## Publish provisional grades for an assignment

### POST /api/v1/courses/:course_id/assignments/:assignment_id/provisional_grades/publish

**Scope:** `url:POST|/api/v1/courses/:course_id/assignments/:assignment_id/provisional_grades/publish`

Publish the selected provisional grade for all submissions to an assignment. Use the “Select provisional grade” endpoint to choose which provisional grade to publish for a particular submission.

Students not in the moderation set will have their one and only provisional grade published.

WARNING: This is irreversible. This will overwrite existing grades in the gradebook.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/1/assignments/2/provisional_grades/publish' \
     -X POST
```

## Show provisional grade status for a student

### GET /api/v1/courses/:course_id/assignments/:assignment_id/anonymous_provisional_grades/status

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/anonymous_provisional_grades/status`

Determine whether or not the student’s submission needs one or more provisional grades.

#### Request Parameters:

| Parameter    |     | Type   | Description                                  |
|--------------|-----|--------|----------------------------------------------|
| anonymous_id |     | string | The id of the student to show the status for |

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/courses/1/assignments/2/anonymous_provisional_grades/status?anonymous_id=1'
```

#### Example Response:

####

``` example
{ "needs_provisional_grade": false }
```
