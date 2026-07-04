# Assignment Extensions API

API for setting extensions on student assignment submissions. These cannot be set for discussion assignments or quizzes. For quizzes, use [Quiz Extensions](/doc/api/quiz_extensions.html) instead.

### An AssignmentExtension object looks like:

``` example
{
  // The ID of the Assignment the extension belongs to.
  "assignment_id": 2,
  // The ID of the Student that needs the assignment extension.
  "user_id": 3,
  // Number of times the student is allowed to re-submit the assignment
  "extra_attempts": 2
}
```

## Set extensions for student assignment submissions

### POST /api/v1/courses/:course_id/assignments/:assignment_id/extensions

**Scope:** `url:POST|/api/v1/courses/:course_id/assignments/:assignment_id/extensions`

**Responses**

- **200 OK** if the request was successful

- **403 Forbidden** if you are not allowed to extend assignments for this course

- **400 Bad Request** if any of the extensions are invalid

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| assignment_extensions\[\]\[user_id\] | Required | integer | The ID of the user we want to add assignment extensions for. |
| assignment_extensions\[\]\[extra_attempts\] | Required | integer | Number of times the student is allowed to re-take the assignment over the limit. |

#### Example Request:

####

``` example
{
  "assignment_extensions": [{
    "user_id": 3,
    "extra_attempts": 2
  },{
    "user_id": 2,
    "extra_attempts": 2
  }]
}
```

#### Example Response:

####

``` example
{
  "assignment_extensions": [AssignmentExtension]
}
```
