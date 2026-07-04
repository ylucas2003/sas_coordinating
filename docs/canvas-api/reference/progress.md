# Progress API

API for querying the progress of asynchronous API operations.

API for querying the progress of asynchronous API operations.

### A Progress object looks like:

``` example
{
  // the ID of the Progress object
  "id": 1,
  // the context owning the job.
  "context_id": 1,
  "context_type": "Account",
  // the id of the user who started the job
  "user_id": 123,
  // the type of operation
  "tag": "course_batch_update",
  // percent completed
  "completion": 100,
  // the state of the job one of 'queued', 'running', 'completed', 'failed'
  "workflow_state": "completed",
  // the time the job was created
  "created_at": "2013-01-15T15:00:00Z",
  // the time the job was last updated
  "updated_at": "2013-01-15T15:04:00Z",
  // optional details about the job
  "message": "17 courses processed",
  // optional results of the job. omitted when job is still pending
  "results": {"id":"123"},
  // url where a progress update can be retrieved
  "url": "https://canvas.example.edu/api/v1/progress/1"
}
```

### A Progress object looks like:

``` example
{
  // the ID of the Progress object
  "id": 1,
  // the context owning the job.
  "context_id": 1,
  "context_type": "Account",
  // the id of the user who started the job
  "user_id": 123,
  // the type of operation
  "tag": "course_batch_update",
  // percent completed
  "completion": 100,
  // the state of the job one of 'queued', 'running', 'completed', 'failed'
  "workflow_state": "completed",
  // the time the job was created
  "created_at": "2013-01-15T15:00:00Z",
  // the time the job was last updated
  "updated_at": "2013-01-15T15:04:00Z",
  // optional details about the job
  "message": "17 courses processed",
  // optional results of the job. omitted when job is still pending
  "results": {"id":"123"},
  // url where a progress update can be retrieved with an LTI access token
  "url": "https://canvas.example.edu/api/lti/courses/1/progress/1"
}
```

## Query progress

### GET /api/v1/progress/:id

**Scope:** `url:GET|/api/v1/progress/:id`

Return completion and status information about an asynchronous job

Returns a [Progress](progress.html#Progress) object

## Cancel progress

### POST /api/v1/progress/:id/cancel

**Scope:** `url:POST|/api/v1/progress/:id/cancel`

Cancel an asynchronous job associated with a Progress object If you include “message” in the POSTed data, it will be set on the Progress and returned. This is handy to distinguish between cancel and fail for a workflow_state of “failed”.

Returns a [Progress](progress.html#Progress) object

## Query progress

### GET /api/lti/courses/:course_id/progress/:id

**Scope:** `url:GET|/api/lti/courses/:course_id/progress/:id`

Return completion and status information about an asynchronous job

Returns a [Progress](progress.html#Progress) object
