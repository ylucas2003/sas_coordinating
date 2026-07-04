# Account Notifications API

API for account notifications.

### An AccountNotification object looks like:

``` example
{
  // The subject of the notifications
  "subject": "Attention Students",
  // The message to be sent in the notification.
  "message": "This is a test of the notification system.",
  // When to send out the notification.
  "start_at": "2013-08-28T23:59:00-06:00",
  // When to expire the notification.
  "end_at": "2013-08-29T23:59:00-06:00",
  // The icon to display with the message.  Defaults to warning.
  "icon": "information",
  // (Deprecated) The roles to send the notification to.  If roles is not passed
  // it defaults to all roles
  "roles": ["StudentEnrollment"],
  // The roles to send the notification to.  If roles is not passed it defaults to
  // all roles
  "role_ids": [1],
  // The author of the notification. Available only to admins using include_all.
  "author": {"id":1,"name":"John Doe"}
}
```

## Index of active global notification for the user

### GET /api/v1/accounts/:account_id/account_notifications

**Scope:** `url:GET|/api/v1/accounts/:account_id/account_notifications`

Returns a list of all global notifications in the account for the current user Any notifications that have been closed by the user will not be returned, unless a include_past parameter is passed in as true. Admins can request all global notifications for the account by passing in an include_all parameter.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| include_past |  | boolean | Include past and dismissed global announcements. |
| include_all |  | boolean | Include all global announcements, regardless of user’s role or availability date. Only available to account admins. |
| show_is_closed |  | boolean | Include a flag for each notification indicating whether it has been read by the user. |

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/accounts/2/users/self/account_notifications
```

Returns a list of [AccountNotification](account_notifications.html#AccountNotification) objects

## Show a global notification

### GET /api/v1/accounts/:account_id/account_notifications/:id

**Scope:** `url:GET|/api/v1/accounts/:account_id/account_notifications/:id`

Returns a global notification for the current user A notification that has been closed by the user will not be returned

#### Example Request:

####

``` example
curl -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/accounts/2/users/self/account_notifications/4
```

Returns an [AccountNotification](account_notifications.html#AccountNotification) object

## Create a global notification

### POST /api/v1/accounts/:account_id/account_notifications

**Scope:** `url:POST|/api/v1/accounts/:account_id/account_notifications`

Create and return a new global notification for an account.

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
<td>account_notification[subject]</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The subject of the notification.</p></td>
</tr>
<tr class="request-param">
<td>account_notification[message]</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The message body of the notification.</p></td>
</tr>
<tr class="request-param">
<td>account_notification[start_at]</td>
<td>Required</td>
<td>DateTime</td>
<td class="param-desc"><p>The start date and time of the notification in ISO8601 format. e.g. 2014-01-01T01:00Z</p></td>
</tr>
<tr class="request-param">
<td>account_notification[end_at]</td>
<td>Required</td>
<td>DateTime</td>
<td class="param-desc"><p>The end date and time of the notification in ISO8601 format. e.g. 2014-01-01T01:00Z</p></td>
</tr>
<tr class="request-param">
<td>account_notification[icon]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The icon to display with the notification. Note: Defaults to warning.</p>
<p>Allowed values: <code class="enum">warning</code>, <code class="enum">information</code>, <code class="enum">question</code>, <code class="enum">error</code>, <code class="enum">calendar</code></p></td>
</tr>
<tr class="request-param">
<td>account_notification_roles[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The role(s) to send global notification to. Note: ommitting this field will send to everyone Example:</p>
`account_notification_roles: ["StudentEnrollment", "TeacherEnrollment"]`</td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl -X POST -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/accounts/2/account_notifications \
-d 'account_notification[subject]=New notification' \
-d 'account_notification[start_at]=2014-01-01T00:00:00Z' \
-d 'account_notification[end_at]=2014-02-01T00:00:00Z' \
-d 'account_notification[message]=This is a global notification'
```

#### Example Response:

####

``` example
{
  "subject": "New notification",
  "start_at": "2014-01-01T00:00:00Z",
  "end_at": "2014-02-01T00:00:00Z",
  "message": "This is a global notification"
}
```

## Update a global notification

### PUT /api/v1/accounts/:account_id/account_notifications/:id

**Scope:** `url:PUT|/api/v1/accounts/:account_id/account_notifications/:id`

Update global notification for an account.

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
<td>account_notification[subject]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The subject of the notification.</p></td>
</tr>
<tr class="request-param">
<td>account_notification[message]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The message body of the notification.</p></td>
</tr>
<tr class="request-param">
<td>account_notification[start_at]</td>
<td></td>
<td>DateTime</td>
<td class="param-desc"><p>The start date and time of the notification in ISO8601 format. e.g. 2014-01-01T01:00Z</p></td>
</tr>
<tr class="request-param">
<td>account_notification[end_at]</td>
<td></td>
<td>DateTime</td>
<td class="param-desc"><p>The end date and time of the notification in ISO8601 format. e.g. 2014-01-01T01:00Z</p></td>
</tr>
<tr class="request-param">
<td>account_notification[icon]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The icon to display with the notification.</p>
<p>Allowed values: <code class="enum">warning</code>, <code class="enum">information</code>, <code class="enum">question</code>, <code class="enum">error</code>, <code class="enum">calendar</code></p></td>
</tr>
<tr class="request-param">
<td>account_notification_roles[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The role(s) to send global notification to. Note: ommitting this field will send to everyone Example:</p>
`account_notification_roles: ["StudentEnrollment", "TeacherEnrollment"]`</td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl -X PUT -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/accounts/2/account_notifications/1 \
-d 'account_notification[subject]=New notification' \
-d 'account_notification[start_at]=2014-01-01T00:00:00Z' \
-d 'account_notification[end_at]=2014-02-01T00:00:00Z' \
-d 'account_notification[message]=This is a global notification'
```

#### Example Response:

####

``` example
{
  "subject": "New notification",
  "start_at": "2014-01-01T00:00:00Z",
  "end_at": "2014-02-01T00:00:00Z",
  "message": "This is a global notification"
}
```

## Close notification for user. Destroy notification for admin

### DELETE /api/v1/accounts/:account_id/account_notifications/:id

**Scope:** `url:DELETE|/api/v1/accounts/:account_id/account_notifications/:id`

If the current user no longer wants to see this account notification, it can be closed with this call. This affects the current user only.

If the current user is an admin and they pass a remove parameter with a value of “true”, the account notification will be destroyed. This affects all users.

#### Request Parameters:

| Parameter |     | Type    | Description                       |
|-----------|-----|---------|-----------------------------------|
| remove    |     | boolean | Destroy the account notification. |

#### Example Request:

####

``` example
curl -X DELETE -H 'Authorization: Bearer <token>' \
https://<canvas>/api/v1/accounts/2/account_notifications/4
```

Returns an [AccountNotification](account_notifications.html#AccountNotification) object
