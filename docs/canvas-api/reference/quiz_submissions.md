# Quiz Submissions API

API for accessing quiz submissions

### A QuizSubmission object looks like:

``` example
{
  // The ID of the quiz submission.
  "id": 1,
  // The ID of the Quiz the quiz submission belongs to.
  "quiz_id": 2,
  // The ID of the Student that made the quiz submission.
  "user_id": 3,
  // The ID of the Submission the quiz submission represents.
  "submission_id": 1,
  // The time at which the student started the quiz submission.
  "started_at": "2013-11-07T13:16:18Z",
  // The time at which the student submitted the quiz submission.
  "finished_at": "2013-11-07T13:16:18Z",
  // The time at which the quiz submission will be overdue, and be flagged as a
  // late submission.
  "end_at": "2013-11-07T13:16:18Z",
  // For quizzes that allow multiple attempts, this field specifies the quiz
  // submission attempt number.
  "attempt": 3,
  // Number of times the student was allowed to re-take the quiz over the
  // multiple-attempt limit.
  "extra_attempts": 1,
  // Amount of extra time allowed for the quiz submission, in minutes.
  "extra_time": 60,
  // The student can take the quiz even if it's locked for everyone else
  "manually_unlocked": true,
  // Amount of time spent, in seconds.
  "time_spent": 300,
  // The score of the quiz submission, if graded.
  "score": 3,
  // The original score of the quiz submission prior to any re-grading.
  "score_before_regrade": 2,
  // For quizzes that allow multiple attempts, this is the score that will be
  // used, which might be the score of the latest, or the highest, quiz
  // submission.
  "kept_score": 5,
  // Number of points the quiz submission's score was fudged by.
  "fudge_points": 1,
  // Whether the student has viewed their results to the quiz.
  "has_seen_results": true,
  // The current state of the quiz submission. Possible values:
  // ['untaken'|'pending_review'|'complete'|'settings_only'|'preview'].
  "workflow_state": "untaken",
  // Indicates whether the quiz submission is overdue and needs submission
  "overdue_and_needs_submission": false
}
```

## Get all quiz submissions.

### GET /api/v1/courses/:course_id/quizzes/:quiz_id/submissions

**Scope:** `url:GET|/api/v1/courses/:course_id/quizzes/:quiz_id/submissions`

Get a list of all submissions for this quiz. Users who can view or manage grades for a course will have submissions from multiple users returned. A user who can only submit will have only their own submissions returned. When a user has an in-progress submission, only that submission is returned. When there isn’t an in-progress quiz_submission, all completed submissions, including previous attempts, are returned.

**200 OK** response code is returned if the request was successful.

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
<td class="param-desc"><p>Associations to include with the quiz submission.</p>
<p>Allowed values: <code class="enum">submission</code>, <code class="enum">quiz</code>, <code class="enum">user</code></p></td>
</tr>
</tbody>
</table>

#### Example Response:

####

``` example
{
  "quiz_submissions": [QuizSubmission]
}
```

## Get the quiz submission.

### GET /api/v1/courses/:course_id/quizzes/:quiz_id/submission

**Scope:** `url:GET|/api/v1/courses/:course_id/quizzes/:quiz_id/submission`

Get the submission for this quiz for the current user.

**200 OK** response code is returned if the request was successful.

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
<td class="param-desc"><p>Associations to include with the quiz submission.</p>
<p>Allowed values: <code class="enum">submission</code>, <code class="enum">quiz</code>, <code class="enum">user</code></p></td>
</tr>
</tbody>
</table>

#### Example Response:

####

``` example
{
  "quiz_submissions": [QuizSubmission]
}
```

## Get a single quiz submission.

### GET /api/v1/courses/:course_id/quizzes/:quiz_id/submissions/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/quizzes/:quiz_id/submissions/:id`

Get a single quiz submission.

**200 OK** response code is returned if the request was successful.

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
<td class="param-desc"><p>Associations to include with the quiz submission.</p>
<p>Allowed values: <code class="enum">submission</code>, <code class="enum">quiz</code>, <code class="enum">user</code></p></td>
</tr>
</tbody>
</table>

#### Example Response:

####

``` example
{
  "quiz_submissions": [QuizSubmission]
}
```

## Create the quiz submission (start a quiz-taking session)

### POST /api/v1/courses/:course_id/quizzes/:quiz_id/submissions

**Scope:** `url:POST|/api/v1/courses/:course_id/quizzes/:quiz_id/submissions`

Start taking a Quiz by creating a QuizSubmission which you can use to answer questions and submit your answers.

**Responses**

- **200 OK** if the request was successful

- **400 Bad Request** if the quiz is locked

- **403 Forbidden** if an invalid access code is specified

