# Authentications Log API

Query audit log of authentication events (logins and logouts).

For each endpoint, a compound document is returned. The primary collection of event objects is paginated, ordered by date descending. Secondary collections of logins, accounts, page views, and users related to the returned events are also included. Refer to the Logins, Accounts, Page Views, and Users APIs for descriptions of the objects in those collections.

Authentication logs are stored for one year.

### An AuthenticationEvent object looks like:

``` example
{
  // timestamp of the event
  "created_at": "2012-07-19T15:00:00-06:00",
  // authentication event type ('login' or 'logout')
  "event_type": "login",
  // ID of the pseudonym (login) associated with the event
  "pseudonym_id": 9478,
  // ID of the account associated with the event. will match the account_id in the
  // associated pseudonym.
  "account_id": 2319,
  // ID of the user associated with the event will match the user_id in the
  // associated pseudonym.
  "user_id": 362
}
```

## Query by login.

### GET /api/v1/audit/authentication/logins/:login_id

**Scope:** `url:GET|/api/v1/audit/authentication/logins/:login_id`

List authentication events for a given login.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| start_time |  | DateTime | The beginning of the time range from which you want events. Events are stored for one year. |
| end_time |  | DateTime | The end of the time range from which you want events. |

## Query by account.

### GET /api/v1/audit/authentication/accounts/:account_id

**Scope:** `url:GET|/api/v1/audit/authentication/accounts/:account_id`

List authentication events for a given account.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| start_time |  | DateTime | The beginning of the time range from which you want events. Events are stored for one year. |
| end_time |  | DateTime | The end of the time range from which you want events. |

## Query by user.

### GET /api/v1/audit/authentication/users/:user_id

**Scope:** `url:GET|/api/v1/audit/authentication/users/:user_id`

List authentication events for a given user.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| start_time |  | DateTime | The beginning of the time range from which you want events. Events are stored for one year. |
| end_time |  | DateTime | The end of the time range from which you want events. |
