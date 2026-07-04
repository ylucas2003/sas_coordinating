# Outcome Groups API

API for accessing learning outcome group information.

Learning outcome groups organize outcomes within a context (or in the global "context" for global outcomes). Every outcome is created in a particular context (that context then becomes its "owning context") but may be linked multiple times in one or more related contexts. This allows different accounts or courses to organize commonly defined outcomes in ways appropriate to their pedagogy, including having the same outcome discoverable at different locations in the organizational hierarchy.

While an outcome can be linked into a context (such as a course) multiple times, it may only be linked into a particular group once.

### An OutcomeGroup object looks like:

``` example
{
  // the ID of the outcome group
  "id": 1,
  // the URL for fetching/updating the outcome group. should be treated as opaque
  "url": "/api/v1/accounts/1/outcome_groups/1",
  // an abbreviated OutcomeGroup object representing the parent group of this
  // outcome group, if any. omitted in the abbreviated form.
  "parent_outcome_group": null,
  // the context owning the outcome group. may be null for global outcome groups.
  // omitted in the abbreviated form.
  "context_id": 1,
  "context_type": "Account",
  // title of the outcome group
  "title": "Outcome group title",
  // description of the outcome group. omitted in the abbreviated form.
  "description": "Outcome group description",
  // A custom GUID for the learning standard.
  "vendor_guid": "customid9000",
  // the URL for listing/creating subgroups under the outcome group. should be
  // treated as opaque
  "subgroups_url": "/api/v1/accounts/1/outcome_groups/1/subgroups",
  // the URL for listing/creating outcome links under the outcome group. should be
  // treated as opaque
  "outcomes_url": "/api/v1/accounts/1/outcome_groups/1/outcomes",
  // the URL for importing another group into this outcome group. should be
  // treated as opaque. omitted in the abbreviated form.
  "import_url": "/api/v1/accounts/1/outcome_groups/1/import",
  // whether the current user can update the outcome group
  "can_edit": true
}
```

### An OutcomeLink object looks like:

``` example
{
  // the URL for fetching/updating the outcome link. should be treated as opaque
  "url": "/api/v1/accounts/1/outcome_groups/1/outcomes/1",
  // the context owning the outcome link. will match the context owning the
  // outcome group containing the outcome link; included for convenience. may be
  // null for links in global outcome groups.
  "context_id": 1,
  "context_type": "Account",
  // an abbreviated OutcomeGroup object representing the group containing the
  // outcome link.
  "outcome_group": null,
  // an abbreviated Outcome object representing the outcome linked into the
  // containing outcome group.
  "outcome": null,
  // whether this outcome has been used to assess a student in the context of this
  // outcome link.  In other words, this will be set to true if the context is a
  // course, and a student has been assessed with this outcome in that course.
  "assessed": true,
  // whether this outcome link is manageable and is not the last link to an
  // aligned outcome
  "can_unlink": null
}
```

## Redirect to root outcome group for context

### GET /api/v1/global/root_outcome_group

**Scope:** `url:GET|/api/v1/global/root_outcome_group`

### GET /api/v1/accounts/:account_id/root_outcome_group

**Scope:** `url:GET|/api/v1/accounts/:account_id/root_outcome_group`

### GET /api/v1/courses/:course_id/root_outcome_group

**Scope:** `url:GET|/api/v1/courses/:course_id/root_outcome_group`

Convenience redirect to find the root outcome group for a particular context. Will redirect to the appropriate outcome group’s URL.

## Get all outcome groups for context

### GET /api/v1/accounts/:account_id/outcome_groups

**Scope:** `url:GET|/api/v1/accounts/:account_id/outcome_groups`

### GET /api/v1/courses/:course_id/outcome_groups

**Scope:** `url:GET|/api/v1/courses/:course_id/outcome_groups`

## Get all outcome links for context

### GET /api/v1/accounts/:account_id/outcome_group_links

**Scope:** `url:GET|/api/v1/accounts/:account_id/outcome_group_links`

### GET /api/v1/courses/:course_id/outcome_group_links

**Scope:** `url:GET|/api/v1/courses/:course_id/outcome_group_links`

## Show an outcome group

### GET /api/v1/global/outcome_groups/:id

**Scope:** `url:GET|/api/v1/global/outcome_groups/:id`

### GET /api/v1/accounts/:account_id/outcome_groups/:id

**Scope:** `url:GET|/api/v1/accounts/:account_id/outcome_groups/:id`

### GET /api/v1/courses/:course_id/outcome_groups/:id

