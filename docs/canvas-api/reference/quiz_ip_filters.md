# Quiz IP Filters API

API for accessing quiz IP filters

### A QuizIPFilter object looks like:

``` example
{
  // A unique name for the filter.
  "name": "Current Filter",
  // Name of the Account (or Quiz) the IP filter is defined in.
  "account": "Some Quiz",
  // An IP address (or range mask) this filter embodies.
  "filter": "192.168.1.1/24"
}
```

## Get available quiz IP filters.

### GET /api/v1/courses/:course_id/quizzes/:quiz_id/ip_filters

**Scope:** `url:GET|/api/v1/courses/:course_id/quizzes/:quiz_id/ip_filters`

Get a list of available IP filters for this Quiz.

**200 OK** response code is returned if the request was successful.

#### Example Response:

####

``` example
{
  "quiz_ip_filters": [QuizIPFilter]
}
```
