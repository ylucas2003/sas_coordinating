# Announcement External Feeds API

External feeds represent RSS feeds that can be attached to a Course or Group, in order to automatically create announcements for each new item in the feed.

### An ExternalFeed object looks like:

``` example
{
  // The ID of the feed
  "id": 5,
  // The title of the feed, pulled from the feed itself. If the feed hasn't yet
  // been pulled, a temporary name will be synthesized based on the URL
  "display_name": "My Blog",
  // The HTTP/HTTPS URL to the feed
  "url": "http://example.com/myblog.rss",
  // If not null, only feed entries whose title contains this string will trigger
  // new posts in Canvas
  "header_match": "pattern",
  // When this external feed was added to Canvas
  "created_at": "2012-06-01T00:00:00-06:00",
  // The verbosity setting determines how much of the feed's content is imported
  // into Canvas as part of the posting. 'link_only' means that only the title and
  // a link to the item. 'truncate' means that a summary of the first portion of
  // the item body will be used. 'full' means that the full item body will be
  // used.
  "verbosity": "truncate"
}
```

## List external feeds

### GET /api/v1/courses/:course_id/external_feeds

**Scope:** `url:GET|/api/v1/courses/:course_id/external_feeds`

### GET /api/v1/groups/:group_id/external_feeds

**Scope:** `url:GET|/api/v1/groups/:group_id/external_feeds`

Returns the paginated list of External Feeds this course or group.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/<course_id>/external_feeds \
     -H 'Authorization: Bearer <token>'
```

Returns a list of [ExternalFeed](announcement_external_feeds.html#ExternalFeed) objects

## Create an external feed

### POST /api/v1/courses/:course_id/external_feeds

**Scope:** `url:POST|/api/v1/courses/:course_id/external_feeds`

### POST /api/v1/groups/:group_id/external_feeds

**Scope:** `url:POST|/api/v1/groups/:group_id/external_feeds`

Create a new external feed for the course or group.

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
<td>url</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The url to the external rss or atom feed</p></td>
</tr>
<tr class="request-param">
<td>header_match</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If given, only feed entries that contain this string in their title will be imported</p></td>
</tr>
<tr class="request-param">
<td>verbosity</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Defaults to “full”</p>
<p>Allowed values: <code class="enum">full</code>, <code class="enum">truncate</code>, <code class="enum">link_only</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/courses/<course_id>/external_feeds \
    -F url='http://example.com/rss.xml' \
    -F header_match='news flash!' \
    -F verbosity='full' \
    -H 'Authorization: Bearer <token>'
```

Returns an [ExternalFeed](announcement_external_feeds.html#ExternalFeed) object

## Delete an external feed

### DELETE /api/v1/courses/:course_id/external_feeds/:external_feed_id

**Scope:** `url:DELETE|/api/v1/courses/:course_id/external_feeds/:external_feed_id`

### DELETE /api/v1/groups/:group_id/external_feeds/:external_feed_id

**Scope:** `url:DELETE|/api/v1/groups/:group_id/external_feeds/:external_feed_id`

Deletes the external feed.

#### Example Request:

####

``` example
curl -X DELETE https://<canvas>/api/v1/courses/<course_id>/external_feeds/<feed_id> \
     -H 'Authorization: Bearer <token>'
```

Returns an [ExternalFeed](announcement_external_feeds.html#ExternalFeed) object
