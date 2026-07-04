# What If Grades API

### A Grade object looks like:

``` example
{
  // The grade for the course
  "grade": 120.0,
  // The total points earned in the course
  "total": 24.0,
  // The total points possible for the course
  "possible": 20.0,
  // The dropped grades for the course
  "dropped": []
}
```

### An AssignmentGroupGrade object looks like:

``` example
{
  // The ID of the Assignment Group
  "id": 123,
  // The global ID of the Assignment Group
  "global_id": 10000000000001,
  // The score for the Assignment Group
  "score": 20.0,
  // The total points possible for the Assignment Group
  "possible": 10.0,
  // The weight for the Assignment Group
  "weight": 0.0,
  // The grade for the Assignment Group
  "grade": 200.0,
  // The dropped grades for the Assignment Group
  "dropped": []
}
```

### A GradeGroup object looks like:

``` example
{
  "submission_id": null
}
```

### A Grades object looks like:

``` example
{
  "current": null,
  "current_groups": null,
  "final": null,
  "final_groups": null
}
```

### A Submission object looks like:

``` example
{
  // The ID of the submission
  "id": 123,
  // The score the student wants to test
  "student_entered_score": "20.0"
}
```

## Update a submission's what-if score and calculate grades

### PUT /api/v1/submissions/:id/what_if_grades

**Scope:** `url:PUT|/api/v1/submissions/:id/what_if_grades`

Enter a what if score for a submission and receive the calculated grades Grade calculation is a costly operation, so this API should be used sparingly

#### Request Parameters:

| Parameter             |     | Type   | Description                         |
|-----------------------|-----|--------|-------------------------------------|
| student_entered_score |     | number | The score the student wants to test |

#### Example Response:

####

``` example
{
    "grades": [
        {
            "current": {
                "grade": 120.0,
                "total": 24.0,
                "possible": 20.0,
                "dropped": []
            },
            "current_groups": {
                "1": {
                    "id": 1,
                    "global_id": 10000000000001,
                    "score": 20.0,
                    "possible": 10.0,
                    "weight": 0.0,
                    "grade": 200.0,
                    "dropped": []
                },
                "3": {
                    "id": 3,
                    "global_id": 10000000000003,
                    "score": 4.0,
                    "possible": 10.0,
                    "weight": 0.0,
                    "grade": 40.0,
                    "dropped": []
                }
            },
            "final": {
                "grade": 21.82,
                "total": 24.0,
                "possible": 110.0,
                "dropped": []
            },
            "final_groups": {
                "1": {
                    "id": 1,
                    "global_id": 10000000000001,
                    "score": 20.0,
                    "possible": 100.0,
                    "weight": 0.0,
                    "grade": 20.0,
                    "dropped": []
                },
                "3": {
                    "id": 3,
                    "global_id": 10000000000003,
                    "score": 4.0,
                    "possible": 10.0,
                    "weight": 0.0,
                    "grade": 40.0,
                    "dropped": []
                }
            }
        }
    ],
    "submission": {
        "id": 166,
        "student_entered_score": 20.0
    }
}
```

Returns a list of [Grades](what_if_grades.html#Grades) objects

## Reset the what-if scores for the current user for an entire course and recalculate grades

### PUT /api/v1/courses/:course_id/what_if_grades/reset

**Scope:** `url:PUT|/api/v1/courses/:course_id/what_if_grades/reset`
