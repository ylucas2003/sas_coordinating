# Content Shares API

API for creating, accessing and updating Content Sharing. Content shares are used to share content directly between users.

### A ContentShare object looks like:

``` example
// Content shared between users
{
  // The id of the content share for the current user
  "id": 1,
  // The name of the shared content
  "name": "War of 1812 homework",
  // The type of content that was shared. Can be assignment, discussion_topic,
  // page, quiz, module, or module_item.
  "content_type": "assignment",
  // The datetime the content was shared with this user.
  "created_at": "2017-05-09T10:12:00Z",
  // The datetime the content was updated.
  "updated_at": "2017-05-09T10:12:00Z",
  // The id of the user who sent or received the content share.
  "user_id": 1578941,
  // The user who shared the content. This field is provided only to receivers; it
  // is not populated in the sender's list of sent content shares.
  "sender": {"id":1,"display_name":"Matilda Vargas","avatar_image_url":"http:\/\/localhost:3000\/image_url","html_url":"http:\/\/localhost:3000\/users\/1"},
  // An Array of users the content is shared with.  This field is provided only to
  // senders; an empty array will be returned for the receiving users.
  "receivers": [{"id":1,"display_name":"Jon Snow","avatar_image_url":"http:\/\/localhost:3000\/image_url2","html_url":"http:\/\/localhost:3000\/users\/2"}],
  // The course the content was originally shared from.
  "source_course": {"id":787,"name":"History 105"},
  // Whether the recipient has viewed the content share.
  "read_state": "read",
  // The content export record associated with this content share
  "content_export": {"id":42}
}
```

## Create a content share

### POST /api/v1/users/:user_id/content_shares

**Scope:** `url:POST|/api/v1/users/:user_id/content_shares`

Share content directly between two or more users

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
<td>receiver_ids</td>
<td>Required</td>
<td>Array</td>
<td class="param-desc"><p>IDs of users to share the content with.</p></td>
</tr>
<tr class="request-param">
<td>content_type</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>Type of content you are sharing.</p>
<p>Allowed values: <code class="enum">assignment</code>, <code class="enum">discussion_topic</code>, <code class="enum">page</code>, <code class="enum">quiz</code>, <code class="enum">module</code>, <code class="enum">module_item</code></p></td>
</tr>
<tr class="request-param">
<td>content_id</td>
<td>Required</td>
<td>integer</td>
<td class="param-desc"><p>The id of the content that you are sharing</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/users/self/content_shares \
      -d 'content_type=assignment' \
      -d 'content_id=1' \
      -H 'Authorization: Bearer <token>' \
      -X POST
```

Returns a [ContentShare](content_shares.html#ContentShare) object

## List content shares

### GET /api/v1/users/:user_id/content_shares/sent

**Scope:** `url:GET|/api/v1/users/:user_id/content_shares/sent`

### GET /api/v1/users/:user_id/content_shares/received

**Scope:** `url:GET|/api/v1/users/:user_id/content_shares/received`

Return a paginated list of content shares a user has sent or received. Use `self` as the user_id to retrieve your own content shares. Only linked observers and administrators may view other users’ content shares.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/users/self/content_shares/received'
```

Returns a list of [ContentShare](content_shares.html#ContentShare) objects

## Get unread shares count

### GET /api/v1/users/:user_id/content_shares/unread_count

**Scope:** `url:GET|/api/v1/users/:user_id/content_shares/unread_count`

Return the number of content shares a user has received that have not yet been read. Use `self` as the user_id to retrieve your own content shares. Only linked observers and administrators may view other users’ content shares.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/users/self/content_shares/unread_count'
```

## Get content share

### GET /api/v1/users/:user_id/content_shares/:id

**Scope:** `url:GET|/api/v1/users/:user_id/content_shares/:id`

Return information about a single content share. You may use `self` as the user_id to retrieve your own content share.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/users/self/content_shares/123'
```

Returns a [ContentShare](content_shares.html#ContentShare) object

## Remove content share

### DELETE /api/v1/users/:user_id/content_shares/:id

**Scope:** `url:DELETE|/api/v1/users/:user_id/content_shares/:id`

Remove a content share from your list. Use `self` as the user_id. Note that this endpoint does not delete other users’ copies of the content share.

#### Example Request:

####

``` example
curl -X DELETE 'https://<canvas>/api/v1/users/self/content_shares/123'
```

## Add users to content share

### POST /api/v1/users/:user_id/content_shares/:id/add_users

**Scope:** `url:POST|/api/v1/users/:user_id/content_shares/:id/add_users`

Send a previously created content share to additional users

#### Request Parameters:

| Parameter    |     | Type  | Description                             |
|--------------|-----|-------|-----------------------------------------|
| receiver_ids |     | Array | IDs of users to share the content with. |

#### Example Request:

####

``` example
curl -X POST 'https://<canvas>/api/v1/users/self/content_shares/123/add_users?receiver_ids[]=789'
```

Returns a [ContentShare](content_shares.html#ContentShare) object

## Update a content share

### PUT /api/v1/users/:user_id/content_shares/:id

**Scope:** `url:PUT|/api/v1/users/:user_id/content_shares/:id`

Mark a content share read or unread

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
<td>read_state</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Read state for the content share</p>
<p>Allowed values: <code class="enum">read</code>, <code class="enum">unread</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl -X PUT 'https://<canvas>/api/v1/users/self/content_shares/123?read_state=read'
```

Returns a [ContentShare](content_shares.html#ContentShare) object
