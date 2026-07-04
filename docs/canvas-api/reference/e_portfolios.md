# ePortfolios API

### An ePortfolio object looks like:

``` example
{
  // The database ID of the ePortfolio
  "id": 1,
  // The user ID to which the ePortfolio belongs
  "user_id": 1,
  // The name of the ePortfolio
  "name": "My Academic Journey",
  // Whether or not the ePortfolio is visible without authentication
  "public": true,
  // The creation timestamp for the ePortfolio
  "created_at": "2021-09-20T18:59:37Z",
  // The timestamp of the last time any of the ePortfolio attributes changed
  "updated_at": "2021-09-20T18:59:37Z",
  // The state of the ePortfolio. Either 'active' or 'deleted'
  "workflow_state": "active",
  // The timestamp when the ePortfolio was deleted, or else null
  "deleted_at": "2021-09-20T18:59:37Z",
  // A flag indicating whether the ePortfolio has been
  // flagged or moderated as spam. One of 'flagged_as_possible_spam',
  // 'marked_as_safe', 'marked_as_spam', or null
  "spam_status": null
}
```

### An ePortfolioPage object looks like:

``` example
{
  // The database ID of the ePortfolio
  "id": 1,
  // The ePortfolio ID to which the entry belongs
  "eportfolio_id": 1,
  // The positional order of the entry in the list
  "position": 1,
  // The name of the ePortfolio
  "name": "My Academic Journey",
  // The user entered content of the entry
  "content": "A long time ago...",
  // The creation timestamp for the ePortfolio
  "created_at": "2021-09-20T18:59:37Z",
  // The timestamp of the last time any of the ePortfolio attributes changed
  "updated_at": "2021-09-20T18:59:37Z"
}
```

## Get all ePortfolios for a User

### GET /api/v1/users/:user_id/eportfolios

**Scope:** `url:GET|/api/v1/users/:user_id/eportfolios`

Get a list of all ePortfolios for the specified user.

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
<td class="param-desc"><dl>
<dt>deleted</dt>
<dd>
<p>Include deleted ePortfolios. Only available to admins who can</p>
</dd>
</dl>
<p>moderate_user_content.</p>
<p>Allowed values: <code class="enum">deleted</code></p></td>
</tr>
</tbody>
</table>

Returns a list of [ePortfolio](e_portfolios.html#ePortfolio) objects

## Get an ePortfolio

### GET /api/v1/eportfolios/:id

**Scope:** `url:GET|/api/v1/eportfolios/:id`

Get details for a single ePortfolio.

Returns an [ePortfolio](e_portfolios.html#ePortfolio) object

## Delete an ePortfolio

### DELETE /api/v1/eportfolios/:id

**Scope:** `url:DELETE|/api/v1/eportfolios/:id`

Mark an ePortfolio as deleted.

Returns an [ePortfolio](e_portfolios.html#ePortfolio) object

## Get ePortfolio Pages

### GET /api/v1/eportfolios/:eportfolio_id/pages

**Scope:** `url:GET|/api/v1/eportfolios/:eportfolio_id/pages`

Get details for the pages of an ePortfolio

Returns a list of [ePortfolioPage](e_portfolios.html#ePortfolioPage) objects

## Moderate an ePortfolio

### PUT /api/v1/eportfolios/:eportfolio_id/moderate

**Scope:** `url:PUT|/api/v1/eportfolios/:eportfolio_id/moderate`

Update the spam_status of an eportfolio. Only available to admins who can moderate_user_content.

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
<td>spam_status</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The spam status for the ePortfolio</p>
<p>Allowed values: <code class="enum">marked_as_spam</code>, <code class="enum">marked_as_safe</code></p></td>
</tr>
</tbody>
</table>

Returns an [ePortfolio](e_portfolios.html#ePortfolio) object

## Moderate all ePortfolios for a User

### PUT /api/v1/users/:user_id/eportfolios

**Scope:** `url:PUT|/api/v1/users/:user_id/eportfolios`

Update the spam_status for all active eportfolios of a user. Only available to admins who can moderate_user_content.

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
<td>spam_status</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The spam status for all the ePortfolios</p>
<p>Allowed values: <code class="enum">marked_as_spam</code>, <code class="enum">marked_as_safe</code></p></td>
</tr>
</tbody>
</table>

## Restore a deleted ePortfolio

### PUT /api/v1/eportfolios/:eportfolio_id/restore

**Scope:** `url:PUT|/api/v1/eportfolios/:eportfolio_id/restore`

Restore an ePortfolio back to active that was previously deleted. Only available to admins who can moderate_user_content.

Returns an [ePortfolio](e_portfolios.html#ePortfolio) object
