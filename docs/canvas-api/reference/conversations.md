# Conversations API

API for creating, accessing and updating user conversations.

### A Conversation object looks like:

``` example
{
  // the unique identifier for the conversation.
  "id": 2,
  // the subject of the conversation.
  "subject": "2",
  // The current state of the conversation (read, unread or archived).
  "workflow_state": "unread",
  // A <=100 character preview from the most recent message.
  "last_message": "sure thing, here's the file",
  // the date and time at which the last message was sent.
  "start_at": "2011-09-02T12:00:00Z",
  // the number of messages in the conversation.
  "message_count": 2,
  // whether the current user is subscribed to the conversation.
  "subscribed": true,
  // whether the conversation is private.
  "private": true,
  // whether the conversation is starred.
  "starred": true,
  // Additional conversation flags (last_author, attachments, media_objects). Each
  // listed property means the flag is set to true (i.e. the current user is the
  // most recent author, there are attachments, or there are media objects)
  "properties": null,
  // Array of user ids who are involved in the conversation, ordered by
  // participation level, then alphabetical. Excludes current user, unless this is
  // a monologue.
  "audience": null,
  // Most relevant shared contexts (courses and groups) between current user and
  // other participants. If there is only one participant, it will also include
  // that user's enrollment(s)/ membership type(s) in each course/group.
  "audience_contexts": null,
  // URL to appropriate icon for this conversation (custom, individual or group
  // avatar, depending on audience).
  "avatar_url": "https://canvas.instructure.com/images/messages/avatar-group-50.png",
  // Array of users participating in the conversation. Includes current user.
  "participants": null,
  // indicates whether the conversation is visible under the current scope and
  // filter. This attribute is always true in the index API response, and is
  // primarily useful in create/update responses so that you can know if the
  // record should be displayed in the UI. The default scope is assumed, unless a
  // scope or filter is passed to the create/update API call.
  "visible": true,
  // Name of the course or group in which the conversation is occurring.
  "context_name": "Canvas 101"
}
```

### A ConversationParticipant object looks like:

``` example
{
  // The user ID for the participant.
  "id": 2,
  // A short name the user has selected, for use in conversations or other less
  // formal places through the site.
  "name": "Shelly",
  // The full name of the user.
  "full_name": "Sheldon Cooper",
  // If requested, this field will be included and contain a url to retrieve the
  // user's avatar.
  "avatar_url": "https://canvas.instructure.com/images/messages/avatar-50.png"
}
```

## List conversations

### GET /api/v1/conversations

**Scope:** `url:GET|/api/v1/conversations`

