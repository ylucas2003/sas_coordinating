# User Observees API

API for accessing information about the users a user is observing.

### A PairingCode object looks like:

``` example
// A code used for linking a user to a student to observe them.
{
  // The ID of the user.
  "user_id": 2,
  // The actual code to be sent to other APIs
  "code": "abc123",
  // When the code expires
  "expires_at": "2012-05-30T17:45:25Z",
  // The current status of the code
  "workflow_state": "active"
}
```

## List observees

### GET /api/v1/users/:user_id/observees

**Scope:** `url:GET|/api/v1/users/:user_id/observees`

A paginated list of the users that the given user is observing.

**Note:** all users are allowed to list their own observees. Administrators can list other users’ observees.

The returned observees will include an attribute “observation_link_root_account_ids”, a list of ids for the root accounts the observer and observee are linked on. The observer will only be able to observe in courses associated with these root accounts.

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
<td class="param-desc"><ul>
<li><p>“avatar_url”: Optionally include avatar_url.</p></li>
</ul>
<p>Allowed values: <code class="enum">avatar_url</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/users/<user_id>/observees \
     -X GET \
     -H 'Authorization: Bearer <token>'
```

Returns a list of [User](users.html#User) objects

## List observers

### GET /api/v1/users/:user_id/observers

**Scope:** `url:GET|/api/v1/users/:user_id/observers`

A paginated list of the observers of a given user.

**Note:** all users are allowed to list their own observers. Administrators can list other users’ observers.

The returned observers will include an attribute “observation_link_root_account_ids”, a list of ids for the root accounts the observer and observee are linked on. The observer will only be able to observe in courses associated with these root accounts.

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
<td class="param-desc"><ul>
<li><p>“avatar_url”: Optionally include avatar_url.</p></li>
</ul>
<p>Allowed values: <code class="enum">avatar_url</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/users/<user_id>/observers \
     -X GET \
     -H 'Authorization: Bearer <token>'
```

Returns a list of [User](users.html#User) objects

## Add an observee with credentials

### POST /api/v1/users/:user_id/observees

**Scope:** `url:POST|/api/v1/users/:user_id/observees`

Register the given user to observe another user, given the observee’s credentials.

**Note:** all users are allowed to add their own observees, given the observee’s credentials or access token are provided. Administrators can add observees given credentials, access token or the [observee’s id](user_observees.html#method.user_observees.update "observee’s id").

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| observee\[unique_id\] |  | string | The login id for the user to observe. Required if access_token is omitted. |
| observee\[password\] |  | string | The password for the user to observe. Required if access_token is omitted. |
| access_token |  | string | The access token for the user to observe. Required if `observee[unique_id]` or `observee[password]` are omitted. |
| pairing_code |  | string | A generated pairing code for the user to observe. Required if the Observer pairing code feature flag is enabled |
| root_account_id |  | integer | The ID for the root account to associate with the observation link. Defaults to the current domain account. If ‘all’ is specified, a link will be created for each root account associated to both the observer and observee. |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/users/<user_id>/observees \
     -X POST \
     -H 'Authorization: Bearer <token>' \
     -F 'observee[unique_id]=UNIQUE_ID' \
     -F 'observee[password]=PASSWORD'
```

Returns an [User](users.html#User) object

## Show an observee

### GET /api/v1/users/:user_id/observees/:observee_id

**Scope:** `url:GET|/api/v1/users/:user_id/observees/:observee_id`

Gets information about an observed user.

**Note:** all users are allowed to view their own observees.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/users/<user_id>/observees/<observee_id> \
     -X GET \
     -H 'Authorization: Bearer <token>'
```

Returns an [User](users.html#User) object

## Show an observer

### GET /api/v1/users/:user_id/observers/:observer_id

**Scope:** `url:GET|/api/v1/users/:user_id/observers/:observer_id`

Gets information about an observer.

**Note:** all users are allowed to view their own observers.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/users/<user_id>/observers/<observer_id> \
     -X GET \
     -H 'Authorization: Bearer <token>'
```

Returns an [User](users.html#User) object

## Add an observee

### PUT /api/v1/users/:user_id/observees/:observee_id

**Scope:** `url:PUT|/api/v1/users/:user_id/observees/:observee_id`

Registers a user as being observed by the given user.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| root_account_id |  | integer | The ID for the root account to associate with the observation link. If not specified, a link will be created for each root account associated to both the observer and observee. |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/users/<user_id>/observees/<observee_id> \
     -X PUT \
     -H 'Authorization: Bearer <token>'
```

Returns an [User](users.html#User) object

## Remove an observee

### DELETE /api/v1/users/:user_id/observees/:observee_id

**Scope:** `url:DELETE|/api/v1/users/:user_id/observees/:observee_id`

Unregisters a user as being observed by the given user.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| root_account_id |  | integer | If specified, only removes the link for the given root account |

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/users/<user_id>/observees/<observee_id> \
     -X DELETE \
     -H 'Authorization: Bearer <token>'
```

Returns an [User](users.html#User) object

## Create observer pairing code

### POST /api/v1/users/:user_id/observer_pairing_codes

**Scope:** `url:POST|/api/v1/users/:user_id/observer_pairing_codes`

If the user is a student, will generate a code to be used with self registration or observees APIs to link another user to this student.

Returns a [PairingCode](user_observees.html#PairingCode) object
