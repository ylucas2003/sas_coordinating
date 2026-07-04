# Pages API

Pages are rich content associated with Courses and Groups in Canvas. The Pages API allows you to create, retrieve, update, and delete pages.

**Note on page identifiers**

Most Pages API endpoints accept identification of the Page as either a URL or an ID. In ambiguous cases, the URL takes precedence.

For example, if you have a page whose ID is 7 and another whose ID is 8 and whose URL is "7", the endpoint `/api/v1/courses/:course_id/pages/7` will refer to the latter (ID 8). To explicitly request by ID, you can use the form `/api/v1/courses/:course_id/pages/page_id:7`.

### A Page object looks like:

``` example
{
  // the ID of the page
  "page_id": 1,
  // the unique locator for the page
  "url": "my-page-title",
  // the title of the page
  "title": "My Page Title",
  // the creation date for the page
  "created_at": "2012-08-06T16:46:33-06:00",
  // the date the page was last updated
  "updated_at": "2012-08-08T14:25:20-06:00",
  // (DEPRECATED) whether this page is hidden from students (note: this is always
  // reflected as the inverse of the published value)
  "hide_from_students": false,
  // roles allowed to edit the page; comma-separated list comprising a combination
  // of 'teachers', 'students', 'members', and/or 'public' if not supplied, course
  // defaults are used
  "editing_roles": "teachers,students",
  // the User who last edited the page (this may not be present if the page was
  // imported from another system)
  "last_edited_by": null,
  // the page content, in HTML (present when requesting a single page; optionally
  // included when listing pages)
  "body": "<p>Page Content</p>",
  // whether the page is published (true) or draft state (false).
  "published": true,
  // scheduled publication date for this page
  "publish_at": "2022-09-01T00:00:00",
  // whether this page is the front page for the wiki
  "front_page": false,
  // Whether or not this is locked for the user.
  "locked_for_user": false,
  // (Optional) Information for the user about the lock. Present when
  // locked_for_user is true.
  "lock_info": null,
  // (Optional) An explanation of why this is locked for the user. Present when
  // locked_for_user is true.
  "lock_explanation": "This page is locked until September 1 at 12:00am",
  // The editor used to create and edit this page. May be one of 'rce' or
  // 'block_editor'.
  "editor": "rce",
  // The block editor attributes for this page. (optionally included, and only if
  // this is a block editor created page)
  "block_editor_attributes": {"id":278,"version":"0.2","blocks":"{...block json here...}"}
}
```

### A PageRevision object looks like:

``` example
{
  // an identifier for this revision of the page
  "revision_id": 7,
  // the time when this revision was saved
  "updated_at": "2012-08-07T11:23:58-06:00",
  // whether this is the latest revision or not
  "latest": true,
  // the User who saved this revision, if applicable (this may not be present if
  // the page was imported from another system)
  "edited_by": null,
  // the following fields are not included in the index action and may be omitted
  // from the show action via summary=1 the historic url of the page
  "url": "old-page-title",
  // the historic page title
  "title": "Old Page Title",
  // the historic page contents
  "body": "<p>Old Page Content</p>"
}
```

## Show front page

### GET /api/v1/courses/:course_id/front_page

**Scope:** `url:GET|/api/v1/courses/:course_id/front_page`

### GET /api/v1/groups/:group_id/front_page

**Scope:** `url:GET|/api/v1/groups/:group_id/front_page`

Retrieve the content of the front page

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
     https://<canvas>/api/v1/courses/123/front_page
```

Returns a [Page](pages.html#Page) object

## Duplicate page

### POST /api/v1/courses/:course_id/pages/:url_or_id/duplicate

**Scope:** `url:POST|/api/v1/courses/:course_id/pages/:url_or_id/duplicate`

Duplicate a wiki page

#### Example Request:

####

``` example
curl -X POST -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/courses/123/pages/14/duplicate
```

Returns a [Page](pages.html#Page) object

## Update/create front page

### PUT /api/v1/courses/:course_id/front_page

**Scope:** `url:PUT|/api/v1/courses/:course_id/front_page`

### PUT /api/v1/groups/:group_id/front_page

**Scope:** `url:PUT|/api/v1/groups/:group_id/front_page`

Update the title or contents of the front page

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
<td>wiki_page[title]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The title for the new page. NOTE: changing a page’s title will change its url. The updated url will be returned in the result.</p></td>
</tr>
<tr class="request-param">
<td>wiki_page[body]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The content for the new page.</p></td>
</tr>
<tr class="request-param">
<td>wiki_page[editing_roles]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Which user roles are allowed to edit this page. Any combination of these roles is allowed (separated by commas).</p>
<dl>
<dt>“teachers”</dt>
<dd>
<p>Allows editing by teachers in the course.</p>
</dd>
<dt>“students”</dt>
<dd>
<p>Allows editing by students in the course.</p>
</dd>
<dt>“members”</dt>
<dd>
<p>For group wikis, allows editing by members of the group.</p>
</dd>
<dt>“public”</dt>
<dd>
<p>Allows editing by any user.</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">teachers</code>, <code class="enum">students</code>, <code class="enum">members</code>, <code class="enum">public</code></p></td>
</tr>
<tr class="request-param">
<td>wiki_page[notify_of_update]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether participants should be notified when this page changes.</p></td>
</tr>
<tr class="request-param">
<td>wiki_page[published]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether the page is published (true) or draft state (false).</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl -X PUT -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/courses/123/front_page \
-d wiki_page[body]=Updated+body+text
```

