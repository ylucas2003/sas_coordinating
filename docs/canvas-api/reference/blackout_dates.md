# Blackout Dates API

API for accessing blackout date information.

### A BlackoutDate object looks like:

``` example
// Blackout dates are used to prevent scheduling assignments on a given date in
// course pacing.
{
  // the ID of the blackout date
  "id": 1,
  // the context owning the blackout date
  "context_id": 1,
  "context_type": "Course",
  // the start date of the blackout date
  "start_date": "2022-01-01",
  // the end date of the blackout date
  "end_date": "2022-01-02",
  // title of the blackout date
  "event_title": "some title"
}
```

## List blackout dates

### GET /api/v1/courses/:course_id/blackout_dates

**Scope:** `url:GET|/api/v1/courses/:course_id/blackout_dates`

### GET /api/v1/accounts/:account_id/blackout_dates

**Scope:** `url:GET|/api/v1/accounts/:account_id/blackout_dates`

Returns the list of blackout dates for the current context.

Returns a list of [BlackoutDate](blackout_dates.html#BlackoutDate) objects

## Get a single blackout date

### GET /api/v1/courses/:course_id/blackout_dates/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/blackout_dates/:id`

### GET /api/v1/accounts/:account_id/blackout_dates/:id

**Scope:** `url:GET|/api/v1/accounts/:account_id/blackout_dates/:id`

Returns the blackout date with the given id.

Returns a [BlackoutDate](blackout_dates.html#BlackoutDate) object

## New Blackout Date

### GET /api/v1/courses/:course_id/blackout_dates/new

**Scope:** `url:GET|/api/v1/courses/:course_id/blackout_dates/new`

### GET /api/v1/accounts/:account_id/blackout_dates/new

**Scope:** `url:GET|/api/v1/accounts/:account_id/blackout_dates/new`

Initialize an unsaved Blackout Date for the given context.

Returns a [BlackoutDate](blackout_dates.html#BlackoutDate) object

## Create Blackout Date

### POST /api/v1/courses/:course_id/blackout_dates

**Scope:** `url:POST|/api/v1/courses/:course_id/blackout_dates`

### POST /api/v1/accounts/:account_id/blackout_dates

**Scope:** `url:POST|/api/v1/accounts/:account_id/blackout_dates`

Create a blackout date for the given context.

#### Request Parameters:

| Parameter   |     | Type   | Description                          |
|-------------|-----|--------|--------------------------------------|
| start_date  |     | Date   | The start date of the blackout date. |
| end_date    |     | Date   | The end date of the blackout date.   |
| event_title |     | string | The title of the blackout date.      |

Returns a [BlackoutDate](blackout_dates.html#BlackoutDate) object

## Update Blackout Date

### PUT /api/v1/courses/:course_id/blackout_dates/:id

**Scope:** `url:PUT|/api/v1/courses/:course_id/blackout_dates/:id`

### PUT /api/v1/accounts/:account_id/blackout_dates/:id

**Scope:** `url:PUT|/api/v1/accounts/:account_id/blackout_dates/:id`

Update a blackout date for the given context.

#### Request Parameters:

| Parameter   |     | Type   | Description                          |
|-------------|-----|--------|--------------------------------------|
| start_date  |     | Date   | The start date of the blackout date. |
| end_date    |     | Date   | The end date of the blackout date.   |
| event_title |     | string | The title of the blackout date.      |

Returns a [BlackoutDate](blackout_dates.html#BlackoutDate) object

## Delete Blackout Date

### DELETE /api/v1/courses/:course_id/blackout_dates/:id

**Scope:** `url:DELETE|/api/v1/courses/:course_id/blackout_dates/:id`

### DELETE /api/v1/accounts/:account_id/blackout_dates/:id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/blackout_dates/:id`

Delete a blackout date for the given context.

Returns a [BlackoutDate](blackout_dates.html#BlackoutDate) object

## Update a list of Blackout Dates

### PUT /api/v1/courses/:course_id/blackout_dates

**Scope:** `url:PUT|/api/v1/courses/:course_id/blackout_dates`

Create, update, and delete blackout dates to sync the db with the incoming data.

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
<td>blackout_dates:</td>
<td></td>
<td>string</td>
<td class="param-desc"><dl>
<dt>blackout_date, …</dt>
<dd>
<p>An object containing the array of BlackoutDates we want to exist after this operation. For array entries, if it has an id it will be updated, if not created, and if an existing BlackoutDate id is missing from the array, it will be deleted.</p>
</dd>
</dl></td>
</tr>
</tbody>
</table>
