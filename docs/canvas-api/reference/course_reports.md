# Course Reports API

API for accessing course reports.

### A Report object looks like:

``` example
{
  // The unique identifier for the report.
  "id": 1,
  // The url to the report download.
  "file_url": "https://example.com/some/path",
  // The attachment api object of the report. Only available after the report has
  // completed.
  "attachment": null,
  // The status of the report
  "status": "complete",
  // The date and time the report was created.
  "created_at": "2013-12-01T23:59:00-06:00",
  // The date and time the report started processing.
  "started_at": "2013-12-02T00:03:21-06:00",
  // The date and time the report finished processing.
  "ended_at": "2013-12-02T00:03:21-06:00",
  // The report parameters
  "parameters": {"course_id":2,"start_at":"2012-07-13T10:55:20-06:00","end_at":"2012-07-13T10:55:20-06:00"},
  // The progress of the report
  "progress": 100
}
```

### A ReportParameters object looks like:

``` example
// The parameters returned will vary for each report.
{

}
```

## Status of a Report

### GET /api/v1/courses/:course_id/reports/:report_type/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/reports/:report_type/:id`

Returns the status of a report.

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
     https://<canvas>/api/v1/courses/<course_id>/reports/<report_type>/<report_id>
```

Returns a [Report](course_reports.html#Report) object

## Start a Report

### POST /api/v1/courses/:course_id/reports/:report_type

**Scope:** `url:POST|/api/v1/courses/:course_id/reports/:report_type`

Generates a report instance for the account. Note that “report” in the request must match one of the available report names.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| course_id |  | integer | The id of the course to report on. |
| report_type |  | string | The type of report to generate. |
| parameters |  | string | The parameters will vary for each report. Note that the example parameters provided below may not be valid for every report. |
| parameters\[section_ids\[\]\] |  | integer | The sections of the course to report on. Note: this parameter has been listed to serve as an example and may not be valid for every report. |

Returns a [Report](course_reports.html#Report) object

## Status of last Report

### GET /api/v1/courses/:course_id/reports/:report_type

**Scope:** `url:GET|/api/v1/courses/:course_id/reports/:report_type`

Returns the status of the last report initiated by the current user.

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
     https://<canvas>/api/v1/courses/<course_id>/reports/<report_type>
```

Returns a [Report](course_reports.html#Report) object
