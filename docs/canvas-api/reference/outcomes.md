# Outcomes API

API for accessing learning outcome information.

### An Outcome object looks like:

``` example
{
  // the ID of the outcome
  "id": 1,
  // the URL for fetching/updating the outcome. should be treated as opaque
  "url": "/api/v1/outcomes/1",
  // the context owning the outcome. may be null for global outcomes
  "context_id": 1,
  "context_type": "Account",
  // title of the outcome
  "title": "Outcome title",
  // Optional friendly name for reporting
  "display_name": "My Favorite Outcome",
  // description of the outcome. omitted in the abbreviated form.
  "description": "Outcome description",
  // A custom GUID for the learning standard.
  "vendor_guid": "customid9000",
  // maximum points possible. included only if the outcome embeds a rubric
  // criterion. omitted in the abbreviated form.
  "points_possible": 5,
  // points necessary to demonstrate mastery outcomes. included only if the
  // outcome embeds a rubric criterion. omitted in the abbreviated form.
  "mastery_points": 3,
  // the method used to calculate a students score
  "calculation_method": "decaying_average",
  // this defines the variable value used by the calculation_method. included only
  // if calculation_method uses it
  "calculation_int": 65,
  // possible ratings for this outcome. included only if the outcome embeds a
  // rubric criterion. omitted in the abbreviated form.
  "ratings": null,
  // whether the current user can update the outcome
  "can_edit": true,
  // whether the outcome can be unlinked
  "can_unlink": true,
  // whether this outcome has been used to assess a student
  "assessed": true,
  // whether updates to this outcome will propagate to unassessed rubrics that
  // have imported it
  "has_updateable_rubrics": true
}
```

### An OutcomeAlignment object looks like:

``` example
{
  // the id of the aligned learning outcome.
  "id": 1,
  // the id of the aligned assignment (null for live assessments).
  "assignment_id": 2,
  // the id of the aligned live assessment (null for assignments).
  "assessment_id": 3,
  // a string representing the different submission types of an aligned
  // assignment.
  "submission_types": "online_text_entry,online_url",
  // the URL for the aligned assignment.
  "url": "/courses/1/assignments/5",
  // the title of the aligned assignment.
  "title": "Unit 1 test"
}
```

## Show an outcome

### GET /api/v1/outcomes/:id

**Scope:** `url:GET|/api/v1/outcomes/:id`

Returns the details of the outcome with the given id.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| add_defaults |  | boolean | If defaults are requested, then color and mastery level defaults will be added to outcome ratings in the result. This will only take effect if the Account Level Mastery Scales FF is DISABLED |

Returns an [Outcome](outcomes.html#Outcome) object

## Update an outcome

### PUT /api/v1/outcomes/:id

**Scope:** `url:PUT|/api/v1/outcomes/:id`

Modify an existing outcome. Fields not provided are left as is; unrecognized fields are ignored.

If any new ratings are provided, the combination of all new ratings provided completely replace any existing embedded rubric criterion; it is not possible to tweak the ratings of the embedded rubric criterion.

A new embedded rubric criterion’s mastery_points default to the maximum points in the highest rating if not specified in the mastery_points parameter. Any new ratings lacking a description are given a default of “No description”. Any new ratings lacking a point value are given a default of 0.

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
<td>title</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The new outcome title.</p></td>
</tr>
<tr class="request-param">
<td>display_name</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A friendly name shown in reports for outcomes with cryptic titles, such as common core standards names.</p></td>
</tr>
<tr class="request-param">
<td>description</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The new outcome description.</p></td>
</tr>
<tr class="request-param">
<td>vendor_guid</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A custom GUID for the learning standard.</p></td>
</tr>
<tr class="request-param">
<td>mastery_points</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The new mastery threshold for the embedded rubric criterion.</p></td>
</tr>
<tr class="request-param">
<td>ratings[][description]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The description of a new rating level for the embedded rubric criterion.</p></td>
</tr>
<tr class="request-param">
<td>ratings[][points]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The points corresponding to a new rating level for the embedded rubric criterion.</p></td>
</tr>
<tr class="request-param">
<td>calculation_method</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The new calculation method. If the Outcomes New Decaying Average Calculation Method FF is ENABLED then “weighted_average” can be used and it is same as previous “decaying_average” and new “decaying_average” will have improved version of calculation.</p>
<p>Allowed values: <code class="enum">weighted_average</code>, <code class="enum">decaying_average</code>, <code class="enum">n_mastery</code>, <code class="enum">latest</code>, <code class="enum">highest</code>, <code class="enum">average</code></p></td>
</tr>
<tr class="request-param">
<td>calculation_int</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The new calculation int. Only applies if the calculation_method is “decaying_average” or “n_mastery”</p></td>
</tr>
<tr class="request-param">
<td>add_defaults</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If defaults are requested, then color and mastery level defaults will be added to outcome ratings in the result. This will only take effect if the Account Level Mastery Scales FF is DISABLED</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/outcomes/1.json' \
     -X PUT \
     -F 'title=Outcome Title' \
     -F 'display_name=Title for reporting' \
     -F 'description=Outcome description' \
     -F 'vendor_guid=customid9001' \
     -F 'mastery_points=3' \
     -F 'calculation_method=decaying_average' \
     -F 'calculation_int=65' \
     -F 'ratings[][description]=Exceeds Expectations' \
     -F 'ratings[][points]=5' \
     -F 'ratings[][description]=Meets Expectations' \
     -F 'ratings[][points]=3' \
     -F 'ratings[][description]=Does Not Meet Expectations' \
     -F 'ratings[][points]=0' \
     -F 'ratings[][points]=0' \
     -H "Authorization: Bearer <token>"
```

####

``` example
curl 'https://<canvas>/api/v1/outcomes/1.json' \
     -X PUT \
     --data-binary '{
           "title": "Outcome Title",
           "display_name": "Title for reporting",
           "description": "Outcome description",
           "vendor_guid": "customid9001",
           "mastery_points": 3,
           "ratings": [
             { "description": "Exceeds Expectations", "points": 5 },
             { "description": "Meets Expectations", "points": 3 },
             { "description": "Does Not Meet Expectations", "points": 0 }
           ]
         }' \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <token>"
```

Returns an [Outcome](outcomes.html#Outcome) object

## Get aligned assignments for an outcome in a course for a particular student

### GET /api/v1/courses/:course_id/outcome_alignments

**Scope:** `url:GET|/api/v1/courses/:course_id/outcome_alignments`
