# BlockEditorTemplate API

Block Editor Templates are pre-build templates that can be used to create pages. The BlockEditorTemplate API allows you to create, retrieve, update, and delete templates.

### A BlockEditorTemplate object looks like:

``` example
{
  // the ID of the page
  "id": 1,
  // name of the template
  "name": "Navigation Bar",
  // description of the template
  "description": "A bar of links to other content",
  // the creation date for the template
  "created_at": "2012-08-06T16:46:33-06:00",
  // the date the template was last updated
  "updated_at": "2012-08-08T14:25:20-06:00",
  // The JSON data that is the template
  "node_tree": null,
  // The version of the editor that created the template
  "editor_version": "1.0",
  // The type of template. One of 'block', 'section', or 'page'
  "template_type": "page",
  // String indicating what state this assignment is in.
  "workflow_state": "unpublished"
}
```

## List block templates

### GET /api/v1/courses/:course_id/block_editor_templates

**Scope:** `url:GET|/api/v1/courses/:course_id/block_editor_templates`

A list of the block templates available to the current user.

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
<p>Allowed values: <code class="enum">name</code>, <code class="enum">created_at</code>, <code class="enum">updated_at</code></p></td>
</tr>
<tr class="request-param">
<td>order</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The sorting order. Defaults to ‘asc’.</p>
<p>Allowed values: <code class="enum">asc</code>, <code class="enum">desc</code></p></td>
</tr>
<tr class="request-param">
<td>drafts</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>If true, include draft templates. If false or omitted only published templates will be returned.</p></td>
</tr>
<tr class="request-param">
<td>type[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>What type of templates should be returned.</p>
<p>Allowed values: <code class="enum">page</code>, <code class="enum">section</code>, <code class="enum">block</code></p></td>
</tr>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>no description</p>
<p>Allowed values: <code class="enum">node_tree</code>, <code class="enum">thumbnail</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
     https://<canvas>/api/v1/courses/123/block_editor_templates?sort=name&order=asc&drafts=true
```

Returns a list of [BlockEditorTemplate](block_editor_template.html#BlockEditorTemplate) objects
