# Search API

## Find recipients

### GET /api/v1/conversations/find_recipients

**Scope:** `url:GET|/api/v1/conversations/find_recipients`

### GET /api/v1/search/recipients

**Scope:** `url:GET|/api/v1/search/recipients`

Find valid recipients (users, courses and groups) that the current user can send messages to. The /api/v1/search/recipients path is the preferred endpoint, /api/v1/conversations/find_recipients is deprecated.

Pagination is supported.

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
<td>search</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Search terms used for matching users/courses/groups (e.g. “bob smith”). If multiple terms are given (separated via whitespace), only results matching all terms will be returned.</p></td>
</tr>
<tr class="request-param">
<td>context</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Limit the search to a particular course/group (e.g. “course_3” or “group_4”).</p></td>
</tr>
<tr class="request-param">
<td>exclude[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Array of ids to exclude from the search. These may be user ids or course/group ids prefixed with “course_” or “group_” respectively, e.g. exclude[]=1&amp;exclude=2&amp;exclude[]=course_3</p></td>
</tr>
<tr class="request-param">
<td>type</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Limit the search just to users or contexts (groups/courses).</p>
<p>Allowed values: <code class="enum">user</code>, <code class="enum">context</code></p></td>
</tr>
<tr class="request-param">
<td>user_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>Search for a specific user id. This ignores the other above parameters, and will never return more than one result.</p></td>
</tr>
<tr class="request-param">
<td>from_conversation_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>When searching by user_id, only users that could be normally messaged by this user will be returned. This parameter allows you to specify a conversation that will be referenced for a shared context – if both the current user and the searched user are in the conversation, the user will be returned. This is used to start new side conversations.</p></td>
</tr>
<tr class="request-param">
<td>permissions[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Array of permission strings to be checked for each matched context (e.g. “send_messages”). This argument determines which permissions may be returned in the response; it won’t prevent contexts from being returned if they don’t grant the permission(s).</p></td>
</tr>
</tbody>
</table>

#### API response field:

-  id

  The unique identifier for the user/context. For groups/courses, the id is prefixed by “group\_”/“course\_” respectively.

-  name

  The name of the context or short name of the user

-  full_name

  Only set for users. The full name of the user

-  avatar_url

  Avatar image url for the user/context

-  type

  “context”\|“course”\|“section”\|“group”\|“user”\|null
  Type of recipients to return, defaults to null (all). “context” encompasses “course”, “section” and “group”

-  types\[\]

  Array of recipient types to return (see type above), e.g. [types\[\]=user&types]()=course

-  user_count

  Only set for contexts, indicates number of messageable users

-  common_courses

  Only set for users. Hash of course ids and enrollment types for each course to show what they share with this user

-  common_groups

  Only set for users. Hash of group ids and enrollment types for each group to show what they share with this user

-  permissions\[\]

  Only set for contexts. Mapping of requested permissions that the context grants the current user, e.g. { send_messages: true }

#### Example Response:

####

``` example
[
  {"id": "group_1", "name": "the group", "type": "context", "user_count": 3},
  {"id": 2, "name": "greg", "full_name": "greg jones", "common_courses": {}, "common_groups": {"1": ["Member"]}}
]
```

## List all courses

### GET /api/v1/search/all_courses

**Scope:** `url:GET|/api/v1/search/all_courses`

A paginated list of all courses visible in the public index

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| search |  | string | Search terms used for matching users/courses/groups (e.g. “bob smith”). If multiple terms are given (separated via whitespace), only results matching all terms will be returned. |
| public_only |  | boolean | Only return courses with public content. Defaults to false. |
| open_enrollment_only |  | boolean | Only return courses that allow self enrollment. Defaults to false. |
