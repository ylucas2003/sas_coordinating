# Quiz Question Groups API

API for accessing information on quiz question groups

### A QuizGroup object looks like:

``` example
{
  // The ID of the question group.
  "id": 1,
  // The ID of the Quiz the question group belongs to.
  "quiz_id": 2,
  // The name of the question group.
  "name": "Fraction questions",
  // The number of questions to pick from the group to display to the student.
  "pick_count": 3,
  // The amount of points allotted to each question in the group.
  "question_points": 10,
  // The ID of the Assessment question bank to pull questions from.
  "assessment_question_bank_id": 2,
  // The order in which the question group will be retrieved and displayed.
  "position": 1
}
```

## Get a single quiz group

### GET /api/v1/courses/:course_id/quizzes/:quiz_id/groups/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/quizzes/:quiz_id/groups/:id`

Returns details of the quiz group with the given id.

Returns a [QuizGroup](quiz_question_groups.html#QuizGroup) object

## Create a question group

### POST /api/v1/courses/:course_id/quizzes/:quiz_id/groups

**Scope:** `url:POST|/api/v1/courses/:course_id/quizzes/:quiz_id/groups`

Create a new question group for this quiz

**201 Created** response code is returned if the creation was successful.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| quiz_groups\[\]\[name\] |  | string | The name of the question group. |
| quiz_groups\[\]\[pick_count\] |  | integer | The number of questions to randomly select for this group. |
| quiz_groups\[\]\[question_points\] |  | integer | The number of points to assign to each question in the group. |
| quiz_groups\[\]\[assessment_question_bank_id\] |  | integer | The id of the assessment question bank to pull questions from. |

#### Example Response:

####

``` example
{
  "quiz_groups": [QuizGroup]
}
```

## Update a question group

### PUT /api/v1/courses/:course_id/quizzes/:quiz_id/groups/:id

**Scope:** `url:PUT|/api/v1/courses/:course_id/quizzes/:quiz_id/groups/:id`

Update a question group

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| quiz_groups\[\]\[name\] |  | string | The name of the question group. |
| quiz_groups\[\]\[pick_count\] |  | integer | The number of questions to randomly select for this group. |
| quiz_groups\[\]\[question_points\] |  | integer | The number of points to assign to each question in the group. |

#### Example Response:

####

``` example
{
  "quiz_groups": [QuizGroup]
}
```

## Delete a question group

### DELETE /api/v1/courses/:course_id/quizzes/:quiz_id/groups/:id

**Scope:** `url:DELETE|/api/v1/courses/:course_id/quizzes/:quiz_id/groups/:id`

Delete a question group

\<b\>204 No Content\<b\> response code is returned if the deletion was successful.

## Reorder question groups

### POST /api/v1/courses/:course_id/quizzes/:quiz_id/groups/:id/reorder

**Scope:** `url:POST|/api/v1/courses/:course_id/quizzes/:quiz_id/groups/:id/reorder`

Change the order of the quiz questions within the group

\<b\>204 No Content\<b\> response code is returned if the reorder was successful.

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
<td>order[][id]</td>
<td>Required</td>
<td>integer</td>
<td class="param-desc"><p>The associated item’s unique identifier</p></td>
</tr>
<tr class="request-param">
<td>order[][type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The type of item is always ‘question’ for a group</p>
<p>Allowed values: <code class="enum">question</code></p></td>
</tr>
</tbody>
</table>
