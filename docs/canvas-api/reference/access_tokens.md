# Access Tokens API

## Show an access token

### GET /api/v1/users/:user_id/tokens/:id

**Scope:** `url:GET|/api/v1/users/:user_id/tokens/:id`

The ID can be the actual database ID of the token, or the ‘token_hint’ value.

## Create an access token

### POST /api/v1/users/:user_id/tokens

**Scope:** `url:POST|/api/v1/users/:user_id/tokens`

Create a new access token for the specified user. If the user is not the current user, the token will be created as “pending”, and must be activated by the user before it can be used.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| token\[purpose\] | Required | string | The purpose of the token. |
| token\[expires_at\] |  | DateTime | The time at which the token will expire. |
| token\[scopes\]\[\] |  | Array | The scopes to associate with the token. Ignored if the default developer key does not have the “enable scopes” option enabled. In such cases, the token will inherit the user’s permissions instead. |

## Update an access token

### PUT /api/v1/users/:user_id/tokens/:id

**Scope:** `url:PUT|/api/v1/users/:user_id/tokens/:id`

Update an existing access token.

The ID can be the actual database ID of the token, or the ‘token_hint’ value.

Regenerating an expired token requires a new expiration date.

#### Request Parameters:

| Parameter           |     | Type     | Description                              |
|---------------------|-----|----------|------------------------------------------|
| token\[purpose\]    |     | string   | The purpose of the token.                |
| token\[expires_at\] |     | DateTime | The time at which the token will expire. |
| token\[scopes\]\[\] |     | Array    | The scopes to associate with the token.  |
| token\[regenerate\] |     | boolean  | Regenerate the actual token.             |

## Delete an access token

### DELETE /api/v1/users/:user_id/tokens/:id

**Scope:** `url:DELETE|/api/v1/users/:user_id/tokens/:id`

The ID can be the actual database ID of the token, or the ‘token_hint’ value.
