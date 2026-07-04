# API Token Scopes API

### BETA: This API resource is not finalized, and there could be breaking changes before its final release.

API for retrieving API scopes

### A Scope object looks like:

``` example
{
  // The resource the scope is associated with
  "resource": "courses",
  // The localized resource name
  "resource_name": "Courses",
  // The controller the scope is associated to
  "controller": "courses",
  // The controller action the scope is associated to
  "action": "index",
  // The HTTP verb for the scope
  "verb": "GET",
  // The identifier for the scope
  "scope": "url:GET|/api/v1/courses"
}
```

## List scopes

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### GET /api/v1/accounts/:account_id/scopes

**Scope:** `url:GET|/api/v1/accounts/:account_id/scopes`

A list of scopes that can be applied to developer keys and access tokens.

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
<td>group_by</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The attribute to group the scopes by. By default no grouping is done.</p>
<p>Allowed values: <code class="enum">resource_name</code></p></td>
</tr>
</tbody>
</table>

Returns a list of [Scope](api_token_scopes.html#Scope) objects
