# Communication Channels API

API for accessing users' email and SMS communication channels.

In this API, the `:user_id` parameter can always be replaced with `self` if the requesting user is asking for his/her own information.

### A CommunicationChannel object looks like:

``` example
{
  // The ID of the communication channel.
  "id": 16,
  // The address, or path, of the communication channel.
  "address": "sheldon@caltech.example.com",
  // The type of communcation channel being described. Possible values are:
  // 'email', 'push', 'sms'. This field determines the type of value seen in
  // 'address'.
  "type": "email",
  // The position of this communication channel relative to the user's other
  // channels when they are ordered.
  "position": 1,
  // The ID of the user that owns this communication channel.
  "user_id": 1,
  // The number of bounces the channel has experienced. This is reset if the
  // channel sends successfully.
  "bounce_count": 0,
  // The time the last bounce occurred.
  "last_bounce_at": "2012-05-30T17:00:00Z",
  // The current state of the communication channel. Possible values are:
  // 'unconfirmed' or 'active'.
  "workflow_state": "active"
}
```

## List user communication channels

### GET /api/v1/users/:user_id/communication_channels

**Scope:** `url:GET|/api/v1/users/:user_id/communication_channels`

Returns a paginated list of communication channels for the specified user, sorted by position.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/users/12345/communication_channels \
     -H 'Authorization: Bearer <token>'
```

Returns a list of [CommunicationChannel](communication_channels.html#CommunicationChannel) objects

## Create a communication channel

### POST /api/v1/users/:user_id/communication_channels

**Scope:** `url:POST|/api/v1/users/:user_id/communication_channels`

Creates a new communication channel for the specified user.

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
<td>communication_channel[address]</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>An email address or SMS number. Not required for “push” type channels.</p></td>
</tr>
<tr class="request-param">
<td>communication_channel[type]</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The type of communication channel.</p>
<p>In order to enable push notification support, the server must be properly configured (via ‘sns_creds` in Vault) to communicate with Amazon Simple Notification Services, and the developer key used to create the access token from this request must have an SNS ARN configured on it.</p>
<p>Allowed values: <code class="enum">email</code>, <code class="enum">sms</code>, <code class="enum">push</code></p></td>
</tr>
<tr class="request-param">
<td>communication_channel[token]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>A registration id, device token, or equivalent token given to an app when registering with a push notification provider. Only valid for “push” type channels.</p></td>
</tr>
<tr class="request-param">
<td>skip_confirmation</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Only valid for site admins and account admins making requests; If true, the channel is automatically validated and no confirmation email or SMS is sent. Otherwise, the user must respond to a confirmation message to confirm the channel.</p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/users/1/communication_channels \
     -H 'Authorization: Bearer <token>' \
     -d 'communication_channel[address]=new@example.com' \
     -d 'communication_channel[type]=email' \
```

Returns a [CommunicationChannel](communication_channels.html#CommunicationChannel) object

## Delete a communication channel

### DELETE /api/v1/users/:user_id/communication_channels/:id

**Scope:** `url:DELETE|/api/v1/users/:user_id/communication_channels/:id`

### DELETE /api/v1/users/:user_id/communication_channels/:type/:address

**Scope:** `url:DELETE|/api/v1/users/:user_id/communication_channels/:type/:address`

Delete an existing communication channel.

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/users/5/communication_channels/3
     -H 'Authorization: Bearer <token>
     -X DELETE
```

Returns a [CommunicationChannel](communication_channels.html#CommunicationChannel) object

## Delete a push notification endpoint

### DELETE /api/v1/users/self/communication_channels/push

**Scope:** `url:DELETE|/api/v1/users/self/communication_channels/push`

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/users/self/communication_channels/push
     -H 'Authorization: Bearer <token>
     -X DELETE
     -d 'push_token=<push_token>'
```
