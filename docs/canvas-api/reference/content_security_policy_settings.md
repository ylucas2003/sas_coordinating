# Content Security Policy Settings API

### BETA: This API resource is not finalized, and there could be breaking changes before its final release.

API for enabling/disabling the use of Content Security Policy headers and configuring allowed domains

## Get current settings for account or course

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### GET /api/v1/courses/:course_id/csp_settings

**Scope:** `url:GET|/api/v1/courses/:course_id/csp_settings`

### GET /api/v1/accounts/:account_id/csp_settings

**Scope:** `url:GET|/api/v1/accounts/:account_id/csp_settings`

Update multiple modules in an account.

#### API response field:

-  enabled

  Whether CSP is enabled.

-  inherited

  Whether the current CSP settings are inherited from a parent account.

-  settings_locked

  Whether current CSP settings can be overridden by sub-accounts and courses.

-  effective_whitelist

  If enabled, lists the currently allowed domains (includes domains automatically allowed through external tools).

-  tools_whitelist

  (Account-only) Lists the automatically allowed domains with their respective external tools

-  current_account_whitelist

  (Account-only) Lists the current list of domains explicitly allowed by this account. (Note: this list will not take effect unless CSP is explicitly enabled on this account)

## Enable, disable, or clear explicit CSP setting

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### PUT /api/v1/courses/:course_id/csp_settings

**Scope:** `url:PUT|/api/v1/courses/:course_id/csp_settings`

### PUT /api/v1/accounts/:account_id/csp_settings

**Scope:** `url:PUT|/api/v1/accounts/:account_id/csp_settings`

Either explicitly sets CSP to be on or off for courses and sub-accounts, or clear the explicit settings to default to those set by a parent account

Note: If “inherited” and “settings_locked” are both true for this account or course, then the CSP setting cannot be modified.

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
<td>status</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>If set to “enabled” for an account, CSP will be enabled for all its courses and sub-accounts (that have not explicitly enabled or disabled it), using the allowed domains set on this account. If set to “disabled”, CSP will be disabled for this account or course and for all sub-accounts that have not explicitly re-enabled it. If set to “inherited”, this account or course will reset to the default state where CSP settings are inherited from the first parent account to have them explicitly set.</p>
<p>Allowed values: <code class="enum">enabled</code>, <code class="enum">disabled</code>, <code class="enum">inherited</code></p></td>
</tr>
</tbody>
</table>

## Lock or unlock current CSP settings for sub-accounts and courses

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### PUT /api/v1/accounts/:account_id/csp_settings/lock

**Scope:** `url:PUT|/api/v1/accounts/:account_id/csp_settings/lock`

Can only be set if CSP is explicitly enabled or disabled on this account (i.e. “inherited” is false).

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| settings_locked | Required | boolean | Whether sub-accounts and courses will be prevented from overriding settings inherited from this account. |

## Add an allowed domain to account

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### POST /api/v1/accounts/:account_id/csp_settings/domains

**Scope:** `url:POST|/api/v1/accounts/:account_id/csp_settings/domains`

Adds an allowed domain for the current account. Note: this will not take effect unless CSP is explicitly enabled on this account.

#### Request Parameters:

| Parameter |          | Type   | Description    |
|-----------|----------|--------|----------------|
| domain    | Required | string | no description |

## Add multiple allowed domains to an account

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### POST /api/v1/accounts/:account_id/csp_settings/domains/batch_create

**Scope:** `url:POST|/api/v1/accounts/:account_id/csp_settings/domains/batch_create`

Adds multiple allowed domains for the current account. Note: this will not take effect unless CSP is explicitly enabled on this account.

#### Request Parameters:

| Parameter |          | Type  | Description    |
|-----------|----------|-------|----------------|
| domains   | Required | Array | no description |

## Remove a domain from account

### BETA: This API endpoint is not finalized, and there could be breaking changes before its final release.

### DELETE /api/v1/accounts/:account_id/csp_settings/domains

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/csp_settings/domains`

Removes an allowed domain from the current account.

#### Request Parameters:

| Parameter |          | Type   | Description    |
|-----------|----------|--------|----------------|
| domain    | Required | string | no description |
