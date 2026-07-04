# Line Items API

Line Item API for IMS Assignment and Grade Services

### A LineItem object looks like:

``` example
{
  // The fully qualified URL for showing, updating, and deleting the Line Item
  "id": "http://institution.canvas.com/api/lti/courses/5/line_items/2",
  // The maximum score of the Line Item
  "scoreMaximum": 50,
  // The label of the Line Item.
  "label": "50",
  // Tag used to qualify a line Item beyond its ids
  "tag": "50",
  // A Tool Provider specified id for the Line Item. Multiple line items can share
  // the same resourceId within a given context
  "resourceId": "50",
  // The resource link id the Line Item is attached to
  "resourceLinkId": "50",
  // The extension that defines the submission_type of the line_item. Only returns
  // if set through the line_item create endpoint.
  "https://canvas.instructure.com/lti/submission_type": "{
    "type":"external_tool",
    "external_tool_url":"https://my.launch.url",
  }",
  // The launch url of the Line Item. Only returned if `include=launch_url` query
  // parameter is passed, and only for Show and List actions.
  "https://canvas.instructure.com/lti/launch_url": "https://my.tool.url/launch"
}
```

## Create a Line Item

### POST /api/lti/courses/:course_id/line_items

**Scope:** `url:POST|/api/lti/courses/:course_id/line_items`

Create a new Line Item

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
<td>scoreMaximum</td>
<td>Required</td>
<td>number</td>
<td class="param-desc"><p>The maximum score for the line item. Scores created for the Line Item may exceed this value.</p></td>
</tr>
<tr class="request-param">
<td>label</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The label for the Line Item. If no resourceLinkId is specified this value will also be used as the name of the placeholder assignment.</p></td>
</tr>
<tr class="request-param">
<td>resourceId</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A Tool Provider specified id for the Line Item. Multiple line items may share the same resourceId within a given context.</p></td>
</tr>
<tr class="request-param">
<td>tag</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A value used to qualify a line Item beyond its ids. Line Items may be queried by this value in the List endpoint. Multiple line items can share the same tag within a given context.</p></td>
</tr>
<tr class="request-param">
<td>resourceLinkId</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The resource link id the Line Item should be attached to. This value should match the LTI id of the Canvas assignment associated with the tool.</p></td>
</tr>
<tr class="request-param">
<td>startDateTime</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The ISO8601 date and time when the line item is made available. Corresponds to the assignment’s unlock_at date.</p></td>
</tr>
<tr class="request-param">
<td>endDateTime</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The ISO8601 date and time when the line item stops receiving submissions. Corresponds to the assignment’s due_at date.</p></td>
</tr>
<tr class="request-param">
<td>https://canvas.instructure.com/lti/submission_type</td>
<td></td>
<td>object</td>
<td class="param-desc"><p>(EXTENSION) - Optional block to set Assignment Submission Type when creating a new assignment is created.</p>
<dl>
<dt>type - ‘none’ or ‘external_tool’<br />
external_tool_url - Submission URL only used when type: ‘external_tool’</dt>
<dd>
&#10;</dd>
</dl></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
{
  "scoreMaximum": 100.0,
  "label": "LineItemLabel1",
  "resourceId": 1,
  "tag": "MyTag",
  "resourceLinkId": "1",
  "startDateTime": "2022-01-31T22:23:11+0000",
  "endDateTime": "2022-02-07T22:23:11+0000",
  "https://canvas.instructure.com/lti/submission_type": {
    "type": "external_tool",
    "external_tool_url": "https://my.launch.url"
  }
}
```

Returns a [LineItem](line_items.html#LineItem) object

## Update a Line Item

### PUT /api/lti/courses/:course_id/line_items/:id

**Scope:** `url:PUT|/api/lti/courses/:course_id/line_items/:id`

Update new Line Item

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| scoreMaximum |  | number | The maximum score for the line item. Scores created for the Line Item may exceed this value. |
| label |  | string | The label for the Line Item. If no resourceLinkId is specified this value will also be used as the name of the placeholder assignment. |
| resourceId |  | string | A Tool Provider specified id for the Line Item. Multiple line items may share the same resourceId within a given context. |
| tag |  | string | A value used to qualify a line Item beyond its ids. Line Items may be queried by this value in the List endpoint. Multiple line items can share the same tag within a given context. |
| startDateTime |  | string | The ISO8601 date and time when the line item is made available. Corresponds to the assignment’s unlock_at date. |
| endDateTime |  | string | The ISO8601 date and time when the line item stops receiving submissions. Corresponds to the assignment’s due_at date. |

Returns a [LineItem](line_items.html#LineItem) object

## Show a Line Item

### GET /api/lti/courses/:course_id/line_items/:id

**Scope:** `url:GET|/api/lti/courses/:course_id/line_items/:id`

Show existing Line Item

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
<td class="param-desc"><p>Array of additional information to include.</p>
<dl>
<dt>“launch_url”</dt>
<dd>
<p>includes the launch URL for this line item using the “https://canvas.instructure.com/lti/launch_url” extension</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">launch_url</code></p></td>
</tr>
</tbody>
</table>

Returns a [LineItem](line_items.html#LineItem) object

## List line Items

### GET /api/lti/courses/:course_id/line_items

**Scope:** `url:GET|/api/lti/courses/:course_id/line_items`

List all Line Items for a course

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
<td>tag</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If specified only Line Items with this tag will be included.</p></td>
</tr>
<tr class="request-param">
<td>resource_id</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If specified only Line Items with this resource_id will be included.</p></td>
</tr>
<tr class="request-param">
<td>resource_link_id</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>If specified only Line Items attached to the specified resource_link_id will be included.</p></td>
</tr>
<tr class="request-param">
<td>limit</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>May be used to limit the number of Line Items returned in a page</p></td>
</tr>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Array of additional information to include.</p>
<dl>
<dt>“launch_url”</dt>
<dd>
<p>includes the launch URL for each line item using the “https://canvas.instructure.com/lti/launch_url” extension</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">launch_url</code></p></td>
</tr>
</tbody>
</table>

Returns a [LineItem](line_items.html#LineItem) object

## Delete a Line Item

### DELETE /api/lti/courses/:course_id/line_items/:id

**Scope:** `url:DELETE|/api/lti/courses/:course_id/line_items/:id`

Delete an existing Line Item

Returns a [LineItem](line_items.html#LineItem) object