**Scope:** `url:GET|/api/v1/courses/:course_id/outcome_groups/:id`

## Update an outcome group

### PUT /api/v1/global/outcome_groups/:id

**Scope:** `url:PUT|/api/v1/global/outcome_groups/:id`

### PUT /api/v1/accounts/:account_id/outcome_groups/:id

**Scope:** `url:PUT|/api/v1/accounts/:account_id/outcome_groups/:id`

### PUT /api/v1/courses/:course_id/outcome_groups/:id

**Scope:** `url:PUT|/api/v1/courses/:course_id/outcome_groups/:id`

Modify an existing outcome group. Fields not provided are left as is; unrecognized fields are ignored.

When changing the parent outcome group, the new parent group must belong to the same context as this outcome group, and must not be a descendant of this outcome group (i.e. no cycles allowed).

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| title |  | string | The new outcome group title. |
| description |  | string | The new outcome group description. |
| vendor_guid |  | string | A custom GUID for the learning standard. |
| parent_outcome_group_id |  | integer | The id of the new parent outcome group. |

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/accounts/1/outcome_groups/2.json' \
     -X PUT \
     -F 'title=Outcome Group Title' \
     -F 'description=Outcome group description' \
     -F 'vendor_guid=customid9000' \
     -F 'parent_outcome_group_id=1' \
     -H "Authorization: Bearer <token>"
```

####

``` example
curl 'https://<canvas>/api/v1/accounts/1/outcome_groups/2.json' \
     -X PUT \
     --data-binary '{
           "title": "Outcome Group Title",
           "description": "Outcome group description",
           "vendor_guid": "customid9000",
           "parent_outcome_group_id": 1
         }' \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <token>"
```

Returns an [OutcomeGroup](outcome_groups.html#OutcomeGroup) object

## Delete an outcome group

### DELETE /api/v1/global/outcome_groups/:id

**Scope:** `url:DELETE|/api/v1/global/outcome_groups/:id`

### DELETE /api/v1/accounts/:account_id/outcome_groups/:id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/outcome_groups/:id`

### DELETE /api/v1/courses/:course_id/outcome_groups/:id

**Scope:** `url:DELETE|/api/v1/courses/:course_id/outcome_groups/:id`

Deleting an outcome group deletes descendant outcome groups and outcome links. The linked outcomes themselves are only deleted if all links to the outcome were deleted.

Aligned outcomes cannot be deleted; as such, if all remaining links to an aligned outcome are included in this group’s descendants, the group deletion will fail.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/accounts/1/outcome_groups/2.json' \
     -X DELETE \
     -H "Authorization: Bearer <token>"
