# Temporary Enrollment Pairings API

### A TemporaryEnrollmentPairing object looks like:

``` example
// A pairing unique to that enrollment period given to a recipient of that
// temporary enrollment.
{
  // the ID of the temporary enrollment pairing
  "id": 1,
  // The current status of the temporary enrollment pairing
  "workflow_state": "active"
}
```

## List temporary enrollment pairings

### GET /api/v1/accounts/:account_id/temporary_enrollment_pairings

**Scope:** `url:GET|/api/v1/accounts/:account_id/temporary_enrollment_pairings`

Returns the list of temporary enrollment pairings for a root account.

Returns a list of [TemporaryEnrollmentPairing](temporary_enrollment_pairings.html#TemporaryEnrollmentPairing) objects

## Get a single temporary enrollment pairing

### GET /api/v1/accounts/:account_id/temporary_enrollment_pairings/:id

**Scope:** `url:GET|/api/v1/accounts/:account_id/temporary_enrollment_pairings/:id`

Returns the temporary enrollment pairing with the given id.

Returns a [TemporaryEnrollmentPairing](temporary_enrollment_pairings.html#TemporaryEnrollmentPairing) object

## New TemporaryEnrollmentPairing

### GET /api/v1/accounts/:account_id/temporary_enrollment_pairings/new

**Scope:** `url:GET|/api/v1/accounts/:account_id/temporary_enrollment_pairings/new`

Initialize an unsaved Temporary Enrollment Pairing.

Returns a [TemporaryEnrollmentPairing](temporary_enrollment_pairings.html#TemporaryEnrollmentPairing) object

## Create Temporary Enrollment Pairing

### POST /api/v1/accounts/:account_id/temporary_enrollment_pairings

**Scope:** `url:POST|/api/v1/accounts/:account_id/temporary_enrollment_pairings`

Create a Temporary Enrollment Pairing.

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
<td>workflow_state</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The workflow state of the temporary enrollment pairing.</p></td>
</tr>
<tr class="request-param">
<td>ending_enrollment_state</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The ending enrollment state to be given to each associated enrollment when the enrollment period has been reached. Defaults to “deleted” if no value is given. Accepted values are “deleted”, “completed”, and “inactive”.</p>
<p>Allowed values: <code class="enum">deleted</code>, <code class="enum">completed</code>, <code class="enum">inactive</code></p></td>
</tr>
</tbody>
</table>

Returns a [TemporaryEnrollmentPairing](temporary_enrollment_pairings.html#TemporaryEnrollmentPairing) object

## Delete Temporary Enrollment Pairing

### DELETE /api/v1/accounts/:account_id/temporary_enrollment_pairings/:id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/temporary_enrollment_pairings/:id`

Delete a temporary enrollment pairing

Returns a [TemporaryEnrollmentPairing](temporary_enrollment_pairings.html#TemporaryEnrollmentPairing) object
