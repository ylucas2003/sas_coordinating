# Peer Reviews API

### A PeerReview object looks like:

``` example
{
  // The assessors user id
  "assessor_id": 23,
  // The id for the asset associated with this Peer Review
  "asset_id": 13,
  // The type of the asset
  "asset_type": "Submission",
  // The id of the Peer Review
  "id": 1,
  // The user id for the owner of the asset
  "user_id": 7,
  // The state of the Peer Review, either 'assigned' or 'completed'
  "workflow_state": "assigned",
  // the User object for the owner of the asset if the user include parameter is
  // provided (see user API) (optional)
  "user": "User",
  // The User object for the assessor if the user include parameter is provided
  // (see user API) (optional)
  "assessor": "User",
  // The submission comments associated with this Peer Review if the
  // submission_comment include parameter is provided (see submissions API)
  // (optional)
  "submission_comments": "SubmissionComment"
}
```

## Get all Peer Reviews

### GET /api/v1/courses/:course_id/assignments/:assignment_id/peer_reviews

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/peer_reviews`

### GET /api/v1/sections/:section_id/assignments/:assignment_id/peer_reviews

**Scope:** `url:GET|/api/v1/sections/:section_id/assignments/:assignment_id/peer_reviews`

### GET /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:submission_id/peer_reviews

**Scope:** `url:GET|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:submission_id/peer_reviews`

### GET /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:submission_id/peer_reviews

**Scope:** `url:GET|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:submission_id/peer_reviews`

Get a list of all Peer Reviews for this assignment

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
<td class="param-desc"><p>Associations to include with the peer review.</p>
<p>Allowed values: <code class="enum">submission_comments</code>, <code class="enum">user</code></p></td>
</tr>
</tbody>
</table>

Returns a list of [PeerReview](peer_reviews.html#PeerReview) objects

## Create Peer Review

### POST /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:submission_id/peer_reviews

**Scope:** `url:POST|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:submission_id/peer_reviews`

### POST /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:submission_id/peer_reviews

**Scope:** `url:POST|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:submission_id/peer_reviews`

Create a peer review for the assignment

#### Request Parameters:

| Parameter |          | Type    | Description                                      |
|-----------|----------|---------|--------------------------------------------------|
| user_id   | Required | integer | user_id to assign as reviewer on this assignment |

Returns a [PeerReview](peer_reviews.html#PeerReview) object

## Delete Peer Review

### DELETE /api/v1/courses/:course_id/assignments/:assignment_id/submissions/:submission_id/peer_reviews

**Scope:** `url:DELETE|/api/v1/courses/:course_id/assignments/:assignment_id/submissions/:submission_id/peer_reviews`

### DELETE /api/v1/sections/:section_id/assignments/:assignment_id/submissions/:submission_id/peer_reviews

**Scope:** `url:DELETE|/api/v1/sections/:section_id/assignments/:assignment_id/submissions/:submission_id/peer_reviews`

Delete a peer review for the assignment

#### Request Parameters:

| Parameter |          | Type    | Description                                      |
|-----------|----------|---------|--------------------------------------------------|
| user_id   | Required | integer | user_id to delete as reviewer on this assignment |

Returns a [PeerReview](peer_reviews.html#PeerReview) object
