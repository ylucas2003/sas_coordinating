# Rubrics API

API for accessing rubric information.

### A Rubric object looks like:

``` example
{
  // the ID of the rubric
  "id": 1,
  // title of the rubric
  "title": "some title",
  // the context owning the rubric
  "context_id": 1,
  "context_type": "Course",
  "points_possible": 10.0,
  "reusable": false,
  "read_only": true,
  // whether or not free-form comments are used
  "free_form_criterion_comments": true,
  "hide_score_total": true,
  // An array with all of this Rubric's grading Criteria
  "data": null,
  // If an assessment type is included in the 'include' parameter, includes an
  // array of rubric assessment objects for a given rubric, based on the
  // assessment type requested. If the user does not request an assessment type
  // this key will be absent.
  "assessments": null,
  // If an association type is included in the 'include' parameter, includes an
  // array of rubric association objects for a given rubric, based on the
  // association type requested. If the user does not request an association type
  // this key will be absent.
  "associations": null
}
```

### A RubricCriterion object looks like:

``` example
{
  // the ID of the criterion
  "id": "_10",
  "description": null,
  "long_description": null,
  "points": 5,
  "criterion_use_range": false,
  // the possible ratings for this Criterion
  "ratings": null
}
```

### A RubricRating object looks like:

``` example
{
  "id": "name_2",
  "criterion_id": "_10",
  "description": null,
  "long_description": null,
  "points": 5
}
```

### A RubricAssessment object looks like:

``` example
{
  // the ID of the rubric
  "id": 1,
  // the rubric the assessment belongs to
  "rubric_id": 1,
  "rubric_association_id": 2,
  "score": 5.0,
  // the object of the assessment
  "artifact_type": "Submission",
  // the id of the object of the assessment
  "artifact_id": 3,
  // the current number of attempts made on the object of the assessment
  "artifact_attempt": 2,
  // the type of assessment. values will be either 'grading', 'peer_review', or
  // 'provisional_grade'
  "assessment_type": "grading",
  // user id of the person who made the assessment
  "assessor_id": 6,
  // (Optional) If 'full' is included in the 'style' parameter, returned
  // assessments will have their full details contained in their data hash. If the
  // user does not request a style, this key will be absent.
  "data": null,
  // (Optional) If 'comments_only' is included in the 'style' parameter, returned
  // assessments will include only the comments portion of their data hash. If the
  // user does not request a style, this key will be absent.
  "comments": null
}
```

### A RubricAssociation object looks like:

``` example
{
  // the ID of the association
  "id": 1,
  // the ID of the rubric
  "rubric_id": 1,
  // the ID of the object this association links to
  "association_id": 1,
  // the type of object this association links to
  "association_type": "Course",
  // Whether or not the associated rubric is used for grade calculation
  "use_for_grading": true,
  "summary_data": "",
  // Whether or not the association is for grading (and thus linked to an
  // assignment) or if it's to indicate the rubric should appear in its context.
  // Values will be grading or bookmark.
  "purpose": "grading",
  // Whether or not the score total is displayed within the rubric. This option is
  // only available if the rubric is not used for grading.
  "hide_score_total": true,
  "hide_points": true,
  "hide_outcome_results": true
}
```

## Create a single rubric

### POST /api/v1/courses/:course_id/rubrics

**Scope:** `url:POST|/api/v1/courses/:course_id/rubrics`

Returns the rubric with the given id.

Unfortuantely this endpoint does not return a standard Rubric object, instead it returns a hash that looks like

``` code
{ 'rubric': Rubric, 'rubric_association': RubricAssociation }
```

This may eventually be deprecated in favor of a more standardized return value, but that is not currently planned.

TODO: document once feature is public: [rubric](criteria_via_llm) \[Boolean\]

