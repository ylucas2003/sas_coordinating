# Custom Gradebook Columns API

API for adding additional columns to the gradebook. Custom gradebook columns will be displayed with the other frozen gradebook columns.

### A CustomColumn object looks like:

``` example
{
  // The ID of the custom gradebook column
  "id": 2,
  // When true, this column's visibility will be toggled in the Gradebook when a
  // user selects to show or hide notes
  "teacher_notes": false,
  // header text
  "title": "Stuff",
  // column order
  "position": 1,
  // won't be displayed if hidden is true
  "hidden": false,
  // won't be editable in the gradebook UI
  "read_only": true
}
```

### A ColumnDatum object looks like:

``` example
// ColumnDatum objects contain the entry for a column for each user.
{
  "content": "Nut allergy",
  "user_id": 2
}
```

## List custom gradebook columns

### GET /api/v1/courses/:course_id/custom_gradebook_columns

**Scope:** `url:GET|/api/v1/courses/:course_id/custom_gradebook_columns`

A paginated list of all custom gradebook columns for a course

#### Request Parameters:

| Parameter      |     | Type    | Description                                   |
|----------------|-----|---------|-----------------------------------------------|
| include_hidden |     | boolean | Include hidden parameters (defaults to false) |

Returns a list of [CustomColumn](custom_gradebook_columns.html#CustomColumn) objects

## Create a custom gradebook column

### POST /api/v1/courses/:course_id/custom_gradebook_columns

**Scope:** `url:POST|/api/v1/courses/:course_id/custom_gradebook_columns`

Create a custom gradebook column

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| column\[title\] | Required | string | no description |
| column\[position\] |  | integer | The position of the column relative to other custom columns |
| column\[hidden\] |  | boolean | Hidden columns are not displayed in the gradebook |
| column\[teacher_notes\] |  | boolean | Set this if the column is created by a teacher. The gradebook only supports one teacher_notes column. |
| column\[read_only\] |  | boolean | Set this to prevent the column from being editable in the gradebook ui |

Returns a [CustomColumn](custom_gradebook_columns.html#CustomColumn) object

## Update a custom gradebook column

### PUT /api/v1/courses/:course_id/custom_gradebook_columns/:id

**Scope:** `url:PUT|/api/v1/courses/:course_id/custom_gradebook_columns/:id`

Accepts the same parameters as custom gradebook column creation

Returns a [CustomColumn](custom_gradebook_columns.html#CustomColumn) object

## Delete a custom gradebook column

### DELETE /api/v1/courses/:course_id/custom_gradebook_columns/:id

**Scope:** `url:DELETE|/api/v1/courses/:course_id/custom_gradebook_columns/:id`

Permanently deletes a custom column and its associated data

Returns a [CustomColumn](custom_gradebook_columns.html#CustomColumn) object

## Reorder custom columns

### POST /api/v1/courses/:course_id/custom_gradebook_columns/reorder

**Scope:** `url:POST|/api/v1/courses/:course_id/custom_gradebook_columns/reorder`

Puts the given columns in the specified order

**200 OK** is returned if successful

#### Request Parameters:

| Parameter |          | Type    | Description    |
|-----------|----------|---------|----------------|
| order\[\] | Required | integer | no description |

## List entries for a column

### GET /api/v1/courses/:course_id/custom_gradebook_columns/:id/data

**Scope:** `url:GET|/api/v1/courses/:course_id/custom_gradebook_columns/:id/data`

This does not list entries for students without associated data.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| include_hidden |  | boolean | If true, hidden columns will be included in the result. If false or absent, only visible columns will be returned. |

Returns a list of [ColumnDatum](custom_gradebook_columns.html#ColumnDatum) objects

## Update column data

### PUT /api/v1/courses/:course_id/custom_gradebook_columns/:id/data/:user_id

**Scope:** `url:PUT|/api/v1/courses/:course_id/custom_gradebook_columns/:id/data/:user_id`

Set the content of a custom column

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| column_data\[content\] | Required | string | Column content. Setting this to blank will delete the datum object. |

Returns a [ColumnDatum](custom_gradebook_columns.html#ColumnDatum) object

## Bulk update column data

### PUT /api/v1/courses/:course_id/custom_gradebook_column_data

**Scope:** `url:PUT|/api/v1/courses/:course_id/custom_gradebook_column_data`

Set the content of custom columns

{

``` code
"column_data": [
  {
    "column_id": example_column_id,
    "user_id": example_student_id,
    "content": example_content
    },
    {
    "column_id": example_column_id,
    "user_id": example_student_id,
    "content: example_content
  }
]
```

}

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| column_data\[\] | Required | Array | Column content. Setting this to an empty string will delete the data object. |

#### Example Request:

####

``` example
```

Returns a [Progress](progress.html#Progress) object
