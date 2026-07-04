# Quiz Submission Questions API

API for answering and flagging questions in a quiz-taking session.

### A QuizSubmissionQuestion object looks like:

``` example
{
  // The ID of the QuizQuestion this answer is for.
  "id": 1,
  // Whether this question is flagged.
  "flagged": true,
  // The provided answer (if any) for this question. The format of this parameter
  // depends on the type of the question, see the Appendix for more information.
  "answer": null,
  // The possible answers for this question when those possible answers are
  // necessary.  The presence of this parameter is dependent on permissions.
  "answers": null
}
```

## Get all quiz submission questions.

### GET /api/v1/quiz_submissions/:quiz_submission_id/questions

**Scope:** `url:GET|/api/v1/quiz_submissions/:quiz_submission_id/questions`

Get a list of all the question records for this quiz submission.

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
<td class="param-desc"><p>Associations to include with the quiz submission question.</p>
<p>Allowed values: <code class="enum">quiz_question</code></p></td>
</tr>
</tbody>
</table>

#### Example Response:

####

``` example
{
  "quiz_submission_questions": [QuizSubmissionQuestion]
}
```

## Answering questions

### POST /api/v1/quiz_submissions/:quiz_submission_id/questions

**Scope:** `url:POST|/api/v1/quiz_submissions/:quiz_submission_id/questions`

Provide or update an answer to one or more QuizQuestions.

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
<td>attempt</td>
<td>Required</td>
<td>integer</td>
<td class="param-desc"><p>The attempt number of the quiz submission being taken. Note that this must be the latest attempt index, as questions for earlier attempts can not be modified.</p></td>
</tr>
<tr class="request-param">
<td>validation_token</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The unique validation token you received when the Quiz Submission was created.</p></td>
</tr>
<tr class="request-param">
<td>access_code</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Access code for the Quiz, if any.</p></td>
</tr>
<tr class="request-param">
<td>quiz_questions[]</td>
<td></td>
<td>QuizSubmissionQuestion</td>
<td class="param-desc"><p>Set of question IDs and the answer value.</p>
<p>See Appendix: Question Answer Formats for the accepted answer formats for each question type.</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
{
  "attempt": 1,
  "validation_token": "YOUR_VALIDATION_TOKEN",
  "access_code": null,
  "quiz_questions": [{
    "id": "1",
    "answer": "Hello World!"
  }, {
    "id": "2",
    "answer": 42.0
  }]
}
```

Returns a list of [QuizSubmissionQuestion](quiz_submission_questions.html#QuizSubmissionQuestion) objects

## Get a formatted student numerical answer.

### GET /api/v1/quiz_submissions/:quiz_submission_id/questions/:id/formatted_answer

**Scope:** `url:GET|/api/v1/quiz_submissions/:quiz_submission_id/questions/:id/formatted_answer`

Matches the intended behavior of the UI when a numerical answer is entered and returns the resulting formatted number

#### Request Parameters:

| Parameter |          | Type    | Description    |
|-----------|----------|---------|----------------|
| answer    | Required | Numeric | no description |

#### Example Response:

####

``` example
{
  "formatted_answer": 12.1234
}
```

## Flagging a question.

### PUT /api/v1/quiz_submissions/:quiz_submission_id/questions/:id/flag

**Scope:** `url:PUT|/api/v1/quiz_submissions/:quiz_submission_id/questions/:id/flag`

Set a flag on a quiz question to indicate that you want to return to it later.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| attempt | Required | integer | The attempt number of the quiz submission being taken. Note that this must be the latest attempt index, as questions for earlier attempts can not be modified. |
| validation_token | Required | string | The unique validation token you received when the Quiz Submission was created. |
| access_code |  | string | Access code for the Quiz, if any. |

#### Example Request:

####

``` example
{
  "attempt": 1,
  "validation_token": "YOUR_VALIDATION_TOKEN",
  "access_code": null
}
```

## Unflagging a question.

### PUT /api/v1/quiz_submissions/:quiz_submission_id/questions/:id/unflag

**Scope:** `url:PUT|/api/v1/quiz_submissions/:quiz_submission_id/questions/:id/unflag`

Remove the flag that you previously set on a quiz question after you’ve returned to it.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| attempt | Required | integer | The attempt number of the quiz submission being taken. Note that this must be the latest attempt index, as questions for earlier attempts can not be modified. |
| validation_token | Required | string | The unique validation token you received when the Quiz Submission was created. |
| access_code |  | string | Access code for the Quiz, if any. |

#### Example Request:

####

``` example
{
  "attempt": 1,
  "validation_token": "YOUR_VALIDATION_TOKEN",
  "access_code": null
}
```

## Appendixes

### Appendix: Question Answer Formats

<style>
  .appendix_entry th { text-align: left; }
  .appendix_entry th,
  .appendix_entry td {
    padding: 10px;
    border: 1px solid #ccc;
  }

  .appendix_entry div.syntaxhighlighter {
    border: none;
    padding: 0;
  }

  .appendix_entry div.syntaxhighlighter table {
    width: 100%;
  }

  .appendix_entry h4 {
    color: green;
  }
</style>

#### Essay Questions

- Question parametric type: `essay_question`
- Parameter type: **`Text`**
- Parameter synopsis: `{ "answer": "Answer text." }`

**Example request**

``` code
{
  "answer": "<h2>My essay</h2>\n\n<p>This is a long article.</p>"
}
```

**Possible errors**

| HTTP RC | Error Message | Cause |
|----|----|----|
| 400 Bad Request | `Text is too long.` | The answer text is larger than the allowed limit of 16 kilobytes. |

#### Fill In Multiple Blanks Questions

- Question parametric type: `fill_in_multiple_blanks_question`
- Parameter type: **`Hash{String => String}`**
- Parameter synopsis: `{ "answer": { "variable": "Answer string." } }`

**Example request**

Given that the question accepts answers to two variables, `color1` and `color2`:

``` code
{
  "answer": {
    "color1": "red",
    "color2": "green"
  }
}
```

**Possible errors**

| HTTP RC | Error Message | Cause |
|----|----|----|
| 400 Bad Request | `Unknown variable 'var'.` | The answer map contains a variable that is not accepted by the question. |
| 400 Bad Request | `Text is too long.` | The answer text is larger than the allowed limit of 16 kilobytes. |

#### Fill In The Blank Questions

- Question parametric type: `short_answer_question`
- Parameter type: **`String`**
- Parameter synopsis: `{ "answer": "Some sentence." }`

**Example request**

``` code
{
  "answer": "Hello World!"
}
```

**Possible errors**

Similar to the errors produced by [Essay Questions](#essay-questions).

#### Formula Questions

- Question parametric type: `calculated_question`
- Parameter type: **`Decimal`**
- Parameter synopsis: `{ "answer": decimal }` where `decimal` is either a rational number, or a literal version of it (String)

**Example request**

With an exponent:

``` code
{
  "answer": 2.3e-6
}
```

With a string for a number:

``` code
{
  "answer": "13.4"
}
```

**Possible errors**

| HTTP RC | Error Message | Cause |
|----|----|----|
| 400 Bad Request | `Parameter must be a valid decimal.` | The specified value could not be processed as a decimal. |

#### Matching Questions

- Question parametric type: `matching_question`
- Parameter type: **`Array<Hash>`**
- Parameter synopsis: `{ "answer": [{ "answer_id": id, "match_id": id }] }` where the IDs must identify answers and matches accepted by the question.

**Example request**

Given that the question accepts 3 answers with IDs `[ 3, 6, 9 ]` and 6 matches with IDs: `[ 10, 11, 12, 13, 14, 15 ]`:

``` code
{
  "answer": [{
    "answer_id": 6,
    "match_id": 10
  }, {
    "answer_id": 3,
    "match_id": 14
  }]
}
```

The above request:

- pairs `answer#6` with `match#10`
- pairs `answer#3` with `match#14`
- leaves `answer#9` *un-matched*

