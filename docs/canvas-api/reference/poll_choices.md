# PollChoices API

Manage choices for polls

### A PollChoice object looks like:

``` example
{
  // The unique identifier for the poll choice.
  "id": 1023,
  // The id of the poll this poll choice belongs to.
  "poll_id": 1779,
  // Specifies whether or not this poll choice is a 'correct' choice.
  "is_correct": true,
  // The text of the poll choice.
  "text": "Choice A",
  // The order of the poll choice in relation to it's sibling poll choices.
  "position": 1
}
```

## List poll choices in a poll

### GET /api/v1/polls/:poll_id/poll_choices

**Scope:** `url:GET|/api/v1/polls/:poll_id/poll_choices`

Returns the paginated list of PollChoices in this poll.

#### Example Response:

####

``` example
{
  "poll_choices": [PollChoice]
}
```

## Get a single poll choice

### GET /api/v1/polls/:poll_id/poll_choices/:id

**Scope:** `url:GET|/api/v1/polls/:poll_id/poll_choices/:id`

Returns the poll choice with the given id

#### Example Response:

####

``` example
{
  "poll_choices": [PollChoice]
}
```

## Create a single poll choice

### POST /api/v1/polls/:poll_id/poll_choices

**Scope:** `url:POST|/api/v1/polls/:poll_id/poll_choices`

Create a new poll choice for this poll

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| poll_choices\[\]\[text\] | Required | string | The descriptive text of the poll choice. |
| poll_choices\[\]\[is_correct\] |  | boolean | Whether this poll choice is considered correct or not. Defaults to false. |
| poll_choices\[\]\[position\] |  | integer | The order this poll choice should be returned in the context it’s sibling poll choices. |

#### Example Response:

####

``` example
{
  "poll_choices": [PollChoice]
}
```

## Update a single poll choice

### PUT /api/v1/polls/:poll_id/poll_choices/:id

**Scope:** `url:PUT|/api/v1/polls/:poll_id/poll_choices/:id`

Update an existing poll choice for this poll

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| poll_choices\[\]\[text\] | Required | string | The descriptive text of the poll choice. |
| poll_choices\[\]\[is_correct\] |  | boolean | Whether this poll choice is considered correct or not. Defaults to false. |
| poll_choices\[\]\[position\] |  | integer | The order this poll choice should be returned in the context it’s sibling poll choices. |

#### Example Response:

####

``` example
{
  "poll_choices": [PollChoice]
}
```

## Delete a poll choice

### DELETE /api/v1/polls/:poll_id/poll_choices/:id

**Scope:** `url:DELETE|/api/v1/polls/:poll_id/poll_choices/:id`

**204 No Content** response code is returned if the deletion was successful.
