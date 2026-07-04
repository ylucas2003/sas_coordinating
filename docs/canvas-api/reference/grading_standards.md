# Grading Standards API

### A GradingSchemeEntry object looks like:

``` example
{
  // The name for an entry value within a GradingStandard that describes the range
  // of the value
  "name": "A",
  // The value for the name of the entry within a GradingStandard. The entry
  // represents the lower bound of the range for the entry. This range includes
  // the value up to the next entry in the GradingStandard, or the maximum value
  // for the scheme if there is no upper bound. The lowest value will have a lower
  // bound range of 0.
  "value": 0.9,
  // The value that will be used to compare against a grade. For percentage based
  // grading schemes, this is a number from 0 - 100 representing a percent. For
  // point based grading schemes, this is the lower bound of points to achieve the
  // grade.
  "calculated_value": 90
}
```

### A GradingStandard object looks like:

``` example
{
  // the title of the grading standard
  "title": "Account Standard",
  // the id of the grading standard
  "id": 1,
  // the context this standard is associated with, either 'Account' or 'Course'
  "context_type": "Account",
  // the id for the context either the Account or Course id
  "context_id": 1,
  // whether this is a points-based standard
  "points_based": false,
  // the factor by which to scale a score. 1 for percentage based schemss and the
  // max value of points for points based schemes. This number cannot be changed
  // for percentage based schemes.
  "scaling_factor": 1.0,
  // A list of GradingSchemeEntry that make up the Grading Standard as an array of
  // values with the scheme name and value
  "grading_scheme": [{"name":"A","value":0.9}, {"name":"B","value":0.8}, {"name":"C","value":0.7}, {"name":"D","value":0.6}]
}
```

## Create a new grading standard

### POST /api/v1/accounts/:account_id/grading_standards

**Scope:** `url:POST|/api/v1/accounts/:account_id/grading_standards`

### POST /api/v1/courses/:course_id/grading_standards

**Scope:** `url:POST|/api/v1/courses/:course_id/grading_standards`

Create a new grading standard

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| title | Required | string | The title for the Grading Standard. |
| points_based |  | boolean | Whether or not a grading scheme is points based. Defaults to false. |
| scaling_factor |  | integer | The factor by which to scale a percentage into a points based scheme grade. This is the maximum number of points possible in the grading scheme. Defaults to 1. Not required for percentage based grading schemes. |
| grading_scheme_entry\[\]\[name\] | Required | string | The name for an entry value within a GradingStandard that describes the range of the value e.g. A- |
| grading_scheme_entry\[\]\[value\] | Required | integer | The value for the name of the entry within a GradingStandard. The entry represents the lower bound of the range for the entry. This range includes the value up to the next entry in the GradingStandard, or 100 if there is no upper bound. The lowest value will have a lower bound range of 0. e.g. 93 |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/<course_id>/grading_standards \
  -X POST \
  -H 'Authorization: Bearer <token>' \
  -d 'title=New standard name' \
  -d 'points_based=false' \
  -d 'scaling_factor=1.0' \
  -d 'grading_scheme_entry[][name]=A' \
  -d 'grading_scheme_entry[][value]=94' \
  -d 'grading_scheme_entry[][name]=A-' \
  -d 'grading_scheme_entry[][value]=90' \
  -d 'grading_scheme_entry[][name]=B+' \
  -d 'grading_scheme_entry[][value]=87' \
  -d 'grading_scheme_entry[][name]=B' \
  -d 'grading_scheme_entry[][value]=84' \
  -d 'grading_scheme_entry[][name]=B-' \
  -d 'grading_scheme_entry[][value]=80' \
  -d 'grading_scheme_entry[][name]=C+' \
  -d 'grading_scheme_entry[][value]=77' \
  -d 'grading_scheme_entry[][name]=C' \
  -d 'grading_scheme_entry[][value]=74' \
  -d 'grading_scheme_entry[][name]=C-' \
  -d 'grading_scheme_entry[][value]=70' \
  -d 'grading_scheme_entry[][name]=D+' \
  -d 'grading_scheme_entry[][value]=67' \
  -d 'grading_scheme_entry[][name]=D' \
  -d 'grading_scheme_entry[][value]=64' \
  -d 'grading_scheme_entry[][name]=D-' \
  -d 'grading_scheme_entry[][value]=61' \
  -d 'grading_scheme_entry[][name]=F' \
  -d 'grading_scheme_entry[][value]=0'
```

#### Example Response:

####

``` example
{
  "title": "New standard name",
  "id": 1,
  "context_id": 1,
  "context_type": "Course",
  "grading_scheme": [
    {"name": "A", "value": 0.9},
    {"name": "B", "value": 0.8}
  ]
}
```

Returns a [GradingStandard](grading_standards.html#GradingStandard) object

## List the grading standards available in a context.

### GET /api/v1/courses/:course_id/grading_standards

**Scope:** `url:GET|/api/v1/courses/:course_id/grading_standards`

### GET /api/v1/accounts/:account_id/grading_standards

**Scope:** `url:GET|/api/v1/accounts/:account_id/grading_standards`

Returns the paginated list of grading standards for the given context that are visible to the user.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/1/grading_standards \
  -H 'Authorization: Bearer <token>'
```

Returns a list of [GradingStandard](grading_standards.html#GradingStandard) objects

## Get a single grading standard in a context.

### GET /api/v1/courses/:course_id/grading_standards/:grading_standard_id

**Scope:** `url:GET|/api/v1/courses/:course_id/grading_standards/:grading_standard_id`

### GET /api/v1/accounts/:account_id/grading_standards/:grading_standard_id

**Scope:** `url:GET|/api/v1/accounts/:account_id/grading_standards/:grading_standard_id`

Returns a grading standard for the given context that is visible to the user.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/1/grading_standards/5 \
  -H 'Authorization: Bearer <token>'
```

Returns a [GradingStandard](grading_standards.html#GradingStandard) object