Returns a [Page](pages.html#Page) object

## List pages

### GET /api/v1/courses/:course_id/pages

**Scope:** `url:GET|/api/v1/courses/:course_id/pages`

### GET /api/v1/groups/:group_id/pages

**Scope:** `url:GET|/api/v1/groups/:group_id/pages`

A paginated list of the wiki pages associated with a course or group

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
<td class="param-desc"><p>Sort results by this field.</p>
<p>Allowed values: <code class="enum">title</code>, <code class="enum">created_at</code>, <code class="enum">updated_at</code></p></td>
</tr>
<tr class="request-param">
<td>order</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The sorting order. Defaults to ‘asc’.</p>
<p>Allowed values: <code class="enum">asc</code>, <code class="enum">desc</code></p></td>
</tr>
<tr class="request-param">
<td>search_term</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The partial title of the pages to match and return.</p></td>
</tr>
<tr class="request-param">
<td>published</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, include only published paqes. If false, exclude published pages. If not present, do not filter on published status.</p></td>
</tr>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><ul>
<li><p>“enrollments”: Optionally include the page body with each Page.</p></li>
</ul>
<p>If this is a block_editor page, returns the block_editor_attributes.</p>
<p>Allowed values: <code class="enum">body</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
     https://<canvas>/api/v1/courses/123/pages?sort=title&order=asc
```

Returns a list of [Page](pages.html#Page) objects

## Create page

### POST /api/v1/courses/:course_id/pages

**Scope:** `url:POST|/api/v1/courses/:course_id/pages`

### POST /api/v1/groups/:group_id/pages

**Scope:** `url:POST|/api/v1/groups/:group_id/pages`

Create a new wiki page

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
<td>wiki_page[title]</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The title for the new page.</p></td>
</tr>
<tr class="request-param">
<td>wiki_page[body]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The content for the new page.</p></td>
</tr>
<tr class="request-param">
<td>wiki_page[editing_roles]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Which user roles are allowed to edit this page. Any combination of these roles is allowed (separated by commas).</p>
<dl>
<dt>“teachers”</dt>
<dd>
<p>Allows editing by teachers in the course.</p>
</dd>
<dt>“students”</dt>
<dd>
<p>Allows editing by students in the course.</p>
</dd>
<dt>“members”</dt>
<dd>
<p>For group wikis, allows editing by members of the group.</p>
</dd>
<dt>“public”</dt>
<dd>
<p>Allows editing by any user.</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">teachers</code>, <code class="enum">students</code>, <code class="enum">members</code>, <code class="enum">public</code></p></td>
</tr>
<tr class="request-param">
<td>wiki_page[notify_of_update]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether participants should be notified when this page changes.</p></td>
</tr>
<tr class="request-param">
<td>wiki_page[published]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether the page is published (true) or draft state (false).</p></td>
</tr>
<tr class="request-param">
<td>wiki_page[front_page]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set an unhidden page as the front page (if true)</p></td>
</tr>
<tr class="request-param">
<td>wiki_page[publish_at]</td>
<td></td>
<td>DateTime</td>
<td class="param-desc"><p>Schedule a future date/time to publish the page. This will have no effect unless the “Scheduled Page Publication” feature is enabled in the account. If a future date is supplied, the page will be unpublished and wiki_page will be ignored.</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl -X POST -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/courses/123/pages \
-d wiki_page[title]=New+page
-d wiki_page[body]=New+body+text
```

Returns a [Page](pages.html#Page) object

## Show page

### GET /api/v1/courses/:course_id/pages/:url_or_id

**Scope:** `url:GET|/api/v1/courses/:course_id/pages/:url_or_id`

### GET /api/v1/groups/:group_id/pages/:url_or_id

**Scope:** `url:GET|/api/v1/groups/:group_id/pages/:url_or_id`

Retrieve the content of a wiki page

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
     https://<canvas>/api/v1/courses/123/pages/the-page-identifier
```

Returns a [Page](pages.html#Page) object

## Update/create page

### PUT /api/v1/courses/:course_id/pages/:url_or_id

**Scope:** `url:PUT|/api/v1/courses/:course_id/pages/:url_or_id`

### PUT /api/v1/groups/:group_id/pages/:url_or_id

**Scope:** `url:PUT|/api/v1/groups/:group_id/pages/:url_or_id`

Update the title or contents of a wiki page

NOTE: You cannot specify the ID when creating a page. If you pass a numeric value as the page identifier and that does not represent a page ID that already exists, it will be interpreted as a URL.

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
<td>wiki_page[title]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The title for the new page. NOTE: changing a page’s title will change its url. The updated url will be returned in the result.</p></td>
</tr>
<tr class="request-param">
<td>wiki_page[body]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The content for the new page.</p></td>
</tr>
<tr class="request-param">
<td>wiki_page[editing_roles]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Which user roles are allowed to edit this page. Any combination of these roles is allowed (separated by commas).</p>
<dl>
<dt>“teachers”</dt>
<dd>
<p>Allows editing by teachers in the course.</p>
</dd>
<dt>“students”</dt>
<dd>
<p>Allows editing by students in the course.</p>
</dd>
<dt>“members”</dt>
<dd>
<p>For group wikis, allows editing by members of the group.</p>
</dd>
<dt>“public”</dt>
<dd>
<p>Allows editing by any user.</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">teachers</code>, <code class="enum">students</code>, <code class="enum">members</code>, <code class="enum">public</code></p></td>
</tr>
<tr class="request-param">
<td>wiki_page[notify_of_update]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether participants should be notified when this page changes.</p></td>
</tr>
<tr class="request-param">
<td>wiki_page[published]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Whether the page is published (true) or draft state (false).</p></td>
</tr>
<tr class="request-param">
<td>wiki_page[publish_at]</td>
<td></td>
<td>DateTime</td>
<td class="param-desc"><p>Schedule a future date/time to publish the page. This will have no effect unless the “Scheduled Page Publication” feature is enabled in the account. If a future date is set and the page is already published, it will be unpublished.</p></td>
</tr>
<tr class="request-param">
<td>wiki_page[front_page]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Set an unhidden page as the front page (if true)</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl -X PUT -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/courses/123/pages/the-page-identifier \
-d 'wiki_page[body]=Updated+body+text'
```

Returns a [Page](pages.html#Page) object

## Delete page

### DELETE /api/v1/courses/:course_id/pages/:url_or_id

**Scope:** `url:DELETE|/api/v1/courses/:course_id/pages/:url_or_id`

### DELETE /api/v1/groups/:group_id/pages/:url_or_id

**Scope:** `url:DELETE|/api/v1/groups/:group_id/pages/:url_or_id`

Delete a wiki page

#### Example Request:

####

``` example
curl -X DELETE -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/courses/123/pages/the-page-identifier
```

Returns a [Page](pages.html#Page) object

## List revisions

### GET /api/v1/courses/:course_id/pages/:url_or_id/revisions

**Scope:** `url:GET|/api/v1/courses/:course_id/pages/:url_or_id/revisions`

### GET /api/v1/groups/:group_id/pages/:url_or_id/revisions

**Scope:** `url:GET|/api/v1/groups/:group_id/pages/:url_or_id/revisions`

A paginated list of the revisions of a page. Callers must have update rights on the page in order to see page history.

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/courses/123/pages/the-page-identifier/revisions
```

Returns a list of [PageRevision](pages.html#PageRevision) objects

## Show revision

### GET /api/v1/courses/:course_id/pages/:url_or_id/revisions/latest

**Scope:** `url:GET|/api/v1/courses/:course_id/pages/:url_or_id/revisions/latest`

### GET /api/v1/groups/:group_id/pages/:url_or_id/revisions/latest

**Scope:** `url:GET|/api/v1/groups/:group_id/pages/:url_or_id/revisions/latest`

### GET /api/v1/courses/:course_id/pages/:url_or_id/revisions/:revision_id

**Scope:** `url:GET|/api/v1/courses/:course_id/pages/:url_or_id/revisions/:revision_id`

### GET /api/v1/groups/:group_id/pages/:url_or_id/revisions/:revision_id

**Scope:** `url:GET|/api/v1/groups/:group_id/pages/:url_or_id/revisions/:revision_id`

Retrieve the metadata and optionally content of a revision of the page. Note that retrieving historic versions of pages requires edit rights.

#### Request Parameters:

| Parameter |     | Type    | Description                               |
|-----------|-----|---------|-------------------------------------------|
| summary   |     | boolean | If set, exclude page content from results |

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/courses/123/pages/the-page-identifier/revisions/latest
```

####

``` example
curl -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/courses/123/pages/the-page-identifier/revisions/4
```

Returns a [PageRevision](pages.html#PageRevision) object

## Revert to revision

### POST /api/v1/courses/:course_id/pages/:url_or_id/revisions/:revision_id

**Scope:** `url:POST|/api/v1/courses/:course_id/pages/:url_or_id/revisions/:revision_id`

### POST /api/v1/groups/:group_id/pages/:url_or_id/revisions/:revision_id

**Scope:** `url:POST|/api/v1/groups/:group_id/pages/:url_or_id/revisions/:revision_id`

Revert a page to a prior revision.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| revision_id | Required | integer | The revision to revert to (use the [List Revisions API](pages.html#method.wiki_pages_api.revisions "List Revisions API") to see available revisions) |

#### Example Request:

####

``` example
curl -X POST -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/courses/123/pages/the-page-identifier/revisions/6
```

Returns a [PageRevision](pages.html#PageRevision) object
