# Bookmarks API

### A Bookmark object looks like:

``` example
{
  "id": 1,
  "name": "Biology 101",
  "url": "/courses/1",
  "position": 1,
  "data": {"active_tab":1}
}
```

## List bookmarks

### GET /api/v1/users/self/bookmarks

**Scope:** `url:GET|/api/v1/users/self/bookmarks`

Returns the paginated list of bookmarks.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/users/self/bookmarks' \
     -H 'Authorization: Bearer <token>'
```

Returns a list of [Bookmark](bookmarks.html#Bookmark) objects

## Create bookmark

### POST /api/v1/users/self/bookmarks

**Scope:** `url:POST|/api/v1/users/self/bookmarks`

Creates a bookmark.

#### Request Parameters:

| Parameter |     | Type    | Description                                           |
|-----------|-----|---------|-------------------------------------------------------|
| name      |     | string  | The name of the bookmark                              |
| url       |     | string  | The url of the bookmark                               |
| position  |     | integer | The position of the bookmark. Defaults to the bottom. |
| data      |     | string  | The data associated with the bookmark                 |

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/users/self/bookmarks' \
     -F 'name=Biology 101' \
     -F 'url=/courses/1' \
     -H 'Authorization: Bearer <token>'
```

Returns a [Bookmark](bookmarks.html#Bookmark) object

## Get bookmark

### GET /api/v1/users/self/bookmarks/:id

**Scope:** `url:GET|/api/v1/users/self/bookmarks/:id`

Returns the details for a bookmark.

#### Example Request:

####

``` example
curl 'https://<canvas>/api/v1/users/self/bookmarks/1' \
     -H 'Authorization: Bearer <token>'
```

Returns a [Bookmark](bookmarks.html#Bookmark) object

## Update bookmark

### PUT /api/v1/users/self/bookmarks/:id

**Scope:** `url:PUT|/api/v1/users/self/bookmarks/:id`

Updates a bookmark

#### Request Parameters:

| Parameter |     | Type    | Description                                           |
|-----------|-----|---------|-------------------------------------------------------|
| name      |     | string  | The name of the bookmark                              |
| url       |     | string  | The url of the bookmark                               |
| position  |     | integer | The position of the bookmark. Defaults to the bottom. |
| data      |     | string  | The data associated with the bookmark                 |

#### Example Request:

####

``` example
curl -X PUT 'https://<canvas>/api/v1/users/self/bookmarks/1' \
     -F 'name=Biology 101' \
     -F 'url=/courses/1' \
     -H 'Authorization: Bearer <token>'
```

Returns a [Folder](files.html#Folder) object

## Delete bookmark

### DELETE /api/v1/users/self/bookmarks/:id

**Scope:** `url:DELETE|/api/v1/users/self/bookmarks/:id`

Deletes a bookmark

#### Example Request:

####

``` example
curl -X DELETE 'https://<canvas>/api/v1/users/self/bookmarks/1' \
     -H 'Authorization: Bearer <token>'
```
