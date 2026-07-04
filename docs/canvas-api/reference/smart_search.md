# Smart Search API

### BETA: This API resource is not finalized, and there could be breaking changes before its final release.

API for AI-powered course content search. NOTE: This feature has limited availability at present.

### A SearchResult object looks like:

``` example
// Reference to an object that matches a smart search
{
  // The ID of the matching object.
  "content_id": 2,
  // The type of the matching object.
  "content_type": "WikiPage",
  // The title of the matching object.
  "title": "Nicolaus Copernicus",
  // The body of the matching object.
  "body": "Nicolaus Copernicus was a Renaissance-era mathematician and astronomer who...",
  // The Canvas URL of the matching object.
  "html_url": "https://canvas.example.com/courses/123/pages/nicolaus-copernicus",
  // The distance between the search query and the result. Smaller numbers
  // indicate closer matches.
  "distance": 0.212
}
```

## Search course content

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### GET /api/v1/courses/:course_id/smartsearch

**Scope:** `url:GET|/api/v1/courses/:course_id/smartsearch`

Find course content using a meaning-based search

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
<td>q</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The search query</p></td>
</tr>
<tr class="request-param">
<td>filter[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Types of objects to search. By default, all supported types are searched. Supported types include <code>pages</code>, <code>assignments</code>, <code>announcements</code>, and <code>discussion_topics</code>.</p></td>
</tr>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Optional information to include with each search result:</p>
<dl>
<dt>modules</dt>
<dd>
<p>An array of module objects that the search result belongs to.</p>
</dd>
<dt>status</dt>
<dd>
<p>The published status for all results and the due_date for all assignments.</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">status</code>, <code class="enum">modules</code></p></td>
</tr>
</tbody>
</table>

Returns a list of [SearchResult](smart_search.html#SearchResult) objects