- **403 Forbidden** if the Quiz’s IP filter restriction does not pass

- **409 Conflict** if a QuizSubmission already exists for this user and quiz

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| access_code |  | string | Access code for the Quiz, if any. |
| preview |  | boolean | Whether this should be a preview QuizSubmission and not count towards the user’s course record. Teachers only. |

#### Example Response:

####

``` example
{
  "quiz_submissions": [QuizSubmission]
}
```

## Update student question scores and comments.

### PUT /api/v1/courses/:course_id/quizzes/:quiz_id/submissions/:id

**Scope:** `url:PUT|/api/v1/courses/:course_id/quizzes/:quiz_id/submissions/:id`

Update the amount of points a student has scored for questions they’ve answered, provide comments for the student about their answer(s), or simply fudge the total score by a specific amount of points.

**Responses**

- **200 OK** if the request was successful

- **403 Forbidden** if you are not a teacher in this course

- **400 Bad Request** if the attempt parameter is missing or invalid

- **400 Bad Request** if the specified QS attempt is not yet complete

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| quiz_submissions\[\]\[attempt\] | Required | integer | The attempt number of the quiz submission that should be updated. This attempt MUST be already completed. |
| quiz_submissions\[\]\[fudge_points\] |  | number | Amount of positive or negative points to fudge the total score by. |
| quiz_submissions\[\]\[questions\] |  | Hash | A set of scores and comments for each question answered by the student. The keys are the question IDs, and the values are hashes of ‘score\` and \`comment\` entries. See [Appendix: Manual Scoring](quiz_submissions.html#Manual+Scoring-appendix "Appendix: Manual Scoring") for more on this parameter. |

#### Example Request:

####

``` example
{
  "quiz_submissions": [{
    "attempt": 1,
    "fudge_points": -2.4,
    "questions": {
      "1": {
        "score": 2.5,
        "comment": "This can't be right, but I'll let it pass this one time."
      },
      "2": {
        "score": 0,
        "comment": "Good thinking. Almost!"
      }
    }
  }]
}
```

#### Example Response:

####

``` example
{
  "quiz_submissions": [QuizSubmission]
}
```

**See Also:**

- [Appendix: Manual Scoring](quiz_submissions.html#Manual+Scoring-appendix "Appendix: Manual Scoring")

## Complete the quiz submission (turn it in).

### POST /api/v1/courses/:course_id/quizzes/:quiz_id/submissions/:id/complete

**Scope:** `url:POST|/api/v1/courses/:course_id/quizzes/:quiz_id/submissions/:id/complete`

Complete the quiz submission by marking it as complete and grading it. When the quiz submission has been marked as complete, no further modifications will be allowed.

**Responses**

- **200 OK** if the request was successful

- **403 Forbidden** if an invalid access code is specified

- **403 Forbidden** if the Quiz’s IP filter restriction does not pass

- **403 Forbidden** if an invalid token is specified

- **400 Bad Request** if the QS is already complete

- **400 Bad Request** if the attempt parameter is missing

- **400 Bad Request** if the attempt parameter is not the latest attempt

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| attempt | Required | integer | The attempt number of the quiz submission that should be completed. Note that this must be the latest attempt index, as earlier attempts can not be modified. |
| validation_token | Required | string | The unique validation token you received when this Quiz Submission was created. |
| access_code |  | string | Access code for the Quiz, if any. |

#### Example Response:

####

``` example
{
  "quiz_submissions": [QuizSubmission]
}
```

## Get current quiz submission times.

### GET /api/v1/courses/:course_id/quizzes/:quiz_id/submissions/:id/time

**Scope:** `url:GET|/api/v1/courses/:course_id/quizzes/:quiz_id/submissions/:id/time`

Get the current timing data for the quiz attempt, both the end_at timestamp and the time_left parameter.

**Responses**

- **200 OK** if the request was successful

#### Example Response:

####

``` example
{
  "end_at": [DateTime],
  "time_left": [Integer]
}
```

## Appendixes

### Appendix: Manual Scoring

**Parameter synopsis**

``` code
{
  "quiz_submissions": [{
    "fudge_points": null, // null for no change, or a signed decimal
    "questions": {
      "QUESTION_ID": {
        "score": null, // null for no change, or an unsigned decimal
        "comment": null // null for no change, '' for no comment, or a string
      }
    }
  }]
}
```

### More example requests

**Fudging the score by a negative amount**

``` code
{
  "quiz_submissions": [{
    "attempt": 1,
    "fudge_points": -2.4
  }]
}
```

**Removing an earlier comment on a question**

``` code
{
  "quiz_submissions": [{
    "attempt": 1,
    "questions": {
      "1": {
        "comment": ""
      }
    }
  }]
}
```
