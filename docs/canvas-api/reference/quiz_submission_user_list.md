# Quiz Submission User List API

List of users who have or haven't submitted for a quiz.

### A QuizSubmissionUserList object looks like:

``` example
{
  "meta": {
    "$ref": "QuizSubmissionUserListMeta",
    "description": "contains meta information (such as pagination) for the list of users"
  },
  "users": {
    "$ref": "User",
    "description": "list of users that match the query"
  }
}
```

### A QuizSubmissionUserListMeta object looks like:

``` example
{
  "pagination": {
    "$ref": "JSONAPIPagination",
    "description": "contains pagination information for the list of users"
  }
}
```

### A JSONAPIPagination object looks like:

``` example
{
  "per_page": {
    "type": "integer",
    "description": "number of results per page",
    "example": 10
  },
  "page": {
    "type": "integer",
    "description": "the current page passed as the ?page= parameter",
    "example": 1
  },
  "template": {
    "type": "string",
    "description": "URL template for building out other paged URLs for this endpoint",
    "example": "https://example.instructure.com/api/v1/courses/1/quizzes/1/submission_users?page={page}"
  },
  "page_count": {
    "type": "integer",
    "description": "number of pages for this collection",
    "example": 10
  },
  "count": {
    "type": "integer",
    "description": "total number of items in this collection",
    "example": 100
  }
}
```

## Send a message to unsubmitted or submitted users for the quiz

### POST /api/v1/courses/:course_id/quizzes/:id/submission_users/message

**Scope:** `url:POST|/api/v1/courses/:course_id/quizzes/:id/submission_users/message`

{

``` code
"body": {
  "type": "string",
  "description": "message body of the conversation to be created",
  "example": "Please take the quiz."
},
"recipients": {
  "type": "string",
  "description": "Who to send the message to. May be either 'submitted' or 'unsubmitted'",
  "example": "submitted"
},
"subject": {
  "type": "string",
  "description": "Subject of the new Conversation created",
  "example": "ATTN: Quiz 101 Students"
}
```

}

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
<td>conversations</td>
<td></td>
<td>QuizUserConversation</td>
<td class="param-desc"><ul>
<li><p>Body and recipients to send the message to.</p></li>
</ul></td>
</tr>
</tbody>
</table>