```

Returns an [OutcomeGroup](outcome_groups.html#OutcomeGroup) object

## List linked outcomes

### GET /api/v1/global/outcome_groups/:id/outcomes

**Scope:** `url:GET|/api/v1/global/outcome_groups/:id/outcomes`

### GET /api/v1/accounts/:account_id/outcome_groups/:id/outcomes

**Scope:** `url:GET|/api/v1/accounts/:account_id/outcome_groups/:id/outcomes`

### GET /api/v1/courses/:course_id/outcome_groups/:id/outcomes

**Scope:** `url:GET|/api/v1/courses/:course_id/outcome_groups/:id/outcomes`

A paginated list of the immediate OutcomeLink children of the outcome group.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| outcome_style |  | string | The detail level of the outcomes. Defaults to “abbrev”. Specify “full” for more information. |

Returns a list of [OutcomeLink](outcome_groups.html#OutcomeLink) objects

## Create/link an outcome

### POST /api/v1/global/outcome_groups/:id/outcomes

**Scope:** `url:POST|/api/v1/global/outcome_groups/:id/outcomes`

### PUT /api/v1/global/outcome_groups/:id/outcomes/:outcome_id

**Scope:** `url:PUT|/api/v1/global/outcome_groups/:id/outcomes/:outcome_id`

### POST /api/v1/accounts/:account_id/outcome_groups/:id/outcomes

**Scope:** `url:POST|/api/v1/accounts/:account_id/outcome_groups/:id/outcomes`

### PUT /api/v1/accounts/:account_id/outcome_groups/:id/outcomes/:outcome_id

**Scope:** `url:PUT|/api/v1/accounts/:account_id/outcome_groups/:id/outcomes/:outcome_id`

### POST /api/v1/courses/:course_id/outcome_groups/:id/outcomes

**Scope:** `url:POST|/api/v1/courses/:course_id/outcome_groups/:id/outcomes`

### PUT /api/v1/courses/:course_id/outcome_groups/:id/outcomes/:outcome_id

**Scope:** `url:PUT|/api/v1/courses/:course_id/outcome_groups/:id/outcomes/:outcome_id`

Link an outcome into the outcome group. The outcome to link can either be specified by a PUT to the link URL for a specific outcome (the outcome_id in the PUT URLs) or by supplying the information for a new outcome (title, description, ratings, mastery_points) in a POST to the collection.

If linking an existing outcome, the outcome_id must identify an outcome available to this context; i.e. an outcome owned by this group’s context, an outcome owned by an associated account, or a global outcome. With outcome_id present, any other parameters (except move_from) are ignored.

If defining a new outcome, the outcome is created in the outcome group’s context using the provided title, description, ratings, and mastery points; the title is required but all other fields are optional. The new outcome is then linked into the outcome group.

If ratings are provided when creating a new outcome, an embedded rubric criterion is included in the new outcome. This criterion’s mastery_points default to the maximum points in the highest rating if not specified in the mastery_points parameter. Any ratings lacking a description are given a default of “No description”. Any ratings lacking a point value are given a default of 0. If no ratings are provided, the mastery_points parameter is ignored.

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
<td>outcome_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The ID of the existing outcome to link.</p></td>
</tr>
<tr class="request-param">
<td>move_from</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The ID of the old outcome group. Only used if outcome_id is present.</p></td>
</tr>
<tr class="request-param">
<td>title</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The title of the new outcome. Required if outcome_id is absent.</p></td>
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
<td class="param-desc"><p>The description of the new outcome.</p></td>
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
<td class="param-desc"><p>The mastery threshold for the embedded rubric criterion.</p></td>
</tr>
<tr class="request-param">
<td>ratings[][description]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The description of a rating level for the embedded rubric criterion.</p></td>
</tr>
<tr class="request-param">
<td>ratings[][points]</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The points corresponding to a rating level for the embedded rubric criterion.</p></td>
</tr>
<tr class="request-param">
<td>calculation_method</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The new calculation method. Defaults to “decaying_average” if the Outcomes New Decaying Average Calculation Method FF is ENABLED then Defaults to “weighted_average”</p>
<p>Allowed values: <code class="enum">weighted_average</code>, <code class="enum">decaying_average</code>, <code class="enum">n_mastery</code>, <code class="enum">latest</code>, <code class="enum">highest</code>, <code class="enum">average</code></p></td>
</tr>
<tr class="request-param">
<td>calculation_int</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The new calculation int. Only applies if the calculation_method is “weighted_average”, “decaying_average” or “n_mastery”. Defaults to 65</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/accounts/1/outcome_groups/1/outcomes/1.json' \
     -X PUT \
     -H "Authorization: Bearer <token>"
```

####

``` example
curl 'https://<canvas>/api/v1/accounts/1/outcome_groups/1/outcomes.json' \
     -X POST \
     -F 'title=Outcome Title' \
     -F 'display_name=Title for reporting' \
     -F 'description=Outcome description' \
     -F 'vendor_guid=customid9000' \
     -F 'mastery_points=3' \
     -F 'calculation_method=decaying_average' \
     -F 'calculation_int=65' \
     -F 'ratings[][description]=Exceeds Expectations' \
     -F 'ratings[][points]=5' \
     -F 'ratings[][description]=Meets Expectations' \
     -F 'ratings[][points]=3' \
     -F 'ratings[][description]=Does Not Meet Expectations' \
     -F 'ratings[][points]=0' \
     -H "Authorization: Bearer <token>"
```

####

``` example
curl 'https://<canvas>/api/v1/accounts/1/outcome_groups/1/outcomes.json' \
     -X POST \
     --data-binary '{
           "title": "Outcome Title",
           "display_name": "Title for reporting",
           "description": "Outcome description",
           "vendor_guid": "customid9000",
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

Returns an [OutcomeLink](outcome_groups.html#OutcomeLink) object

## Unlink an outcome

### DELETE /api/v1/global/outcome_groups/:id/outcomes/:outcome_id

**Scope:** `url:DELETE|/api/v1/global/outcome_groups/:id/outcomes/:outcome_id`

### DELETE /api/v1/accounts/:account_id/outcome_groups/:id/outcomes/:outcome_id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/outcome_groups/:id/outcomes/:outcome_id`