**Possible errors**

| HTTP RC | Error Message | Cause |
|----|----|----|
| 400 Bad Request | `Answer must be of type Array.` | The match-pairings set you supplied is not an array. |
| 400 Bad Request | `Answer entry must be of type Hash, got '...'.` | One of the entries of the match-pairings set is not a valid hash. |
| 400 Bad Request | `Missing parameter 'answer_id'.` | One of the entries of the match-pairings does not specify an `answer_id`. |
| 400 Bad Request | `Missing parameter 'match_id'.` | One of the entries of the match-pairings does not specify an `match_id`. |
| 400 Bad Request | `Parameter must be of type Integer.` | One of the specified `answer_id` or `match_id` is not an integer. |
| 400 Bad Request | `Unknown answer '123'.` | An `answer_id` you supplied does not identify a valid answer for that question. |
| 400 Bad Request | `Unknown match '123'.` | A `match_id` you supplied does not identify a valid match for that question. |

#### Multiple Choice Questions

- Question parametric type: `multiple_choice_question`
- Parameter type: **`Integer`**
- Parameter synopsis: `{ "answer": answer_id }` where `answer_id` is an ID of one of the question's answers.

**Example request**

Given an answer with an ID of 5:

``` code
{
  "answer": 5
}
```

**Possible errors**

| HTTP RC | Error Message | Cause |
|----|----|----|
| 400 Bad Request | `Parameter must be of type Integer.` | The specified \`answer_id\` is not an integer. |
| 400 Bad Request | `Unknown answer '123'` | The specified \`answer_id\` is not a valid answer. |

#### Multiple Dropdowns Questions

- Question parametric type: `multiple_dropdowns_question`
- Parameter type: **`Hash{String => Integer}`**
- Parameter synopsis: `{ "answer": { "variable": answer_id } }` where the keys are variables accepted by the question, and their values are IDs of answers provided by the question.

**Example request**

Given that the question accepts 3 answers to a variable named `color` with the ids `[ 3, 6, 9 ]`:

``` code
{
  "answer": {
    "color": 6
  }
}
```

**Possible errors**

| HTTP RC | Error Message | Cause |
|----|----|----|
| 400 Bad Request | `Unknown variable 'var'.` | The answer map you supplied contains a variable that is not accepted by the question. |
| 400 Bad Request | `Unknown answer '123'.` | An `answer_id` you supplied does not identify a valid answer for that question. |

#### Multiple Answers Questions

- Question parametric type: `multiple_answers_question`
- Parameter type: **`Array<Integer>`**
- Parameter synopsis: `{ "answer": [ answer_id ] }` where the array items are IDs of answers accepted by the question.

**Example request**

Given that the question accepts 3 answers with the ids `[ 3, 6, 9 ]` and we want to select the answers `3` and `6`:

``` code
{
  "answer": [ 3, 6 ]
}
```

**Possible errors**

| HTTP RC | Error Message | Cause |
|----|----|----|
| 400 Bad Request | `Selection must be of type Array.` | The selection set you supplied is not an array. |
| 400 Bad Request | `Parameter must be of type Integer.` | One of the answer IDs you supplied is not a valid ID. |
| 400 Bad Request | `Unknown answer '123'.` | An answer ID you supplied in the selection set does not identify a valid answer for that question. |

#### Numerical Questions

- Question parametric type: `numerical_question`

This is similar to [Formula Questions](#formula-questions).

#### True/False Questions

- Question parametric type: `true_false_question`

The rest is similar to [Multiple Choice questions](#multiple-choice-questions).
