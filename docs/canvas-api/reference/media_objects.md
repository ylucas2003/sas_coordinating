# Media Objects API

Closed captions added to a video MediaObject

When you upload or record webcam video/audio to kaltura, it makes a Media Object

### A MediaTrack object looks like:

``` example
{
  "id": 42,
  "user_id": 1,
  "media_object_id": 14,
  "kind": "subtitles",
  "locale": "es",
  "content": "1]\\n00:00:00,000 --> 00:00:01,251\nI'm spanish",
  "created_at": "Mon, 24 Feb 2020 16:04:02 EST -05:00",
  "updated_at": "Mon, 24 Feb 2020 16:59:05 EST -05:00",
  "webvtt_content": "WEBVTT\n\n1]\\n00:00:00.000 --> 00:00:01.251\nI'm spanish"
}
```

### A MediaObject object looks like:

``` example
{
  // whether or not the current user can upload media_tracks (subtitles) to this Media Object
  "can_add_captions": true,
  "user_entered_title": "User Entered Title",
  "title": "filename-or-user-title-or-untitled",
  "media_id": "m-JYmy6TLsHkxcrhgYmqa7XW1HCH3wEYc",
  "media_type": "video",
  // an array of all the media_tracks uploaded to this Media Object
  "media_tracks": [{
    "kind": "captions",
    "created_at": "2012-09-27T16:46:50-06:00",
    "updated_at": "2012-09-27T16:46:50-06:00",
    "url": "https://<canvas>/media_objects/0_r949z9lk/media_tracks/1",
    "id": 1,
    "locale": "af"
  }, {
    "kind": "subtitles",
    "created_at": "2012-09-27T20:29:17-06:00",
    "updated_at": "2012-09-27T20:29:17-06:00",
    "url": "https://<canvas>/media_objects/0_r949z9lk/media_tracks/14",
    "id": 14,
    "locale": "cs"
  }],
  // an array of all the transcoded files (flavors) available for this Media Object
  "media_sources": [{
    "height": "240",
    "width": "336",
    "content_type": "video/mp4",
    "containerFormat": "isom",
    "url": "http://example.com/p/100/sp/10000/download/entry_id/0_r949z9lk/flavor/0_xdp3qrpc/ks/MjUxNjY4MjlhMTkxN2VmNTA0OGRkZjY2ODNjMjgxNTkwYWE3NGMyNHwxMDA7MTAwOzEzNDkyNzU5MDY7MDsxMzQ5MTg5NTA2LjUxOTk7O2Rvd25sb2FkOjBfcjk0OXo5bGs7/relocate/download.mp4",
    "bitrate": "382",
    "size": "204",
    "isOriginal": "0",
    "fileExt": "mp4"
  }, {
    "height": "252",
    "width": "336",
    "content_type": "video/x-flv",
    "containerFormat": "flash video",
    "url": "http://example.com/p/100/sp/10000/download/entry_id/0_r949z9lk/flavor/0_0f2x4odx/ks/NmY2M2Q2MDdhMjBlMzA2ZmRhMWZjZjAxNWUyOTg0MzA5MDI5NGE4ZXwxMDA7MTAwOzEzNDkyNzU5MDY7MDsxMzQ5MTg5NTA2LjI5MDM7O2Rvd25sb2FkOjBfcjk0OXo5bGs7/relocate/download.flv",
    "bitrate": "797",
    "size": "347",
    "isOriginal": "1",
    "fileExt": "flv"
  }]
}
```

## List media tracks for a Media Object or Attachment

### GET /api/v1/media_objects/:media_object_id/media_tracks

**Scope:** `url:GET|/api/v1/media_objects/:media_object_id/media_tracks`

### GET /api/v1/media_attachments/:attachment_id/media_tracks

**Scope:** `url:GET|/api/v1/media_attachments/:attachment_id/media_tracks`

List the media tracks associated with a media object or attachment

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
<td class="param-desc"><p>By default, index returns id, locale, kind, media_object_id, and user_id for each of the result MediaTracks. Use include[] to add additional fields. For example include[]=content</p>
<p>Allowed values: <code class="enum">content</code>, <code class="enum">webvtt_content</code>, <code class="enum">updated_at</code>, <code class="enum">created_at</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/media_objects/<media_object_id>/media_tracks?include[]=content
    -H 'Authorization: Bearer <token>'