### DELETE /api/v1/courses/:course_id/outcome_groups/:id/outcomes/:outcome_id

**Scope:** `url:DELETE|/api/v1/courses/:course_id/outcome_groups/:id/outcomes/:outcome_id`

Unlinking an outcome only deletes the outcome itself if this was the last link to the outcome in any group in any context. Aligned outcomes cannot be deleted; as such, if this is the last link to an aligned outcome, the unlinking will fail.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/accounts/1/outcome_groups/1/outcomes/1.json' \
     -X DELETE \
     -H "Authorization: Bearer <token>"
```

Returns an [OutcomeLink](outcome_groups.html#OutcomeLink) object

## List subgroups

### GET /api/v1/global/outcome_groups/:id/subgroups

**Scope:** `url:GET|/api/v1/global/outcome_groups/:id/subgroups`

### GET /api/v1/accounts/:account_id/outcome_groups/:id/subgroups

**Scope:** `url:GET|/api/v1/accounts/:account_id/outcome_groups/:id/subgroups`

### GET /api/v1/courses/:course_id/outcome_groups/:id/subgroups

**Scope:** `url:GET|/api/v1/courses/:course_id/outcome_groups/:id/subgroups`

A paginated list of the immediate OutcomeGroup children of the outcome group.

Returns a list of [OutcomeGroup](outcome_groups.html#OutcomeGroup) objects

## Create a subgroup

### POST /api/v1/global/outcome_groups/:id/subgroups

**Scope:** `url:POST|/api/v1/global/outcome_groups/:id/subgroups`

### POST /api/v1/accounts/:account_id/outcome_groups/:id/subgroups

**Scope:** `url:POST|/api/v1/accounts/:account_id/outcome_groups/:id/subgroups`

### POST /api/v1/courses/:course_id/outcome_groups/:id/subgroups

**Scope:** `url:POST|/api/v1/courses/:course_id/outcome_groups/:id/subgroups`

Creates a new empty subgroup under the outcome group with the given title and description.

#### Request Parameters:

| Parameter   |          | Type   | Description                               |
|-------------|----------|--------|-------------------------------------------|
| title       | Required | string | The title of the new outcome group.       |
| description |          | string | The description of the new outcome group. |
| vendor_guid |          | string | A custom GUID for the learning standard   |

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/accounts/1/outcome_groups/1/subgroups.json' \
     -X POST \
     -F 'title=Outcome Group Title' \
     -F 'description=Outcome group description' \
     -F 'vendor_guid=customid9000' \
     -H "Authorization: Bearer <token>"
```

####

``` example
curl 'https://<canvas>/api/v1/accounts/1/outcome_groups/1/subgroups.json' \
     -X POST \
     --data-binary '{
           "title": "Outcome Group Title",
           "description": "Outcome group description",
           "vendor_guid": "customid9000"
         }' \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <token>"
```

Returns an [OutcomeGroup](outcome_groups.html#OutcomeGroup) object

## Import an outcome group

### POST /api/v1/global/outcome_groups/:id/import

**Scope:** `url:POST|/api/v1/global/outcome_groups/:id/import`

### POST /api/v1/accounts/:account_id/outcome_groups/:id/import

**Scope:** `url:POST|/api/v1/accounts/:account_id/outcome_groups/:id/import`

### POST /api/v1/courses/:course_id/outcome_groups/:id/import

**Scope:** `url:POST|/api/v1/courses/:course_id/outcome_groups/:id/import`

Creates a new subgroup of the outcome group with the same title and description as the source group, then creates links in that new subgroup to the same outcomes that are linked in the source group. Recurses on the subgroups of the source group, importing them each in turn into the new subgroup.

Allows you to copy organizational structure, but does not create copies of the outcomes themselves, only new links.

The source group must be either global, from the same context as this outcome group, or from an associated account. The source group cannot be the root outcome group of its context.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| source_outcome_group_id | Required | integer | The ID of the source outcome group. |
| async |  | boolean | If true, perform action asynchronously. In that case, this endpoint will return a Progress object instead of an OutcomeGroup. Use the [progress endpoint](progress.html#method.progress.show "progress endpoint") to query the status of the operation. The imported outcome group id and url will be returned in the results of the Progress object as “outcome_group_id” and “outcome_group_url” |

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/accounts/2/outcome_groups/3/import.json' \
     -X POST \
     -F 'source_outcome_group_id=2' \
     -H "Authorization: Bearer <token>"
```

Returns an [OutcomeGroup](outcome_groups.html#OutcomeGroup) object
