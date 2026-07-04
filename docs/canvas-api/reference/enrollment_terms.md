# Enrollment Terms API

API for viewing enrollment terms. For all actions, the specified account must be a root account and the caller must have permission to manage the account (when called on non-root accounts, the errorwill be indicate the appropriate root account).

### An EnrollmentTerm object looks like:

``` example
{
  // The unique identifier for the enrollment term.
  "id": 1,
  // The SIS id of the term. Only included if the user has permission to view SIS
  // information.
  "sis_term_id": "Sp2014",
  // the unique identifier for the SIS import. This field is only included if the
  // user has permission to manage SIS information.
  "sis_import_id": 34,
  // The name of the term.
  "name": "Spring 2014",
  // The datetime of the start of the term.
  "start_at": "2014-01-06T08:00:00-05:00",
  // The datetime of the end of the term.
  "end_at": "2014-05-16T05:00:00-04:00",
  // The state of the term. Can be 'active' or 'deleted'.
  "workflow_state": "active",
  // Term date overrides for specific enrollment types
  "overrides": {"StudentEnrollment":{"start_at":"2014-01-07T08:00:00-05:00","end_at":"2014-05-14T05:00:00-04:0"}},
  // The number of courses in the term (available via include)
  "course_count": 80
}
```

### An EnrollmentTermsList object looks like:

``` example
{
  // a paginated list of all terms in the account
  "enrollment_terms": []
}
```

## Create enrollment term

### POST /api/v1/accounts/:account_id/terms

**Scope:** `url:POST|/api/v1/accounts/:account_id/terms`

Create a new enrollment term for the specified account.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| enrollment_term\[name\] |  | string | The name of the term. |
| enrollment_term\[start_at\] |  | DateTime | The day/time the term starts. Accepts times in ISO 8601 format, e.g. 2015-01-10T18:48:00Z. |
| enrollment_term\[end_at\] |  | DateTime | The day/time the term ends. Accepts times in ISO 8601 format, e.g. 2015-01-10T18:48:00Z. |
| enrollment_term\[sis_term_id\] |  | string | The unique SIS identifier for the term. |
| enrollment_term\[overrides\]\[enrollment_type\]\[start_at\] |  | DateTime | The day/time the term starts, overridden for the given enrollment type. **enrollment_type** can be one of StudentEnrollment, TeacherEnrollment, TaEnrollment, or DesignerEnrollment |
| enrollment_term\[overrides\]\[enrollment_type\]\[end_at\] |  | DateTime | The day/time the term ends, overridden for the given enrollment type. **enrollment_type** can be one of StudentEnrollment, TeacherEnrollment, TaEnrollment, or DesignerEnrollment |

Returns an [EnrollmentTerm](enrollment_terms.html#EnrollmentTerm) object

## Update enrollment term

### PUT /api/v1/accounts/:account_id/terms/:id

**Scope:** `url:PUT|/api/v1/accounts/:account_id/terms/:id`

Update an existing enrollment term for the specified account.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| enrollment_term\[name\] |  | string | The name of the term. |
| enrollment_term\[start_at\] |  | DateTime | The day/time the term starts. Accepts times in ISO 8601 format, e.g. 2015-01-10T18:48:00Z. |
| enrollment_term\[end_at\] |  | DateTime | The day/time the term ends. Accepts times in ISO 8601 format, e.g. 2015-01-10T18:48:00Z. |
| enrollment_term\[sis_term_id\] |  | string | The unique SIS identifier for the term. |
| enrollment_term\[overrides\]\[enrollment_type\]\[start_at\] |  | DateTime | The day/time the term starts, overridden for the given enrollment type. **enrollment_type** can be one of StudentEnrollment, TeacherEnrollment, TaEnrollment, or DesignerEnrollment |
| enrollment_term\[overrides\]\[enrollment_type\]\[end_at\] |  | DateTime | The day/time the term ends, overridden for the given enrollment type. **enrollment_type** can be one of StudentEnrollment, TeacherEnrollment, TaEnrollment, or DesignerEnrollment |
| override_sis_stickiness |  | boolean | Default is true. If false, any fields containing “sticky” changes will not be updated. See SIS CSV Format documentation for information on which fields can have SIS stickiness |

Returns an [EnrollmentTerm](enrollment_terms.html#EnrollmentTerm) object

## Delete enrollment term

### DELETE /api/v1/accounts/:account_id/terms/:id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/terms/:id`

Delete the specified enrollment term.

Returns an [EnrollmentTerm](enrollment_terms.html#EnrollmentTerm) object

## List enrollment terms

### GET /api/v1/accounts/:account_id/terms

**Scope:** `url:GET|/api/v1/accounts/:account_id/terms`

An object with a paginated list of all of the terms in the account.

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
<td>workflow_state[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If set, only returns terms that are in the given state. Defaults to ‘active’.</p>
<p>Allowed values: <code class="enum">active</code>, <code class="enum">deleted</code>, <code class="enum">all</code></p></td>
</tr>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Array of additional information to include.</p>
<dl>
<dt>“overrides”</dt>
<dd>
<p>term start/end dates overridden for different enrollment types</p>
</dd>
<dt>“course_count”</dt>
<dd>
<p>the number of courses in each term</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">overrides</code></p></td>
</tr>
<tr class="request-param">
<td>term_name</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If set, only returns terms that match the given search keyword. Search keyword is matched against term name.</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/accounts/1/terms?include[]=overrides
```

#### Example Response:

####

``` example
{
  "enrollment_terms": [
    {
      "id": 1,
      "name": "Fall 20X6"
      "start_at": "2026-08-31T20:00:00Z",
      "end_at": "2026-12-20T20:00:00Z",
      "created_at": "2025-01-02T03:43:11Z",
      "workflow_state": "active",
      "grading_period_group_id": 1,
      "sis_term_id": null,
      "overrides": {
        "StudentEnrollment": {
          "start_at": "2026-09-03T20:00:00Z",
          "end_at": "2026-12-19T20:00:00Z"
        },
        "TeacherEnrollment": {
          "start_at": null,
          "end_at": "2026-12-30T20:00:00Z"
        }
      }
    }
  ]
}
```

Returns an [EnrollmentTermsList](enrollment_terms.html#EnrollmentTermsList) object

## Retrieve enrollment term

### GET /api/v1/accounts/:account_id/terms/:id

**Scope:** `url:GET|/api/v1/accounts/:account_id/terms/:id`

Retrieves the details for an enrollment term in the account. Includes overrides by default.

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/accounts/1/terms/2
```

Returns an [EnrollmentTerm](enrollment_terms.html#EnrollmentTerm) object
