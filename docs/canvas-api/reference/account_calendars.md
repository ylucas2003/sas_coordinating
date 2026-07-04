# Account Calendars API

API for viewing and toggling settings of account calendars.

An account calendar is available for each account in Canvas. All account calendars are hidden by default, but administrators with the `manage_account_calendar_visibility` permission may set calendars as visible. Administrators with the `manage_account_calendar_events` permission can create events in visible account calendars, and users associated with an account can add the calendar and see its events (if the calendar is visible). Events on calendars set as `auto_subscribe` calendars will appear on users' calendars even if they do not manually add it.

### An AccountCalendar object looks like:

``` example
{
  // the ID of the account associated with this calendar
  "id": 204,
  // the name of the account associated with this calendar
  "name": "Department of Chemistry",
  // the account's parent ID, or null if this is the root account
  "parent_account_id": 1,
  // the ID of the root account, or null if this is the root account
  "root_account_id": 1,
  // whether this calendar is visible to users
  "visible": true,
  // whether users see this calendar's events without needing to manually add it
  "auto_subscribe": false,
  // number of this account's direct sub-accounts
  "sub_account_count": 0,
  // Asset string of the account
  "asset_string": "account_4",
  // Object type
  "type": "account",
  // url to get full detailed events
  "calendar_event_url": "/accounts/2/calendar_events/%7B%7B%20id%20%7D%7D",
  // whether the user can create calendar events
  "can_create_calendar_events": true,
  // API path to create events for the account
  "create_calendar_event_url": "/accounts/2/calendar_events",
  // url to open the more options event editor
  "new_calendar_event_url": "/accounts/6/calendar_events/new"
}
```

## List available account calendars

### GET /api/v1/account_calendars

**Scope:** `url:GET|/api/v1/account_calendars`

Returns a paginated list of account calendars available to the current user. Includes visible account calendars where the user has an account association.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| search_term |  | string | When included, searches available account calendars for the term. Returns matching results. Term must be at least 2 characters. |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/account_calendars \
  -H 'Authorization: Bearer <token>'
```

Returns a list of [AccountCalendar](account_calendars.html#AccountCalendar) objects

## Get a single account calendar

### GET /api/v1/account_calendars/:account_id

**Scope:** `url:GET|/api/v1/account_calendars/:account_id`

Get details about a specific account calendar.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/account_calendars/204 \
  -H 'Authorization: Bearer <token>'
```

Returns an [AccountCalendar](account_calendars.html#AccountCalendar) object

## Update a calendar

### PUT /api/v1/account_calendars/:account_id

**Scope:** `url:PUT|/api/v1/account_calendars/:account_id`

Set an account calendar’s visibility and auto_subscribe values. Requires the ‘manage_account_calendar_visibility\` permission on the account.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| visible |  | boolean | Allow administrators with ‘manage_account_calendar_events\` permission to create events on this calendar, and allow users to view this calendar and its events. |
| auto_subscribe |  | boolean | When true, users will automatically see events from this account in their calendar, even if they haven’t manually added that calendar. |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/account_calendars/204 \
  -X PUT \
  -H 'Authorization: Bearer <token>' \
  -d 'visible=false' \
  -d 'auto_subscribe=false'
```

Returns an [AccountCalendar](account_calendars.html#AccountCalendar) object

## Update several calendars

### PUT /api/v1/accounts/:account_id/account_calendars

**Scope:** `url:PUT|/api/v1/accounts/:account_id/account_calendars`

Set visibility and/or auto_subscribe on many calendars simultaneously. Requires the ‘manage_account_calendar_visibility\` permission on the account.

Accepts a JSON array of objects containing 2-3 keys each: ‘id\` (the account’s id, required), ‘visible\` (a boolean indicating whether the account calendar is visible), and \`auto_subscribe\` (a boolean indicating whether users should see these events in their calendar without manually subscribing).

Returns the count of updated accounts.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/1/account_calendars \
  -X PUT \
  -H 'Authorization: Bearer <token>' \
  --data '[{"id": 1, "visible": true, "auto_subscribe": false}, {"id": 13, "visible": false, "auto_subscribe": true}]'
```

## List all account calendars

### GET /api/v1/accounts/:account_id/account_calendars

**Scope:** `url:GET|/api/v1/accounts/:account_id/account_calendars`

Returns a paginated list of account calendars for the provided account and its first level of sub-accounts. Includes hidden calendars in the response. Requires the ‘manage_account_calendar_visibility\` permission.

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
<td>search_term</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>When included, searches all descendent accounts of provided account for the term. Returns matching results. Term must be at least 2 characters. Can be combined with a filter value.</p></td>
</tr>
<tr class="request-param">
<td>filter</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>When included, only returns calendars that are either visible or hidden. Can be combined with a search term.</p>
<p>Allowed values: <code class="enum">visible</code>, <code class="enum">hidden</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/1/account_calendars \
  -H 'Authorization: Bearer <token>'
```

Returns a list of [AccountCalendar](account_calendars.html#AccountCalendar) objects

## Count of all visible account calendars

### GET /api/v1/accounts/:account_id/visible_calendars_count

**Scope:** `url:GET|/api/v1/accounts/:account_id/visible_calendars_count`

Returns the number of visible account calendars.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/accounts/1/visible_calendars_count \
  -H 'Authorization: Bearer <token>'
```
