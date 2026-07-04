# Admins API

Manage account role assignments

### An Admin object looks like:

``` example
{
  // The unique identifier for the account role/user assignment.
  "id": 1023,
  // The account role assigned. This can be 'AccountAdmin' or a user-defined role
  // created by the Roles API.
  "role": "AccountAdmin",
  // The user the role is assigned to. See the Users API for details.
  "user": null,
  // The status of the account role/user assignment.
  "workflow_state": "deleted"
}
```

## Make an account admin

### POST /api/v1/accounts/:account_id/admins

**Scope:** `url:POST|/api/v1/accounts/:account_id/admins`

Flag an existing user as an admin within the account.

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
<td>user_id</td>
<td>Required</td>
<td>integer</td>
<td class="param-desc"><p>The id of the user to promote.</p></td>
</tr>
<tr class="request-param">
<td>role</td>
<td></td>
<td>string</td>
<td class="param-desc"><dl>
<dt>DEPRECATED</dt>
<dd>
<p>The user’s admin relationship with the account will be</p>
</dd>
</dl>
<p>created with the given role. Defaults to ‘AccountAdmin’.</p></td>
</tr>
<tr class="request-param">
<td>role_id</td>
<td></td>
<td>integer</td>
<td class="param-desc"><p>The user’s admin relationship with the account will be created with the given role. Defaults to the built-in role for ‘AccountAdmin’.</p></td>
</tr>
<tr class="request-param">
<td>send_confirmation</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Send a notification email to the new admin if true. Default is true.</p></td>
</tr>
</tbody>
</table>

Returns an [Admin](admins.html#Admin) object

## Remove account admin

### DELETE /api/v1/accounts/:account_id/admins/:user_id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/admins/:user_id`

Remove the rights associated with an account admin role from a user.

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
<td>role</td>
<td></td>
<td>string</td>
<td class="param-desc"><dl>
<dt>DEPRECATED</dt>
<dd>
<p>Account role to remove from the user.</p>
</dd>
</dl></td>
</tr>
<tr class="request-param">
<td>role_id</td>
<td>Required</td>
<td>integer</td>
<td class="param-desc"><p>The id of the role representing the user’s admin relationship with the account.</p></td>
</tr>
</tbody>
</table>

Returns an [Admin](admins.html#Admin) object

## List account admins

### GET /api/v1/accounts/:account_id/admins

**Scope:** `url:GET|/api/v1/accounts/:account_id/admins`

A paginated list of the admins in the account

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| user_id\[\] |  | \[Integer\] | Scope the results to those with user IDs equal to any of the IDs specified here. |

Returns a list of [Admin](admins.html#Admin) objects

## List my admin roles

### GET /api/v1/accounts/:account_id/admins/self

**Scope:** `url:GET|/api/v1/accounts/:account_id/admins/self`

A paginated list of the current user’s roles in the account. The results are the same as those returned by the [List account admins](admins.html#method.admins.index "List account admins") endpoint with `user_id` set to `self`, except the “Admins - Add / Remove” permission is not required.

Returns a list of [Admin](admins.html#Admin) objects
