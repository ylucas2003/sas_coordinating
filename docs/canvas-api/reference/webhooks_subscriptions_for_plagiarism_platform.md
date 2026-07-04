# Webhooks Subscriptions for Plagiarism Platform API

**LTI API for Webhook Subscriptions (Must use [JWT access tokens](jwt_access_tokens.html) with this API).**

This is intended for use with Canvas' [Plagiarism Detection Platform](plagiarism_platform.html). For general-purpose event subscriptions see [Live Events](data_service_introduction.html).

The tool proxy must also have the appropriate enabled capabilities (See appendix).

Webhooks from Canvas are your way to know that a change (e.g. new or updated submission, new or updated assignment, etc.) has taken place.

Webhooks are available via HTTPS to an endpoint you own and specify, or via an AWS SQS queue that you provision, own, and specify. We recommend SQS for the most robust integration, but do support HTTPS for lower volume applications.

We do not deduplicate or batch messages before transmission. Avoid creating multiple identical subscriptions. Webhooks always identify the ID of the subscription that caused them to be sent, allowing you to identify problematic or high volume subscriptions.

We cannot guarantee the transmission order of webhooks. If order is important to your application, you must check the "event_time" attribute in the "metadata" hash to determine sequence.

## Create a Webhook Subscription

### POST /api/lti/subscriptions

**Scope:** `url:POST|/api/lti/subscriptions`

Creates a webook subscription for the specified event type and context.

#### Request Parameters:

| Parameter |  | Type | Description |
|----|----|----|----|
| subscription\[ContextId\] | Required | string | The id of the context for the subscription. |
| subscription\[ContextType\] | Required | string | The type of context for the subscription. Must be ‘assignment’, ‘account’, or ‘course’. |
| subscription\[EventTypes\] | Required | Array | Array of strings representing the event types for the subscription. |
| subscription\[Format\] | Required | string | Format to deliver the live events. Must be ‘live-event’ or ‘caliper’. |
| subscription\[TransportMetadata\] | Required | Object | An object with a single key: ‘Url’. Example: { “Url”: “sqs.example” } |
| subscription\[TransportType\] | Required | string | Must be either ‘sqs’ or ‘https’. |

## Delete a Webhook Subscription

### DELETE /api/lti/subscriptions/:id

**Scope:** `url:DELETE|/api/lti/subscriptions/:id`

## Show a single Webhook Subscription

### GET /api/lti/subscriptions/:id

**Scope:** `url:GET|/api/lti/subscriptions/:id`

## Update a Webhook Subscription

### PUT /api/lti/subscriptions/:id

**Scope:** `url:PUT|/api/lti/subscriptions/:id`

This endpoint uses the same parameters as the create endpoint

## List all Webhook Subscription for a tool proxy

### GET /api/lti/subscriptions

**Scope:** `url:GET|/api/lti/subscriptions`

This endpoint returns a paginated list with a default limit of 100 items per result set. You can retrieve the next result set by setting a ‘StartKey’ header in your next request with the value of the ‘EndKey’ header in the response.

Example use of a ‘StartKey’ header object:

``` code
{ "Id":"71d6dfba-0547-477d-b41d-db8cb528c6d1","DeveloperKey":"10000000000001" }
```

## Appendixes

### Appendix: Webhook Subscription Required Capabilities

A tool must have certain capabilities enabled in order to create webhook subscriptions for a given event type in a given context. These capabilities can only be obtained through the use of a custom tool consumer profile.

All available event types are listed bellow along with the capability that will allow creating subscriptions of the associated type.

### `QUIZ_SUBMITTED` Event Type

- vnd.instructure.webhooks.root_account.quiz_submitted
- vnd.instructure.webhooks.assignment.quiz_submitted

### `GRADE_CHANGE` Event Type

- vnd.instructure.webhooks.root_account.grade_change

### `ATTACHMENT_CREATED` Event Type

- vnd.instructure.webhooks.root_account.attachment_created
- vnd.instructure.webhooks.assignment.attachment_created

### `SUBMISSION_CREATED` Event Type

- vnd.instructure.webhooks.root_account.submission_created
- vnd.instructure.webhooks.assignment.submission_created

### `SUBMISSION_UPDATED` Event Type

- vnd.instructure.webhooks.root_account.submission_updated
- vnd.instructure.webhooks.assignment.submission_updated

### `PLAGIARISM_RESUBMIT` Event Type

- vnd.instructure.webhooks.root_account.plagiarism_resubmit
- vnd.instructure.webhooks.assignment.plagiarism_resubmit

### All Event Types

- vnd.instructure.webhooks.root_account.all
