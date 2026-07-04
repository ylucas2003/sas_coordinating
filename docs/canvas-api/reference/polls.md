# Polls API

Manage polls

### A Poll object looks like:

``` example
{
  // The unique identifier for the poll.
  "id": 1023,
  // The question/title of the poll.
  "question": "What do you consider most important to your learning in this course?",
  // A short description of the poll.
  "description": "This poll is to determine what priorities the students in the course have.",
  // The time at which the poll was created.
  "created_at": "2014-01-07T15:16:18Z",
  // The unique identifier for the user that created the poll.
  "user_id": 105,
  // An aggregate of the results of all associated poll sessions, with the poll
  // choice id as the key, and the aggregated submission count as the value.
  "total_results": {"543":20,"544":5,"545":17}
}
```

## List polls

### GET /api/v1/polls

**Scope:** `url:GET|/api/v1/polls`

Returns the paginated list of polls for the current user.

#### Example Response:

####

``` example
{
  "polls": [Poll]
}
```

## Get a single poll

### GET /api/v1/polls/:id

**Scope:** `url:GET|/api/v1/polls/:id`

Returns the poll with the given id

#### Example Response:

####

``` example
{
  "polls": [Poll]
}
```

## Create a single poll

### POST /api/v1/polls

**Scope:** `url:POST|/api/v1/polls`

Create a new poll for the current user

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| polls\[\]\[question\] | Required | string | The title of the poll. |
| polls\[\]\[description\] |  | string | A brief description or instructions for the poll. |

#### Example Response:

####

``` example
{
  "polls": [Poll]
}
```

## Update a single poll

### PUT /api/v1/polls/:id

**Scope:** `url:PUT|/api/v1/polls/:id`

Update an existing poll belonging to the current user

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| polls\[\]\[question\] | Required | string | The title of the poll. |
| polls\[\]\[description\] |  | string | A brief description or instructions for the poll. |

#### Example Response:

####

``` example
{
  "polls": [Poll]
}
```

## Delete a poll

### DELETE /api/v1/polls/:id

**Scope:** `url:DELETE|/api/v1/polls/:id`

**204 No Content** response code is returned if the deletion was successful.