``` code
When true, rubric[criteria] will be ignored (does not need to be included
at all). Instead, rubric criteria will be automatically generated from a
large language model (llm).
```

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
<td>id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the rubric</p></td>
</tr>
<tr class="request-param">
<td>rubric_association_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the rubric association object (not the course/assignment itself, but the join table record id). It can be used in place of rubric_association and rubric_association if desired.</p></td>
</tr>
<tr class="request-param">
<td>rubric[title]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The title of the rubric</p></td>
</tr>
<tr class="request-param">
<td>rubric[free_form_criterion_comments]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not you can write custom comments in the ratings field for a rubric</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[association_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the object with which this rubric is associated</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[association_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The type of object this rubric is associated with</p>
<p>Allowed values: <code class="enum">Assignment</code>, <code class="enum">Course</code>, <code class="enum">Account</code></p></td>
</tr>
<tr class="request-param">
<td>rubric_association[use_for_grading]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not the associated rubric is used for grade calculation</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[hide_score_total]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not the score total is displayed within the rubric. This option is only available if the rubric is not used for grading.</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[purpose]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Whether or not the association is for grading (and thus linked to an assignment) or if it’s to indicate the rubric should appear in its context</p></td>
</tr>
<tr class="request-param">
<td>rubric[criteria]</td>
<td></td>
<td>Hash</td>
<td class="param-desc"><p>An indexed Hash of RubricCriteria objects where the keys are integer ids and the values are the RubricCriteria objects</p></td>
</tr>
</tbody>
</table>

## Update a single rubric

### PUT /api/v1/courses/:course_id/rubrics/:id

**Scope:** `url:PUT|/api/v1/courses/:course_id/rubrics/:id`

Returns the rubric with the given id.

Unfortuantely this endpoint does not return a standard Rubric object, instead it returns a hash that looks like

``` code
{ 'rubric': Rubric, 'rubric_association': RubricAssociation }
```

This may eventually be deprecated in favor of a more standardized return value, but that is not currently planned.

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
<td>id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the rubric</p></td>
</tr>
<tr class="request-param">
<td>rubric_association_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the rubric association object (not the course/assignment itself, but the join table record id). It can be used in place of rubric_association and rubric_association if desired.</p></td>
</tr>
<tr class="request-param">
<td>rubric[title]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The title of the rubric</p></td>
</tr>
<tr class="request-param">
<td>rubric[free_form_criterion_comments]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not you can write custom comments in the ratings field for a rubric</p></td>
</tr>
<tr class="request-param">
<td>rubric[skip_updating_points_possible]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not to update the points possible</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[association_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the object with which this rubric is associated</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[association_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The type of object this rubric is associated with</p>
<p>Allowed values: <code class="enum">Assignment</code>, <code class="enum">Course</code>, <code class="enum">Account</code></p></td>
</tr>
<tr class="request-param">
<td>rubric_association[use_for_grading]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not the associated rubric is used for grade calculation</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[hide_score_total]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not the score total is displayed within the rubric. This option is only available if the rubric is not used for grading.</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[purpose]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Whether or not the association is for grading (and thus linked to an assignment) or if it’s to indicate the rubric should appear in its context</p>
<p>Allowed values: <code class="enum">grading</code>, <code class="enum">bookmark</code></p></td>
</tr>
<tr class="request-param">
<td>rubric[criteria]</td>
<td></td>
<td>Hash</td>
<td class="param-desc"><p>An indexed Hash of RubricCriteria objects where the keys are integer ids and the values are the RubricCriteria objects</p></td>
</tr>
</tbody>
</table>

## Delete a single

### DELETE /api/v1/courses/:course_id/rubrics/:id

**Scope:** `url:DELETE|/api/v1/courses/:course_id/rubrics/:id`

Deletes a Rubric and removes all RubricAssociations.

Returns a [Rubric](rubrics.html#Rubric) object

## List rubrics

### GET /api/v1/accounts/:account_id/rubrics

**Scope:** `url:GET|/api/v1/accounts/:account_id/rubrics`

### GET /api/v1/courses/:course_id/rubrics

**Scope:** `url:GET|/api/v1/courses/:course_id/rubrics`

Returns the paginated list of active rubrics for the current context.

## Get a single rubric

### GET /api/v1/accounts/:account_id/rubrics/:id

**Scope:** `url:GET|/api/v1/accounts/:account_id/rubrics/:id`

### GET /api/v1/courses/:course_id/rubrics/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/rubrics/:id`

Returns the rubric with the given id.

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
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Related records to include in the response.</p>
<p>Allowed values: <code class="enum">assessments</code>, <code class="enum">graded_assessments</code>, <code class="enum">peer_assessments</code>, <code class="enum">associations</code>, <code class="enum">assignment_associations</code>, <code class="enum">course_associations</code>, <code class="enum">account_associations</code></p></td>
</tr>
<tr class="request-param">
<td>style</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Applicable only if assessments are being returned. If included, returns either all criteria data associated with the assessment, or just the comments. If not included, both data and comments are omitted.</p>
<p>Allowed values: <code class="enum">full</code>, <code class="enum">comments_only</code></p></td>
</tr>
</tbody>
</table>

Returns a [Rubric](rubrics.html#Rubric) object

## Get the courses and assignments for

### GET /api/v1/courses/:course_id/rubrics/:id/used_locations

**Scope:** `url:GET|/api/v1/courses/:course_id/rubrics/:id/used_locations`

### GET /api/v1/accounts/:account_id/rubrics/:id/used_locations

**Scope:** `url:GET|/api/v1/accounts/:account_id/rubrics/:id/used_locations`

Returns the rubric with the given id.

## Creates a rubric using a CSV file

### POST /api/v1/courses/:course_id/rubrics/upload

**Scope:** `url:POST|/api/v1/courses/:course_id/rubrics/upload`

### POST /api/v1/accounts/:account_id/rubrics/upload

**Scope:** `url:POST|/api/v1/accounts/:account_id/rubrics/upload`

Returns the rubric import object that was created

## Templated file for importing a rubric

### GET /api/v1/rubrics/upload_template

**Scope:** `url:GET|/api/v1/rubrics/upload_template`

## Get the status of a rubric import

### GET /api/v1/courses/:course_id/rubrics/upload/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/rubrics/upload/:id`

### GET /api/v1/accounts/:account_id/rubrics/upload/:id

**Scope:** `url:GET|/api/v1/accounts/:account_id/rubrics/upload/:id`

Can return the latest rubric import for an account or course, or a specific import by id

## Create a single rubric assessment

### POST /api/v1/courses/:course_id/rubric_associations/:rubric_association_id/rubric_assessments

**Scope:** `url:POST|/api/v1/courses/:course_id/rubric_associations/:rubric_association_id/rubric_assessments`

Returns the rubric assessment with the given id. The returned object also provides the information of

``` code
:ratings, :assessor_name, :related_group_submissions_and_assessments, :artifact
```

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
<td>course_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the course</p></td>
</tr>
<tr class="request-param">
<td>rubric_association_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the object with which this rubric assessment is associated</p></td>
</tr>
<tr class="request-param">
<td>provisional</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>(optional) Indicates whether this assessment is provisional, defaults to false.</p></td>
</tr>
<tr class="request-param">
<td>final</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>(optional) Indicates a provisional grade will be marked as final. It only takes effect if the provisional param is passed as true. Defaults to false.</p></td>
</tr>
<tr class="request-param">
<td>graded_anonymously</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>(optional) Defaults to false</p></td>
</tr>
<tr class="request-param">
<td>rubric_assessment</td>
<td></td>
<td>Hash</td>
<td class="param-desc"><p>A Hash of data to complement the rubric assessment: The user id that refers to the person being assessed</p>
`rubric_assessment[user_id]`
<p>Assessment type. There are only three valid types: ‘grading’, ‘peer_review’, or ‘provisional_grade’</p>
`rubric_assessment[assessment_type]`
<p>The points awarded for this row.</p>
`rubric_assessment[criterion_id][points]`
<p>Comments to add for this row.</p>
`rubric_assessment[criterion_id][comments]`
<p>For each criterion_id, change the id by the criterion number, ex: criterion_123 If the criterion_id is not specified it defaults to false, and nothing is updated.</p></td>
</tr>
</tbody>
</table>

## Update a single rubric assessment

### PUT /api/v1/courses/:course_id/rubric_associations/:rubric_association_id/rubric_assessments/:id

**Scope:** `url:PUT|/api/v1/courses/:course_id/rubric_associations/:rubric_association_id/rubric_assessments/:id`

Returns the rubric assessment with the given id. The returned object also provides the information of

``` code
:ratings, :assessor_name, :related_group_submissions_and_assessments, :artifact
```

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
<td>id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the rubric assessment</p></td>
</tr>
<tr class="request-param">
<td>course_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the course</p></td>
</tr>
<tr class="request-param">
<td>rubric_association_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the object with which this rubric assessment is associated</p></td>
</tr>
<tr class="request-param">
<td>provisional</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>(optional) Indicates whether this assessment is provisional, defaults to false.</p></td>
</tr>
<tr class="request-param">
<td>final</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>(optional) Indicates a provisional grade will be marked as final. It only takes effect if the provisional param is passed as true. Defaults to false.</p></td>
</tr>
<tr class="request-param">
<td>graded_anonymously</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>(optional) Defaults to false</p></td>
</tr>
<tr class="request-param">
<td>rubric_assessment</td>
<td></td>
<td>Hash</td>
<td class="param-desc"><p>A Hash of data to complement the rubric assessment: The user id that refers to the person being assessed</p>
`rubric_assessment[user_id]`
<p>Assessment type. There are only three valid types: ‘grading’, ‘peer_review’, or ‘provisional_grade’</p>
`rubric_assessment[assessment_type]`
<p>The points awarded for this row.</p>
`rubric_assessment[criterion_id][points]`
<p>Comments to add for this row.</p>
`rubric_assessment[criterion_id][comments]`
<p>For each criterion_id, change the id by the criterion number, ex: criterion_123 If the criterion_id is not specified it defaults to false, and nothing is updated.</p></td>
</tr>
</tbody>
</table>

## Delete a single rubric assessment

### DELETE /api/v1/courses/:course_id/rubric_associations/:rubric_association_id/rubric_assessments/:id

**Scope:** `url:DELETE|/api/v1/courses/:course_id/rubric_associations/:rubric_association_id/rubric_assessments/:id`

Deletes a rubric assessment

Returns a [RubricAssessment](rubrics.html#RubricAssessment) object

## Create a RubricAssociation

### POST /api/v1/courses/:course_id/rubric_associations

**Scope:** `url:POST|/api/v1/courses/:course_id/rubric_associations`

Returns the rubric with the given id.

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
<td>rubric_association[rubric_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the Rubric</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[association_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the object with which this rubric is associated</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[association_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The type of object this rubric is associated with</p>
<p>Allowed values: <code class="enum">Assignment</code>, <code class="enum">Course</code>, <code class="enum">Account</code></p></td>
</tr>
<tr class="request-param">
<td>rubric_association[title]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The name of the object this rubric is associated with</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[use_for_grading]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not the associated rubric is used for grade calculation</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[hide_score_total]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not the score total is displayed within the rubric. This option is only available if the rubric is not used for grading.</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[purpose]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Whether or not the association is for grading (and thus linked to an assignment) or if it’s to indicate the rubric should appear in its context</p>
<p>Allowed values: <code class="enum">grading</code>, <code class="enum">bookmark</code></p></td>
</tr>
<tr class="request-param">
<td>rubric_association[bookmarked]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not the associated rubric appears in its context</p></td>
</tr>
</tbody>
</table>

Returns a [RubricAssociation](rubrics.html#RubricAssociation) object

## Update a RubricAssociation

### PUT /api/v1/courses/:course_id/rubric_associations/:id

**Scope:** `url:PUT|/api/v1/courses/:course_id/rubric_associations/:id`

Returns the rubric with the given id.

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
<td>id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the RubricAssociation to update</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[rubric_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the Rubric</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[association_id]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The id of the object with which this rubric is associated</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[association_type]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The type of object this rubric is associated with</p>
<p>Allowed values: <code class="enum">Assignment</code>, <code class="enum">Course</code>, <code class="enum">Account</code></p></td>
</tr>
<tr class="request-param">
<td>rubric_association[title]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The name of the object this rubric is associated with</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[use_for_grading]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not the associated rubric is used for grade calculation</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[hide_score_total]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not the score total is displayed within the rubric. This option is only available if the rubric is not used for grading.</p></td>
</tr>
<tr class="request-param">
<td>rubric_association[purpose]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Whether or not the association is for grading (and thus linked to an assignment) or if it’s to indicate the rubric should appear in its context</p>
<p>Allowed values: <code class="enum">grading</code>, <code class="enum">bookmark</code></p></td>
</tr>
<tr class="request-param">
<td>rubric_association[bookmarked]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether or not the associated rubric appears in its context</p></td>
</tr>
</tbody>
</table>

Returns a [RubricAssociation](rubrics.html#RubricAssociation) object

## Delete a RubricAssociation

### DELETE /api/v1/courses/:course_id/rubric_associations/:id

**Scope:** `url:DELETE|/api/v1/courses/:course_id/rubric_associations/:id`

Delete the RubricAssociation with the given ID

Returns a [RubricAssociation](rubrics.html#RubricAssociation) object