Returns the paginated list of conversations for the current user, most recent ones first.

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
<td>scope</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>When set, only return conversations of the specified type. For example, set to “unread” to return only conversations that haven’t been read. The default behavior is to return all non-archived conversations (i.e. read and unread).</p>
<p>Allowed values: <code class="enum">unread</code>, <code class="enum">starred</code>, <code class="enum">archived</code>, <code class="enum">sent</code></p></td>
</tr>
<tr class="request-param">
<td>filter[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>When set, only return conversations for the specified courses, groups or users. The id should be prefixed with its type, e.g. “user_123” or “course_456”. Can be an array (by setting “filter[]”) or single value (by setting “filter”)</p></td>
</tr>
<tr class="request-param">
<td>filter_mode</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>When filter[] contains multiple filters, combine them with this mode, filtering conversations that at have at least all of the contexts (“and”) or at least one of the contexts (“or”)</p>
<p>Allowed values: <code class="enum">and</code>, <code class="enum">or</code>, <code class="enum">default or</code></p></td>
</tr>
<tr class="request-param">
<td>interleave_submissions</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>(Obsolete) Submissions are no longer linked to conversations. This parameter is ignored.</p></td>
</tr>
<tr class="request-param">
<td>include_all_conversation_ids</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Default is false. If true, the top-level element of the response will be an object rather than an array, and will have the keys “conversations” which will contain the paged conversation data, and “conversation_ids” which will contain the ids of all conversations under this scope/filter in the same order.</p></td>
</tr>
<tr class="request-param">
<td>include[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><dl>
<dt>“participant_avatars”</dt>
<dd>
<p>Optionally include an “avatar_url” key for each user participanting in the conversation</p>
</dd>
</dl>
<p>Allowed values: <code class="enum">participant_avatars</code></p></td>
</tr>
</tbody>
</table>

#### API response field:

-  id

  The unique identifier for the conversation.

-  subject

  The subject of the conversation.

-  workflow_state

  The current state of the conversation (read, unread or archived)

-  last_message

  A \<=100 character preview from the most recent message

-  last_message_at

  The timestamp of the latest message

-  message_count

  The number of messages in this conversation

-  subscribed

  Indicates whether the user is actively subscribed to the conversation

-  private

  Indicates whether this is a private conversation (i.e. audience of one)

-  starred

  Whether the conversation is starred

-  properties

  Additional conversation flags (last_author, attachments, media_objects). Each listed property means the flag is set to true (i.e. the current user is the most recent author, there are attachments, or there are media objects)

-  audience

  Array of user ids who are involved in the conversation, ordered by participation level, then alphabetical. Excludes current user, unless this is a monologue.

-  audience_contexts

  Most relevant shared contexts (courses and groups) between current user and other participants. If there is only one participant, it will also include that user’s enrollment(s)/ membership type(s) in each course/group

-  avatar_url

  URL to appropriate icon for this conversation (custom, individual or group avatar, depending on audience)

-  participants

  Array of users (id, name, full_name) participating in the conversation. Includes current user. If ‘include\[\]=participant_avatars\` was passed as an argument, each user in the array will also have an “avatar_url” field

-  visible

  Boolean, indicates whether the conversation is visible under the current scope and filter. This attribute is always true in the index API response, and is primarily useful in create/update responses so that you can know if the record should be displayed in the UI. The default scope is assumed, unless a scope or filter is passed to the create/update API call.

#### Example Response:

####

``` example
[
  {
    "id": 2,
    "subject": "conversations api example",
    "workflow_state": "unread",
    "last_message": "sure thing, here's the file",
    "last_message_at": "2011-09-02T12:00:00Z",
    "message_count": 2,
    "subscribed": true,
    "private": true,
    "starred": false,
    "properties": ["attachments"],
    "audience": [2],
    "audience_contexts": {"courses": {"1": ["StudentEnrollment"]}, "groups": {}},
    "avatar_url": "https://canvas.instructure.com/images/messages/avatar-group-50.png",
    "participants": [
      {"id": 1, "name": "Joe", "full_name": "Joe TA"},
      {"id": 2, "name": "Jane", "full_name": "Jane Teacher"}
    ],
    "visible": true,
    "context_name": "Canvas 101"
  }
]
```

Returns a list of [Conversation](conversations.html#Conversation) objects

## Create a conversation

### POST /api/v1/conversations

**Scope:** `url:POST|/api/v1/conversations`

Create a new conversation with one or more recipients. If there is already an existing private conversation with the given recipients, it will be reused.

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
<td>recipients[]</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>An array of recipient ids. These may be user ids or course/group ids prefixed with “course_” or “group_” respectively, e.g. recipients[]=1&amp;recipients=2&amp;recipients[]=course_3. If the course/group has over 100 enrollments, ‘bulk_message’ and ‘group_conversation’ must be set to true.</p></td>
</tr>
<tr class="request-param">
<td>subject</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The subject of the conversation. This is ignored when reusing a conversation. Maximum length is 255 characters.</p></td>
</tr>
<tr class="request-param">
<td>body</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The message to be sent</p></td>
</tr>
<tr class="request-param">
<td>force_new</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Forces a new message to be created, even if there is an existing private conversation.</p></td>
</tr>
<tr class="request-param">
<td>group_conversation</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Defaults to false. When false, individual private conversations will be created with each recipient. If true, this will be a group conversation (i.e. all recipients may see all messages and replies). Must be set true if the number of recipients is over the set maximum (default is 100).</p></td>
</tr>
<tr class="request-param">
<td>attachment_ids[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>An array of attachments ids. These must be files that have been previously uploaded to the sender’s “conversation attachments” folder.</p></td>
</tr>
<tr class="request-param">
<td>media_comment_id</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Media comment id of an audio or video file to be associated with this message.</p></td>
</tr>
<tr class="request-param">
<td>media_comment_type</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Type of the associated media file</p>
<p>Allowed values: <code class="enum">audio</code>, <code class="enum">video</code></p></td>
</tr>
<tr class="request-param">
<td>mode</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Determines whether the messages will be created/sent synchronously or asynchronously. Defaults to sync, and this option is ignored if this is a group conversation or there is just one recipient (i.e. it must be a bulk private message). When sent async, the response will be an empty array (batch status can be queried via the batches API)</p>
<p>Allowed values: <code class="enum">sync</code>, <code class="enum">async</code></p></td>
</tr>
<tr class="request-param">
<td>scope</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Used when generating “visible” in the API response. See the explanation under the index API action</p>
<p>Allowed values: <code class="enum">unread</code>, <code class="enum">starred</code>, <code class="enum">archived</code></p></td>
</tr>
<tr class="request-param">
<td>filter[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Used when generating “visible” in the API response. See the explanation under the index API action</p></td>
</tr>
<tr class="request-param">
<td>filter_mode</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Used when generating “visible” in the API response. See the explanation under the index API action</p>
<p>Allowed values: <code class="enum">and</code>, <code class="enum">or</code>, <code class="enum">default or</code></p></td>
</tr>
<tr class="request-param">
<td>context_code</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>The course or group that is the context for this conversation. Same format as courses or groups in the recipients argument.</p></td>
</tr>
</tbody>
</table>

## Get running batches

### GET /api/v1/conversations/batches

**Scope:** `url:GET|/api/v1/conversations/batches`

Returns any currently running conversation batches for the current user. Conversation batches are created when a bulk private message is sent asynchronously (see the mode argument to the [create API action](conversations.html#method.conversations.create "create API action")).

#### Example Response:

####

``` example
[
  {
    "id": 1,
    "subject": "conversations api example",
    "workflow_state": "created",
    "completion": 0.1234,
    "tags": [],
    "message":
    {
      "id": 1,
      "created_at": "2011-09-02T10:00:00Z",
      "body": "quick reminder, no class tomorrow",
      "author_id": 1,
      "generated": false,
      "media_comment": null,
      "forwarded_messages": [],
      "attachments": []
    }
  }
]
```

## Get a single conversation

### GET /api/v1/conversations/:id

**Scope:** `url:GET|/api/v1/conversations/:id`

Returns information for a single conversation for the current user. Response includes all fields that are present in the list/index action as well as messages and extended participant information.

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
<td>interleave_submissions</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>(Obsolete) Submissions are no longer linked to conversations. This parameter is ignored.</p></td>
</tr>
<tr class="request-param">
<td>scope</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Used when generating “visible” in the API response. See the explanation under the index API action</p>
<p>Allowed values: <code class="enum">unread</code>, <code class="enum">starred</code>, <code class="enum">archived</code></p></td>
</tr>
<tr class="request-param">
<td>filter[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Used when generating “visible” in the API response. See the explanation under the index API action</p></td>
</tr>
<tr class="request-param">
<td>filter_mode</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Used when generating “visible” in the API response. See the explanation under the index API action</p>
<p>Allowed values: <code class="enum">and</code>, <code class="enum">or</code>, <code class="enum">default or</code></p></td>
</tr>
<tr class="request-param">
<td>auto_mark_as_read</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Default true. If true, unread conversations will be automatically marked as read. This will default to false in a future API release, so clients should explicitly send true if that is the desired behavior.</p></td>
</tr>
</tbody>
</table>

#### API response field:

-  participants

  Array of relevant users. Includes current user. If there are forwarded messages in this conversation, the authors of those messages will also be included, even if they are not participating in this conversation. Fields include:

-  messages

  Array of messages, newest first. Fields include:

  id
  The unique identifier for the message

  created_at
  The timestamp of the message

  body
  The actual message body

  author_id
  The id of the user who sent the message (see audience, participants)

  generated
  If true, indicates this is a system-generated message (e.g. “Bob added Alice to the conversation”)

  media_comment
  Audio/video comment data for this message (if applicable). Fields include: display_name, content-type, media_id, media_type, url

  forwarded_messages
  If this message contains forwarded messages, they will be included here (same format as this list). Note that those messages may have forwarded messages of their own, etc.

  attachments
  Array of attachments for this message. Fields include: display_name, content-type, filename, url

-  submissions

  (Obsolete) Array of assignment submissions having comments relevant to this conversation. Submissions are no longer linked to conversations. This field will always be nil or empty.

#### Example Response:

####

``` example
{
  "id": 2,
  "subject": "conversations api example",
  "workflow_state": "unread",
  "last_message": "sure thing, here's the file",
  "last_message_at": "2011-09-02T12:00:00-06:00",
  "message_count": 2,
  "subscribed": true,
  "private": true,
  "starred": false,
  "properties": ["attachments"],
  "audience": [2],
  "audience_contexts": {"courses": {"1": []}, "groups": {}},
  "avatar_url": "https://canvas.instructure.com/images/messages/avatar-50.png",
  "participants": [
    {"id": 1, "name": "Joe", "full_name": "Joe TA"},
    {"id": 2, "name": "Jane", "full_name": "Jane Teacher"},
    {"id": 3, "name": "Bob", "full_name": "Bob Student"}
  ],
  "messages":
    [
      {
        "id": 3,
        "created_at": "2011-09-02T12:00:00Z",
        "body": "sure thing, here's the file",
        "author_id": 2,
        "generated": false,
        "media_comment": null,
        "forwarded_messages": [],
        "attachments": [{"id": 1, "display_name": "notes.doc", "uuid": "abcdefabcdefabcdefabcdefabcdef"}]
      },
      {
        "id": 2,
        "created_at": "2011-09-02T11:00:00Z",
        "body": "hey, bob didn't get the notes. do you have a copy i can give him?",
        "author_id": 2,
        "generated": false,
        "media_comment": null,
        "forwarded_messages":
          [
            {
              "id": 1,
              "created_at": "2011-09-02T10:00:00Z",
              "body": "can i get a copy of the notes? i was out",
              "author_id": 3,
              "generated": false,
              "media_comment": null,
              "forwarded_messages": [],
              "attachments": []
            }
          ],
        "attachments": []
      }
    ],
  "submissions": []
}
```

## Edit a conversation

### PUT /api/v1/conversations/:id

**Scope:** `url:PUT|/api/v1/conversations/:id`

Updates attributes for a single conversation.

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
<td>conversation[workflow_state]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Change the state of this conversation</p>
<p>Allowed values: <code class="enum">read</code>, <code class="enum">unread</code>, <code class="enum">archived</code></p></td>
</tr>
<tr class="request-param">
<td>conversation[subscribed]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Toggle the current user’s subscription to the conversation (only valid for group conversations). If unsubscribed, the user will still have access to the latest messages, but the conversation won’t be automatically flagged as unread, nor will it jump to the top of the inbox.</p></td>
</tr>
<tr class="request-param">
<td>conversation[starred]</td>
<td></td>
<td>boolean</td>
<td class="param-desc"><p>Toggle the starred state of the current user’s view of the conversation.</p></td>
</tr>
<tr class="request-param">
<td>scope</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Used when generating “visible” in the API response. See the explanation under the index API action</p>
<p>Allowed values: <code class="enum">unread</code>, <code class="enum">starred</code>, <code class="enum">archived</code></p></td>
</tr>
<tr class="request-param">
<td>filter[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Used when generating “visible” in the API response. See the explanation under the index API action</p></td>
</tr>
<tr class="request-param">
<td>filter_mode</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Used when generating “visible” in the API response. See the explanation under the index API action</p>
<p>Allowed values: <code class="enum">and</code>, <code class="enum">or</code>, <code class="enum">default or</code></p></td>
</tr>
</tbody>
</table>

#### Example Response:

####

``` example
{
  "id": 2,
  "subject": "conversations api example",
  "workflow_state": "read",
  "last_message": "sure thing, here's the file",
  "last_message_at": "2011-09-02T12:00:00-06:00",
  "message_count": 2,
  "subscribed": true,
  "private": true,
  "starred": false,
  "properties": ["attachments"],
  "audience": [2],
  "audience_contexts": {"courses": {"1": []}, "groups": {}},
  "avatar_url": "https://canvas.instructure.com/images/messages/avatar-50.png",
  "participants": [{"id": 1, "name": "Joe", "full_name": "Joe TA"}]
}
```

## Mark all as read

### POST /api/v1/conversations/mark_all_as_read

**Scope:** `url:POST|/api/v1/conversations/mark_all_as_read`

Mark all conversations as read.

## Delete a conversation

### DELETE /api/v1/conversations/:id

**Scope:** `url:DELETE|/api/v1/conversations/:id`

Delete this conversation and its messages. Note that this only deletes this user’s view of the conversation.

Response includes same fields as UPDATE action

#### Example Response:

####

``` example
{
  "id": 2,
  "subject": "conversations api example",
  "workflow_state": "read",
  "last_message": null,
  "last_message_at": null,
  "message_count": 0,
  "subscribed": true,
  "private": true,
  "starred": false,
  "properties": []
}
```

## Add recipients

### POST /api/v1/conversations/:id/add_recipients

**Scope:** `url:POST|/api/v1/conversations/:id/add_recipients`

Add recipients to an existing group conversation. Response is similar to the GET/show action, except that only includes the latest message (e.g. “joe was added to the conversation by bob”)

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| recipients\[\] | Required | string | An array of recipient ids. These may be user ids or course/group ids prefixed with “course\_” or “group\_” respectively, e.g. [recipients\[\]=1&recipients]()=2&recipients\[\]=course_3 |

#### Example Response:

####

``` example
{
  "id": 2,
  "subject": "conversations api example",
  "workflow_state": "read",
  "last_message": "let's talk this over with jim",
  "last_message_at": "2011-09-02T12:00:00-06:00",
  "message_count": 2,
  "subscribed": true,
  "private": false,
  "starred": null,
  "properties": [],
  "audience": [2, 3, 4],
  "audience_contexts": {"courses": {"1": []}, "groups": {}},
  "avatar_url": "https://canvas.instructure.com/images/messages/avatar-group-50.png",
  "participants": [
    {"id": 1, "name": "Joe", "full_name": "Joe TA"},
    {"id": 2, "name": "Jane", "full_name": "Jane Teacher"},
    {"id": 3, "name": "Bob", "full_name": "Bob Student"},
    {"id": 4, "name": "Jim", "full_name": "Jim Admin"}
  ],
  "messages":
    [
      {
        "id": 4,
        "created_at": "2011-09-02T12:10:00Z",
        "body": "Jim was added to the conversation by Joe TA",
        "author_id": 1,
        "generated": true,
        "media_comment": null,
        "forwarded_messages": [],
        "attachments": []
      }
    ]
}
```

## Add a message

### POST /api/v1/conversations/:id/add_message

**Scope:** `url:POST|/api/v1/conversations/:id/add_message`

Add a message to an existing conversation. Response is similar to the GET/show action, except that only includes the latest message (i.e. what we just sent)

An array of user ids. Defaults to all of the current conversation recipients. To explicitly send a message to no other recipients, this array should consist of the logged-in user id.

An array of message ids from this conversation to send to recipients of the new message. Recipients who already had a copy of included messages will not be affected.

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
<td>body</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The message to be sent.</p></td>
</tr>
<tr class="request-param">
<td>attachment_ids[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>An array of attachments ids. These must be files that have been previously uploaded to the sender’s “conversation attachments” folder.</p></td>
</tr>
<tr class="request-param">
<td>media_comment_id</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Media comment id of an audio of video file to be associated with this message.</p></td>
</tr>
<tr class="request-param">
<td>media_comment_type</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>Type of the associated media file.</p>
<p>Allowed values: <code class="enum">audio</code>, <code class="enum">video</code></p></td>
</tr>
<tr class="request-param">
<td>recipients[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>no description</p></td>
</tr>
<tr class="request-param">
<td>included_messages[]</td>
<td></td>
<td>string</td>
<td class="param-desc"><p>no description</p></td>
</tr>
</tbody>
</table>

#### Example Response:

####

``` example
{
  "id": 2,
  "subject": "conversations api example",
  "workflow_state": "unread",
  "last_message": "let's talk this over with jim",
  "last_message_at": "2011-09-02T12:00:00-06:00",
  "message_count": 2,
  "subscribed": true,
  "private": false,
  "starred": null,
  "properties": [],
  "audience": [2, 3],
  "audience_contexts": {"courses": {"1": []}, "groups": {}},
  "avatar_url": "https://canvas.instructure.com/images/messages/avatar-group-50.png",
  "participants": [
    {"id": 1, "name": "Joe", "full_name": "Joe TA"},
    {"id": 2, "name": "Jane", "full_name": "Jane Teacher"},
    {"id": 3, "name": "Bob", "full_name": "Bob Student"}
  ],
  "messages":
    [
      {
        "id": 3,
        "created_at": "2011-09-02T12:00:00Z",
        "body": "let's talk this over with jim",
        "author_id": 2,
        "generated": false,
        "media_comment": null,
        "forwarded_messages": [],
        "attachments": []
      }
    ]
}
```

## Delete a message

### POST /api/v1/conversations/:id/remove_messages

**Scope:** `url:POST|/api/v1/conversations/:id/remove_messages`

Delete messages from this conversation. Note that this only affects this user’s view of the conversation. If all messages are deleted, the conversation will be as well (equivalent to DELETE)

#### Request Parameters:

| Parameter  |          | Type   | Description                        |
|------------|----------|--------|------------------------------------|
| remove\[\] | Required | string | Array of message ids to be deleted |

#### Example Response:

####

``` example
{
  "id": 2,
  "subject": "conversations api example",
  "workflow_state": "read",
  "last_message": "sure thing, here's the file",
  "last_message_at": "2011-09-02T12:00:00-06:00",
  "message_count": 1,
  "subscribed": true,
  "private": true,
  "starred": null,
  "properties": ["attachments"]
}
```

## Batch update conversations

### PUT /api/v1/conversations

**Scope:** `url:PUT|/api/v1/conversations`

Perform a change on a set of conversations. Operates asynchronously; use the [progress endpoint](progress.html#method.progress.show "progress endpoint") to query the status of an operation.

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
<td>conversation_ids[]</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>List of conversations to update. Limited to 500 conversations.</p></td>
</tr>
<tr class="request-param">
<td>event</td>
<td>Required</td>
<td>string</td>
<td class="param-desc"><p>The action to take on each conversation.</p>
<p>Allowed values: <code class="enum">mark_as_read</code>, <code class="enum">mark_as_unread</code>, <code class="enum">star</code>, <code class="enum">unstar</code>, <code class="enum">archive</code>, <code class="enum">destroy</code></p></td>
</tr>
</tbody>
</table>

#### Example Request:

####

``` example
curl https://<canvas>/api/v1/conversations \
  -X PUT \
  -H 'Authorization: Bearer <token>' \
  -d 'event=mark_as_read' \
  -d 'conversation_ids[]=1' \
  -d 'conversation_ids[]=2'
```

Returns a [Progress](progress.html#Progress) object

## Find recipients

### GET /api/v1/conversations/find_recipients

**Scope:** `url:GET|/api/v1/conversations/find_recipients`

Deprecated, see the [Find recipients endpoint](search.html#method.search.recipients "Find recipients endpoint") in the Search API

## Unread count

### GET /api/v1/conversations/unread_count

**Scope:** `url:GET|/api/v1/conversations/unread_count`

Get the number of unread conversations for the current user

#### Example Response:

####

``` example
{'unread_count': '7'}
```