```

####

``` example
curl https://<canvas>/api/v1/media_attachments/<attachment_id>/media_tracks?include[]=content
    -H 'Authorization: Bearer <token>'
```

Returns a list of [MediaTrack](media_objects.html#MediaTrack) objects

## Update Media Tracks

### PUT /api/v1/media_objects/:media_object_id/media_tracks

**Scope:** `url:PUT|/api/v1/media_objects/:media_object_id/media_tracks`

### PUT /api/v1/media_attachments/:attachment_id/media_tracks

**Scope:** `url:PUT|/api/v1/media_attachments/:attachment_id/media_tracks`

Replace the media tracks associated with a media object or attachment with the array of tracks provided in the body. Update will delete any existing tracks not listed, leave untouched any tracks with no content field, and update or create tracks with a content field.

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
<td class="param-desc"><p>By default, an update returns id, locale, kind, media_object_id, and user_id for each of the result MediaTracks. Use include[] to add additional fields. For example include[]=content</p>
<p>Allowed values: <code class="enum">content</code>, <code class="enum">webvtt_content</code>, <code class="enum">updated_at</code>, <code class="enum">created_at</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl -X PUT https://<canvas>/api/v1/media_objects/<media_object_id>/media_tracks?include[]=content \
  -H 'Authorization: Bearer <token>'
  -d '[{"locale": "en"}, {"locale": "af","content": "1\r\n00:00:00,000 --> 00:00:01,251\r\nThis is the content\r\n"}]'
```

####

``` example
curl -X PUT https://<canvas>/api/v1/media_attachments/<attachment_id>/media_tracks?include[]=content \
  -H 'Authorization: Bearer <token>'
  -d '[{"locale": "en"}, {"locale": "af","content": "1\r\n00:00:00,000 --> 00:00:01,251\r\nThis is the content\r\n"}]'
```

Returns a list of [MediaTrack](media_objects.html#MediaTrack) objects

## List Media Objects

### GET /api/v1/media_objects

**Scope:** `url:GET|/api/v1/media_objects`

### GET /api/v1/courses/:course_id/media_objects

**Scope:** `url:GET|/api/v1/courses/:course_id/media_objects`

### GET /api/v1/groups/:group_id/media_objects

**Scope:** `url:GET|/api/v1/groups/:group_id/media_objects`

### GET /api/v1/media_attachments

**Scope:** `url:GET|/api/v1/media_attachments`

### GET /api/v1/courses/:course_id/media_attachments

**Scope:** `url:GET|/api/v1/courses/:course_id/media_attachments`

### GET /api/v1/groups/:group_id/media_attachments

**Scope:** `url:GET|/api/v1/groups/:group_id/media_attachments`

Returns media objects created by the user making the request. When using the second version, returns media objects associated with the given course.

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
<td>sort</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Field to sort on. Default is “title”</p>
<dl>
<dt>title</dt>
<dd>
<p>sorts on user_entered_title if available, title if not.</p>
</dd>
<dt>created_at</dt>
<dd>
<p>sorts on the object’s creation time.</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">title</code>, <code class="enum">created_at</code></p></td>
</tr>
<tr class="request-param">
<td>order</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Sort direction. Default is “asc”</p>
<p>Allowed values: <code class="enum">asc</code>, <code class="enum">desc</code></p></td>
</tr>
<tr class="request-param">
<td>exclude[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Array of data to exclude. By excluding “sources” and “tracks”, the api will not need to query kaltura, which greatly speeds up its response.</p>
<dl>
<dt>sources</dt>
<dd>
<p>Do not query kaltura for media_sources</p>
</dd>
<dt>tracks</dt>
<dd>
<p>Do not query kaltura for media_tracks</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">sources</code>, <code class="enum">tracks</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/media_objects?exclude[]=sources&exclude[]=tracks \
     -H 'Authorization: Bearer <token>'

curl https://<canvas>/api/v1/courses/17/media_objects?exclude[]=sources&exclude[]=tracks \
     -H 'Authorization: Bearer <token>'
```

Returns a list of [MediaObject](media_objects.html#MediaObject) objects

## Update Media Object

### PUT /api/v1/media_objects/:media_object_id

**Scope:** `url:PUT|/api/v1/media_objects/:media_object_id`

### PUT /api/v1/media_attachments/:attachment_id

**Scope:** `url:PUT|/api/v1/media_attachments/:attachment_id`
